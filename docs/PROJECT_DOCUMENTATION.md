# AI Assistant Hub — Project Documentation

> **Created:** 2026-09-06  
> **Purpose:** Complete project map for future reference after migrating to a new platform.  
> **Audience:** Non-coder / business owner who needs to understand what we built and where everything lives.

---

## 1. What Is This Project?

**AI Assistant Hub** (в коде: `ai-app-frontend`) — это **Telegram Mini App** (встроенное приложение внутри Telegram), которое позволяет пользователям общаться с разными ИИ-моделями (OpenRouter, Google Gemini и др.) через удобный интерфейс, похожий на ChatGPT.

- **Фронтенд:** Single Page Application (SPA) на чистом JS, развернуто на GitHub Pages.
- **Бэкенд:** Два канала отправки запросов:
  1. **Supabase Edge Functions** (`/chat`, `/settings`, `/dialogs`) — основной путь в production.
  2. **Локальный aiohttp-сервер** (`openrouter-telegram-bot/`) — запасной/отладочный путь.
- **Телеграм-бот:** `main.py` управляет запуском Mini App и авторизацией, но основной функционал живёт во фронтенде.

---

## 2. Repositories (Где что лежит)

| Repo | Ссылка | Что внутри | Активность |
|------|--------|------------|------------|
| **ai-app-frontend** | `ThreepleS/ai-app-frontend` | Фронтенд, GitHub Pages, gh-pages ветка | **Активный, продакшен** |
| **openrouter-telegram-bot** | Локально на рабочем столе | Телеграм-бот (main.py), локальный бэкенд (aiohttp), скрипт деплоя | Неактивный, резерв |

> **Важно:** Все изменения, которые видят пользователи, делаются в `ai-app-frontend`. Второй репозиторий сейчас не используется, но может понадобиться, если вы решите разворачивать бэкенд самостоятельно.

---

## 3. File Structure — Что где лежит

### 3.1 ai-app-frontend (prod)

```
gh-pages/
├── index.html              # Точка входа. Подключает app.js и стили.
├── app.js                  # ВЕСЬ фронтенд в одном файле (4615 строк).
│                           # Содержит: маршрутизацию, UI, логику чата,
│                           # onboarding, настройки, загрузку тем.
├── sw.js                   # Service Worker (офлайн-кэш, network-first).
├── deploy.ps1              # Скрипт деплоя: bump version, копирует app.js → app_<version>.js
├── eruda.min.js            # Консоль разработчика для отладки в телефоне.
├── eruda-init.js           # Инициализация eruda (dark theme, без автопоказа).
├── style.css               # Все стили.
├── app_<version>.js        # Развёрнутые бэкапы app.js (только последний важен).
└── version.json            # Метка версии для кэша.
```

### 3.2 openrouter-telegram-bot (резерв)

```
├── main.py                 # Telegram-бот (aiogram 3.x). Обрабатывает /start, /help,
│                           # вебхук-инициализацию, запуск Mini App.
├── requirements.txt        # Зависимости Python.
├── .env                    # СЕКРЕТЫ (см. раздел 5).
├── .gitignore
├── README.md
├── supabase/
│   ├── config.toml         # Локальный Supabase (если запускаете оффлайн).
│   └── functions/
│       └── chat/           # Edge Function /chat (отправка запроса в OpenRouter).
├── web_app/                # (Опционально) статика, если разворачиваете отдельно.
├── scripts/
│   └── deploy.ps1          # Деплой фронтенда на gh-pages (такой же, как в ai-app-frontend).
└── kilo.json / AGENTS.md   # Конфигурация Kilo (ИИ-ассистента).
```

---

## 4. How It Works (Архитектура)

### 4.1 Пользовательский путь

1. Пользователь открывает бота в Telegram → нажимает кнопку **"Open App"**.
2. Telegram открывает Mini App (WebView) по ссылке: `https://threeples.github.io/ai-app-frontend/?v=<timestamp>`.
3. Фронтенд проверяет `Telegram.WebApp.initData` (подпись от Telegram).
4. Загружаются:
   - Настройки пользователя (`/settings` Edge Function).
   - Список диалогов (`/dialogs` Edge Function).
   - Ключи API (`/keyinfo` Edge Function).
5. Пользователь пишет сообщение → фронтенд отправляет его в `/chat` Edge Function.
6. Edge Function пересылает запрос в **OpenRouter API** → получает ответ → возвращает в фронтенд.
7. Ответ отображается в чате.

### 4.2 Почему два пути (Supabase vs локальный)?

- **Supabase Edge Functions** — без серверов, масштабируются сами, используются в production.
- **Локальный aiohttp** — нужен для отладки, если Supabase не работает или вы хотите держать всё на своём хостинге.

