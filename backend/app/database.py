"""Database helpers — SQLite for clicks + sent log."""

import sqlite3
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config


# ─── Clicks DB ───────────────────────────────────────────────────────────────


def get_connection() -> sqlite3.Connection:
    """Get a writable SQLite connection (autocommit off)."""
    config.ensure_dirs()
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS clicks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    TEXT NOT NULL,
            title       TEXT,
            channel_id  TEXT,
            user_id     TEXT,
            timestamp   REAL NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_clicks_video_id ON clicks(video_id);
        CREATE INDEX IF NOT EXISTS idx_clicks_timestamp ON clicks(timestamp);
    """)


def log_click(video_id: str, title: Optional[str] = None,
              channel_id: Optional[str] = None,
              user_id: str = "unknown") -> Optional[int]:
    """Record a click, return row id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO clicks (video_id, title, channel_id, user_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (video_id, title, channel_id, user_id, time.time()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_clicked_ids() -> set[str]:
    """Return set of all video IDs that have ever been clicked."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT DISTINCT video_id FROM clicks")
        return {row["video_id"] for row in cur.fetchall()}
    finally:
        conn.close()


def get_recent_clicks(limit: int = 100) -> list[dict]:
    """Return most recent clicks."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT video_id, title, channel_id, user_id, timestamp "
            "FROM clicks ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# ─── Sent Log ─────────────────────────────────────────────────────────────────


def load_sent_ids(today: str | None = None) -> set[str]:
    """Load video IDs already sent today."""
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    log_path = config.SENT_LOG_DIR / f"{today}.json"
    if not log_path.exists():
        return set()
    data = json.loads(log_path.read_text())
    return {v["id"] for v in data.get("video_ids", [])}


def append_sent_log(videos: list[dict], today: str | None = None):
    """Append new sent videos to today's log (with dedup)."""
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")
    config.ensure_dirs()
    log_path = config.SENT_LOG_DIR / f"{today}.json"

    existing = []
    if log_path.exists():
        data = json.loads(log_path.read_text())
        existing = data.get("video_ids", [])

    existing_ids = {v["id"] for v in existing}
    for v in videos:
        if v["video_id"] not in existing_ids:
            existing.append({
                "id": v["video_id"],
                "title": v.get("title", ""),
                "channel": v.get("channel", ""),
            })
            existing_ids.add(v["video_id"])

    log_path.write_text(json.dumps({
        "date": today,
        "last_updated": datetime.now().isoformat(),
        "video_ids": existing,
        "count": len(existing),
    }, ensure_ascii=False, indent=2))
