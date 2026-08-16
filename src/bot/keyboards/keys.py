"""API key keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.ai.providers import provider_label
from src.utils.text import shorten_key


def api_keys_keyboard(available_keys: list[str], selected_index: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, key in enumerate(available_keys):
        label = f"🔑 {idx + 1}. {shorten_key(key)}"
        if idx == selected_index:
            label = "✅ " + label
        builder.row(InlineKeyboardButton(text=label, callback_data=f"keys:select:{idx}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить / заменить ключ", callback_data="keys:add"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="settings"))
    return builder.as_markup()


def api_key_provider_keyboard() -> InlineKeyboardMarkup:
    providers = [
        ("OpenRouter", "openrouter"),
        ("Venice AI", "venice"),
        # ("OpenAI", "openai"),  # отключено: провайдер пока не поддерживается в UI
        ("Gemini", "gemini"),
        # ("Groq", "groq"),  # отключено: провайдер пока не поддерживается в UI
        # ("HuggingFace", "huggingface"),  # отключено: провайдер пока не поддерживается в UI
    ]
    builder = InlineKeyboardBuilder()
    for label, provider in providers:
        builder.row(InlineKeyboardButton(text=label, callback_data=f"keys:provider:{provider}"))
    builder.row(InlineKeyboardButton(text="◀️ Отмена", callback_data="settings"))
    return builder.as_markup()
