"""Settings-related keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import CONTEXT_LIMIT_OPTIONS, StatsDisplay


def stats_display_cycle(current: str) -> str:
    options = [StatsDisplay.DISABLED, StatsDisplay.COMPACT, StatsDisplay.FULL]
    try:
        idx = options.index(current)
    except ValueError:
        idx = 0
    next_idx = (idx + 1) % len(options)
    return options[next_idx]


def stats_display_label(value: str) -> str:
    mapping = {
        StatsDisplay.DISABLED: "📊 Выкл",
        StatsDisplay.COMPACT: "📊 Компакт",
        StatsDisplay.FULL: "📊 Полная",
    }
    return mapping.get(value, value)


def settings_keyboard(is_admin: bool = False, stats_display: str = StatsDisplay.FULL) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🤖 Выбор модели", callback_data="settings:models")
    )
    builder.row(
        InlineKeyboardButton(text="📝 Изменить System Prompt", callback_data="settings:prompt")
    )
    builder.row(
        InlineKeyboardButton(text="🧠 Лимит контекста", callback_data="settings:context")
    )
    builder.row(
        InlineKeyboardButton(text=f"{stats_display_label(stats_display)} статистика", callback_data="settings:stats"),
        InlineKeyboardButton(text="🔑 Мои ключи", callback_data="settings:keys"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Очистить чат", callback_data="settings:clear_chat")
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="🛠 Админ-панель", callback_data="settings:admin")
        )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="settings:back")
    )
    return builder.as_markup()


def cancel_to_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Отмена", callback_data="settings")
    )
    return builder.as_markup()


def cancel_to_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Отмена", callback_data="settings:admin")
    )
    return builder.as_markup()


def context_limit_keyboard(current_limit: int, custom_requested: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for limit in CONTEXT_LIMIT_OPTIONS:
        mark = "✅ " if limit == current_limit else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{mark}{limit} сообщений",
                callback_data=f"context:{limit}",
            )
        )
    mark = "✅ " if custom_requested else ""
    builder.row(
        InlineKeyboardButton(
            text=f"{mark}Свой лимит",
            callback_data="context:custom",
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад в настройки", callback_data="settings")
    )
    return builder.as_markup()


def confirm_clear_chat_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, очистить", callback_data="settings:clear_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="settings"),
    )
    return builder.as_markup()
