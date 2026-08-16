"""Model management handlers."""

import aiohttp
import logging

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.ai.client import fetch_provider_models, fetch_provider_model_detail, ping_model
from src.ai.providers import (
    build_user_provider_keys,
    detect_provider,
    ensure_model_id_for_provider,
    model_id_for_provider,
    provider_label,
)
from src.bot.handlers.states import UserStates
from aiogram.utils.markdown import markdown_decoration
from src.bot.keyboards import (
    cancel_to_settings_keyboard,
    external_model_detail_keyboard,
    external_models_keyboard,
    format_external_model,
    gemini_list_type_keyboard,
    model_provider_keyboard,
    model_provider_menu_keyboard,
    models_keyboard,
    provider_list_type_keyboard,
)
from src.config import PROVIDER_LABELS, PROVIDER_LIST_ENABLED
from src.database import (
    add_user_model,
    create_user,
    get_user,
    get_user_favorites,
    get_user_model_by_short,
    get_user_models,
    get_user_models_by_provider,
    remove_user_model_by_short,
    update_selected_model,
    update_user_model_meta,
)
from .common import edit_callback_message_text, router

EXTERNAL_MODELS_STATE_PREFIX = "external_models_"


async def store_external_models(state: FSMContext, provider: str, models: list[dict]) -> None:
    await state.update_data(**{f"{EXTERNAL_MODELS_STATE_PREFIX}{provider}": models})


async def get_external_models(state: FSMContext, provider: str) -> list[dict]:
    data = await state.get_data()
    return data.get(f"{EXTERNAL_MODELS_STATE_PREFIX}{provider}", []) or []


def get_external_model_by_hash(models: list[dict], model_hash: str) -> dict | None:
    for model in models:
        if model.get("hash") == model_hash:
            return model
    return None


@router.callback_query(F.data == "models:providers")
async def callback_models_providers(callback: CallbackQuery) -> None:
    await edit_callback_message_text(
        callback,
        "Выбери провайдера модели:",
        reply_markup=model_provider_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("models:provider:"))
async def callback_models_provider(callback: CallbackQuery, state: FSMContext) -> None:
    provider = callback.data.split(":", 2)[2]
    if provider not in PROVIDER_LABELS:
        await callback.answer("❌ Неизвестный провайдер", show_alert=True)
        return

    await state.update_data(model_provider=provider)
    show_list = PROVIDER_LIST_ENABLED.get(provider, True)
    await edit_callback_message_text(
        callback,
        f"Провайдер: {provider_label(provider)}\n\n"
        f"Выбери способ добавления модели.",
        reply_markup=model_provider_menu_keyboard(provider, show_list_button=show_list),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("models:manual:"))
async def callback_models_manual(callback: CallbackQuery, state: FSMContext) -> None:
    provider = callback.data.split(":", 2)[2]
    if provider not in PROVIDER_LABELS:
        await callback.answer("❌ Неизвестный провайдер", show_alert=True)
        return

    await state.update_data(model_provider=provider)
    await state.set_state(UserStates.waiting_for_new_model_provider)
    await edit_callback_message_text(
        callback,
        f"Отправь модель для {provider_label(provider)} в формате:\n"
        "model_id | Display Name | краткая характеристика\n"
        f"Имя модели автоматически получит префикс «{provider_label(provider)} ·».\n\n"
        f"Пример OpenRouter: openai/gpt-4o | GPT-4o | быстрый универсальный чат\n"
        f"Пример Gemini: gemini-2.5-flash | Gemini Flash | быстрая мультимодальная модель\n"
        f"Пример HuggingFace: meta-llama/Llama-3.1-8B-Instruct | Llama 3.1 8B | текстовая модель",
        reply_markup=cancel_to_settings_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("models:my:"))
async def callback_models_my(callback: CallbackQuery, state: FSMContext) -> None:
    provider = callback.data.split(":", 2)[2]
    user_id = callback.from_user.id
    user = await get_user(user_id)
    selected = user.get("selected_model", "") if user else ""

    if provider == "all":
        user_models = await get_user_favorites(user_id)
        text = "⭐ Избранное:\n\n"
        if not user_models:
            text += "У тебя нет добавленных моделей."

        await edit_callback_message_text(
        callback,
            text,
            reply_markup=models_keyboard(user_models, selected, show_check_button=True, show_note_button=True, back_callback="models:providers"),
        )
        await callback.answer()
        return

    if provider not in PROVIDER_LABELS:
        await callback.answer("❌ Неизвестный провайдер", show_alert=True)
        return

    await state.update_data(current_provider=provider)
    user_models = await get_user_models_by_provider(user_id, provider)

    text = f"📦 Модели {provider_label(provider)}:\n\n"
    if not user_models:
        text += "У тебя нет добавленных моделей этого провайдера."

    await edit_callback_message_text(
        callback,
        text,
        reply_markup=models_keyboard(user_models, selected, show_check_button=True, show_note_button=True, back_callback=f"models:provider:{provider}"),
    )
    await callback.answer()


