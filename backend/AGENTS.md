# YoutubeHook Backend — AI Agent Integration Guide

> This document describes how **any AI agent** (Hermes, OpenClaw, Claude Code, etc.) can integrate with the YoutubeHook Backend.

## Overview

The YoutubeHook Backend provides three services for an AI agent:

1. **Webhook receiver** — collects video tracking data from the YoutubeHook userscript
2. **Click tracking** — logs which videos the user actually watched/clicked
3. **Digest generation** — produces daily YouTube digests as formatted messages or raw JSON

## Integration Points

### 1. Receiving Tracked Videos

YoutubeHook userscript sends a GET request to `/hook` every time a user opens a YouTube video. Your agent can query tracked videos via the `/videos` endpoint:

```bash
# Get videos from the last 6 hours
curl "http://ythook-backend:8800/videos?since=2026-05-27T00:00:00Z&limit=100"
```

**Response:**
```json
{
  "videos": [
    {
      "id": 1,
      "video_id": "abc123def45",
      "title": "How to Deploy Docker",
      "channel_id": "",
      "user_id": "yt-hook",
      "timestamp": 1745712345.678,
      "created_at": "2026-05-27 14:30:00"
    }
  ],
  "count": 1
}
```

### 2. Checking Click Stats

```bash
# Get most recent clicks
curl "http://ythook-backend:8800/feed?limit=20"
```

The digest generator automatically filters out clicked videos — they won't appear in future digests.

### 3. Running the Digest

There are **three modes** depending on how your agent wants to handle the output:

#### A. Raw JSON mode (for agent-side formatting)

```bash
python -m app.digest --hours 3 --raw
```

Returns JSON with video data, formatted chunks, and metadata. The agent can use the `description` field for LLM summarization.

```json
{
  "videos": [
    {
      "video_id": "abc123",
      "title": "Video Title",
      "channel": "Channel Name",
      "description": "Full video description from YouTube API..."
    }
  ],
  "chunks": ["📺 <b>YouTube Digest</b>..."],
  "count": 5
}
```

#### B. Chunk mode (agent relays to Telegram/chat)

```bash
python -m app.digest --hours 3 --no-send
```

Outputs chunks separated by `===CHUNKS_START===` / `===CHUNK N===` / `===CHUNKS_END===` markers. The agent reads these and forwards them.

#### C. Direct send mode (script delivers to Telegram)

```bash
python -m app.digest --hours 3 --send
```

Script sends directly to Telegram via Bot API. Use this if your agent just needs to trigger and forget.

### 4. Setting Up Cron with Your Agent

**Hermes Agent** example:

```yaml
# In hermes config.yaml or via cron CLI
cron:
  - name: youtube-digest
    schedule: "0 */3 * * *"
    skills: ["youtube-digest"]
    prompt: |
      ⚠️ No preamble. Start with content.
      Run: `python -m app.digest --hours 3 --raw`
      If exit code 10 → [SILENT]
      If JSON has videos → format a Telegram digest with emoji descriptions.
      Return markdown, use `||spoiler||` for footer.
    deliver: telegram
```

**OpenClaw** example (from system prompt):

```
You have access to the YoutubeHook backend at http://ythook-backend:8800.
Every 3 hours, run the digest: python -m app.digest --hours 3 --raw
Format the output as a friendly digest message.
```

### 5. Agent Commands Reference

| Task | Command |
|------|---------|
| **Refresh channel cache** | `python -m app.digest --refresh` |
| **Run digest (raw JSON)** | `python -m app.digest --hours 3 --raw` |
| **Run digest (chunks)** | `python -m app.digest --hours 3 --no-send` |
| **Run digest (direct send)** | `python -m app.digest --hours 3 --send` |
| **Query tracked videos** | `curl http://ythook-backend:8800/videos?since=...` |
| **Health check** | `curl http://ythook-backend:8800/health` |
| **Recent clicks** | `curl http://ythook-backend:8800/feed` |

### 6. Exit Code Protocol

The digest CLI uses exit codes to signal to the agent:

| Code | Meaning | Agent Action |
|------|---------|-------------|
| `0` | Videos found and processed | Send the digest (from stdout) |
| `10` | No new videos | Remain silent (`[SILENT]`) |
| `2` | Config error | Alert user: missing token/cache |

### 7. Docker Compose for Agent Deployment

The backend runs as a standalone container. Your agent can:

```bash
# Start the backend
docker compose -f /path/to/backend/docker-compose.yml up -d

# Wait for health
curl --retry 5 --retry-delay 2 http://localhost:8800/health

# Initialize channels
docker compose -f /path/to/backend/docker-compose.yml exec ythook-backend python -m app.digest --refresh

# Schedule recurrent digests (via agent's cron or host crontab)
```

## File Structure

```
backend/
├── app/
│   ├── __init__.py        # Package metadata
│   ├── __main__.py        # CLI entry point
│   ├── config.py          # Environment-based configuration
│   ├── database.py        # SQLite helpers (clicks, sent log)
│   ├── main.py            # FastAPI webhook server
│   └── digest.py          # Digest CLI generator
├── Dockerfile             # Container build
├── docker-compose.yml     # Service orchestration
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
├── README.md              # User-facing docs
└── AGENTS.md              # This file
```

## See Also

- [YoutubeHook userscript](../README.md) — browser-side tracker
- [SKILL.md](../SKILL.md) — full skill integration guide
