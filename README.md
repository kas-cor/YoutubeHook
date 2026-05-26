# YoutubeHook

[![License](https://img.shields.io/github/license/kas-cor/YoutubeHook)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-kas--cor/YoutubeHook-181717?logo=github)](https://github.com/kas-cor/YoutubeHook)

> 🌐 [Русская версия](README_ru.md)

A **Tampermonkey userscript** that automatically detects watched YouTube videos and sends their metadata to a configurable webhook via GET request.

## Features

- 🎬 **Auto-detection** of watched videos on YouTube (`/watch`, `/shorts`, `/embed`, `/live`)
- 🔗 **Webhook delivery** — configurable URL with placeholder support
- 🧩 **Placeholders:** `{videoId}`, `{title}`, `{url}`, `{timestamp}`
- 🚫 **Deduplication** — same video ID never sent twice
- 🔄 **SPA navigation support** — works with YouTube's single-page app
- 🛠️ **Tampermonkey menu** — set webhook URL, clear history, view stats

## Quick Install

1. Install [Tampermonkey](https://www.tampermonkey.net/) for your browser
2. **[Install YoutubeHook](https://github.com/kas-cor/YoutubeHook/raw/refs/heads/main/youtube-hook.user.js)**
3. Open YouTube, click Tampermonkey icon → **📝 Set Webhook URL**
4. Enter your webhook URL with placeholders, e.g.:
```
https://your-server.com/hook?id={videoId}&title={title}
```

## Placeholders

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{videoId}` / `{id}` | YouTube video ID | `Qah3kw1-La0` |
| `{title}` | Video title (URL-encoded) | `How+to+Deploy` |
| `{url}` | Full YouTube URL (URL-encoded) | `https%3A%2F%2F...` |
| `{timestamp}` | ISO timestamp (URL-encoded) | `2026-05-26T22%3A...` |

## Tampermonkey Menu

| Command | Action |
|---------|--------|
| 📝 **Set Webhook URL** | Configure your webhook endpoint |
| 🗑️ **Clear Sent History** | Reset all tracked video IDs |
| 📊 **Show Stats** | View webhook URL and sent count |

## Development

```bash
npm install
npm run lint
```

---

<p align="center">
  <a href="README_ru.md">🌐 Русская версия</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/kas-cor/YoutubeHook/issues">🐛 Report a Bug</a>
</p>