"""Supabase Postgres repository (cloud backend) via PostgREST.

All functions mirror the SQLite backend but talk to Supabase REST API using the
service_role key. Uses aiohttp (already a dependency) so no new packages needed.
"""

from __future__ import annotations

import hashlib
import time

import aiohttp

from src.config import (
    DEFAULT_CONTEXT_LIMIT,
    DEFAULT_MODEL,
    DEFAULT_STATS_DISPLAY,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_THEME,
)
from src.config.env import get_settings

_settings = get_settings()
_BASE = _settings.supabase_url.rstrip("/")
_KEY = _settings.supabase_service_role_key
_HEADERS = {
    "apikey": _KEY,
    "Authorization": f"Bearer {_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Reusable session (aiohttp recommends one session per app).
_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(headers=_HEADERS)
    return _session


def _tbl(name: str) -> str:
    return f"{_BASE}/rest/v1/{name}"


async def _get(url: str, params: dict | None = None) -> list[dict]:
    async with _get_session().get(url, params=params) as resp:
        resp.raise_for_status()
        return await resp.json()


async def _post(url: str, json: list | dict) -> list[dict]:
    async with _get_session().post(url, json=json) as resp:
        resp.raise_for_status()
        return await resp.json()


async def _patch(url: str, params: dict, json: dict) -> list[dict]:
    async with _get_session().patch(url, params=params, json=json) as resp:
        resp.raise_for_status()
        return await resp.json()


async def _delete(url: str, params: dict) -> None:
    async with _get_session().delete(url, params=params) as resp:
        resp.raise_for_status()


async def init_db() -> None:
    # Tables are created via migration 0001_bot_schema.sql.
    pass


async def close() -> None:
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
        _session = None


async def get_user(user_id: int) -> dict | None:
    rows = await _get(_tbl("users"), {"user_id": f"eq.{user_id}"})
    return rows[0] if rows else None


async def create_user(user_id: int, api_key: str, api_key_provider: str = "openrouter") -> None:
    await _post(
        _tbl("users"),
        {
            "user_id": user_id,
            "api_key": api_key,
            "api_key_provider": api_key_provider,
            "selected_model": DEFAULT_MODEL,
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "context_limit": DEFAULT_CONTEXT_LIMIT,
            "stats_display": DEFAULT_STATS_DISPLAY,
            "theme": DEFAULT_THEME,
            "notify_sound": 0,
            "notify_vibrate": 0,
            "notify_sound_id": "chime",
            "vib_strength": 40,
        },
    )


async def ensure_user(user_id: int) -> None:
    if await get_user(user_id) is None:
        await create_user(user_id, "")


async def update_provider_key(user_id: int, provider: str, api_key: str) -> None:
    provider_col_map = {
        "openrouter": "api_key_openrouter",
        "openai": "api_key_openai",
        "gemini": "api_key_gemini",
        "groq": "api_key_groq",
        "huggingface": "api_key_huggingface",
        "venice": "api_key_venice",
    }
    col = provider_col_map.get(provider)
    if not col:
        return
    await _patch(
        _tbl("users"),
        {"user_id": f"eq.{user_id}"},
        {col: api_key or None},
    )


async def update_api_key(user_id: int, api_key: str, api_key_provider: str = "openrouter", set_personal_key: bool = True) -> None:
    provider_col_map = {
        "openrouter": "api_key_openrouter",
        "openai": "api_key_openai",
        "gemini": "api_key_gemini",
        "groq": "api_key_groq",
        "huggingface": "api_key_huggingface",
        "venice": "api_key_venice",
    }
    payload = {"api_key": api_key, "api_key_provider": api_key_provider}
    if set_personal_key:
        provider_col = provider_col_map.get(api_key_provider)
        if provider_col:
            payload[provider_col] = api_key
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, payload)


async def update_selected_model(user_id: int, model_id: str) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"selected_model": model_id})


async def update_system_prompt(user_id: int, system_prompt: str) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"system_prompt": system_prompt})


async def update_context_limit(user_id: int, context_limit: int) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"context_limit": context_limit})


async def update_theme(user_id: int, theme: str) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"theme": theme})


async def update_notify_sound(user_id: int, enabled: bool) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"notify_sound": 1 if enabled else 0})


