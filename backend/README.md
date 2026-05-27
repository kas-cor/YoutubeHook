# YoutubeHook Backend

> Backend for the [YoutubeHook](https://github.com/kas-cor/YoutubeHook) ecosystem — webhook receiver, click tracker, and YouTube digest generator.

## Architecture

```
┌─────────────────┐     GET /hook     ┌──────────────────────────────┐
│  YoutubeHook    │  ───────────────→  │  FastAPI Webhook Receiver    │
│  (Tampermonkey) │                    │  └─ /hook?videoId=&title=…   │
└─────────────────┘                    │  └─ /r/{video_id} (redirect) │
                                       │  └─ /videos (data feed)      │
                                       │  └─ /health                  │
                                       │  └─ /feed (clicks feed)      │
                                       └──────────┬───────────────────┘
                                                  │
                                          ┌───────▼────────┐
                                          │  SQLite         │
                                          │  (clicks.db)    │
                                          └────────────────┘
                                                  │
                                          ┌───────▼────────┐
                                          │  Digest CLI     │
                                          │  python -m app  │
                                          │  (cron every 3h)│
                                          └───────┬────────┘
                                                  │
                                                  ▼
                                          Telegram Digest
```

## Components

| Component | Purpose |
|-----------|---------|
| **API Server** (`app/main.py`) | FastAPI server: receives YouTube webhooks, tracks clicks, serves data feeds |
| **Digest Generator** (`app/digest.py`) | CLI tool: collects YouTube videos via API, formats digest, sends to Telegram |
| **Click Tracker** (`app/database.py`) | SQLite: logs all video views and redirect clicks |

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose
- Google Cloud OAuth token with `youtube.readonly` scope
- Telegram Bot Token (optional, for digest delivery)

### 2. Setup

```bash
# Clone the repository
git clone https://github.com/kas-cor/YoutubeHook.git
cd YoutubeHook/backend

# Copy and edit environment
cp .env.example .env
# Edit .env with your Telegram token, chat ID, and redirect URL

# Place your Google OAuth token
# The token must have youtube.readonly scope
cp /path/to/google_token.json .

# Start the backend
docker compose up -d
```

### 3. Configure YoutubeHook

In your Tampermonkey userscript, set the webhook URL to:
```
http://your-server:8800/hook?videoId={videoId}&title={title}&ts={timestamp}&channel={channel}
```

### 4. Initialize Channel Cache

```bash
docker compose exec ythook-backend python -m app.digest --refresh
```

### 5. Set Up Digest Cron

Add to your host crontab (or agent's scheduler):

```cron
# Refresh channel cache daily at 6:00
0 6 * * * docker compose -f /path/to/backend/docker-compose.yml exec ythook-backend python -m app.digest --refresh

# Generate digest every 3 hours
0 */3 * * * docker compose -f /path/to/backend/docker-compose.yml exec ythook-backend python -m app.digest --hours 3 --send
```

For AI-agent based scheduling, see [AGENTS.md](AGENTS.md).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/hook?videoId=X&title=...` | Receive video tracking data from YoutubeHook |
| GET | `/r/{video_id}?t=title&u=user` | Redirect to YouTube + log click |
| GET | `/health` | Health check |
| GET | `/feed?limit=100` | Recent clicks JSON feed |
| GET | `/videos?since=...&until=...&limit=50` | Video data within time range |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YTHOOK_HOST` | `0.0.0.0` | Server bind address |
| `YTHOOK_PORT` | `8800` | Server port |
| `YTHOOK_DATA_DIR` | `/data` | Data volume mount point |
| `YTHOOK_REDIRECT_BASE` | `http://localhost:8800/r` | Base URL for click-tracked redirect links |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token for digest delivery |
| `TELEGRAM_CHAT_ID` | — | Telegram chat/channel ID for digests |
| `YTHOOK_GOOGLE_CREDS` | `/data/google_token.json` | Google OAuth token path |
| `YTHOOK_DIGEST_HOURS` | `3` | Default hours window for digest |

## Digest CLI

```bash
# Refresh channel cache (requires Google OAuth)
python -m app.digest --refresh

# Run digest for last 3 hours, send to Telegram
python -m app.digest --hours 3 --send

# Run digest, output raw JSON for agent processing
python -m app.digest --hours 3 --raw

# Run digest, output formatted chunks (for agent to forward)
python -m app.digest --hours 3 --no-send
```

Exit codes:
- `0` — success, videos found and processed
- `10` — no new videos (agent should remain silent)
- `2` — configuration error (missing token, no channel cache)

## Data Storage

All persistent data lives in the `ythook-data` Docker volume:

| File | Description |
|------|-------------|
| `clicks.db` | SQLite database of tracked views and clicks |
| `channels_cache.json` | Cached YouTube subscription data |
| `digest_cache.json` | Last digest run data (for agent processing) |
| `sent/YYYY-MM-DD.json` | Daily log of sent video IDs (dedup) |
| `google_token.json` | Google OAuth token (mounted read-only) |
