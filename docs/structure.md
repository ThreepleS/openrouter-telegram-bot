# Структура проекта

## Корень проекта

```text
openrouter-telegram-bot/
├── main.py
├── start.bat
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── docs/
└── src/
```

## Основные файлы

| Файл | Назначение |
|---|---|
| `main.py` | Совместимый entry point для `python main.py`. Вызывает `src.app.main()`. |
| `start.bat` | Запуск через локальный `venv`, если он есть. |
| `requirements.txt` | Зависимости Python. |
| `.env.example` | Шаблон переменных окружения без секретов. |
| `.gitignore` | Исключает `.env`, `api.env`, `venv`, `__pycache__`, SQLite и временные файлы. |
| `README.md` | Быстрый старт и общее описание. |

## `src/`

Главный код приложения.

```text
src/
├── app.py
├── ai/
├── bot/
├── config/
├── database/
└── utils/
```

### `src/app.py`

Запуск приложения:

- загрузка настроек;
- проверка `BOT_TOKEN` и `ADMIN_ID`;
- инициализация SQLite;
- создание бота и dispatcher;
- подключение router;
- запуск polling.

### `src/config/`

```text
config/
├── __init__.py
├── constants.py
└── env.py
```

- `constants.py` — URL API, провайдеры, лимиты, цены, значения по умолчанию.
- `env.py` — загрузка `.env` и типизированные настройки.
- `__init__.py` — удобный экспорт общих констант.

### `src/ai/`

```text
ai/
├── __init__.py
├── client.py
├── models.py
└── providers.py
```

- `client.py` — HTTP-запросы к AI API, retry, таймауты, обработка ответов.
- `models.py` — нормализация списков моделей из API.
- `providers.py` — определение провайдера, нормализация ID модели, сборка messages/contents, форматирование статистики.

### `src/bot/`

```text
bot/
├── __init__.py
├── client.py
├── session.py
├── handlers/
└── keyboards/
```

- `client.py` — создание aiogram `Bot` и `Dispatcher`.
- `session.py` — кастомная сессия с `trust_env=True` для системного прокси/VPN.
- `handlers/` — обработчики Telegram messages/callbacks.
- `keyboards/` — клавиатуры.

#### `src/bot/handlers/`

```text
handlers/
├── __init__.py
├── admin.py
├── chat.py
├── common.py
├── context.py
├── keys.py
├── models.py
└── states.py
```

- `states.py` — FSM-состояния пользователя и админки.
- `common.py` — общий router, проверки доступа, `/start`, `/settings`, главное меню.
- `chat.py` — текстовые сообщения, фото, основной AI-request pipeline.
- `keys.py` — управление API-ключами.
- `models.py` — добавление, выбор, удаление, проверка и заметки моделей.
- `context.py` — system prompt, лимит контекста, статистика.
- `admin.py` — админ-панель, белый список, сбросы, статистика.

#### `src/bot/keyboards/`

```text
keyboards/
├── __init__.py
├── admin.py
├── common.py
├── keys.py
├── models.py
└── settings.py
```

- `common.py` — главная reply/inline клавиатура.
- `settings.py` — настройки, контекст, prompt, очистка чата.
- `models.py` — выбор моделей, провайдеры, внешние модели.
- `keys.py` — выбор API-провайдера и списка ключей.
- `admin.py` — админ-панель, доступ, сбросы.

### `src/database/`

```text
database/
├── __init__.py
└── repository.py
```

Все SQLite-операции находятся в `repository.py`:

- пользователи;
- белый список;
- временный доступ;
- история сообщений;
- пользовательские модели;
- статистика API-вызовов;
- сброс данных.

### `src/utils/`

```text
utils/
├── __init__.py
├── errors.py
└── text.py
```

- `errors.py` — понятные сообщения для API-ошибок.
- `text.py` — разбиение длинных сообщений и сокращение ключей для UI.

## `docs/`

```text
docs/
├── architecture.md
├── env.md
└── structure.md
```

- `architecture.md` — общая архитектура и поток сообщения.
- `structure.md` — этот файл, описание папок.
- `env.md` — переменные окружения.

## Куда добавлять новое

| Задача | Куда добавлять |
|---|---|
| Новая команда бота | `src/bot/handlers/common.py` или новый handler-файл |
| Новый callback | `src/bot/handlers/` по тематике |
| Новая клавиатура | `src/bot/keyboards/` |
| Новый AI-провайдер | `src/ai/providers.py`, `src/ai/client.py` |
| Новый запрос к SQLite | `src/database/repository.py` |
| Новая переменная окружения | `src/config/env.py`, `.env.example`, `docs/env.md` |
| Новая утилита | `src/utils/` |
