# Архитектура

Проект разделён по ответственностям: Telegram-бот, AI/API-клиент, SQLite-хранилище, конфигурация и утилиты находятся в разных модулях.

## Общая схема

```text
Telegram Update
    ↓
aiogram Dispatcher
    ↓
src/bot/handlers/
    ↓
src/database/repository.py
src/ai/client.py
src/bot/keyboards/
```

## Поток пользовательского сообщения

1. Пользователь отправляет текст или фото.
2. `aiogram` передаёт update в dispatcher.
3. Обработчик из `src/bot/handlers/chat.py` проверяет доступ через белый список.
4. Для текстового сообщения или фото формируется список сообщений для AI.
5. `src/ai/client.py` определяет провайдера модели:
   - `openrouter`
   - `openai`
   - `gemini`
   - `groq`
   - `huggingface`
6. Запрос отправляется в нужный API.
7. Ответ сохраняется в историю сообщений.
8. Статистика токенов записывается в `api_stats`.
9. Ответ отправляется пользователю с учётом режима статистики.

## Модули

### `src/config/`

Хранит настройки окружения и константы без секретов.

- `env.py` — загрузка `.env`, типизированные `Settings`.
- `constants.py` — URL API, провайдеры, лимиты, цены, режимы статистики.

### `src/bot/`

Telegram-часть приложения.

- `client.py` — создание `Bot` и `Dispatcher`.
- `session.py` — aiogram session с `trust_env=True` для системного прокси/VPN.
- `handlers/` — обработчики команд, callback query и FSM-состояний.
- `keyboards/` — inline/reply клавиатуры.

### `src/ai/`

AI/API-часть приложения.

- `client.py` — HTTP-запросы к AI-провайдерам, retry, таймауты, обработка ошибок.
- `models.py` — нормализация списков внешних моделей.
- `providers.py` — определение провайдера, нормализация model id, сборка payload, статистика токенов.

### `src/database/`

SQLite repository.

- `repository.py` — все операции с пользователями, белым списком, историей, моделями и статистикой.
- `__init__.py` — экспорт repository API.

### `src/utils/`

Общие утилиты.

- `errors.py` — расшифровка API-ошибок.
- `text.py` — разбиение длинных сообщений и сокращение ключей для UI.

## Запуск

Entry point:

```powershell
python main.py
```

`main.py` намеренно оставлен в корне как совместимый wrapper. Реальная логика запуска находится в `src/app.py`.

## Расширение

- Новые команды и callback-кнопки добавляй в `src/bot/handlers/`.
- Новые клавиатуры добавляй в `src/bot/keyboards/`.
- Новая AI-логика и провайдеры — в `src/ai/`.
- Новые таблицы и запросы — в `src/database/repository.py`.
- Новые переменные окружения — в `src/config/env.py` и `.env.example`.
