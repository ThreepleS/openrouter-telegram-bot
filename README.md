# OpenRouter Telegram Bot

Личный Telegram-бот для общения с AI через OpenRouter и другие совместимые API. Бот хранит пользователей, историю сообщений, модели и настройки в SQLite или Supabase Postgres.

## Быстрый старт

### Вариант A: Локальный запуск

### 1. Установи Python

Нужен Python **3.10** или новее.

При установке Windows включи **Add Python to PATH**.

### 2. Создай виртуальное окружение

PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Установи зависимости

```powershell
pip install -r requirements.txt
```

### 4. Настрой `.env`

```powershell
Copy-Item .env.example .env
```

Заполни `.env`:

```env
BOT_TOKEN=
ADMIN_ID=
DB_PATH=bot.db
```

Опционально можно задать серверные API-ключи:

```env
OPENAI_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
HF_API_KEY=
```

Не коммить `.env` и реальные секреты в репозиторий.

### 5. Запусти бота

```powershell
python main.py
```

Или через ярлык:

```powershell
.\start.bat
```

### Вариант B: Облачный запуск (Railway)

Бот можно запустить в облаке, чтобы он работал 24/7 без твоего ПК.

### 1. Подготовь репозиторий

Запушь этот репозиторий на GitHub.

### 2. Создай проект на Railway

1. Зайди на [railway.app](https://railway.app) и создай новый проект
2. Выбери **Deploy from GitHub repo**
3. Укажи этот репозиторий
4. Railway автоматически определит Python и установит зависимости

### 3. Заполни переменные окружения

В разделе **Variables** добавь:

```env
BOT_TOKEN=твой_токен_от_BotFather
ADMIN_ID=твой_telegram_id
USE_SUPABASE_DB=0
DB_PATH=bot.db
```

Если используешь Supabase:

```env
USE_SUPABASE_DB=1
SUPABASE_URL=https://твой-проект.supabase.co
SUPABASE_SERVICE_ROLE_KEY=твой_service_role_key
```

### 4. Деплой

Railway автоматически запустит бота после первого деплоя. В логах увидишь:

```
Bot started as @твой_бот
```

### 5. Проверь

Открой Telegram, напиши `/start` боту — он должен ответить приветствием и кнопкой открытия приложения.

## Команды

| Команда | Описание |
|---|---|
| `/start` | Открывает приложение |
| `/settings` | Открывает настройки |
| `/admin` | Админ-панель, доступна только `ADMIN_ID` |

## Основные возможности

- Бот в Telegram — **только шлюз**: проверяет доступ и даёт кнопку открытия приложения. Вся переписка с AI идёт через Mini App / PWA.
- Общий бэкенд (AI + SQLite/Supabase) для бота и веб-приложения.
- Локальная SQLite-база или облачная Supabase Postgres.

## Структура проекта

```text
openrouter-telegram-bot/
├── main.py                  # совместимый entry point: python main.py
├── start.bat                # запуск через локальный venv
├── requirements.txt         # зависимости Python
├── .env.example             # шаблон переменных окружения
├── railway.toml             # конфигурация Railway
├── Procfile                 # процесс для PaaS
├── src/
│   ├── app.py               # запуск бота + веб/PWA, логирование, валидация
│   ├── config/              # env и константы
│   ├── ai/                  # OpenRouter/OpenAI/Gemini/Groq/HF клиент
│   ├── bot/                 # aiogram client, keyboards, handlers
│   ├── web/                 # PWA + Telegram Mini App (aiohttp, auth, markdown)
│   ├── database/            # SQLite/Supabase repository
│   └── utils/               # ошибки и текстовые helpers
└── docs/
    ├── architecture.md
    ├── env.md
    └── structure.md
```

## Web App / PWA (Telegram Mini App)

Тот же бэкенд (AI + SQLite/Supabase) отдаётся и через веб. На телефоне это устанавливается
как PWA-приложение, в браузере ПК открывается как сайт. Внутри Telegram бот
открывает тот же адрес как Mini App через Menu Button.

Переменные (`.env`):

```env
WEB_APP_HOST=0.0.0.0
WEB_APP_PORT=8080
WEB_APP_URL=https://your-https-domain   # публичный HTTPS для Mini App
WEB_APP_DEV=0                            # 1 = локальная отладка по ?dev_user=<id>
```

Эндпоинты: `POST /api/auth`, `POST /api/chat`. Markdown от AI рендерится в
HTML на бэкенде (`src/web/markdown.py`).

> Для Telegram Mini App нужен публичный **HTTPS**-адрес. Локально проверяй
> через `WEB_APP_DEV=1` и `http://localhost:8080/?dev_user=<твой_id>`.

## Где менять логику

- Конфигурация и переменные окружения: `src/config/`.
- Telegram-клиент и polling: `src/app.py`, `src/bot/client.py`.
- Клавиатуры: `src/bot/keyboards/`.
- Обработчики команд и сообщений: `src/bot/handlers/`.
- AI/API-запросы: `src/ai/`.
- База данных: `src/database/repository.py`.
- Ошибки API и форматирование текста: `src/utils/`.

## Документация

- `docs/architecture.md` — общий поток сообщения и архитектура.
- `docs/structure.md` — назначение папок и файлов.
- `docs/env.md` — переменные окружения и примеры.

## Частые проблемы

| Проблема | Решение |
|---|---|
| `BOT_TOKEN не указан` | Скопируй `.env.example` в `.env` и заполни `BOT_TOKEN` |
| `ADMIN_ID не указан` | Укажи свой Telegram ID в `ADMIN_ID` |
| Бот не отвечает в облаке | Проверь логи в Railway, убедись что `BOT_TOKEN` правильный |
| Ошибка Telegram API | Проверь интернет, VPN/прокси и доступ к `api.telegram.org` |
| Ошибка AI API | Проверь API-ключ, модель и баланс у провайдера |
