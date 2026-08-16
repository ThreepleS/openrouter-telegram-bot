"""FSM states for bot handlers."""

from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    waiting_for_api_key_provider = State()
    waiting_for_api_key = State()
    waiting_for_new_api_key_provider = State()
    waiting_for_new_api_key = State()
    waiting_for_system_prompt = State()
    waiting_for_model_provider = State()
    waiting_for_new_model_provider = State()
    waiting_for_new_model = State()
    waiting_for_model_note = State()
    waiting_for_context_limit = State()


class AdminStates(StatesGroup):
    waiting_for_user_id_to_add = State()
    waiting_for_user_id_to_remove = State()
    waiting_for_access_days = State()
    waiting_for_note_index = State()
    waiting_for_note_text = State()
    waiting_for_reset_user_identifier = State()
