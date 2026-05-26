# YoutubeHook

[![License](https://img.shields.io/github/license/kas-cor/YoutubeHook)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-kas--cor/YoutubeHook-181717?logo=github)](https://github.com/kas-cor/YoutubeHook)

> 🇬🇧 [English version](README.md)

UserScript для отслеживания просмотренных видео на YouTube и отправки информации на вебхук.

## Функции

- 🎬 **Автоматическое отслеживание** просмотренных видео на YouTube
- 🔗 **Отправка данных** о видео на указанный вебхук через GET-запрос
- 🧩 **Placeholders** для формирования URL: `{videoId}`, `{title}`, `{url}`, `{timestamp}`
- 🚫 **Дедупликация** — один и тот же ID не отправляется дважды
- 🔄 **Поддержка SPA-навигации** YouTube
- 🛠️ **Настройка** через меню Tampermonkey

## Быстрая установка

1. Установите [Tampermonkey](https://www.tampermonkey.net/)
2. **[Установить YoutubeHook](https://github.com/kas-cor/YoutubeHook/raw/refs/heads/main/youtube-hook.user.js)**
3. Откройте YouTube, иконка Tampermonkey → **📝 Set Webhook URL**
4. Укажите URL, например:
```
https://your-server.com/hook?id={videoId}&title={title}
```

## Меню Tampermonkey

| Команда | Действие |
|---------|----------|
| 📝 **Set Webhook URL** | Настроить URL вебхука |
| 🗑️ **Clear Sent History** | Очистить историю отправленных |
| 📊 **Show Stats** | Статистика (URL + количество) |

## Разработка

```bash
npm install
npm run lint
```

---

<p align="center">
  <a href="README.md">🇬🇧 English version</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/kas-cor/YoutubeHook/issues">🐛 Сообщить об ошибке</a>
</p>