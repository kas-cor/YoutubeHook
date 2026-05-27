---
name: youtube-hook
description: "Tampermonkey userscript + backend server — tracks watched YouTube videos, collects via webhook, generates periodic digests"
version: 0.3.0
author: kas-cor
license: MIT
tags:
  - youtube
  - webhook
  - tampermonkey
  - userscript
  - tracking
  - video
  - digest
  - backend
  - fastapi
platforms: [web, linux, macos, windows]
setup_needed: true
---

# YoutubeHook — AI Agent Integration Guide

> **Browser userscript + backend server** that tracks watched YouTube videos, stores them via webhook, and generates periodic digests with click tracking.

---

## 📦 Components

| Component | Stack | Purpose |
|-----------|-------|---------|
| **UserScript** | JavaScript (Tampermonkey) | Runs in browser, intercepts YouTube navigation, sends webhook GET requests |
| **Backend API** | Python (FastAPI + SQLite) | Receives webhook data, tracks clicks, serves video feed |
| **Digest CLI** | Python CLI | Generates YouTube digests via YouTube Data API v3, sends to Telegram |
| **Click Tracker** | SQLite | Logs video views and redirect clicks for dedup filtering |

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Browser                                │
│  ┌─────────────────────────────────────────────────┐     │
│  │  YoutubeHook (Tampermonkey)                      │     │
│  │   → extractVideoId() → buildPayload()            │     │
│  │   → sendToWebhook()                              │     │
│  └────────────────────┬────────────────────────────┘     │
└───────────────────────┼──────────────────────────────────┘
                        │ GET /hook?videoId=X&title=...
                        ▼
┌──────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                       │
│  ┌──────────────────────────────────────────────────┐    │
│  │  /hook          — receive video tracking data     │    │
│  │  /r/{video_id}  — redirect + log click            │    │
│  │  /videos        — query video data by time range   │    │
│  │  /feed          — recent clicks JSON               │    │
│  └────────────────────┬─────────────────────────────┘    │
└───────────────────────┼──────────────────────────────────┘
                        │
                  ┌─────▼─────┐
                  │  SQLite    │
                  │ clicks.db  │
                  └─────┬─────┘
                        │
                  ┌─────▼─────┐
                  │  Digest    │
                  │  CLI       │
                  │ (cron)     │
                  └─────┬─────┘
                        │
                        ▼
                 Telegram / Agent
```

---

## 🚀 Quick Start

### 1. Install the UserScript

- **Install Tampermonkey** for your browser: [tampermonkey.net](https://www.tampermonkey.net/)
- **Click to install YoutubeHook:** [Install](https://github.com/kas-cor/YoutubeHook/raw/refs/heads/main/youtube-hook.user.js)
- Click "Install" in the Tampermonkey dialog

### 2. Start the Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your Telegram token, chat ID, etc.
docker compose up -d
```

### 3. Configure Webhook URL

1. Open YouTube
2. Click Tampermonkey icon → 📝 **Set Webhook URL**
3. Enter your backend's webhook URL:
```
http://your-server:8800/hook?videoId={videoId}&title={title}&ts={timestamp}
```

### 4. Initialize Channel Cache

```bash
docker compose exec ythook-backend python -m app.digest --refresh
```

---

## 🤖 AI Agent Integration

### Webhook URL Format

The userscript sends a **GET request** to your configured URL with placeholders replaced:

```
http://your-backend:8800/hook?video=Qah3kw1-La0&title=How+to+Deploy+Docker&ts=2026-05-26T22%3A30%3A00.000Z
```

### Placeholders

| Placeholder | Description | Example Value |
|-------------|-------------|---------------|
| `{videoId}` or `{id}` | YouTube video ID | `Qah3kw1-La0` |
| `{title}` | Video title (URL-encoded) | `How+to+Deploy+Docker` |
| `{url}` | Full YouTube URL (URL-encoded) | `https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D...` |
| `{timestamp}` | ISO timestamp (URL-encoded) | `2026-05-26T22%3A30%3A00.000Z` |