@router.callback_query(F.data == "models:list:gemini")
@router.callback_query(F.data == "models:list:openrouter")
async def callback_models_list_menu(callback: CallbackQuery) -> None:
    provider = callback.data.split(":", 2)[2]
    await edit_callback_message_text(
        callback,
        "Выбери тип списка моделей:",
        reply_markup=provider_list_type_keyboard(provider),
    )


@router.callback_query(F.data.startswith("models:list:gemini:"))
@router.callback_query(F.data.startswith("models:list:openrouter:"))
async def callback_models_list_action(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    provider = parts[2]
    action = parts[3] if len(parts) > 3 else ""
    if action not in {"all", "checked"}:
        await callback.answer("❌ Неверный тип списка", show_alert=True)
        return
    check_availability = (action == "checked") or provider == "openrouter"
    await _fetch_list_models(callback, state, provider, check_availability=check_availability, show_free_only=True)


async def _fetch_list_models(callback: CallbackQuery, state: FSMContext, provider: str, check_availability: bool, show_free_only: bool = False) -> None:
    user = await get_user(callback.from_user.id)
    if user is None or not user.get("api_key"):
        await callback.answer("Сначала укажи API-ключ", show_alert=True)
        return

    if check_availability:
        await edit_callback_message_text(
            callback,
            f"🔍 Проверяю доступные БЕСПЛАТНЫЕ модели {provider_label(provider)}...\n"
            "(бот не завис, пингуем сервера - на это требуется время, подожди немного)",
            reply_markup=external_models_keyboard(provider, [], f"models:list:{provider}"),
        )

    models, error = await fetch_provider_models(
        provider,
        user["api_key"],
        user.get("api_key_provider", "openrouter"),
        build_user_provider_keys(user),
        check_availability=check_availability,
        show_free_only=show_free_only,
    )
    if error:
        await edit_callback_message_text(
            callback,
            f"⚠️ {error}\n\n"
            f"Можешь добавить модель вручную.",
            reply_markup=model_provider_menu_keyboard(provider, show_list_button=True),
        )
        return

    await store_external_models(state, provider, models)
    await state.update_data(external_models_page=0)
    if check_availability:
        text = f"📋 Доступные БЕСПЛАТНЫЕ модели {provider_label(provider)}:\n\n"
    else:
        text = f"📋 Бесплатные модели {provider_label(provider)}:\n\n"
    if not models:
        text += "Список пуст. Возможно, API-ключ недействителен или модели недоступны."
    else:
        text += f"Найдено {len(models)} моделей. Выбери модель (показаны 50 на странице):"
    await edit_callback_message_text(
        callback,
        text,
        reply_markup=external_models_keyboard(provider, models, f"models:list:{provider}", page=0),
    )


@router.callback_query(F.data.startswith("models:page:"))
async def callback_models_page(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("❌ Неверный запрос", show_alert=True)
        return
    provider = parts[2]
    try:
        page = int(parts[3])
    except ValueError:
        await callback.answer("❌ Неверный номер страницы", show_alert=True)
        return

    models = await get_external_models(state, provider)
    if not models:
        await callback.answer("❌ Список моделей устарел. Открой список заново.", show_alert=True)
        return

    total_pages = (len(models) + 49) // 50
    if page < 0 or page >= total_pages:
        await callback.answer("❌ Страница не найдена", show_alert=True)
        return

    await state.update_data(external_models_page=page)
    text = f"📋 Модели {provider_label(provider)}:\n\nВыбери модель (страница {page+1}/{total_pages}):"
    await edit_callback_message_text(
        callback,
        text,
        reply_markup=external_models_keyboard(provider, models, f"models:list:{provider}", page=page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("model:external:"))
async def callback_external_model(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("❌ Неверная ссылка на модель", show_alert=True)
        return
    provider = parts[2]
    model_hash = parts[3]

    models = await get_external_models(state, provider)
    model = get_external_model_by_hash(models, model_hash)
    if model is None:
        await callback.answer("❌ Список моделей устарел. Открой список заново.", show_alert=True)
        return

    await edit_callback_message_text(
        callback,
        format_external_model(provider, model),
        reply_markup=external_model_detail_keyboard(provider, model_hash),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("model:add_external:"))
async def callback_add_external_model(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) < 4:
        await callback.answer("❌ Неверная ссылка на модель", show_alert=True)
        return
    provider = parts[2]
    model_hash = parts[3]

    models = await get_external_models(state, provider)
    model = get_external_model_by_hash(models, model_hash)
    if model is None:
        await callback.answer("❌ Список моделей устарел. Открой список заново.", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await get_user(user_id)
    if user is None:
        await create_user(user_id, "")

    model_id = model_id_for_provider(provider, model["id"])
    display_name = model["name"]
    provider_label_text = provider_label(provider)
    if provider == "venice":
        lower_name = display_name.lower()
        if lower_name.startswith(f"{provider_label_text.lower()} · venice:"):
            display_name = provider_label_text + " · " + display_name[len(f"{provider_label_text} · venice:"):]
        elif lower_name.startswith("venice:"):
            display_name = display_name[7:]
    meta = model.get("meta") or model.get("description") or None
    if provider == "openrouter":
        user_api_key = user.get("api_key", "") or ""
        user_key_provider = user.get("api_key_provider", "openrouter")
        if user_api_key and user_key_provider == "openrouter":
            fetched, _ = await fetch_provider_model_detail(
                "openrouter", model_id, user_api_key, "openrouter", build_user_provider_keys(user)
            )
            if fetched:
                api_meta = fetched.get("meta")
                if api_meta:
                    filtered_meta = api_meta.replace("⚠️ За проверку платных моделей взымается плата, модель не проверялась!", "").strip(" |")
                    meta = filtered_meta if filtered_meta else None
                api_name = fetched.get("name")
                if api_name and display_name == model_id:
                    display_name = api_name

    await add_user_model(user_id, model_id, display_name, meta)
    await state.update_data(current_provider=provider)

    user_models = await get_user_models(user_id)
    user = await get_user(user_id)
    selected = user.get("selected_model", "") if user else ""
    await edit_callback_message_text(
        callback,
        f"✅ Модель добавлена: {display_name}",
        reply_markup=models_keyboard(user_models, selected, show_check_button=True, show_note_button=True, back_callback=f"models:my:{provider}"),
    )
    await callback.answer("Модель добавлена")


@router.callback_query(F.data == "models:add")
async def callback_models_add(callback: CallbackQuery, state: FSMContext) -> None:
    await edit_callback_message_text(
        callback,
        "Выбери провайдера модели:",
        reply_markup=model_provider_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:models")
async def callback_models(callback: CallbackQuery) -> None:
    await edit_callback_message_text(
        callback,
        "Выбери провайдера модели:",
        reply_markup=model_provider_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "models:help")
async def callback_models_help(callback: CallbackQuery, state: FSMContext) -> None:
    text = (
        "📘 Инструкция по моделям:\n\n"
        "1. Нажми «Выбор модель» и выбери провайдера: OpenRouter или Gemini.\n"
        "2. Выбери «Ручной ввод» или «Добавить из списка».\n"
        "3. Для OpenRouter ручной ввод подтягивает цену и возможности модели с сайта.\n"
        "4. При ручном вводе отправь: <code>model_id | Имя | Краткое описание</code>.\n"
        "5. После добавления модель появится в списке. Выбери её, чтобы сделать активной.\n"
        "6. Заметка поможет запомнить, для чего эта модель.\n\n"

        "Если модель не работает, проверь выбранный API-ключ, префикс модели и точный идентификатор."
    )

    await edit_callback_message_text(
        callback, text, parse_mode="HTML", reply_markup=models_keyboard([], "", show_check_button=True, show_note_button=False))
    await callback.answer()


@router.callback_query(F.data == "models:note")
async def callback_models_note(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    if user is None or not user.get("selected_model"):
        await callback.answer("❗ Сначала выбери модель", show_alert=True)
        return

    await state.set_state(UserStates.waiting_for_model_note)
    await edit_callback_message_text(
        callback,
        "✏️ Отправь заметку для выбранной модели одним сообщением.\n"
        "Эта заметка будет отображаться в списке моделей в скобках.",
        reply_markup=cancel_to_settings_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "models:check")
async def callback_models_check(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    if user is None or not user.get("api_key"):
        await callback.answer("Сначала укажи API-ключ", show_alert=True)
        return

    data = await state.get_data()
    provider = data.get("current_provider")
    if provider and provider in PROVIDER_LABELS:
        user_models = await get_user_models_by_provider(callback.from_user.id, provider)
    else:
        user_models = await get_user_models(callback.from_user.id)

    if not user_models:
        await callback.answer("У тебя нет добавленных моделей", show_alert=True)
        return

    await callback.answer("Проверяю модели...")

    statuses = []
    for model in user_models:
        try:
            model_provider = detect_provider(model["model_id"])
            status, info = await ping_model(
                user["api_key"],
                model["model_id"],
                user["system_prompt"],
                model_provider,
                build_user_provider_keys(user),
            )
            statuses.append(f"• {model['display_name']}: {info}")
        except aiohttp.ClientError as exc:
            logging.error("aiohttp error checking model %s: %s", model["model_id"], exc)
            statuses.append(f"• {model['display_name']}: ❌ Ошибка подключения")
        except Exception as exc:
            logging.error("Error checking model %s", model["model_id"])
            statuses.append(f"• {model['display_name']}: ❌ Ошибка при проверке")

    text = "🔎 Проверка моделей:\n" + "\n".join(statuses)
    back_cb = f"models:my:{provider}" if provider and provider in PROVIDER_LABELS else "models:my:all"
    try:
        await edit_callback_message_text(
            callback,
            text,
            reply_markup=models_keyboard(user_models, user.get("selected_model", ""), show_check_button=True, show_note_button=True, back_callback=back_cb),
        )
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("model:") & ~F.data.startswith("model:remove:"))
async def callback_select_model(callback: CallbackQuery, state: FSMContext) -> None:
    short_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    model = await get_user_model_by_short(user_id, short_id)

    if model is None:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return

    user = await get_user(user_id)
    if user is None:
        await create_user(user_id, "")

    await update_selected_model(user_id, model['model_id'])

    model_provider = detect_provider(model['model_id'])
    if model_provider in PROVIDER_LABELS:
        await state.update_data(current_provider=model_provider)
        back_callback = f"models:my:{model_provider}"
        user_models = await get_user_models_by_provider(user_id, model_provider)
    else:
        back_callback = "models:my:all"
        user_models = await get_user_models(user_id)

    meta_text = markdown_decoration.quote(model.get('meta') or '(без описания)')
    await edit_callback_message_text(
        callback,
        f"✅ Модель активирована: *{markdown_decoration.quote(model['display_name'])}*\n\n"
        f"📖 Кратко: {meta_text}",
        reply_markup=models_keyboard(user_models, model['model_id'], show_check_button=True, show_note_button=True, back_callback=back_callback),
        parse_mode="Markdown",
    )
    await callback.answer(f"Выбрана: {model['display_name']}")


@router.callback_query(F.data == "models:remove")
async def callback_models_remove(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    provider = data.get("current_provider")
    if provider and provider in PROVIDER_LABELS:
        user_models = await get_user_models_by_provider(callback.from_user.id, provider)
    else:
        user_models = await get_user_models(callback.from_user.id)

    if not user_models:
        await callback.answer("У тебя нет добавленных моделей")
        return

    back_cb = f"models:my:{provider}" if provider and provider in PROVIDER_LABELS else "models:my:all"
    await edit_callback_message_text(
        callback,
        "Выбери модель для удаления:",
        reply_markup=models_keyboard(user_models, "", action_prefix="model:remove:", back_callback=back_cb),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("model:remove:"))
async def callback_remove_model(callback: CallbackQuery, state: FSMContext) -> None:
    short_id = callback.data.split(":", 2)[2]
    removed = await remove_user_model_by_short(callback.from_user.id, short_id)
    if removed:
        await callback.answer("✅ Модель удалена")
    else:
        await callback.answer("❌ Не удалось удалить модель", show_alert=True)

    data = await state.get_data()
    provider = data.get("current_provider")

    user = await get_user(callback.from_user.id)
    selected = user.get("selected_model", "") if user else ""
    if provider and provider in PROVIDER_LABELS:
        user_models = await get_user_models_by_provider(callback.from_user.id, provider)
        back_cb = f"models:my:{provider}"
    else:
        user_models = await get_user_models(callback.from_user.id)
        back_cb = "models:my:all"

    text = f"📦 {'Модели ' + provider_label(provider) + ':\n\n' if provider and provider in PROVIDER_LABELS else 'Все мои модели:\n\n'}"
    if not user_models:
        text += "У тебя нет добавленных моделей."
    else:
        text += "Выбери модель или удалите:"

    await edit_callback_message_text(
        callback,
        text,
        reply_markup=models_keyboard(user_models, selected, show_check_button=True, show_note_button=True, back_callback=back_cb),
    )


@router.message(UserStates.waiting_for_new_model_provider)
@router.message(UserStates.waiting_for_new_model)
async def process_new_model(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    if not text:
        data = await state.get_data()
        provider = data.get("model_provider", "openrouter")
        await message.answer(f"❌ Отправь модель для {provider_label(provider)} текстом в формате: model_id | Display Name | краткая характеристика")
        return

    parts = [p.strip() for p in text.split("|")]
    if not parts or not parts[0]:
        await message.answer("❌ Неверный формат. Отправь идентификатор модели.")
        return

    data = await state.get_data()
    provider = data.get("model_provider", "openrouter")
    if provider not in PROVIDER_LABELS:
        provider = "openrouter"

    model_id = ensure_model_id_for_provider(provider, parts[0])
    display_name = parts[1] if len(parts) > 1 and parts[1] else model_id
    provider_label_text = provider_label(provider)
    if provider == "venice":
        lower_name = display_name.lower()
        if lower_name.startswith(f"{provider_label_text.lower()} · venice:"):
            display_name = provider_label_text + " · " + display_name[len(f"{provider_label_text} · venice:"):]
        elif lower_name.startswith("venice:"):
            display_name = display_name[7:]
            if not display_name.startswith(f"{provider_label_text} ·"):
                display_name = f"{provider_label_text} · {display_name}"
    elif not display_name.startswith(f"{provider_label_text} ·"):
        display_name = f"{provider_label_text} · {display_name}"
    meta = parts[2] if len(parts) > 2 else None

    user_id = message.from_user.id
    user = await get_user(user_id)
    if user is None:
        await create_user(user_id, "")
    user = await get_user(user_id)

    if provider == "openrouter":
        user_api_key = user.get("api_key", "") or ""
        user_key_provider = user.get("api_key_provider", "openrouter")
        if user_api_key and user_key_provider == "openrouter":
            fetched, _ = await fetch_provider_model_detail(
                "openrouter", model_id, user_api_key, "openrouter", build_user_provider_keys(user)
            )
            if fetched:
                api_meta = fetched.get("meta")
                if api_meta:
                    filtered_meta = api_meta.replace("⚠️ За проверку платных моделей взымается плата, модель не проверялась!", "").strip(" |")
                    meta = filtered_meta if filtered_meta else None
                api_name = fetched.get("name")
                if api_name and display_name == model_id:
                    display_name = api_name

    await add_user_model(user_id, model_id, display_name, meta)

    user = await get_user(user_id)
    selected = user.get("selected_model", "") if user else ""
    user_models = await get_user_models_by_provider(user_id, provider)
    meta_info = f" ({meta})" if meta else ""
    await state.update_data(current_provider=provider)
    await state.clear()
    await message.answer(
        f"✅ Модель добавлена: {display_name}{meta_info}",
        reply_markup=models_keyboard(user_models, selected, show_check_button=True, show_note_button=True, back_callback=f"models:my:{provider}"),
    )


@router.message(UserStates.waiting_for_model_note)
async def process_model_note(message: Message, state: FSMContext) -> None:
    note = message.text.strip()
    if not note:
        await message.answer("❌ Заметка не может быть пустой.")
        return

    user = await get_user(message.from_user.id)
    if user is None or not user.get("selected_model"):
        await state.clear()
        await message.answer("❌ Сначала выбери модель в настройках.")
        return

    await update_user_model_meta(message.from_user.id, user["selected_model"], note)
    await state.clear()

    user_models = await get_user_models(message.from_user.id)
    await message.answer(
        f"✅ Заметка сохранена для выбранной модели.",
        reply_markup=models_keyboard(user_models, user["selected_model"], show_check_button=True, show_note_button=True),
    )
