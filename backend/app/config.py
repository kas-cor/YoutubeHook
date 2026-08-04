"""Configuration for YoutubeHook backend — all values from environment."""

import os
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────

DATA_DIR = Path(os.environ.get("YTHOOK_DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "clicks.db"
CHANNELS_CACHE = DATA_DIR / "channels_cache.json"
DIGEST_CACHE = DATA_DIR / "digest_cache.json"
SENT_LOG_DIR = DATA_DIR / "sent"

# ─── URLs ────────────────────────────────────────────────────────────────────

REDIRECT_BASE = os.environ.get(
    "YTHOOK_REDIRECT_BASE",
    "http://localhost:8800/r",
)

# ─── Telegram ────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─── Digest ──────────────────────────────────────────────────────────────────

DIGEST_HOURS_BACK = int(os.environ.get("YTHOOK_DIGEST_HOURS", "3"))
MAX_MSG_LEN = 3800
MAX_PER_CHANNEL = 3
MAX_WORKERS = 20

# ─── Server ──────────────────────────────────────────────────────────────────

HOST = os.environ.get("YTHOOK_HOST", "0.0.0.0")
PORT = int(os.environ.get("YTHOOK_PORT", "8800"))
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")

# ─── Google OAuth ────────────────────────────────────────────────────────────

GOOGLE_CREDENTIALS_FILE = os.environ.get(
    "YTHOOK_GOOGLE_CREDS",
    str(DATA_DIR / "google_token.json"),
)

# Helper: ensure DATA_DIR exists
def ensure_dirs():
    """Create data directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
