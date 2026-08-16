"""Main reply and inline keyboards.

Бот теперь только открывает Mini App — настройки и очистка истории
переехали в само приложение, поэтому в чате оставляем только кнопку входа.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .web_app import web_app_url


def main_menu_reply_keyboard():
    url = web_app_url()
    if not url:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=url))]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    url = web_app_url()
    builder = InlineKeyboardBuilder()
    if url:
        builder.button(text="🚀 Открыть приложение", web_app=WebAppInfo(url=url))
    return builder.as_markup()
