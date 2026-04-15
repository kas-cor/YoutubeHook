# YoutubeHook

UserScript для отслеживания просмотренных видео на YouTube и отправки информации на вебхук.

## Функции

- Автоматическое отслеживание просмотренных видео на YouTube
- Отправка данных о видео на указанный вебхук через GET-запрос
- Поддержка placeholders для формирования URL: `{videoId}`, `{title}`, `{url}`, `{timestamp}`
- Дедупликация — один и тот же ID видео не отправляется дважды
- Поддержка SPA-навигации YouTube (без перезагрузки страницы)
- Настройка вебхука через меню Tampermonkey

## Установка

1. Установите расширение [Tampermonkey](https://www.tampermonkey.net/)
2. Откройте файл `youtube-hook.user.js` в браузере
3. Нажмите "Установить"
4. Откройте YouTube, нажмите на иконку Tampermonkey → "📝 Set Webhook URL"
5. Укажите URL вебхука с placeholders, например:
   ```
   https://your-server.com/api?id={videoId}&title={title}&ts={timestamp}
   ```

## Настройка

После установки в меню Tampermonkey доступны команды:

- **📝 Set Webhook URL** — задать URL вебхука с поддержкой placeholders
- **🗑️ Clear Sent History** — очистить историю отправленных видео
- **📊 Show Stats** — показать статистику (количество отправленных видео)

### Доступные placeholders

| Placeholder | Описание |
|-------------|----------|
| `{videoId}` или `{id}` | ID видео (например: `Qah3kw1-La0`) |
| `{title}` | Название видео |
| `{url}` | Полный URL YouTube |
| `{timestamp}` | Дата и время в ISO формате |

**Примеры URL:**
```
https://api.example.com/track?id={videoId}
https://myserver.com/hook?video={videoId}&title={title}
https://backend.com/api?url={url}&ts={timestamp}
```

## Разработка

```bash
# Инициализация проекта
npm install

# Линтинг
npm run lint
```

## Структура проекта

```
youtube-hook.user.js    # Основной файл скрипта
package.json             # Конфигурация npm
.eslintrc.json          # Настройки линтера
README.md                # Документация
```

## Как это работает

1. Скрипт отслеживает изменения URL на YouTube (SPA-навигация)
2. При обнаружении страницы видео (`/watch?v=ID`) извлекает ID видео
3. Проверяет, не было ли это видео уже отправлено
4. Формирует GET-запрос, заменяя placeholders на реальные данные
5. Отправляет запрос на вебхук
6. Сохраняет ID в историю (учитываются HTTP 200-399 как успех)

## Требования

- Браузер с поддержкой расширений (Chrome, Firefox, Edge)
- [Tampermonkey](https://www.tampermonkey.net/) или совместимый менеджер userscripts

## Лицензия

MIT
