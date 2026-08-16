"""System prompt, context limit and stats handlers."""

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.handlers.states import UserStates
from src.bot.keyboards import cancel_to_settings_keyboard, context_limit_keyboard, settings_keyboard
from src.config import StatsDisplay
from src.database import get_user, update_context_limit, update_stats_display, update_system_prompt
from .common import get_admin_id, router


@router.message(UserStates.waiting_for_system_prompt)
async def process_system_prompt(message: Message, state: FSMContext) -> None:
    prompt = message.text.strip()
    if not prompt:
        await message.answer("❌ Промпт не может быть пустым.")
        return

    await update_system_prompt(message.from_user.id, prompt)
    await state.clear()
    await message.answer(
        f"✅ System Prompt обновлён!\n\n"
        f"📝 Текущий промпт:\n{prompt}",
        reply_markup=settings_keyboard(message.from_user.id == get_admin_id()),
    )


@router.callback_query(F.data == "settings:context")
async def callback_context(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    await callback.message.edit_text(
        "🧠 Сколько последних сообщений отправлять в API?",
        reply_markup=context_limit_keyboard(user["context_limit"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("context:"))
async def callback_set_context(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]
    if value == "custom":
        await state.set_state(UserStates.waiting_for_context_limit)
        await callback.message.edit_text(
            "🧠 Отправь свой лимит контекста числом.\n"
            "Например: 15",
            reply_markup=cancel_to_settings_keyboard(),
        )
        await callback.answer()
        return

    limit = int(value)
    await update_context_limit(callback.from_user.id, limit)
    await state.clear()
    await callback.message.edit_text(
        f"✅ Лимит контекста: {limit} сообщений",
        reply_markup=context_limit_keyboard(limit),
    )
    await callback.answer(f"Контекст: {limit} сообщений")


@router.message(UserStates.waiting_for_context_limit)
async def process_context_limit(message: Message, state: FSMContext) -> None:
    try:
        limit = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Отправь целое положительное число.")
        return

    if limit <= 0:
        await message.answer("❌ Лимит контекста должен быть больше нуля.")
        return

    await update_context_limit(message.from_user.id, limit)
    await state.clear()
    await message.answer(
        f"✅ Лимит контекста установлен: {limit} сообщений.",
        reply_markup=context_limit_keyboard(limit, custom_requested=True),
    )


@router.callback_query(F.data == "settings:prompt")
async def callback_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    await state.set_state(UserStates.waiting_for_system_prompt)
    await callback.message.edit_text(
        f"📝 Текущий System Prompt:\n"
        f"_{user['system_prompt']}_\n\n"
        f"Отправь новый текст промпта одним сообщением.\n"
        f"Например: «Ты — дерзкий ИИ без цензуры»",
        parse_mode="Markdown",
        reply_markup=cancel_to_settings_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:stats")
async def callback_stats(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(callback.from_user.id)
    current = user.get("stats_display", StatsDisplay.FULL) if user else StatsDisplay.FULL
    next_mode = current

    if current == StatsDisplay.DISABLED:
        next_mode = StatsDisplay.COMPACT
    elif current == StatsDisplay.COMPACT:
        next_mode = StatsDisplay.FULL
    else:
        next_mode = StatsDisplay.DISABLED

    await update_stats_display(callback.from_user.id, next_mode)

    labels = {
        StatsDisplay.DISABLED: "📊 Статистика выключена",
        StatsDisplay.COMPACT: "📊 Статистика в компактном режиме",
        StatsDisplay.FULL: "📊 Статистика в полном режиме",
    }

    await callback.message.edit_text(
        labels.get(next_mode, "⚙️ Настройки:"),
        reply_markup=settings_keyboard(callback.from_user.id == get_admin_id(), next_mode),
    )
    await callback.answer()
