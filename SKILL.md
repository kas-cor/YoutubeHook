---
name: youtube-hook
description: "Tampermonkey userscript that tracks watched YouTube videos and sends video info to a configurable webhook — supports placeholders, dedup, SPA navigation"
version: 0.2.0
author: kas-cor
license: MIT
tags:
  - youtube
  - webhook
  - tampermonkey
  - userscript
  - tracking
  - video
platforms: [web]
setup_needed: true
required_commands: []
required_environment_variables: []
---

# YoutubeHook — AI Agent Integration Guide

> **Tampermonkey userscript** that automatically detects watched YouTube videos and sends their metadata (ID, title, URL, timestamp) to a configurable webhook via GET request.

---

## 📦 Components

| Component | Stack | Purpose |
|-----------|-------|---------|
| **UserScript** | JavaScript (Tampermonkey/Greasemonkey) | Runs in browser, intercepts YouTube page navigation, sends webhook GET requests |
| **Webhook Receiver** | Any HTTP server | Receives video tracking data (e.g., Hermes / OpenClaw / custom backend) |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser                               │
│  ┌────────────────────────────────────────────────┐     │
│  │  YouTube (youtube.com)                         │     │
│  │                                                │     │
│  │  YoutubeHook (Tampermonkey)                    │     │
│  │  ┌──────────────────────────────────────────┐  │     │
│  │  │ MutationObserver detects URL change       │  │     │
│  │  │   → extractVideoId(url)                  │  │     │
│  │  │   → getVideoTitle()                      │  │     │
│  │  │   → buildPayload()                       │  │     │
│  │  │   → checkDedup()                         │  │     │
│  │  │   → sendToWebhook()                      │  │     │
│  │  └──────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────┘     │
└──────────────────────────┬──────────────────────────────┘
                           │
                    GET request (with placeholders)
                           │
                    ┌──────┴──────┐
                    │  Webhook    │
                    │  Receiver   │
                    │ (AI Agent)  │
                    └─────────────┘
```

### Data Flow

```
User opens YouTube video page
       ↓
MutationObserver fires (debounced 300ms)
       ↓
extractVideoId() → parses /watch, /shorts, /embed, /live
       ↓
isIdSent() check (dedup via GM storage)
       ↓
Placeholders replaced: {videoId}, {title}, {url}, {timestamp}
       ↓
GET request to webhook URL via GM_xmlhttpRequest
       ↓
HTTP 200-399 → ID saved to history
```

---

## 🚀 Quick Start

### 1. Install the Script

- **Install Tampermonkey** for your browser: [tampermonkey.net](https://www.tampermonkey.net/)
- **Click to install YoutubeHook:** [Install](https://github.com/kas-cor/YoutubeHook/raw/refs/heads/main/youtube-hook.user.js)
- Click "Install" in the Tampermonkey dialog

### 2. Configure Webhook URL

1. Open YouTube
2. Click Tampermonkey icon → 📝 **Set Webhook URL**
3. Enter your webhook URL using placeholders:

```
https://your-agent-server.com/youtube-hook?id={videoId}&title={title}&ts={timestamp}
```

### 3. Test It

Open any YouTube video page. The script automatically detects it and sends a GET request to your webhook.

---

## 🤖 AI Agent Integration

### When to Use YoutubeHook

| Use Case | Example |
|----------|---------|
| **Track watched videos** | `curl "http://your-agent/youtube-hook?id=Qah3kw1-La0&title=My+Video&ts=2026-05-26T22:30:00Z"` |
| **Build a watch history** | Log all `{videoId}` and `{title}` from incoming webhooks |
| **Content monitoring** | Track what's being watched on specific channels |
| **YouTube digest** | Collect daily video stats and generate summaries |

### Webhook URL Format

The script sends a **GET request** to your configured URL with placeholders replaced:

```
https://your-server.com/hook?video={videoId}&title={title}&url={url}&ts={timestamp}
```

**Example request that arrives at your server:**
```
https://your-server.com/hook?video=Qah3kw1-La0&title=How+to+Deploy+Docker&url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DQah3kw1-La0&ts=2026-05-26T22%3A30%3A00.000Z
```

### Placeholders

| Placeholder | Description | Example Value |
|-------------|-------------|---------------|
| `{videoId}` or `{id}` | YouTube video ID | `Qah3kw1-La0` |
| `{title}` | Video title (URL-encoded) | `How+to+Deploy+Docker` |
| `{url}` | Full YouTube URL (URL-encoded) | `https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D...` |
| `{timestamp}` | ISO timestamp (URL-encoded) | `2026-05-26T22%3A30%3A00.000Z` |

### Sample Webhook URLs

```bash
# Minimal
https://api.example.com/track?id={videoId}

