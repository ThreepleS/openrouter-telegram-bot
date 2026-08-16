"""Application entry point and startup orchestration."""

from __future__ import annotations

import asyncio
import logging
import sys

import src.database as db
from aiohttp import web
from aiogram.types import MenuButtonWebApp, WebAppInfo
from src.bot.client import create_bot, create_dispatcher
from src.bot.handlers import router
from src.config.env import Settings, get_settings
from src.web.app import create_web_app


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def validate_settings(settings: Settings) -> None:
    if not settings.bot_token:
        print("❌ Ошибка: BOT_TOKEN не указан в файле .env")
        print("Создай файл .env рядом с main.py (см. .env.example)")
        input("\nНажми Enter, чтобы закрыть окно...")
        sys.exit(1)

    if not settings.admin_id:
        print("❌ Ошибка: ADMIN_ID не указан в файле .env")
        input("\nНажми Enter, чтобы закрыть окно...")
        sys.exit(1)


async def set_menu_button(bot, web_app_url: str) -> None:
    # Версия в URL для сброса кэша Telegram WebView (initData всё равно
    # пробрасывается Telegram поверх любых query-параметров).
    try:
        from urllib.parse import urlparse, urlencode, urlunparse

        p = urlparse(web_app_url)
        q = urlencode({"v": "20260723_0400"})
        new_url = urlunparse((p.scheme, p.netloc, p.path, p.params, q, p.fragment))
    except Exception:
        new_url = web_app_url
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🚀 Открыть приложение",
                web_app=WebAppInfo(url=new_url),
            )
        )
        logging.info("Menu Button установлена на Mini App: %s", new_url)
    except Exception as exc:  # pragma: no cover - network dependent
        logging.warning("Не удалось установить Menu Button: %s", exc)


async def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    validate_settings(settings)
    configure_logging()

    await db.init_db()
    logging.info("База данных инициализирована")

    bot = create_bot(settings)
    dispatcher = create_dispatcher()
    dispatcher.include_router(router)

    # Menu Button ставим всегда, когда задан WEB_APP_URL (даже если локальный
    # WebApp-сервер не поднимается — фронт теперь на Supabase).
    if settings.web_app_url:
        await set_menu_button(bot, settings.web_app_url)
    else:
        logging.warning(
            "WEB_APP_URL не задан — Menu Button не установлена. "
            "Укажи публичный HTTPS-адрес Mini App в .env."
        )

    runner: web.AppRunner | None = None
    if settings.web_app_port > 0:
        web_app = create_web_app(settings)
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, settings.web_app_host, settings.web_app_port)
        await site.start()
        logging.info("Web/PWA запущен на http://%s:%s", settings.web_app_host, settings.web_app_port)

    logging.info("Бот запущен! Нажми Ctrl+C для остановки.")
    try:
        await dispatcher.start_polling(bot)
    finally:
        if runner is not None:
            await runner.cleanup()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nБот остановлен.")
    except Exception as error:
        print(f"\n[ОШИБКА] Не удалось запустить бота: {error}")
        if "api.telegram.org" in str(error):
            print(
                "Проверь интернет и доступ к Telegram. "
                "Если Telegram заблокирован — нужен VPN."
            )
        input("\nНажми Enter, чтобы закрыть окно...")
        raise


if __name__ == "__main__":
    main()
