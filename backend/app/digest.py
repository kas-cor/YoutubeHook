"""
YouTube Digest Generator — CLI tool for AI agents.

Usage:
  python -m app.digest --hours 3          # Run digest for last 3 hours
  python -m app.digest --refresh           # Refresh channel cache via YouTube API
  python -m app.digest --hours 3 --raw     # Output raw JSON for agent processing
  python -m app.digest --hours 3 --send    # Send directly to Telegram

Exit codes:
  0 — success (videos found and processed)
  10 — no videos (agent should remain silent)
  2 — configuration error
"""

import argparse
import json
import os
import sys
import time
from urllib.parse import quote
import re
from datetime import datetime, timezone
from typing import Optional

from . import config
from . import database as db

# ─── YouTube API Fetching ─────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
]

_yt_service = None


def _get_yt():
    """Get cached YouTube API service (singleton)."""
    global _yt_service
    if _yt_service is None:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds_path = config.GOOGLE_CREDENTIALS_FILE
        if not os.path.exists(creds_path):
            print(f"ERROR: Google token not found at {creds_path}", file=sys.stderr)
            sys.exit(2)

        creds = Credentials.from_authorized_user_file(creds_path, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(creds_path, "w") as f:
                f.write(creds.to_json())
        _yt_service = build("youtube", "v3", credentials=creds)
    return _yt_service


def _parse_duration(iso: str) -> int:
    """Parse ISO 8601 duration (PT1H2M3S) to total seconds."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 9999
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mins * 60 + s


# ─── YouTube API Error Handling ─────────────────────────────────────────────

_HTTPError = None
try:
    from googleapiclient.errors import HttpError as _HTTPError
except Exception:  # pragma: no cover - optional dep
    _HTTPError = None


def _is_quota_error(exc) -> bool:
    """Detect YouTube quota exceeded (HTTP 403, reason=quotaExceeded)."""
    if _HTTPError is not None and isinstance(exc, _HTTPError):
        try:
            reason = exc.resp.get("reason", "")
        except Exception:
            reason = ""
        status = getattr(exc, "resp", None)
        status_code = getattr(status, "status", None) if status else None
        return (
            status_code == 403 or (getattr(exc, "status_code", None) == 403)
        ) and "quota" in reason.lower()
    return False


def _is_rate_limit(exc) -> bool:
    """Detect rate limiting (HTTP 429) and Retry-After quota exhaustion."""
    if _HTTPError is not None and isinstance(exc, _HTTPError):
        try:
            reason = exc.resp.get("reason", "")
            status = getattr(exc.resp, "status", None)
        except Exception:
            reason, status = "", None
        reason_l = reason.lower()
        return (
            getattr(exc, "status_code", None) == 429
            or status == 429
            or (
                status == 403
                and "ratelimitexceeded" in reason_l
            )
        )
    return False


def _is_network_error(exc) -> bool:
    """Detect transient network/transport failures (not HTTP errors)."""
    return _HTTPError is None or not isinstance(exc, _HTTPError)


def _api_call(fn, *args, retries=3, **kwargs):
    """
    Execute one YouTube API call with resilient error handling.

    429 (rate limit)   → retry with exponential backoff (up to `retries`),
                         then raise HTTPException 429.
    403 (quota)        → hard fail: print to stderr and exit code 2.
    network errors     → retry up to `retries` times, then raise the last error.

    Raises the final exception when retries are exhausted (429/network), so
    callers never silently swallow API failures.
    """
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if _is_quota_error(e):
                print(
                    "ERROR: YouTube API quota exceeded (403). "
                    "Wait for quota reset or check your API key.",
                    file=sys.stderr,
                )
                sys.exit(2)
            if _is_rate_limit(e):
                attempt += 1
                if attempt > retries:
                    print(
                        f"ERROR: YouTube API rate limited after {retries} retries.",
                        file=sys.stderr,
                    )
                    raise e
                delay = min(2 ** attempt, 30)
                print(
                    f"  Rate limited, retrying in {delay}s "
                    f"(attempt {attempt}/{retries})...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            if _is_network_error(e):
                attempt += 1
                if attempt > retries:
                    print(
                        f"ERROR: YouTube API network error after {retries} retries: {e}",
                        file=sys.stderr,
                    )
                    raise e
                delay = min(2 ** attempt, 10)
                print(
                    f"  Network error ({e}), retrying in {delay}s "
                    f"(attempt {attempt}/{retries})...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            # Non-transient error (auth, bad request, ...): re-raise.
            raise e


def fetch_channel_videos(channel_id: str, info: dict, cutoff_ts: float) -> list[dict]:
    """Fetch recent videos for one channel via YouTube API."""
    uploads_id = info.get("uploads", "")
    if not uploads_id:
        return []

    yt = _get_yt()
    resp = _api_call(
        lambda: yt.playlistItems().list(
            part="snippet",
            playlistId=uploads_id,
            maxResults=15,
        ).execute(),
        retries=3,
    )

    items = resp.get("items", [])
    if not items:
        return []

    vid_ids = [it["snippet"]["resourceId"]["videoId"] for it in items]
    durations = {}
    for i in range(0, len(vid_ids), 50):
        batch = vid_ids[i : i + 50]
        vresp = _api_call(
            lambda: yt.videos().list(
                part="contentDetails", id=",".join(batch)
            ).execute(),
            retries=3,
        )
        for v in vresp.get("items", []):
            durations[v["id"]] = v["contentDetails"]["duration"]

    fresh = []
    for item in items:
        try:
            snip = item["snippet"]
            pub_str = snip["publishedAt"]
            pub_dt = datetime.strptime(pub_str[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            pub_ts = pub_dt.timestamp()
            if pub_ts <= cutoff_ts:
                continue

            vid_id = snip["resourceId"]["videoId"]
            title = snip.get("title", "")
            desc = snip.get("description", "")
            dur_str = durations.get(vid_id, "")
            dur_sec = _parse_duration(dur_str)

            # Filter shorts: duration ≤ 120s or #shorts in description
            if dur_sec <= 120 or "#shorts" in desc.lower():
                continue

            fresh.append({
                "video_id": vid_id,
                "title": title,
                "channel": info.get("title", channel_id),
                "published": pub_str,
                "published_ts": pub_ts,
                "description": desc,
            })
        except Exception as e:
            print(
                f"  Skipping item for {info.get('title', channel_id)}: {e}",
                file=sys.stderr,
            )

    return fresh


def fetch_all_videos(channels: dict, hours_back: int) -> list[dict]:
    """Fetch videos from all channels via API."""
    cutoff_ts = time.time() - hours_back * 3600
    all_fresh = []
    total = len(channels)
    done = 0

    for cid, info in channels.items():
        done += 1
        if done % 50 == 0:
            print(f"  ... {done}/{total}", file=sys.stderr)
        videos = fetch_channel_videos(cid, info, cutoff_ts)
        all_fresh.extend(videos)

    all_fresh.sort(key=lambda x: x["published_ts"], reverse=True)
    return all_fresh


# ─── Channel Cache Refresh ────────────────────────────────────────────────────


def cmd_refresh():
    """Fetch all subscriptions and channel info, save to cache."""
    print(f"Refreshing channel cache via YouTube API...", file=sys.stderr)
    yt = _get_yt()

    sub_ids = []
    page_token = None
    while True:
        resp = yt.subscriptions().list(
            part="snippet", mine=True, maxResults=50, pageToken=page_token
        ).execute()
        for item in resp["items"]:
            sub_ids.append(item["snippet"]["resourceId"]["channelId"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"  Got {len(sub_ids)} subscriptions", file=sys.stderr)

    channels = {}
    for i in range(0, len(sub_ids), 50):
        ids = ",".join(sub_ids[i : i + 50])
        resp = yt.channels().list(part="contentDetails,snippet", id=ids).execute()
        for ch in resp["items"]:
            channels[ch["id"]] = {
                "title": ch["snippet"]["title"],
                "uploads": ch["contentDetails"]["relatedPlaylists"]["uploads"],
            }

    print(f"  Got info for {len(channels)} channels", file=sys.stderr)

    config.ensure_dirs()
    with open(config.CHANNELS_CACHE, "w") as f:
        json.dump(channels, f, ensure_ascii=False)
    print(f"  Saved to {config.CHANNELS_CACHE}", file=sys.stderr)
    print("  Done!", file=sys.stderr)


# ─── Formatting ───────────────────────────────────────────────────────────────


def format_digest(
    fresh: list[dict],
    hours_back: int,
    redirect_base: str,
) -> list[str]:
    """Format video list into Telegram HTML chunks (≤ MAX_MSG_LEN each)."""
    if not fresh:
        return []

    by_channel: dict[str, list[dict]] = {}
    for v in fresh:
        by_channel.setdefault(v["channel"], []).append(v)

    sorted_channels = sorted(
        by_channel.items(),
        key=lambda kv: max(v["published_ts"] for v in kv[1]),
        reverse=True,
    )

    chunks: list[str] = []
    current_lines: list[str] = []
    current_len = 0
    chunk_num = 1
    total_placeholder = None

    def start_new_chunk(tc=None):
        nonlocal current_lines, current_len, chunk_num, total_placeholder
        if tc is not None:
            total_placeholder = tc
        total_channels = len(sorted_channels)
        suffix = f" ({chunk_num} из {total_placeholder or '?'})"
        prefix = (
            f"📺 <b>YouTube Digest</b> — за последние "
            f"{hours_back}ч ({len(fresh)} видео, {total_channels} каналов){suffix}"
        )
        current_lines = [prefix, "", "─────────────────────", ""]
        current_len = sum(len(l) + 1 for l in current_lines)
        chunk_num += 1

    def finish_chunk():
        nonlocal current_lines, current_len
        current_lines.append("─────────────────────")
        current_lines.append("<i>Клики учитываются</i>")
        current_lines.append(f"<i>Авто. сводка • {datetime.now().strftime('%H:%M')}</i>")
        chunks.append("\n".join(current_lines))
        current_lines.clear()
        current_len = 0

    start_new_chunk()

    for ch, videos in sorted_channels:
        ch_line = f"📁 <b>{ch}</b> ({len(videos)} видео)"
        video_lines = []

        for v in videos[: config.MAX_PER_CHANNEL]:
            url = f"{redirect_base}/{v['video_id']}?t={quote(v['title'])}"
            title = v["title"][:65] + ("…" if len(v["title"]) > 65 else "")
            vid_line = f'  ▶ <a href="{url}">{title}</a>'
            if len(vid_line) > config.MAX_MSG_LEN:
                vid_line = f"  ▶ <code>{v['video_id']}</code>"
            video_lines.append((vid_line, len(vid_line) + 1))

        channel_size = len(ch_line) + 1 + sum(vl[1] for vl in video_lines) + 1

        if channel_size > config.MAX_MSG_LEN:
            continue

        if current_len + channel_size <= config.MAX_MSG_LEN:
            current_lines.append(ch_line)
            current_len += len(ch_line) + 1
            for vl, vlen in video_lines:
                current_lines.append(vl)
                current_len += vlen
            current_lines.append("")
            current_len += 1
        else:
            if current_lines:
                finish_chunk()
            start_new_chunk()
            if current_len + channel_size <= config.MAX_MSG_LEN:
                current_lines.append(ch_line)
                current_len += len(ch_line) + 1
                for vl, vlen in video_lines:
                    if current_len + vlen <= config.MAX_MSG_LEN:
                        current_lines.append(vl)
                        current_len += vlen
                current_lines.append("")
                current_len += 1

    if current_lines:
        finish_chunk()

    total_chunks = len(chunks)
    for i, chunk in enumerate(chunks):
        if total_chunks == 1:
            chunks[i] = chunk.replace(f" (1 из ?)", "")
        else:
            chunks[i] = chunk.replace(f"({i + 1} из ?)", f"({i + 1} из {total_chunks})")

    return chunks


# ─── Telegram Sender ──────────────────────────────────────────────────────────


def _send_telegram(text: str) -> bool:
    """Send a single message to Telegram via Bot API."""
    import urllib.request

    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"  Sent: msg_id={result['result']['message_id']} ({len(text)} chars)",
                      file=sys.stderr)
                return True
            else:
                print(f"  Telegram error: {result}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"  Telegram send failed: {e}", file=sys.stderr)
        return False


def send_chunks(chunks: list[str]):
    """Send digest chunks to Telegram with rate limiting."""
    if not chunks:
        print("  Nothing to send", file=sys.stderr)
        return
    for i, chunk in enumerate(chunks):
        tag = f"[{i + 1}/{len(chunks)}]"
        ok = _send_telegram(chunk)
        if not ok:
            print(f"  {tag} FAILED — stopping", file=sys.stderr)
            break
        if i < len(chunks) - 1:
            time.sleep(0.5)


# ─── Main CLI ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="YouTube Digest Generator")
    parser.add_argument(
        "--hours", type=int, default=None,
        help="Hours back to look (default: from config or 3)",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Refresh channel cache via YouTube API",
    )
    parser.add_argument(
        "--raw", action="store_true",
        help="Output raw JSON for agent processing (implies --no-send)",
    )
    parser.add_argument(
        "--no-send", action="store_true",
        help="Print digest chunks to stdout, do not send to Telegram",
    )
    parser.add_argument(
        "--send", action="store_true",
        help="Send digest directly to Telegram",
    )
    args = parser.parse_args()

    # ── Refresh mode ──
    if args.refresh:
        cmd_refresh()
        return

    # ── Auto-detect agent cron context ──
    agent_cron = os.environ.get("HERMES_CRON_SESSION", "").lower() in (
        "1", "true", "yes", "on"
    ) or os.environ.get("OPENCLAW_CRON", "").lower() in (
        "1", "true", "yes", "on"
    )
    if agent_cron:
        args.no_send = True
        print("  Agent cron mode detected — skipping direct Telegram send",
              file=sys.stderr)

    # ── Load channel cache ──
    if not config.CHANNELS_CACHE.exists():
        print("ERROR: Channel cache not found. Run with --refresh first.",
              file=sys.stderr)
        sys.exit(2)

    channels = json.loads(config.CHANNELS_CACHE.read_text())
    print(f"  Loaded {len(channels)} channels from cache", file=sys.stderr)

    # ── Time window ──
    hours_back = args.hours or config.DIGEST_HOURS_BACK
    now = datetime.now()
    if 6 <= now.hour < 12:
        extended = (now.hour - 21 + 24) if hours_back == 3 else hours_back
        if extended != hours_back:
            print(f"  First digest of the day — extending window to {extended}h",
                  file=sys.stderr)
            hours_back = extended

    # ── Check cache freshness ──
    use_cache = False
    if config.DIGEST_CACHE.exists():
        mtime = config.DIGEST_CACHE.stat().st_mtime
        if time.time() - mtime < 600:
            cached = json.loads(config.DIGEST_CACHE.read_text())
            cached_fresh = cached.get("fresh", [])
            active_hours = (
                (9 <= now.hour < 12)
                or (14 <= now.hour < 23)
                or (0 <= now.hour < 3)
            )
            if cached_fresh or not active_hours:
                print("  Using cached data", file=sys.stderr)
                use_cache = True

    # ── Fetch ──
    if use_cache:
        data = json.loads(config.DIGEST_CACHE.read_text())
        fresh = data.get("fresh", [])
        print(f"  Loaded from cache: {len(fresh)} videos", file=sys.stderr)
    else:
        print(f"  Fetching via YouTube API ({hours_back}h window)...",
              file=sys.stderr)
        fresh = fetch_all_videos(channels, hours_back)
        print(f"  Found {len(fresh)} fresh videos via API", file=sys.stderr)

    # ── Filter clicked ──
    clicked_ids = db.get_clicked_ids()
    if clicked_ids:
        before = len(fresh)
        fresh = [v for v in fresh if v["video_id"] not in clicked_ids]
        skipped = before - len(fresh)
        if skipped:
            print(f"  Filtered out {skipped} clicked videos ({len(fresh)} remaining)",
                  file=sys.stderr)

    # ── Format ──
    redirect_base = config.REDIRECT_BASE
    chunks = format_digest(fresh, hours_back, redirect_base) if fresh else []

    # ── Save cache ──
    config.ensure_dirs()
    config.DIGEST_CACHE.write_text(json.dumps({
        "fresh": fresh,
        "chunks": chunks,
        "generated_at": datetime.now().isoformat(),
    }, ensure_ascii=False))

    # ── Output ──
    if not chunks:
        print("===NO_VIDEOS===")
        sys.exit(10)

    db.append_sent_log(fresh)

    if args.send:
        send_chunks(chunks)
        print("  Done!", file=sys.stderr)
    elif args.no_send or agent_cron:
        if args.raw:
            output = {
                "videos": fresh,
                "chunks": chunks,
                "count": len(fresh),
                "generated_at": datetime.now().isoformat(),
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print("===CHUNKS_START===")
            print(f"COUNT:{len(chunks)}")
            for i, chunk in enumerate(chunks):
                print(f"===CHUNK {i + 1}===")
                print(chunk)
            print("===CHUNKS_END===")
        print("  Done!", file=sys.stderr)
    else:
        send_chunks(chunks)
        print("  Done!", file=sys.stderr)


if __name__ == "__main__":
    main()
