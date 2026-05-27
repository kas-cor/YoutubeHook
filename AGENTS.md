# YoutubeHook — Agent Documentation

## Project Overview

A **Tampermonkey userscript + backend server** that tracks watched YouTube videos, stores them via webhook, and generates periodic digests.

---

## Architecture

```
Browser (YouTube)
    │
    ├── YoutubeHook (Tampermonkey)
    │   ├── MutationObserver detects URL change (300ms debounce)
    │   ├── extractVideoId() — parses /watch, /shorts, /embed, /live
    │   ├── getVideoTitle() — fallback chain
    │   ├── isIdSent() — dedup check (GM storage)
    │   └── sendToWebhook() — GET via GM_xmlhttpRequest
    └──────┬──────┘
           │ GET /hook?videoId=X&title=...
           ▼
┌──────────────────────────────────┐
│  Backend (FastAPI + SQLite)      │
│  ├── /hook       - webhook RX   │
│  ├── /r/{id}     - redirect+log │
│  ├── /videos     - data query   │
│  ├── /feed       - clicks feed  │
│  └── /health     - health check │
└──────────┬───────────────────────┘
           │
           ├── Digest CLI (python -m app.digest)
           │   ├── --hours 3 --raw    → JSON for agent
           │   ├── --hours 3 --no-send → HTML chunks
           │   ├── --hours 3 --send    → direct Telegram
           │   └── --refresh           → YouTube API cache
           │
           ├── SQLite (clicks.db)
           └── Telegram (Bot API)
```

## Components

### 1. UserScript (browser-side)

**`youtube-hook.user.js`** — Tampermonkey script

| Feature | Detail |
|---------|--------|
| **URL detection** | MutationObserver on `document.body`, 300ms debounce |
| **Video ID parsing** | `/watch`, `/shorts`, `/embed`, `/live` patterns |
| **Title resolution** | Fallback chain: `og:title` → `h1` → `document.title` |
| **Deduplication** | `GM_setValue` / `GM_getValue` — same ID never sent twice |
| **Webhook delivery** | GET via `GM_xmlhttpRequest`, 10s timeout |
| **SPA navigation** | Handles YouTube SPA transitions without page reload |

### 2. Backend (server-side)

Located in `backend/`. Docker Compose deployment.

| Service | Technology |
|---------|-----------|
| **API Server** | Python FastAPI, port 8800 |
| **Database** | SQLite (clicks.db, WAL mode) |
| **Digest CLI** | Python CLI, `python -m app.digest` |

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/hook?videoId=X&title=...` | Receive video tracking data |
| GET | `/r/{video_id}?t=title&u=user` | Redirect + log click |
| GET | `/health` | Health check |
| GET | `/feed?limit=100` | Clicks JSON feed |
| GET | `/videos?since=...&until=...` | Video data query |

#### Digest CLI Exit Codes

| Code | Meaning | Agent Action |
|------|---------|-------------|
| `0` | Videos found | Process stdout (JSON or chunks) |
| `10` | No new videos | Remain silent (`[SILENT]`) |
| `2` | Config error | Alert user |

## Digest Modes for AI Agents

### Raw JSON (agent formats the message)

```bash
python -m app.digest --hours 3 --raw
```

Returns JSON with full video data including `description` field for LLM summarization.

### Chunks (agent relays)

```bash
python -m app.digest --hours 3 --no-send
```

Outputs `===CHUNKS_START===` / `===CHUNK N===` / `===CHUNKS_END===` delimiters. Agent forwards them to the chat.

### Direct send (script handles everything)

```bash
python -m app.digest --hours 3 --send
```

Script formats and sends directly to Telegram. Agent just triggers and forgets.

## Integration

### YoutubeHook Webhook URL Format

Configure in Tampermonkey menu:
```
http://your-backend:8800/hook?videoId={videoId}&title={title}&ts={timestamp}&channel={channel}
```

### Placeholders

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{videoId}` / `{id}` | YouTube video ID | `Qah3kw1-La0` |
| `{title}` | Video title (URL-encoded) | `How+to+Deploy` |
| `{url}` | Full URL | `https%3A%2F%2F...` |
| `{timestamp}` | ISO timestamp | `2026-05-26T22%3A...` |

## Quick Start

```bash
# 1. Install Tampermonkey + userscript
# 2. Start backend
docker compose -f backend/docker-compose.yml up -d

# 3. Configure webhook URL in Tampermonkey menu
# 4. Initialize channel cache
docker compose exec ythook-backend python -m app.digest --refresh

# 5. Run digest manually
python -m app.digest --hours 3 --raw
```

## File Structure

```
YoutubeHook/
├── youtube-hook.user.js    ← Main userscript (browser)
├── SKILL.md                ← AI agent integration guide
├── AGENTS.md               ← This file
├── README.md               ← User-facing (EN)
├── README_ru.md            ← User-facing (RU)
├── package.json            ← Linting deps
├── .eslintrc.json          ← ESLint config
├── .gitignore
└── backend/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── .env.example
    ├── README.md
    ├── AGENTS.md            ← Backend-specific agent guide
    └── app/
        ├── main.py         ← FastAPI server
        ├── digest.py       ← Digest CLI
        ├── config.py
        ├── database.py
        ├── __init__.py
        └── __main__.py
```

## Development

```bash
# UserScript linting
npm install
npm run lint

# Backend (Python)
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## See Also

- [backend/AGENTS.md](backend/AGENTS.md) — detailed backend agent integration
- [SKILL.md](SKILL.md) — full skill integration guide