### Querying Tracked Videos

```bash
# Get videos from the last 6 hours
curl "http://back-end:8800/videos?since=2026-05-27T00:00:00Z&limit=100"

# Get recent clicks (for dedup filtering)
curl "http://back-end:8800/feed?limit=20"

# Health check
curl "http://back-end:8800/health"
```

### Running the Digest

```bash
# Refresh channel cache (daily)
python -m app.digest --refresh

# Get digest — raw JSON (agent processes and formats)
python -m app.digest --hours 3 --raw

# Get digest — formatted chunks (agent relays)
python -m app.digest --hours 3 --no-send

# Get digest — send directly to Telegram
python -m app.digest --hours 3 --send
```

**Exit codes for agent automation:**
| Code | Meaning | Agent Action |
|------|---------|-------------|
| `0` | Videos found | Process stdout |
| `10` | No new videos | Remain silent |
| `2` | Config error | Alert user |

---

## ⚙️ Configuration

### In-Script Constants (editable)

```javascript
const CONFIG = {
  debug: true,
  storageKey: 'sent_video_ids',
  webhookUrlKey: 'webhook_url',
  videoIdLength: 11,
  requestTimeout: 10000,       // 10s
  debounceDelay: 300           // 300ms
};
```

### Tampermonkey Menu Commands

| Command | Action |
|---------|--------|
| 📝 **Set Webhook URL** | Enter webhook URL with placeholders |
| 🗑️ **Clear Sent History** | Reset all tracked video IDs |
| 📊 **Show Stats** | Show current webhook URL + sent count |

### Backend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YTHOOK_PORT` | `8800` | Server port |
| `YTHOOK_DATA_DIR` | `/data` | Data volume mount |
| `YTHOOK_REDIRECT_BASE` | `http://localhost:8800/r` | Redirect base URL for digest links |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token |
| `TELEGRAM_CHAT_ID` | — | Telegram chat ID |
| `YTHOOK_DIGEST_HOURS` | `3` | Default digest window |

---

## 📁 Repository Structure

```
YoutubeHook/
├── SKILL.md                  ← This file — AI agent integration guide
├── AGENTS.md                 ← Development docs
├── README.md                 ← User-facing docs (EN)
├── README_ru.md              ← User-facing docs (RU)
│
├── youtube-hook.user.js      ← Main userscript
├── package.json              ← npm config (linting)
├── .eslintrc.json            ← ESLint config
├── bun.lock                  ← Bun lockfile
├── .gitignore
│
└── backend/                  ← FastAPI backend + digest CLI
    ├── README.md
    ├── AGENTS.md
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── .env.example
    └── app/
        ├── __init__.py
        ├── __main__.py
        ├── config.py
        ├── database.py
        ├── main.py            ← FastAPI webhook server
        └── digest.py          ← Digest CLI generator
```

---

## 📊 Use with YouTube Digest Skill

The complete workflow for automated YouTube digests:

1. **YoutubeHook userscript** sends video IDs to the backend's `/hook` endpoint
2. **Backend** stores them in SQLite (clicks.db)
3. **Digest CLI** (cron) generates periodic digests via YouTube Data API, filtering already-clicked videos
4. **AI agent** formats the digest (raw JSON mode) or relays formatted HTML chunks
5. **Telegram delivery** via bot API or agent's messaging platform

---

## ⚠️ Common Pitfalls

- **Webhook URL must be set** — userscript does nothing until configured via Tampermonkey menu
- **Placeholders are URL-encoded** — `{title}` and `{url}` are encoded for GET safety
- **Dedup is per-install** — clearing browser storage also clears sent history
- **Tampermonkey required** — userscript uses `GM_*` APIs not available in plain JS
- **Google OAuth required** for digest generation (youtube.readonly scope)
- **First run requires `--refresh`** to populate channel cache
- **Click tracking**: videos the user clicks via redirect links are filtered from future digests
