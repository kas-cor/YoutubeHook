# Code Review: YoutubeHook

> **Источник:** автоматический code review через kanban (воркер `deep-reasoner`, задача `t_6058ee08`)
> **Дата отчёта:** 2026-08-02 · **Дата исправления:** 2026-08-03
> 🔴 Critical: 2 · ⚠️ Warnings: 5 · 💡 Suggestions: 6

---

Verdict: Проект в хорошем состоянии для v0.3.0. Архитектура чистая, документация отличная. Обнаружено 2 Critical (безопасность), 5 Warnings и 6 Suggestions. Критические — отсутствие аутентификации на webhook и подавление всех ошибок YouTube API. Рекомендую к принятию после устранения Critical.

Структура


YoutubeHook/
├── youtube-hook.user.js      ← Tampermonkey userscript (браузер, 242 строки)
├── package.json / .eslintrc  ← линтинг (ESLint)
├── README.md / README_ru.md  ← пользовательская документация
├── AGENTS.md / SKILL.md      ← документация для AI-агентов
└── backend/
    ├── Dockerfile / docker-compose.yml
    ├── requirements.txt / .env.example
    └── app/
        ├── main.py           ← FastAPI: /hook, /r/{id}, /feed, /videos, /health
        ├── digest.py          ← CLI: генератор дайджестов + Telegram-отправка
        ├── config.py          ← конфигурация из env
        ├── database.py        ← SQLite: clicks + sent-log
        ├── init.py / main.py


Data flow: Browser (MutationObserver) → GET /hook → SQLite → Digest CLI (YouTube API) → Telegram / stdout. Чистая линейная архитектура.

🔴 Critical (2)

1. Отсутствие аутентификации на /hook — main.py:59
Проблема: Эндпоинт /hook принимает запросы от кого угодно без токена, API-ключа или любой другой формы аутентификации. Злоумышленник может заспамить БД миллионами фейковых записей, что приведёт к отказу в обслуживании (SQLite не рассчитан на такой объём) и загрязнению дайджестов.
Решение: Добавить ?token= query-параметр с проверкой через config.WEBHOOK_TOKEN (из env). В userscript добавить плейсхолдер {token}.

2. Подавление всех ошибок YouTube API — digest.py:84-86, 100-101, 133-134
Проблема: Три блока except Exception: pass / except Exception as e: print(...); return [] молча глотают все ошибки YouTube API: rate limiting (HTTP 429), network errors, auth failures, quota exceeded. При превышении квоты дайджест будет молча возвращать пустой список, и оператор не узнает о проблеме, пока не заметит отсутствие дайджестов.
Решение: Различать типы ошибок: 429 → retry с exponential backoff; 403 (quota) → exit code 2 с сообщением в stderr; network errors → retry 3 раза. Для auth errors — немедленный exit 2.

⚠️ Warnings (5)

1. CORS allow_origins=["*"] раскрывает данные — main.py:36
Проблема: allow_origins=["*"] + allow_credentials=True — любой сайт может делать cross-origin запросы к /feed и /videos и читать историю просмотров пользователя. С allow_credentials=True и * браузеры всё равно блокируют credentialed-запросы, но комбинация семантически некорректна.
Решение: Либо убрать allow_credentials=True, либо ограничить origins конкретными доменами.

2. Нет валидации videoId — main.py:74, 102
Проблема: videoId не проверяется на длину (должен быть 11 символов) и формат ([a-zA-Z0-9_-]{11}). Можно передать строку произвольной длины, что замусорит БД и сломает редирект-ссылку.
Решение: Валидировать videoId через regex ^[a-zA-Z0-9_-]{11}$ на обоих эндпоинтах, возвращать 400 при несоответствии.

3. Google OAuth token перезаписывается без atomic write — digest.py:54
Проблема: with open(creds_path, "w") as f: f.write(creds.to_json()) — если процесс упадёт во время записи, файл токена будет повреждён, и все последующие запуски дайджеста сломаются до ручного восстановления.
Решение: Писать во временный файл + os.rename() (atomic на Linux) или использовать tempfile + shutil.move.