async def update_notify_vibrate(user_id: int, enabled: bool) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"notify_vibrate": 1 if enabled else 0})


async def update_notify_sound_id(user_id: int, sound_id: str) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"notify_sound_id": sound_id})


async def update_vib_strength(user_id: int, strength: int) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"vib_strength": strength})


async def add_message(user_id: int, role: str, content: str, image_url: str | None = None) -> None:
    await _post(
        _tbl("messages"),
        {
            "user_id": user_id,
            "role": role,
            "content": content,
            "image_url": image_url,
        },
    )


async def get_recent_messages(user_id: int, limit: int) -> list[dict]:
    rows = await _get(
        _tbl("messages"),
        {
            "user_id": f"eq.{user_id}",
            "order": "id.desc",
            "limit": str(limit),
            "select": "role,content,image_url",
        },
    )
    return [{**row, "image_url": row.get("image_url")} for row in reversed(rows)]


async def clear_messages(user_id: int) -> None:
    await _delete(_tbl("messages"), {"user_id": f"eq.{user_id}"})


async def reset_user_state(user_id: int) -> None:
    await _delete(_tbl("messages"), {"user_id": f"eq.{user_id}"})
    await _delete(_tbl("api_stats"), {"user_id": f"eq.{user_id}"})
    await _delete(_tbl("user_models"), {"user_id": f"eq.{user_id}"})
    await _delete(_tbl("users"), {"user_id": f"eq.{user_id}"})


async def reset_all_users_state() -> None:
    await _delete(_tbl("messages"), {})
    await _delete(_tbl("api_stats"), {})
    await _delete(_tbl("user_models"), {})
    await _delete(_tbl("users"), {})


async def get_user_models(user_id: int) -> list[dict]:
    rows = await _get(
        _tbl("user_models"),
        {
            "user_id": f"eq.{user_id}",
            "order": "added_at.asc,display_name.asc",
            "select": "model_id,display_name,meta,short_id,added_at,context,mod_in,mod_out,price_prompt,price_completion,description,is_free",
        },
    )
    result = []
    for row in rows:
        if not row.get("short_id") and row.get("model_id"):
            row["short_id"] = hashlib.sha1(row["model_id"].encode()).hexdigest()[:16]
        if row.get("added_at") is None:
            row["added_at"] = 0
        result.append(row)
    return result


async def get_user_models_by_provider(user_id: int, provider: str) -> list[dict]:
    prefixes = {
        "openai": "openai:",
        "gemini": "gemini:",
        "groq": "groq:",
        "huggingface": "hf:",
        "venice": "venice:",
    }
    prefix = prefixes.get(provider, "")
    if prefix:
        rows = await _get(
            _tbl("user_models"),
            {
                "user_id": f"eq.{user_id}",
                "model_id": f"like.{prefix}%",
                "order": "added_at.asc,display_name.asc",
                "select": "model_id,display_name,meta,short_id,added_at,context,mod_in,mod_out,price_prompt,price_completion,description,is_free",
            },
        )
    else:
        rows = await _get(
            _tbl("user_models"),
            {
                "user_id": f"eq.{user_id}",
                "order": "added_at.asc,display_name.asc",
                "select": "model_id,display_name,meta,short_id,added_at,context,mod_in,mod_out,price_prompt,price_completion,description,is_free",
            },
        )
        rows = [r for r in rows if not any(r["model_id"].startswith(p) for p in prefixes.values())]
    result = []
    for row in rows:
        if not row.get("short_id") and row.get("model_id"):
            row["short_id"] = hashlib.sha1(row["model_id"].encode()).hexdigest()[:16]
        if row.get("added_at") is None:
            row["added_at"] = 0
        result.append(row)
    return result


async def get_user_model(user_id: int, model_id: str) -> dict | None:
    rows = await _get(
        _tbl("user_models"),
        {
            "user_id": f"eq.{user_id}",
            "model_id": f"eq.{model_id}",
            "limit": "1",
            "select": "model_id,display_name,meta,short_id,context,mod_in,mod_out,price_prompt,price_completion,description,is_free",
        },
    )
    if not rows:
        return None
    row = rows[0]
    if not row.get("short_id") and row.get("model_id"):
        row["short_id"] = hashlib.sha1(row["model_id"].encode()).hexdigest()[:16]
    return row


