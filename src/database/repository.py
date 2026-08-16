"""Storage layer: Supabase Postgres (cloud) or local SQLite, selected by env.

When USE_SUPABASE_DB=1 the bot reads/writes all data in Supabase Postgres via
the PostgREST API (service_role key). Otherwise it falls back to the original
local SQLite file (bot.db). All public function signatures are unchanged so the
rest of the bot (handlers, session, etc.) works with either backend.
"""

from __future__ import annotations

import hashlib
import time

from src.config import (
    DEFAULT_CONTEXT_LIMIT,
    DEFAULT_MODEL,
    DEFAULT_STATS_DISPLAY,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_THEME,
)
from src.config.env import get_settings

USE_SUPABASE = get_settings().use_supabase_db

if USE_SUPABASE:
    from src.database import supabase_repo as _repo
else:
    from src.database import sqlite_repo as _repo


async def init_db() -> None:
    await _repo.init_db()


async def get_user(user_id: int):
    return await _repo.get_user(user_id)


async def create_user(user_id: int, api_key: str, api_key_provider: str = "openrouter") -> None:
    await _repo.create_user(user_id, api_key, api_key_provider)


async def ensure_user(user_id: int) -> None:
    await _repo.ensure_user(user_id)


async def update_provider_key(user_id: int, provider: str, api_key: str) -> None:
    await _repo.update_provider_key(user_id, provider, api_key)


async def update_api_key(user_id: int, api_key: str, api_key_provider: str = "openrouter", set_personal_key: bool = True) -> None:
    await _repo.update_api_key(user_id, api_key, api_key_provider, set_personal_key)


async def update_selected_model(user_id: int, model_id: str) -> None:
    await _repo.update_selected_model(user_id, model_id)


async def update_system_prompt(user_id: int, system_prompt: str) -> None:
    await _repo.update_system_prompt(user_id, system_prompt)


async def update_context_limit(user_id: int, context_limit: int) -> None:
    await _repo.update_context_limit(user_id, context_limit)


async def update_theme(user_id: int, theme: str) -> None:
    await _repo.update_theme(user_id, theme)


async def update_notify_sound(user_id: int, enabled: bool) -> None:
    await _repo.update_notify_sound(user_id, enabled)


async def update_notify_vibrate(user_id: int, enabled: bool) -> None:
    await _repo.update_notify_vibrate(user_id, enabled)


async def update_notify_sound_id(user_id: int, sound_id: str) -> None:
    await _repo.update_notify_sound_id(user_id, sound_id)


async def update_vib_strength(user_id: int, strength: int) -> None:
    await _repo.update_vib_strength(user_id, strength)


async def add_message(user_id: int, role: str, content: str, image_url: str | None = None) -> None:
    await _repo.add_message(user_id, role, content, image_url)


async def get_recent_messages(user_id: int, limit: int) -> list[dict]:
    return await _repo.get_recent_messages(user_id, limit)


async def clear_messages(user_id: int) -> None:
    await _repo.clear_messages(user_id)


async def reset_user_state(user_id: int) -> None:
    await _repo.reset_user_state(user_id)


async def reset_all_users_state() -> None:
    await _repo.reset_all_users_state()


async def get_user_models(user_id: int) -> list[dict]:
    return await _repo.get_user_models(user_id)


async def get_user_models_by_provider(user_id: int, provider: str) -> list[dict]:
    return await _repo.get_user_models_by_provider(user_id, provider)


async def get_user_model(user_id: int, model_id: str):
    return await _repo.get_user_model(user_id, model_id)


async def get_user_model_by_short(user_id: int, short_id: str):
    return await _repo.get_user_model_by_short(user_id, short_id)


