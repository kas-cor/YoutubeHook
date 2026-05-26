# YoutubeHook — Agent Documentation

## Project Overview

A Tampermonkey userscript that tracks watched YouTube videos and sends metadata (ID, title, URL, timestamp) to a configurable webhook via GET request. Designed to integrate with AI agents for watch history tracking, content monitoring, and daily YouTube digests.

---

## Architecture

```
Browser (YouTube)
    │
    ├── MutationObserver detects URL change (300ms debounce)
    ├── extractVideoId() — parses /watch, /shorts, /embed, /live
    ├── getVideoTitle() — fallback chain
    ├── isIdSent() — dedup check (GM storage)
    └── sendToWebhook() — GET via GM_xmlhttpRequest
        │
        └── Webhook Receiver
                │
                └── AI Agent / Digest System
```

## Script Metadata

```javascript
// @name         YoutubeHook
// @version      0.2.0
// @description  YouTube webhook tracker – sends watched video IDs to webhook
// @author       kas-cor
// @match        https://www.youtube.com/*
// @match        https://youtube.com/*
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @grant        GM_xmlhttpRequest
// @connect      *
// @run-at       document-start
```

## Core Components

### Logger Utility
- Wraps `console.log/info/warn/error/group/groupEnd`
- Respects `CONFIG.debug` flag (default: `true`)
- Adds `[YoutubeHook]` prefix to all messages

### Settings Management (GM Storage)

| Function | Storage Key | Description |
|----------|-------------|-------------|
| `getWebhookUrl()` | `webhook_url` | Returns stored webhook URL string |
| `setWebhookUrl(url)` | `webhook_url` | Saves webhook URL |
| `getSentIds()` | `sent_video_ids` | Loads JSON array of sent IDs |
| `addSentId(id)` | `sent_video_ids` | Adds ID to array (no duplicates) |
| `isIdSent(id)` | — | Memory-cached check |
| `clearSentIds()` | `sent_video_ids` | Clears array |

### Video Information Extraction

**`extractVideoId(url)`** — supports 4 patterns:
```javascript
const patterns = [
  /[?&]v=([a-zA-Z0-9_-]{11})/,    // /watch?v=...
  /\/shorts\/([a-zA-Z0-9_-]{11})/, // /shorts/...
  /\/embed\/([a-zA-Z0-9_-]{11})/,  // /embed/...
  /\/live\/([a-zA-Z0-9_-]{11})/    // /live/...
];
```

**`getVideoTitle()`** — fallback chain:
1. `<meta property="og:title">`
2. `<h1>` element
3. `document.title` (stripping " - YouTube")

### Send to Webhook (`sendToWebhook(videoId)`)

1. Checks webhook URL is configured
2. Checks dedup (in-memory cache)
3. Builds `videoInfo` object `{videoId, id, title, url, timestamp}`
4. Replaces placeholders (`{videoId}`, `{id}`, `{title}`, `{url}`, `{timestamp}`) — values URL-encoded
5. Sends GET via `GM_xmlhttpRequest` with 10s timeout
6. HTTP 200-399 → saves to history; failure → logged, not saved

### URL Change Handling (SPA)

- **MutationObserver** on `document.body` (subtree + childList)
- **Debounced** 300ms to handle YouTube's SPA transitions
- Triggers `handleUrlChange()` → `sendToWebhook()`
- Initial check on page load

## Tampermonkey Menu Commands

| Command | Implementation |
|---------|---------------|
| **📝 Set Webhook URL** | `prompt()` with placeholder help; validates http/https |
| **🗑️ Clear Sent History** | `confirm()` → `GM_deleteValue(CONFIG.storageKey)` |
| **📊 Show Stats** | `alert()` with webhook URL + sent count |

## Key Behaviors

- **Debounce:** 300ms between URL changes (prevents duplicate sends)
- **Validation:** Webhook URL must be valid http/https
- **Error handling:** Errors logged, never block the page
- **Persistence:** `GM_setValue`/`GM_getValue` (survives page refreshes)
- **Dedup:** Same video ID never sent twice (in-memory + GM storage)
- **Performance:** In-memory cache for sent IDs; storage read once per session

## Integration with YouTube Digest

### Expected Webhook Endpoint (Python FastAPI example)
```python
@app.get("/youtube-hook")
async def track_video(videoId: str, title: str = "", ts: str = ""):
    # Store in DB
    return {"ok": True}
```

### Data Flow for Digest
```
YoutubeHook → webhook → SQLite DB (daily accumulation)
                              ↓
                    Daily cron → query DB → generate digest
                              ↓
                    Deliver to user (Telegram / email)
```

## Development

```bash
npm install    # Install dependencies (for linting)
npm run lint   # Run ESLint
```

## File Structure

```
YoutubeHook/
├── youtube-hook.user.js    ← Main userscript
├── package.json            ← npm dependencies
├── .eslintrc.json          ← ESLint config
├── SKILL.md                ← AI agent integration guide
├── AGENTS.md               ← This file
├── README.md               ← User-facing docs (EN)
└── README_ru.md            ← User-facing docs (RU)
```