В коде выбор происходит по флагу. Сейчас активен Supabase.

---

## 5. Database & Secrets (База данных и секреты)

### 5.1 Supabase (PostgreSQL + Edge Functions)

Проект Supabase: `amhszfvqruzpydqyjlya`

**Таблицы (основные):**
- `profiles` — профили пользователей Telegram (`telegram_id`, username, first_name, last_name).
- `api_keys` — ключи OpenRouter/Gemini пользователей (зашифрованы/маскированы).
- `settings` — настройки пользователя (модель, температура, system prompt, звук, вибрация).
- `dialogs` — история переписки (массив сообщений в JSONB).

**Секреты Supabase (где искать):**
- В файле `.env` в папке `openrouter-telegram-bot/`:
  - `SUPABASE_URL` — адрес проекта Supabase.
  - `SUPABASE_ANON_KEY` — публичный ключ (безопасно хранить в коде).
  - `SUPABASE_SERVICE_ROLE_KEY` — секретный ключ (админ, НЕ показывать никому).
  - `OPENROUTER_API_KEY` — ключ OpenRouter (для тестов/fallback).
- В **Supabase Dashboard** → Settings → API: те же ключи.
- В **Supabase Dashboard** → Edge Functions → Secrets: переменные окружения функций (`OPENROUTER_API_KEY`, `SUPABASE_URL` и т.д.).

### 5.2 Telegram Bot Token

- `TELEGRAM_BOT_TOKEN` — в `.env` файле `openrouter-telegram-bot/`.
- Также можно посмотреть в **@BotFather** → `/mybots` → выберите бота → API Token.

---

## 6. Deployment (Как это попадает в интернет)

### 6.1 Фронтенд (GitHub Pages)

1. Изменяете `gh-pages/app.js` (или `style.css`).
2. Запускаете `cd gh-pages; powershell -ExecutionPolicy Bypass -File deploy.ps1`.
3. Скрипт:
   - Bump версии (дата_время).
   - Копирует `app.js` → `app_<version>.js`.
   - Инжектирует `APP_VERSION` в файл.
   - Коммитит и пушит в ветку `gh-pages`.
4. GitHub автоматически разворачивает на `https://threeples.github.io/ai-app-frontend/`.

**Важно:**
- В `index.html` всегда ссылка на **последний** `app_<version>.js?v=<version>`.
- Старые версии (`app_20260826_1939.js` и т.д.) **не нужны** — Git хранит историю.
- Кэш-бастинг: `?v=` в URL + имя файла с версией. Если пользователь видит старую версию — нужно принудительное обновление (закрыть/открыть приложение, или Ctrl+Shift+R в браузере).

### 6.2 Edge Functions (Supabase)

- Разворачиваются через `supabase functions deploy <имя>`.
- Или через веб-интерфейс Supabase Dashboard → Edge Functions → Deploy.
- Требуют CLI `supabase` и логин.

### 6.3 Telegram Bot

- Хостится на **Replit** (или любом VPS).
- Запускается через `python main.py`.
- Вебхук настроен через `@BotFather` → `/setwebapp`.

---

## 7. Important URLs

| Что | URL |
|-----|-----|
| Продакшен фронтенд | https://threeples.github.io/ai-app-frontend/ |
| GitHub repo (фронтенд) | https://github.com/ThreepleS/ai-app-frontend |
| Supabase Dashboard | https://supabase.com/dashboard/project/amhszfvqruzpydqyjlya |
| OpenRouter Dashboard | https://openrouter.ai/keys |
| Telegram бот (если есть) | @<username_bot> |

---

## 8. Key Technical Decisions (Почему так сделано)

1. **Один большой app.js** — чтобы избежать проблем с CORS и путями при деплое на GitHub Pages.
2. **`aiHubQueryAll` вместо `querySelectorAll`** —Telegram WebView на старых Android не поддерживает `forEach` на NodeList. Наша функция всегда возвращает **настоящий Array**.
3. **`Array.prototype.forEach` polyfill + guards** — защита от старых WebView, где `forEach` отсутствует вообще.
4. **CSP строгий** — запрет inline-скриптов, только локальные файлы. Никаких CDN.
5. **DOMPurify** — для безопасности при отображении HTML из ИИ.
6. **Service Worker network-first** — чтобы всегда получать свежую версию, но работать офлайн.
7. **Без TypeScript** — файлы `.js`, чтобы не было проблем с парсингом в старых средах.

---

## 9. Known Issues & Fixes (Что ломалось и как чинили)