async def add_user_model(
    user_id: int,
    model_id: str,
    display_name: str,
    meta: str | None = None,
    context: int | None = None,
    mod_in: str | None = None,
    mod_out: str | None = None,
    price_prompt: str | None = None,
    price_completion: str | None = None,
    description: str | None = None,
    is_free: bool | None = None,
) -> None:
    await _repo.add_user_model(
        user_id, model_id, display_name, meta, context, mod_in, mod_out,
        price_prompt, price_completion, description, is_free,
    )


FAVORITES_PROVIDER_ORDER = ["openrouter", "openai", "gemini", "groq", "huggingface", "venice"]


def _detect_provider_from_model(model_id: str) -> str:
    lower = (model_id or "").lower()
    if lower.startswith("openai:"):
        return "openai"
    if lower.startswith("gemini:") or lower.startswith("gemini-") or lower.startswith("models/gemini-"):
        return "gemini"
    if lower.startswith("groq:"):
        return "groq"
    if lower.startswith("hf:"):
        return "huggingface"
    if lower.startswith("venice:"):
        return "venice"
    return "openrouter"


async def get_user_favorites(user_id: int) -> list[dict]:
    models = await get_user_models(user_id)
    grouped: dict[str, list[dict]] = {p: [] for p in FAVORITES_PROVIDER_ORDER}
    for m in models:
        prov = _detect_provider_from_model(m["model_id"])
        if prov not in grouped:
            grouped[prov] = []
        grouped[prov].append(m)

    result: list[dict] = []
    for p in FAVORITES_PROVIDER_ORDER:
        items = sorted(grouped.get(p, []), key=lambda x: x.get("added_at") or 0)
        result.extend(items)
    for p, items in grouped.items():
        if p not in FAVORITES_PROVIDER_ORDER:
            result.extend(sorted(items, key=lambda x: x.get("added_at") or 0))
    return result


async def is_whitelisted(user_id: int) -> bool:
    return True


async def add_to_whitelist(user_id: int) -> None:
    return None


async def remove_from_whitelist(user_id: int) -> bool:
    return False


async def get_whitelist() -> list[int]:
    return []


async def update_user_model_meta(user_id: int, model_id: str, meta: str | None) -> None:
    await _repo.update_user_model_meta(user_id, model_id, meta)


async def remove_user_model(user_id: int, model_id: str) -> bool:
    return await _repo.remove_user_model(user_id, model_id)


async def remove_user_model_by_short(user_id: int, short_id: str) -> bool:
    return await _repo.remove_user_model_by_short(user_id, short_id)


async def get_stats_display(user_id: int) -> str:
    return await _repo.get_stats_display(user_id)


async def update_stats_display(user_id: int, stats_display: str) -> None:
    await _repo.update_stats_display(user_id, stats_display)


async def get_whitelist_with_details() -> list[dict]:
    return []


async def get_whitelist_entry_by_index(index: int):
    return None


async def resolve_whitelist_identifier(identifier: str):
    return None


async def update_whitelist_note(user_id: int, note: str) -> None:
    return None


async def add_to_whitelist_with_access(user_id: int, access_type: str = "permanent", days: int | None = None) -> None:
    return None


async def is_whitelist_active(user_id: int) -> bool:
    return True


async def log_api_call(user_id: int, tokens_used: int) -> None:
    await _repo.log_api_call(user_id, tokens_used)


async def get_api_stats(user_id: int, since_ts: int):
    return await _repo.get_api_stats(user_id, since_ts)


async def get_all_api_stats(since_ts: int) -> list[dict]:
    return await _repo.get_all_api_stats(since_ts)


async def get_message_count(user_id: int) -> int:
    return await _repo.get_message_count(user_id)


async def get_total_message_count() -> int:
    return await _repo.get_total_message_count()


async def get_total_token_count() -> int:
    return await _repo.get_total_token_count()


async def count_users() -> int:
    return await _repo.count_users()


async def get_all_users() -> list[dict]:
    return await _repo.get_all_users()


async def close() -> None:
    if hasattr(_repo, "close"):
        await _repo.close()