4. Два независимых механизма дедупликации — userscript:57 + database.py:43
Проблема: Userscript хранит sent IDs в GM storage, backend — в SQLite clicks. Они не синхронизированы. Если пользователь очистит Tampermonkey storage, видео будут отправлены повторно. В БД нет UNIQUE constraint на video_id, поэтому будут дубликаты записей.
Решение: Добавить UNIQUE(video_id, user_id) в схему clicks или использовать INSERT OR IGNORE.

5. Сложная логика format_digest с nonlocal-мутациями — digest.py:201-300
Проблема: Функция format_digest использует вложенные функции start_new_chunk и finish_chunk, мутирующие 4 переменные через nonlocal. Код трудно читать, тестировать и модифицировать. При размере чанка, близком к MAX_MSG_LEN, возможен off-by-one в расчёте current_len.
Решение: Выделить класс ChunkBuilder с инкапсулированным состоянием, либо разбить на чистые функции без побочных эффектов.

💡 Suggestions (6)

1. GET вместо POST для webhook — userscript:129
GET-запросы кэшируются прокси, логируются с параметрами в URL, имеют ограничение длины ~2048 символов. Для отправки данных лучше подходит POST с JSON body.
Решение: Перейти на method: 'POST' с data: JSON.stringify(videoInfo) и Content-Type: application/json.

2. Мёртвый код: MAX_WORKERS, videoIdLength
MAX_WORKERS = 20 в config.py и videoIdLength: 11 в userscript CONFIG объявлены, но нигде не используются. Удалить.

3. Параметр ts в /hook не сохраняется — main.py:65
Query-параметр ts (ISO timestamp от клиента) принимается, но не передаётся в db.log_click(). Клиентский timestamp теряется, вместо него используется time.time() на сервере.
Решение: Либо сохранять ts в БД, либо убрать параметр из сигнатуры.

4. bun.lock при npm в package.json
bun.lock лежит в репозитории, но package.json не содержит bun как менеджер. Либо добавить bun в packageManager, либо удалить lock-файл и добавить package-lock.json.

5. Нет retry для GM_xmlhttpRequest — userscript:129
При ошибке сети (onerror) или таймауте (ontimeout) запрос просто логируется и забывается. Видео остаётся неотправленным.
Решение: Добавить очередь с retry (до 3 попыток с экспоненциальной задержкой) или хотя бы сохранять failed IDs для повторной отправки.

6. /r/{video_id} — открытый редирект — main.py:100
Любой video_id редиректит на youtube.com/watch?v=.... Злоумышленник может использовать ваш домен для фишинга: жертва видит your-domain.com/r/... и доверяет ссылке.
Решение: Валидировать video_id (regex), либо добавить промежуточную страницу с подтверждением перехода.

✅ Что сделано отлично

- Чистая архитектура: userscript → webhook → SQLite → digest → Telegram. Каждый компонент имеет одну ответственность.
- Продуманные exit codes: 0/10/2 для бесшовной интеграции с AI-агентами и cron.
- WAL-режим SQLite: конкурентные чтения при записи, правильный выбор для web-сервера.
- Debounce MutationObserver (300ms): грамотная обработка SPA-навигации YouTube без лишних срабатываний.
- Fallback-цепочка для заголовка: og:title → h1 → document.title — устойчиво к изменениям вёрстки YouTube.
- Placeholder-система: гибкая настройка webhook URL с {videoId}, {title}, {url}, {timestamp}.
- Кэширование дайджеста (600s TTL): снижает нагрузку на YouTube API при частых запусках.
- Фильтрация shorts: по длительности (≤120s) и описанию (#shorts) — правильно, YouTube API не имеет явного флага isShort.
- Docker Compose с healthcheck: production-ready деплой.
- Документация: AGENTS.md, SKILL.md, README на двух языках — редкое качество для проекта такого размера.
- Graceful degradation: понятные сообщения об ошибках при отсутствии Google token или channel cache.

Итог

  ┊ ✔
---

## Статус исправления (kanban)

Исправлены 2 critical: токен-аутентификация на GET /hook (?token= из WEBHOOK_TOKEN, 401 при несовпадении) + плейсхолдер {token} в userscript; в `digest.py` три блока `except pass` заменены на `_api_call` (429→backoff, 403→exit 2, network→retry).

> Изменения внесены воркером (`t_9a6a725c`) в рабочую директорию проекта — **не закоммичены**.
