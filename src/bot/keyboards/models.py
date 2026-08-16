"""Model selection keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.ai.providers import model_page_url, provider_label


def models_keyboard(models_list: list[dict], current_model_id: str, action_prefix: str = "model:", show_check_button: bool = False, show_note_button: bool = False, back_callback: str = "settings") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not models_list:
        builder.row(InlineKeyboardButton(text="(список пуст) Добавь модель ➕", callback_data="models:add"))
    else:
        for model in models_list:
            short = model.get("short_id") or model.get("model_id")
            name = model.get("display_name") or model.get("model_id")
            meta = model.get("meta") or ""
            mark = "✅ " if model.get("model_id") == current_model_id else ""
            label = f"{mark}{name}"
            if meta:
                label = f"{label} ({meta})"
            builder.row(
                InlineKeyboardButton(text=label, callback_data=f"{action_prefix}{short}"),
            )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить модель", callback_data="models:add"),
        InlineKeyboardButton(text="➖ Удалить модель", callback_data="models:remove"),
    )
    if show_check_button:
        builder.row(
            InlineKeyboardButton(text="🔎 Проверить модели", callback_data="models:check")
        )
    builder.row(
        InlineKeyboardButton(text="📘 Инструкция", callback_data="models:help")
    )
    if show_note_button and current_model_id:
        builder.row(
            InlineKeyboardButton(text="✏️ Пометка выбранной модели", callback_data="models:note")
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад в настройки", callback_data=back_callback))
    return builder.as_markup()


def model_provider_keyboard() -> InlineKeyboardMarkup:
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
        builder.row(InlineKeyboardButton(text=label, callback_data=f"models:provider:{provider}"))
    builder.row(InlineKeyboardButton(text="⭐ Избранное", callback_data="models:my:all"))
    builder.row(InlineKeyboardButton(text="◀️ Назад в настройки", callback_data="settings"))
    return builder.as_markup()


def model_provider_menu_keyboard(provider: str, show_list_button: bool = True, show_my_models_button: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if provider != "gemini":
        builder.row(InlineKeyboardButton(text="✍️ Ручной ввод", callback_data=f"models:manual:{provider}"))
    if show_list_button:
        builder.row(InlineKeyboardButton(text="➕ Добавить из списка", callback_data=f"models:list:{provider}"))
    if show_my_models_button:
        builder.row(InlineKeyboardButton(text="📦 Уже имеющиеся", callback_data=f"models:my:{provider}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к провайдерам", callback_data="models:providers"))
    return builder.as_markup()


def provider_list_type_keyboard(provider: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Показать бесплатные модели", callback_data=f"models:list:{provider}:all"))
    builder.row(InlineKeyboardButton(text="🔍 Проверить доступные (30-60с)", callback_data=f"models:list:{provider}:checked"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"models:provider:{provider}"))
    return builder.as_markup()


def gemini_list_type_keyboard() -> InlineKeyboardMarkup:
    return provider_list_type_keyboard("gemini")


def external_models_keyboard(provider: str, models: list[dict], back_callback: str, page: int = 0, page_size: int = 50) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not models:
        builder.row(InlineKeyboardButton(text="(список пуст)", callback_data=back_callback))
    else:
        start = page * page_size
        end = start + page_size
        page_models = models[start:end]
        for model in page_models:
            meta = model.get("meta") or ""
            label = f"{model.get('name') or model.get('id')}"
            if meta:
                label = f"{label} | {meta}"
            builder.row(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"model:external:{provider}:{model['hash']}",
                )
            )
        total_pages = (len(models) + page_size - 1) // page_size
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"models:page:{provider}:{page-1}"))
            nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(text="След. ➡️", callback_data=f"models:page:{provider}:{page+1}"))
            builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback))
    return builder.as_markup()


def external_model_detail_keyboard(provider: str, model_hash: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить себе", callback_data=f"model:add_external:{provider}:{model_hash}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"models:list:{provider}"))
    return builder.as_markup()


def format_external_model(provider: str, model: dict) -> str:
    lines = [
        f"🔎 Модель: {model['name']}",
        f"ID: {model['id']}",
        f"Страница: {model_page_url(provider, model['id'])}",
    ]
    if model.get("description"):
        lines.append(f"Описание: {model['description']}")
    if model.get("meta"):
        lines.append(f"Мета: {model['meta']}")
    return "\n".join(lines)
