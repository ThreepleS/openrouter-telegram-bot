"""Shared bot handlers and main menu."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards import main_menu_keyboard
from src.config.env import get_settings

router = Router()


async def edit_callback_message_text(callback: CallbackQuery, *args, **kwargs):
    if callback.message is None:
        await callback.answer()
        return None

    async def edit_once():
        return await callback.message.edit_text(*args, **kwargs)

    for attempt in range(1, 3):
        try:
            return await edit_once()
        except TelegramRetryAfter as e:
            retry_after = getattr(e, "retry_after", 1)
            logging.warning("Telegram rate limit while editing callback message, waiting %s seconds", retry_after)
            await asyncio.sleep(retry_after)
        except TelegramNetworkError:
            if attempt < 2:
                await asyncio.sleep(1)
                continue
            raise

    try:
        return await callback.message.answer(*args, **kwargs)
    except TelegramRetryAfter as e:
        retry_after = getattr(e, "retry_after", 1)
        logging.warning("Telegram rate limit while sending fallback callback message, waiting %s seconds", retry_after)
        await asyncio.sleep(retry_after)
        return await callback.message.answer(*args, **kwargs)
    except TelegramNetworkError:
        await asyncio.sleep(1)
        return await callback.message.answer(*args, **kwargs)


def get_admin_id() -> int:
    return get_settings().admin_id


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    from src.bot.keyboards import open_app_keyboard, open_app_text

    await message.answer(open_app_text(), reply_markup=open_app_keyboard())


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    from src.bot.keyboards import open_app_keyboard, open_app_text

    await message.answer(open_app_text(), reply_markup=open_app_keyboard())


@router.callback_query(F.data == "settings")
async def callback_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_callback_message_text(
        callback,
        "⚙️ Настройки:",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:back")
async def callback_settings_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_callback_message_text(
        callback,
        "Главное меню 👇",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
