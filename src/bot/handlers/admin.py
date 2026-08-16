"""Admin handlers."""

import time

from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.handlers.states import AdminStates
from src.bot.keyboards import (
    admin_panel_keyboard,
    admin_reset_keyboard,
    cancel_to_admin_keyboard,
    confirm_admin_reset_keyboard,
    confirm_clear_chat_keyboard,
    settings_keyboard,
)
from src.database import (
    clear_messages,
    get_all_api_stats,
    reset_all_users_state,
    reset_user_state,
)
from .common import get_admin_id, router


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if message.from_user.id != get_admin_id():
        await message.answer("🚫 Эта команда только для администратора.")
        return

    await state.clear()
    await message.answer(
        "🛠 Админ-панель\n\n"
        "Здесь ты управляешь статистикой и сбросом данных.",
        reply_markup=admin_panel_keyboard(),
    )


@router.callback_query(F.data == "settings:clear_chat")
async def callback_clear_chat(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🗑 Удалить всю историю переписки?\nЭто действие нельзя отменить.",
        reply_markup=confirm_clear_chat_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:clear_confirm")
async def callback_clear_confirm(callback: CallbackQuery) -> None:
    await clear_messages(callback.from_user.id)
    await callback.message.edit_text(
        "✅ История чата очищена!",
        reply_markup=settings_keyboard(callback.from_user.id == get_admin_id()),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:admin")
async def callback_admin_via_settings(callback: CallbackQuery) -> None:
    if callback.from_user.id != get_admin_id():
        await callback.answer("🚫 Только для админа", show_alert=True)
        return

    await callback.message.edit_text(
        "🛠 Админ-панель\n\n"
        "Здесь ты управляешь статистикой и сбросом данных.",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def callback_admin_stats(callback: CallbackQuery) -> None:
    if callback.from_user.id != get_admin_id():
        await callback.answer("🚫 Только для админа", show_alert=True)
        return

    now = int(time.time())
    day_ago = now - 86400
    week_ago = now - 7 * 86400

    stats_24h = await get_all_api_stats(day_ago)
    stats_7d = await get_all_api_stats(week_ago)

    lines = ["📊 Статистика использования:\n"]

    if not stats_24h and not stats_7d:
        lines.append("Нет данных за выбранный период.")
    else:
        lines.append("<b>За 24 часа:</b>")
        if stats_24h:
            for entry in stats_24h:
                lines.append(f"• {entry['user_id']}: {entry['message_count']} сообщений, {entry['total_tokens']} токенов")
        else:
            lines.append("Нет запросов.")

        lines.append("\n<b>За 7 дней:</b>")
        if stats_7d:
            for entry in stats_7d:
                lines.append(f"• {entry['user_id']}: {entry['message_count']} сообщений, {entry['total_tokens']} токенов")
        else:
            lines.append("Нет запросов.")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_panel_keyboard(show_stats_button=False, back_callback="settings:admin"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:reset")
async def callback_admin_reset(callback: CallbackQuery) -> None:
    if callback.from_user.id != get_admin_id():
        await callback.answer("🚫 Только для админа", show_alert=True)
        return

    await callback.message.edit_text(
        "🧹 Сброс базы пользователей\n\n"
        "Выбери область сброса. Будут удалены настройки, история, статистика и пользовательские модели.",
        reply_markup=admin_reset_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:reset:self")
async def callback_admin_reset_self(callback: CallbackQuery) -> None:
    if callback.from_user.id != get_admin_id():
        return
    await reset_user_state(callback.from_user.id)
    await callback.message.edit_text("✅ Твои личные данные сброшены, но статистика администрирования сохранена.", reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:reset:self_confirm")
async def callback_admin_reset_self_confirm(callback: CallbackQuery) -> None:
    if callback.from_user.id != get_admin_id():
        await callback.answer("🚫 Только для админа", show_alert=True)
        return

    await reset_user_state(get_admin_id())
    await callback.message.edit_text(
        "✅ База администратора сброшена. Бот снова как при первом запуске.",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:reset:user")
async def callback_admin_reset_user(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id != get_admin_id():
        await callback.answer("🚫 Только для админа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_reset_user_identifier)
    await callback.message.edit_text(
        "🧹 Отправь Telegram ID пользователя для сброса.\n"
        "Telegram ID обычно начинается с 9 или 7 и намного больше 1000.",
        reply_markup=cancel_to_admin_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_reset_user_identifier)
async def admin_reset_user(message: Message, state: FSMContext) -> None:
    if message.from_user.id != get_admin_id():
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Отправь числовой Telegram ID, например: 123456789")
        return

    if user_id == get_admin_id():
        await message.answer("Для сброса себя используй кнопку «Сбросить меня» в админ-панели.")
        return

    await reset_user_state(user_id)
    await state.clear()
    await message.answer(
        f"✅ База пользователя {user_id} сброшена до первого запуска.",
        reply_markup=admin_panel_keyboard(),
    )


@router.callback_query(F.data == "admin:reset:all")
async def callback_admin_reset_all(callback: CallbackQuery) -> None:
    if callback.from_user.id != get_admin_id():
        await callback.answer("🚫 Только для админа", show_alert=True)
        return

    await callback.message.edit_text(
        "🧹 Сбросить базу всех пользователей?\n"
        "Это удалит настройки, историю, статистику и модели у всех пользователей.",
        reply_markup=confirm_admin_reset_keyboard("admin:reset:all_confirm"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:reset:all_confirm")
async def callback_admin_reset_all_confirm(callback: CallbackQuery) -> None:
    if callback.from_user.id != get_admin_id():
        await callback.answer("🚫 Только для админа", show_alert=True)
        return

    await reset_all_users_state()
    await callback.message.edit_text(
        "✅ База всех пользователей сброшена до первого запуска.",
        reply_markup=admin_panel_keyboard(),
    )
    await callback.answer()
