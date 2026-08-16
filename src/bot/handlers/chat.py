"""Telegram gateway handlers.

The bot no longer holds AI conversations inside Telegram. Its only job here is
to point the user to the Mini App / PWA. The actual chat runs in the web app
(``src/web``), which reuses the same AI/database layer.
"""

from __future__ import annotations

from aiogram import F
from aiogram.types import Message

from src.bot.keyboards import open_app_keyboard, open_app_text
from .common import router


@router.message(F.text)
async def handle_chat_message(message: Message) -> None:
    await message.answer(open_app_text(), reply_markup=open_app_keyboard())


@router.message(F.photo | F.sticker | F.animation)
async def handle_visual_message(message: Message) -> None:
    await message.answer(open_app_text(), reply_markup=open_app_keyboard())


@router.message()
async def handle_any_message(message: Message) -> None:
    await message.answer(open_app_text(), reply_markup=open_app_keyboard())
