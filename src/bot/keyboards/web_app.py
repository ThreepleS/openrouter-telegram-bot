"""Keyboard/helpers for pointing Telegram users to the Mini App / PWA.

The bot no longer chats inside Telegram — it only checks access and offers a
button that opens the web app. The public HTTPS URL comes from ``WEB_APP_URL``.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config.env import get_settings


def web_app_url() -> str:
    return (get_settings().web_app_url or "").strip()


def open_app_text() -> str:
    url = web_app_url()
    if url:
        return (
            "👋 Привет! Общение с AI теперь в приложении.\n\n"
            "Открой его по кнопке ниже или по ссылке:\n"
            f"{url}"
        )
    return (
        "👋 Привет! Общение с AI теперь в приложении.\n\n"
        "⚠️ WEB_APP_URL не задан — укажи публичный HTTPS-адрес приложения в .env, "
        "чтобы появилась кнопка открытия."
    )


def open_app_keyboard() -> InlineKeyboardMarkup | None:
    url = web_app_url()
    if not url:
        return None
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Открыть приложение", web_app=WebAppInfo(url=url))
    return builder.as_markup()