async def get_user_model_by_short(user_id: int, short_id: str) -> dict | None:
    rows = await _get(
        _tbl("user_models"),
        {
            "user_id": f"eq.{user_id}",
            "short_id": f"eq.{short_id}",
            "limit": "1",
            "select": "model_id,display_name,meta,short_id,context,mod_in,mod_out,price_prompt,price_completion,description,is_free",
        },
    )
    return rows[0] if rows else None


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
    short_id = hashlib.sha1(model_id.encode()).hexdigest()[:16]
    now = int(time.time())
    is_free_val = int(is_free) if is_free is not None else None
    await _post(
        _tbl("user_models"),
        {
            "user_id": user_id,
            "model_id": model_id,
            "display_name": display_name,
            "meta": meta,
            "short_id": short_id,
            "added_at": now,
            "context": context,
            "mod_in": mod_in,
            "mod_out": mod_out,
            "price_prompt": price_prompt,
            "price_completion": price_completion,
            "description": description,
            "is_free": is_free_val,
        },
    )


async def update_user_model_meta(user_id: int, model_id: str, meta: str | None) -> None:
    await _patch(
        _tbl("user_models"),
        {"user_id": f"eq.{user_id}", "model_id": f"eq.{model_id}"},
        {"meta": meta},
    )


async def remove_user_model(user_id: int, model_id: str) -> bool:
    await _delete(_tbl("user_models"), {"user_id": f"eq.{user_id}", "model_id": f"eq.{model_id}"})
    return True


async def remove_user_model_by_short(user_id: int, short_id: str) -> bool:
    await _delete(_tbl("user_models"), {"user_id": f"eq.{user_id}", "short_id": f"eq.{short_id}"})
    return True


async def get_stats_display(user_id: int) -> str:
    rows = await _get(
        _tbl("users"),
        {"user_id": f"eq.{user_id}", "select": "stats_display"},
    )
    if not rows:
        return DEFAULT_STATS_DISPLAY
    return rows[0].get("stats_display") or DEFAULT_STATS_DISPLAY


async def update_stats_display(user_id: int, stats_display: str) -> None:
    await _patch(_tbl("users"), {"user_id": f"eq.{user_id}"}, {"stats_display": stats_display})


async def log_api_call(user_id: int, tokens_used: int) -> None:
    await _post(
        _tbl("api_stats"),
        {
            "user_id": user_id,
            "tokens_used": tokens_used,
            "timestamp": int(time.time()),
        },
    )


async def get_api_stats(user_id: int, since_ts: int) -> tuple[int, int]:
    rows = await _get(
        _tbl("api_stats"),
        {
            "user_id": f"eq.{user_id}",
            "timestamp": f"gte.{since_ts}",
            "select": "count,tokens_used",
        },
    )
    count = 0
    tokens = 0
    for row in rows:
        count += 1
        tokens += row.get("tokens_used") or 0
    return count, tokens


async def get_all_api_stats(since_ts: int) -> list[dict]:
    rows = await _get(
        _tbl("api_stats"),
        {
            "timestamp": f"gte.{since_ts}",
            "select": "user_id,count,tokens_used",
        },
    )
    result = []
    for row in rows:
        result.append({
            "user_id": row["user_id"],
            "message_count": row.get("count", 0),
            "total_tokens": row.get("tokens_used", 0),
        })
    return result


async def get_message_count(user_id: int) -> int:
    rows = await _get(
        _tbl("messages"),
        {
            "user_id": f"eq.{user_id}",
            "select": "count",
        },
    )
    return rows[0].get("count", 0) if rows else 0


async def get_total_message_count() -> int:
    rows = await _get(
        _tbl("messages"),
        {
            "select": "count",
        },
    )
    return rows[0].get("count", 0) if rows else 0


async def get_total_token_count() -> int:
    rows = await _get(
        _tbl("api_stats"),
        {
            "select": "sum(tokens_used)",
        },
    )
    return rows[0].get("sum", 0) if rows else 0


async def count_users() -> int:
    rows = await _get(
        _tbl("users"),
        {
            "select": "count",
        },
    )
    return rows[0].get("count", 0) if rows else 0


async def get_all_users() -> list[dict]:
    return await _get(
        _tbl("users"),
        {
            "order": "user_id.asc",
            "select": "*",
        },
    )