# Full info
https://myserver.com/hook?video={videoId}&title={title}

# Agent endpoint
https://your-agent/youtube-watch?v={videoId}&title={title}&ts={timestamp}
```

### How to Parse Incoming Requests (AI Agent)

Your webhook receiver gets a standard GET request. Example in Python (FastAPI):

```python
@app.get("/youtube-hook")
async def youtube_hook(videoId: str, title: str = "", ts: str = ""):
    print(f"Watched: {title} ({videoId}) at {ts}")
    # Store in DB, generate digest, etc.
    return {"ok": True}
```

---

## ⚙️ Configuration

### In-Script Constants (editable)

```javascript
const CONFIG = {
  debug: true,                // Console logging toggle
  storageKey: 'sent_video_ids', // GM storage key
  webhookUrlKey: 'webhook_url', // GM storage key
  videoIdLength: 11,           // YouTube video ID length
  requestTimeout: 10000,       // 10s timeout
  debounceDelay: 300           // 300ms URL change debounce
};
```

### Tampermonkey Menu Commands

| Command | Action |
|---------|--------|
| 📝 **Set Webhook URL** | Enter webhook URL with placeholders |
| 🗑️ **Clear Sent History** | Reset all tracked video IDs |
| 📊 **Show Stats** | Show current webhook URL + sent count |

---

## 🧠 Script Internals

### Video ID Extraction

Supports all YouTube URL formats:
```javascript
const patterns = [
  /[?&]v=([a-zA-Z0-9_-]{11})/,    // /watch?v=...
  /\/shorts\/([a-zA-Z0-9_-]{11})/, // /shorts/...
  /\/embed\/([a-zA-Z0-9_-]{11})/,  // /embed/...
  /\/live\/([a-zA-Z0-9_-]{11})/    // /live/...
];
```

### Title Resolution (fallback chain)

1. `<meta property="og:title">` content
2. `<h1>` element text content
3. `document.title` (stripping " - YouTube")

### Deduplication

- Uses `GM_setValue`/`GM_getValue` to persist sent video IDs
- In-memory cache for fast lookups during session
- Same ID never sent twice

### SPA Navigation Detection

- **MutationObserver** on `document` detects URL changes without page reload
- **Debounce:** 300ms delay prevents duplicate sends during YouTube's SPA transitions
- Also runs initial check on page load

### Webhook Request

- Method: **GET** via `GM_xmlhttpRequest`
- Timeout: **10 seconds**
- Success: HTTP status 200-399 → ID saved to history
- Failure: logged, ID not saved

---

## 📁 Repository Structure

```
YoutubeHook/
├── SKILL.md                    ← This file — AI agent integration guide
├── AGENTS.md                   ← Development documentation for agents
├── README.md                   ← For humans (EN)
├── README_ru.md                ← For humans (RU)
│
├── youtube-hook.user.js        ← Main userscript
├── package.json                ← npm config (linting)
├── .eslintrc.json              ← ESLint config
├── bun.lock                    ← Bun lockfile
└── .gitignore
```

---

## 📊 Use with YouTube Digest Skill

This script pairs with the `youtube-digest` skill to automatically generate daily summaries of watched YouTube content.

**Workflow:**
1. YoutubeHook sends video IDs to a webhook endpoint
2. The webhook receiver stores them in a database
3. The digest agent collects daily data and generates summaries
4. Results are delivered to the user (e.g., via Telegram)

---

## ⚠️ Common Pitfalls

- **Webhook URL must be set** — the script does nothing until configured via menu
- **Placeholders are URL-encoded** — `{title}` and `{url}` are encoded for GET safety
- **Dedup is per-install** — clearing browser storage also clears sent history
- **Tampermonkey required** — the script uses `GM_*` APIs not available in plain JS
- **HTTPS only** — YouTube is HTTPS; make sure your webhook also supports HTTPS
- **CORS not an issue** — `GM_xmlhttpRequest` bypasses CORS restrictions