| Проблема | Статус | Решение |
|-----------|--------|---------|
| `querySelectorAll(...).forEach is not a function` | **Починилено** | `aiHubQueryAll` возвращает Array, добавлен полифилл `forEach` |
| `SyntaxError` из-за TypeScript-синтаксиса в `.js` | **Починилено** | Убраны `: type`, `as`, `Promise<void>` |
| `tourActive is not defined` | **Починилено** | Добавлена инициализация переменной |
| `Uncaught TypeError: validateTimestamp is not a function` | **Починилено** | Удалены `validateTimestamp`, `checkRateLimit`, `auditLog` из Edge Functions |
| Авто-сжатие контекста чата | **Отклонено** | Решено не делать — пользователь управляет контекстом вручную |
| Старые версии `app_*.js` в репозитории | **Починилено** | Удалены 31 файл, оставлен только последний |

---

## 10. How to Edit / Extend (Как дорабатывать)

### Если нужно поменять текст/стиль:
1. Открываете `gh-pages/app.js` (фронтенд) или `gh-pages/style.css`.
2. Правите.
3. Запускаете деплой (`deploy.ps1`).
4. Проверяете в Telegram (закрыть/открыть приложение).

### Если нужно поменять логику бэкенда:
1. **Supabase Edge Functions:** правите код в папке `supabase/functions/<name>/index.ts`.
2. **Локальный бэкенд:** правите `openrouter-telegram-bot/main.py` или `web_app/` (если есть).
3. Деплоите: `supabase functions deploy <name>` или перезапускаете Python-сервер.

### Если нужно добавить новую модель ИИ:
1. В `gh-pages/app.js` найдите массив/список моделей (обычно в settings или при инициализации).
2. Добавьте новую модель с `id`, `name`, `provider` (openrouter/gemini).
3. Для OpenRouter моделей нужен `id` вида `openai/gpt-4o` или `google/gemini-2.0-flash-exp:free`.
4. Деплой.

---

## 11. Glossary (Словарик)

| Термин | Что значит |
|--------|------------|
| **Mini App** | Приложение внутри Telegram, открывается по кнопке. |
| **WebView** | Браузер внутри Telegram, который показывает Mini App. |
| **Edge Function** | Функция, которая запускается "у края" (ближе к пользователю), без отдельного сервера. У нас на Supabase. |
| **GitHub Pages** | Хостинг статики от GitHub. У нас там лежит фронтенд. |
| **gh-pages** | Ветка в GitHub repo, которая автоматически разворачивается на GitHub Pages. |
| **OpenRouter** | Агрегатор ИИ-моделей (один API для GPT-4, Claude, Gemini и т.д.). |
| **CSP (Content Security Policy)** | Заголовки, которые запрещают browser выполнять подозрительный код. |
| **Service Worker** | Скрипт, который кэширует файлы для офлайн-работы. |
| **aiohttp** | Python-библиотека для веб-серверов. У нас используется как запасной бэкенд. |
| **eruda** | Консоль разработчика для мобильных браузеров (как DevTools в Chrome, но в телефоне). |
| **JSONB** | Тип данных в Postgres для хранения JSON. У нас там хранится история диалогов. |

---

## 12. Contacts & Accounts

| Сервис | Аккаунт |
|--------|---------|
| GitHub | `ThreepleS` |
| Telegram (предположительно) | `@ThreepleS` или бот от этого аккаунта |
| Supabase | Проект `amhszfvqruzpydqyjlya` |
| OpenRouter | Аккаунт на openrouter.ai |

---

## 13. Next Steps (Если вы мигрируете)

1. **Фронтенд:** Можно развернуть на любом хостинге (Vercel, Netlify, свой VPS). Главное — поддерживать `index.html` + `app.js` + `style.css` + `sw.js`.
2. **Бэкенд:** Если отказываетесь от Supabase — нужно:
   - Поднять свой сервер (Python/FastAPI/Node.js).
   - Написать эндпоинты `/chat`, `/settings`, `/dialogs`, `/keyinfo` (аналоги Edge Functions).
   - Подключить базу данных (PostgreSQL).
3. **Telegram Bot:** Если меняете хостинг — переносите `main.py` + `.env` на новый сервер, обновляете вебхук в BotFather.
4. **Домены:** Сейчас используется GitHub Pages (`*.github.io`). Если нужен свой домен — настройте CNAME и DNS.

---

## 14. Quick Reference (Шпаргалка)

- **Последний деплой фронтенда:** `app_20260906_1726.js`
- **Версия в коде:** `v20260906_1726`
- **Основная ошибка, которую чинили:** `aiHubQueryAll(...).forEach is not a function` (починилено навсегда).
- **Главное правило:** Никаких CDN, никаких inline-скриптов, только локальные файлы из-за CSP.

---

*Если что-то неясно — ищите по ключевым словам в `app.js`. Там всё есть, хоть и в одном большом файле.*
