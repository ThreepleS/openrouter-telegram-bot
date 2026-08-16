# OpenRouter Telegram Bot

Telegram-бот для работы с AI через OpenRouter и другие совместимые API. Приложение открытое, без белого списка. Бот хранит пользователей, историю сообщений, модели и настройки в SQLite или Supabase Postgres.

## Быстрый старт

### Локальный запуск

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Деплой в облако (Railway)

Бот готов к деплою на Railway. Репозиторий уже на GitHub: https://github.com/ThreepleS/openrouter-telegram-bot

### 1. Создай проект на Railway

1. Зайди на [railway.app](https://railway.app) и создай новый проект
2. Выбери **Deploy from GitHub repo**
3. Укажи репозиторий `ThreepleS/openrouter-telegram-bot`

### 2. Заполни переменные окружения

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

### 3. Деплой

Railway автоматически запустит бота после первого деплоя. В логах увидишь:

```
Bot started as @твой_бот
```

### 4. Проверь

Открой Telegram, напиши `/start` боту — он должен ответить приветствием и кнопкой открытия приложения.

## Переменные окружения

| Переменная | Обязательно | Описание |
|---|---|---|
| `BOT_TOKEN` | Да | Токен бота от @BotFather |
| `ADMIN_ID` | Да | Telegram ID администратора |
| `USE_SUPABASE_DB` | Нет | `1` для Supabase, `0` для SQLite |
| `SUPABASE_URL` | Нет | URL Supabase проекта |
| `SUPABASE_SERVICE_ROLE_KEY` | Нет | Service role ключ Supabase |
| `DB_PATH` | Нет | Путь к SQLite файлу (по умолчанию `bot.db`) |

## Команды

| Команда | Описание |
|---|---|
| `/start` | Открывает приложение |
| `/settings` | Открывает настройки |
| `/admin` | Админ-панель, доступна только `ADMIN_ID` |

## Структура проекта

```text
openrouter-telegram-bot/
├── main.py                  # entry point
├── start.bat                # запуск через локальный venv
├── requirements.txt         # зависимости Python
├── .env.example             # шаблон переменных окружения
├── railway.toml             # конфигурация Railway
├── Procfile                 # процесс для PaaS
└── src/
    ├── app.py               # запуск бота + веб/PWA
    ├── config/              # env и константы
    ├── ai/                  # AI клиенты
    ├── bot/                 # aiogram handlers и keyboards
    ├── web/                 # PWA + Telegram Mini App
    ├── database/            # SQLite/Supabase repository
    └── utils/               # helpers
```

## Документация

- `docs/architecture.md` — архитектура
- `docs/env.md` — переменные окружения
- `docs/structure.md` — структура проекта
