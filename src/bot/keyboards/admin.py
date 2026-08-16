"""Admin keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def access_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="♾️ Вечный доступ", callback_data="admin:add:permanent"),
    )
    builder.row(
        InlineKeyboardButton(text="⏳ Временный доступ", callback_data="admin:add:temporary"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Отмена", callback_data="settings:admin"),
    )
    return builder.as_markup()


def admin_panel_keyboard(show_note_button: bool = False, show_list_button: bool = True, show_stats_button: bool = True, back_callback: str = "settings:back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="admin:add")
    )
    builder.row(
        InlineKeyboardButton(text="➖ Удалить пользователя", callback_data="admin:remove")
    )
    if show_list_button:
        builder.row(
            InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin:list")
        )
    if show_note_button:
        builder.row(
            InlineKeyboardButton(text="✏️ Сделать пометку", callback_data="admin:note")
        )
    builder.row(
        InlineKeyboardButton(text="🧹 Сброс БД пользователей", callback_data="admin:reset")
    )
    if show_stats_button:
        builder.row(
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")
        )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)
    )
    return builder.as_markup()


def admin_reset_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🧹 Сбросить меня", callback_data="admin:reset:self")
    )
    builder.row(
        InlineKeyboardButton(text="🧹 Сбросить конкретного пользователя", callback_data="admin:reset:user")
    )
    builder.row(
        InlineKeyboardButton(text="🧹 Сбросить всех пользователей", callback_data="admin:reset:all")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="settings:admin")
    )
    return builder.as_markup()


def confirm_admin_reset_keyboard(confirm_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, сбросить", callback_data=confirm_callback),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:reset"),
    )
    return builder.as_markup()
