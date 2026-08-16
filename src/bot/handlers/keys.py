"""API key handlers."""

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.ai.providers import provider_env_key, provider_key_hint, provider_label
from src.bot.handlers.states import UserStates
from src.bot.keyboards import api_key_provider_keyboard, api_keys_keyboard, main_menu_reply_keyboard, settings_keyboard
from src.config import PROVIDER_LABELS
from src.database import create_user, get_user, update_api_key
from src.utils.text import shorten_key
from .common import get_admin_id, router


@router.callback_query(F.data.startswith("keys:provider:"))
async def callback_select_api_key_provider(callback: CallbackQuery, state: FSMContext) -> None:
    provider = callback.data.split(":", 2)[2]
    if provider not in PROVIDER_LABELS:
        await callback.answer("❌ Неизвестный провайдер", show_alert=True)
        return

    await state.update_data(api_key_provider=provider)
    await state.set_state(UserStates.waiting_for_new_api_key_provider)
    await callback.message.edit_text(
        f"Выбран API-ключ: {provider_label(provider)}\n\n"
        f"{provider_key_hint(provider)}\n\n"
        "⚠️ Ключ хранится только в твоей личной записи в базе бота.",
        reply_markup=api_key_provider_keyboard(),
    )
    await callback.answer()


@router.message(UserStates.waiting_for_new_api_key_provider)
async def process_first_api_key(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if text == "-":
        return

    if len(text) < 10:
        await message.answer("❌ Ключ слишком короткий. Отправь полный API-ключ.")
        return

    data = await state.get_data()
    provider = data.get("api_key_provider", "openrouter")
    if provider not in PROVIDER_LABELS:
        provider = "openrouter"

    user_id = message.from_user.id
    user = await get_user(user_id)

    if user is None:
        await create_user(user_id, text, provider)
    else:
        await update_api_key(user_id, text, provider)

    await state.clear()
    await message.answer(
        f"✅ API-ключ {provider_label(provider)} сохранён!\n\n"
        "Теперь можешь писать сообщения. Открой приложение по кнопке ниже 👇",
        reply_markup=main_menu_reply_keyboard(),
    )


@router.message(UserStates.waiting_for_new_api_key_provider)
async def process_new_api_key(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""

    if text == "-":
        user = await get_user(message.from_user.id)
        provider = user.get("api_key_provider", "openrouter") if user else "openrouter"
        await update_api_key(message.from_user.id, "", provider)
        await state.clear()
        await message.answer(
            "✅ Твой API-ключ удалён.",
            reply_markup=settings_keyboard(message.from_user.id == get_admin_id()),
        )
        return

    if len(text) < 10:
        await message.answer("❌ Ключ слишком короткий. Попробуй ещё раз.")
        return

    data = await state.get_data()
    provider = data.get("api_key_provider", "openrouter")
    if provider not in PROVIDER_LABELS:
        provider = "openrouter"

    await update_api_key(message.from_user.id, text, provider)
    await state.clear()
    await message.answer(
        f"✅ API-ключ {provider_label(provider)} обновлён!",
        reply_markup=settings_keyboard(message.from_user.id == get_admin_id()),
    )


@router.callback_query(F.data == "settings:keys")
async def callback_keys(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    user_key = user.get("api_key", "") if user else ""
    user_key_provider = user.get("api_key_provider", "openrouter") if user else "openrouter"

    available_keys = []
    for provider in ["openai", "gemini", "groq", "huggingface", "venice"]:
        env_key = provider_env_key(provider)
        if env_key:
            available_keys.append({"name": f"{provider_label(provider)} из .env", "key": env_key, "provider": provider})
    if user_key:
        available_keys.append({"name": f"Твой {provider_label(user_key_provider)}", "key": user_key, "provider": user_key_provider})
    if user:
        for provider in ["openrouter", "openai", "gemini", "groq", "huggingface", "venice"]:
            col = f"api_key_{provider}"
            val = user.get(col, "")
            if val and val != user_key:
                available_keys.append({"name": f"Твой {provider_label(provider)}", "key": val, "provider": provider})

    lines = ["🔑 Доступные ключи:\n"]
    for i, item in enumerate(available_keys):
        lines.append(f"{i + 1}. [{item['name']}] {shorten_key(item['key'])}")

    if not available_keys:
        lines.append("(ни одного ключа не задано)")

    lines.append("\nОтправь номер (1, 2, 3...) для выбора ключа из списка.")
    lines.append("Отправь '-' для удаления твоего ключа.")
    lines.append("Или нажми «Добавить / заменить ключ» и выбери тип ключа.")

    await state.set_state(UserStates.waiting_for_new_api_key_provider)
    await state.update_data(api_key_provider="openrouter")
    text = "\n".join(lines)
    reply_markup = api_keys_keyboard([item['key'] for item in available_keys])
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.answer()
        return
    await callback.answer()


@router.callback_query(F.data.startswith("keys:select:"))
async def callback_keys_select(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    user_key = user.get("api_key", "") if user else ""
    user_key_provider = user.get("api_key_provider", "openrouter") if user else "openrouter"

    available_keys = []
    for provider in ["openai", "gemini", "groq", "huggingface", "venice"]:
        env_key = provider_env_key(provider)
        if env_key:
            available_keys.append({"name": f"{provider_label(provider)} из .env", "key": env_key, "provider": provider})
    if user_key:
        available_keys.append({"name": f"Твой {provider_label(user_key_provider)}", "key": user_key, "provider": user_key_provider})

    try:
        idx = int(callback.data.split(":", 2)[2]) - 1
    except ValueError:
        await callback.answer("❌ Некорректный номер ключа", show_alert=True)
        return

    if idx < 0 or idx >= len(available_keys):
        await callback.answer("❌ Ключ с таким номером не найден", show_alert=True)
        return

    item = available_keys[idx]
    provider = item["provider"]

    await update_api_key(callback.from_user.id, item["key"], provider, set_personal_key=False)
    await state.clear()
    await callback.message.edit_text(
        f"✅ Выбран ключ: {item['name']}",
        reply_markup=settings_keyboard(callback.from_user.id == get_admin_id()),
    )
    await callback.answer(f"Выбран {item['name']}")


@router.callback_query(F.data == "keys:add")
async def callback_keys_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(UserStates.waiting_for_api_key_provider)
    await callback.message.edit_text(
        "Выбери, какой API-ключ хочешь добавить или заменить:",
        reply_markup=api_key_provider_keyboard(),
    )
    await callback.answer()
