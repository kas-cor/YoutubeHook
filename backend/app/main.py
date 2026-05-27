"""
YoutubeHook Backend — FastAPI application.

Endpoints:
  GET /hook         — Receive video tracking data from YoutubeHook userscript
  GET /r/{video_id} — Redirect with click tracking
  GET /health       — Health check
  GET /feed         — Recent clicks feed (JSON)
  GET /videos       — List tracked videos for a date range
"""

import json
import time
import logging
from datetime import datetime, timezone
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import uvicorn

from . import config
from . import database as db

logger = logging.getLogger("ythook")

app = FastAPI(
    title="YoutubeHook Backend",
    description="Webhook receiver + click tracker + digest API for YoutubeHook",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Startup ──────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def startup():
    config.ensure_dirs()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("YoutubeHook Backend starting on %s:%s", config.HOST, config.PORT)


# ─── Webhook Receiver ─────────────────────────────────────────────────────────


@app.get("/hook")
async def webhook_receiver(
    videoId: str = Query(..., description="YouTube video ID"),
    id: str = Query(None, description="Alias for videoId (from userscript)"),
    title: str = Query("", description="Video title"),
    url: str = Query("", description="Full YouTube URL"),
    ts: str = Query("", description="ISO timestamp"),
    channel: str = Query("", description="Channel name"),
    user_id: str = Query("yt-hook", description="User/source identifier"),
):
    """
    Receive video tracking data from YoutubeHook userscript (GET request).

    Supports both `?videoId=` and `?id=` parameter names for compatibility.
    """
    vid = videoId or id
    if not vid:
        raise HTTPException(status_code=400, detail="Missing videoId parameter")

    decoded_title = unquote(title) if title else ""
    decoded_channel = unquote(channel) if channel else ""

    db.log_click(
        video_id=vid,
        title=decoded_title,
        channel_id=decoded_channel,
        user_id=user_id,
    )

    logger.info("Tracked: %s — %s", vid, decoded_title[:60] if decoded_title else "(no title)")

    return {
        "ok": True,
        "video_id": vid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Redirect with Click Tracking ────────────────────────────────────────────


@app.get("/r/{video_id}")
async def redirect_with_tracking(
    video_id: str,
    t: str = Query(None, description="Video title (optional)"),
    u: str = Query("unknown", description="User identifier"),
):
    """
    Redirect to YouTube video page, logging the click first.

    Used in digest links to track which videos were watched/clicked.
    """
    decoded_title = unquote(t) if t else None

    db.log_click(
        video_id=video_id,
        title=decoded_title,
        user_id=u,
    )

    logger.info("Redirect: %s → YouTube", video_id)

    return RedirectResponse(
        url=f"https://www.youtube.com/watch?v={video_id}",
        status_code=302,
    )


# ─── Data Endpoints ────────────────────────────────────────────────────────────


@app.get("/feed")
async def feed(limit: int = Query(100, ge=1, le=1000)):
    """
    Return recent clicks as JSON feed.

    Useful for AI agents to query what was watched/clicked.
    """
    clicks = db.get_recent_clicks(limit=limit)
    return {"clicks": clicks, "count": len(clicks)}


@app.get("/videos")
async def list_videos(
    since: str = Query(None, description="ISO timestamp (e.g. 2026-05-27T00:00:00Z)"),
    until: str = Query(None, description="ISO timestamp"),
    limit: int = Query(50, ge=1, le=500),
):
    """
    List tracked video entries within a time range.

    Returns click data — useful for building daily digests.
    """
    conn = db.get_connection()
    try:
        query = "SELECT * FROM clicks WHERE 1=1"
        params = []

        if since:
            query += " AND created_at >= ?"
            params.append(since)
        if until:
            query += " AND created_at <= ?"
            params.append(until)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cur = conn.execute(query, params)
        rows = [dict(row) for row in cur.fetchall()]
        return {"videos": rows, "count": len(rows)}
    finally:
        conn.close()


# ─── Health ────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Simple health check."""
    return {
        "status": "ok",
        "service": "ythook-backend",
        "version": "0.3.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    """Run the server."""
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
