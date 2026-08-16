"""HTTP routes for the PWA + Telegram Mini App.

These handlers reuse the existing AI/database layers so the web client and the
Telegram bot share exactly the same logic. No chat UI lives here yet — the
frontend is intentionally schematic so the request/response flow can be tested.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import json
import re

from aiohttp import web

from src.ai.client import fetch_provider_models, ping_model, stream_ai_api
from src.ai.providers import build_user_provider_keys, format_usage_stats, get_provider_api_key, model_id_for_provider, provider_label
from src.config import PROVIDER_LABELS, STATS_DISPLAY_OPTIONS, StatsDisplay
from src.config.env import Settings
from src.database import (
    add_message,
    add_user_model,
    clear_messages,
    count_users,
    ensure_user,
    get_all_api_stats,
    get_all_users,
    get_api_stats,
    get_message_count,
    get_recent_messages,
    get_stats_display,
    get_total_token_count,
    remove_user_model,
    get_user,
    get_user_favorites,
    get_whitelist_with_details,
    is_whitelisted,
    log_api_call,
    remove_from_whitelist,
    reset_all_users_state,
    reset_user_state,
    update_api_key,
    update_provider_key,
    update_context_limit,
    update_selected_model,
    update_stats_display,
    update_system_prompt,
    update_whitelist_note,
    add_to_whitelist_with_access,
    update_theme,
    update_notify_sound,
    update_notify_vibrate,
    update_notify_sound_id,
    update_vib_strength,
)
from src.utils.text import markdown_to_html, shorten_key
from src.web.auth import extract_user, verify_init_data
from src.web.markdown import render_markdown_html


def _settings(request: web.Request) -> Settings:
    return request.app["settings"]


def _resolve_user(request: web.Request, payload: dict) -> tuple[int | None, str | None]:
    """Authenticate the caller and return (user_id, error).

    In production the caller must supply a valid Telegram ``init_data``. In dev
    mode (``WEB_APP_DEV=1``) a raw ``user_id`` is accepted for local testing.
    """
    settings = _settings(request)

    if settings.web_app_dev and payload.get("user_id"):
        return int(payload["user_id"]), None

    init_data = payload.get("init_data") or ""
    if not verify_init_data(init_data, settings.bot_token):
        return None, "❌ Невалидные данные Telegram (initData)."

    user = extract_user(init_data)
    if not user or not user.get("id"):
        return None, "❌ Не удалось извлечь пользователя из initData."
    return int(user["id"]), None


async def _check_access(user_id: int) -> tuple[dict | None, str | None]:
    """Return (user_row, error) after whitelist + key + model checks.

    Used by chat/auth endpoints that actually need a working key+model.
    """
    if not await is_whitelisted(user_id):
        return None, "⛔ Нет доступа. Запросите доступ у администратора."

    user = await get_user(user_id)
    if user is None:
        return None, "🔑 Сначала укажи API-ключ в настройках (кнопка ⚙)."

    has_any_key = bool(user.get("api_key")) or any(
        (user.get(col) or "").strip() for col in _PROVIDER_KEY_COLS.values()
    )
    if not has_any_key:
        return None, "🔑 Сначала укажи API-ключ в настройках (кнопка ⚙)."

    if not user.get("selected_model"):
        return None, "🤖 Сначала выбери модель в настройках (кнопка ⚙)."

    return user, None


def _mask_key(key: str) -> str:
    """Mask a secret key, keeping a short prefix/suffix so it is recognisable."""
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}{'•' * min(12, len(key) - 8)}{key[-4:]}"


def _resolve_image_bytes(image_url: str | None) -> tuple[str | None, str | None]:
    """Extract base64 bytes and mime type from a stored data: URL, if present."""
    if not image_url or not image_url.startswith("data:"):
        return None, None
    comma = image_url.find(",")
    if comma < 0:
        return None, None
    mime = "image/jpeg"
    mime_match = re.match(r"^data:([^;]+);", image_url[:comma])
    if mime_match:
        mime = mime_match[1]
    return image_url[comma + 1:], mime


async def _require_admin(request: web.Request, payload: dict) -> tuple[int | None, str | None]:
    """Resolve the caller and ensure it is the configured admin."""
    user_id, error = _resolve_user(request, payload)
    if error:
        return None, error
    if user_id != _settings(request).admin_id:
        return None, "⛔ Только для администратора."
    return user_id, None


def _history_to_messages(history: list[dict]) -> list[dict]:
    """Convert stored history (with optional data-URL images) to provider messages.

    Each stored image is kept as an ``image_url`` data URL; we expose it as
    ``image_bytes`` and ``image_mime`` so the provider payload builders can
    attach it with the correct MIME type.
    """
    messages: list[dict] = []
    for m in history:
        item = {"role": m.get("role", "user"), "content": m.get("content") or ""}
        img_bytes, img_mime = _resolve_image_bytes(m.get("image_url"))
        if img_bytes:
            item["image_bytes"] = img_bytes
            item["image_mime"] = img_mime
        messages.append(item)
    return messages


async def api_auth(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = _resolve_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=401)

    user, access_error = await _check_access(user_id)
    if access_error:
        return web.json_response({"ok": False, "error": access_error}, status=403)

    return web.json_response({
        "ok": True,
        "user_id": user_id,
        "is_admin": user_id == _settings(request).admin_id,
        "settings": {
            "selected_model": user.get("selected_model"),
            "system_prompt": user.get("system_prompt"),
            "context_limit": user.get("context_limit"),
            "stats_display": user.get("stats_display"),
            "api_key_provider": user.get("api_key_provider"),
            "theme": user.get("theme"),
            "notify_sound": user.get("notify_sound"),
            "notify_vibrate": user.get("notify_vibrate"),
            "notify_sound_id": user.get("notify_sound_id"),
            "vib_strength": user.get("vib_strength"),
        },
    })


async def api_whoami(request: web.Request) -> web.Response:
    """Dev-only helper: reveal the admin id to the app owner.

    The admin id is returned ONLY when the request originates from the local
    machine (the owner) AND dev mode is enabled. Remote users (e.g. opened via
    a public tunnel) get ``admin_id: null`` and therefore never see the admin
    panel — no manual id/password entry required.
    """
    settings = _settings(request)
    remote = request.remote or ""
    is_local = (
        remote in ("127.0.0.1", "::1", "localhost", "")
        or remote.startswith("192.168.")
        or remote.startswith("10.")
        or remote.startswith("172.16.")
    )
    # Only expose the admin id on the owner's local machine / local network.
    # Public tunnels (ngrok, cloudflare) must NOT reveal it — otherwise any
    # remote visitor could become admin. The Host header reveals tunnel domains.
    host = (request.headers.get("Host") or "").lower()
    is_tunnel = "ngrok" in host or "trycloudflare" in host or "cloudflare" in host
    if settings.web_app_dev and is_local and not is_tunnel:
        return web.json_response({"ok": True, "admin_id": settings.admin_id})
    return web.json_response({"ok": True, "admin_id": None})


async def api_chat(request: web.Request) -> web.StreamResponse:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = _resolve_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=401)

    message_text = (payload.get("message") or "").strip()
    image_raw = payload.get("image") or None

    if not message_text and not image_raw:
        return web.json_response({"ok": False, "error": "❌ Пустое сообщение."}, status=400)

    user, access_error = await _check_access(user_id)
    if access_error:
        return web.json_response({"ok": False, "error": access_error}, status=403)

    await add_message(user_id, "user", message_text, image_url=image_raw)

    history = await get_recent_messages(user_id, user["context_limit"])
    messages = _history_to_messages(history)

    request_start = time.monotonic()
    resp = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "application/x-ndjson; charset=utf-8",
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(request)

    async def send(obj: dict) -> None:
        await resp.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))

    await send({"type": "start"})

    full = ""
    usage: dict = {}
    errored = False
    async for event in stream_ai_api(
        api_key=user["api_key"],
        model=user["selected_model"],
        system_prompt=user["system_prompt"],
        messages=messages,
        user_api_key_provider=user.get("api_key_provider", "openrouter"),
        db_provider_keys=build_user_provider_keys(user),
    ):
        if event["type"] == "delta":
            full += event.get("text", "")
            await send(event)
        elif event["type"] == "error":
            errored = True
            await send(event)
            break
        elif event["type"] == "done":
            usage = event.get("usage", {}) or {}

    if errored:
        await resp.write_eof()
        return resp

    elapsed = time.monotonic() - request_start
    await add_message(user_id, "assistant", full or "")

    total_tokens = usage.get("total_tokens") or (
        (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
    )
    if total_tokens:
        await log_api_call(user_id, total_tokens)

    stats_display = await get_stats_display(user_id)
    stats_text = ""
    if stats_display != StatsDisplay.DISABLED and full:
        stats_text = format_usage_stats(
            user["selected_model"], usage, elapsed,
            compact=stats_display == StatsDisplay.COMPACT,
        )

    # Markdown is rendered to real HTML for the web client. For reference we
    # also keep the Telegram-compatible variant used by the bot.
    html = render_markdown_html(full or "")
    tg_html = markdown_to_html(full or "")

    await send({
        "type": "result",
        "ok": True,
        "reply": full,
        "markdown": full,
        "html": html,
        "tg_html": tg_html,
        "model": user["selected_model"],
        "usage": usage,
        "stats": stats_text,
    })
    await resp.write_eof()
    return resp


# --- Static PWA assets -----------------------------------------------------

def _read(path: Path) -> bytes:
    return path.read_bytes()


async def serve_index(request: web.Request) -> web.Response:
    data = _read(request.app["static_dir"] / "index.html")
    return web.Response(body=data, content_type="text/html", charset="utf-8")


async def serve_admin(request: web.Request) -> web.Response:
    data = _read(request.app["static_dir"] / "admin.html")
    return web.Response(body=data, content_type="text/html", charset="utf-8")


async def serve_manifest(request: web.Request) -> web.Response:
    data = _read(request.app["static_dir"] / "manifest.webmanifest")
    return web.Response(body=data, content_type="application/manifest+json", charset="utf-8")


async def serve_service_worker(request: web.Request) -> web.Response:
    data = _read(request.app["static_dir"] / "sw.js")
    return web.Response(body=data, content_type="application/javascript", charset="utf-8")


def _icon(request: web.Request, file_name: str) -> web.Response:
    data = _read(request.app["static_dir"] / file_name)
    return web.Response(body=data, content_type="image/png")


async def serve_icon_192(request: web.Request) -> web.Response:
    return _icon(request, "icon-192.png")


async def serve_icon_512(request: web.Request) -> web.Response:
    return _icon(request, "icon-512.png")


async def api_chat_clear(request: web.Request) -> web.Response:
    """Clear the caller's chat history."""
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = _require_settings_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    try:
        await clear_messages(user_id)
    except Exception as exc:
        return web.json_response({"ok": False, "error": f"❌ {exc}"}, status=500)
    return web.json_response({"ok": True})


async def serve_sw_register(request: web.Request) -> web.Response:
    data = _read(request.app["static_dir"] / "sw-register.js")
    return web.Response(body=data, content_type="application/javascript", charset="utf-8")


async def _require_settings_user(request: web.Request, payload: dict) -> tuple[int | None, str | None]:
    """Light access check for the settings endpoint.

    Unlike ``_check_access`` this does NOT require an existing API key or model
    — the whole point of this endpoint is to let the user set them. It only
    checks the whitelist and makes sure a DB row exists for the user.
    """
    user_id, error = _resolve_user(request, payload)
    if error:
        return None, error
    if not await is_whitelisted(user_id):
        return None, "⛔ Нет доступа. Запросите доступ у администратора."
    await ensure_user(user_id)
    return user_id, None


async def api_settings(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = await _require_settings_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    if payload.get("api_key"):
        key = str(payload["api_key"]).strip()
        provider = payload.get("api_key_provider") or user.get("api_key_provider", "openrouter")
        if provider not in PROVIDER_LABELS:
            return web.json_response({"ok": False, "error": "❌ Неизвестный провайдер."}, status=400)
        await update_api_key(user_id, key, provider)

    # Поддержка нескольких ключей сразу: каждый провайдер в свою колонку.
    provider_keys = payload.get("provider_keys")
    if isinstance(provider_keys, dict):
        for provider, key in provider_keys.items():
            if provider not in PROVIDER_LABELS:
                continue
            key_val = str(key).strip() if key else ""
            await update_provider_key(user_id, provider, key_val)
    if "selected_model" in payload and payload["selected_model"]:
        await update_selected_model(user_id, str(payload["selected_model"]).strip())
    if "system_prompt" in payload and payload["system_prompt"] is not None:
        await update_system_prompt(user_id, str(payload["system_prompt"]))
    if "context_limit" in payload:
        try:
            cl = int(payload["context_limit"])
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "❌ Лимит контекста должен быть числом."}, status=400)
        cl = max(1, min(100, cl))
        await update_context_limit(user_id, cl)
    if "stats_display" in payload:
        sd = payload["stats_display"]
        if sd not in STATS_DISPLAY_OPTIONS:
            return web.json_response({"ok": False, "error": "❌ Неизвестный режим статистики."}, status=400)
        await update_stats_display(user_id, sd)
    if "theme" in payload:
        theme = str(payload["theme"]).strip()
        if theme not in ("dark", "light", "midnight", "aurora", "sunset", "cyber", "neon", "lava", "ocean", "custom"):
            return web.json_response({"ok": False, "error": "❌ Неизвестная тема."}, status=400)
        await update_theme(user_id, theme)
    if "notify_sound" in payload:
        await update_notify_sound(user_id, bool(payload["notify_sound"]))
    if "notify_vibrate" in payload:
        await update_notify_vibrate(user_id, bool(payload["notify_vibrate"]))
    if "notify_sound_id" in payload:
        await update_notify_sound_id(user_id, str(payload["notify_sound_id"]))
    if "vib_strength" in payload:
        try:
            vs = int(payload["vib_strength"])
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "❌ Сила вибрации должна быть числом."}, status=400)
        vs = max(10, min(200, vs))
        await update_vib_strength(user_id, vs)

    fresh = await get_user(user_id)
    return web.json_response({
        "ok": True,
        "settings": {
            "selected_model": fresh.get("selected_model"),
            "system_prompt": fresh.get("system_prompt"),
            "context_limit": fresh.get("context_limit"),
            "stats_display": fresh.get("stats_display"),
            "api_key_provider": fresh.get("api_key_provider"),
            "theme": fresh.get("theme"),
            "notify_sound": fresh.get("notify_sound"),
            "notify_vibrate": fresh.get("notify_vibrate"),
            "notify_sound_id": fresh.get("notify_sound_id"),
            "vib_strength": fresh.get("vib_strength"),
        },
    })


async def api_keyinfo(request: web.Request) -> web.Response:
    """Return per-provider key status (has/masked). Never expose the raw key."""
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = await _require_settings_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    user = await get_user(user_id)
    provider = user.get("api_key_provider") or "openrouter"
    keys = {}
    for prov, col in _PROVIDER_KEY_COLS.items():
        raw = (user.get(col) or "").strip()
        if not raw and prov == provider:
            raw = (user.get("api_key") or "").strip()
        keys[prov] = {"has": bool(raw), "masked": _mask_key(raw)}
    return web.json_response({
        "ok": True,
        "provider": provider,
        "keys": keys,
    })


async def api_models(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = await _require_settings_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    user = await get_user(user_id)
    req_provider = (payload.get("provider") or user.get("api_key_provider") or "openrouter")
    if req_provider not in PROVIDER_LABELS and req_provider != "paid":
        req_provider = user.get("api_key_provider") or "openrouter"
    provider = req_provider

    key = get_provider_api_key(
        "openrouter" if provider == "paid" else provider,
        user.get("api_key", ""),
        user.get("api_key_provider", "openrouter"),
        build_user_provider_keys(user),
    )
    if not key:
        return web.json_response(
            {"ok": False, "error": f"🔑 Сначала укажи API-ключ {provider_label(provider)} в настройках (кнопка ⚙)."},
            status=400,
        )

    if provider == "paid":
        # Платные модели OpenRouter: только список, без пинга (платно!).
        models, err = await fetch_provider_models(
            "openrouter",
            user.get("api_key", ""),
            user.get("api_key_provider", "openrouter"),
            build_user_provider_keys(user),
            check_availability=False,
            show_free_only=False,
        )
        if err:
            return web.json_response({"ok": False, "error": f"❌ {err}"}, status=502)
        paid = [m for m in models if not m.get("is_free")]
        return web.json_response({"ok": True, "provider": "paid", "category": "paid", "models": paid})

    show_free_only = provider == "openrouter"
    check_availability = False
    models, err = await fetch_provider_models(
        provider,
        user.get("api_key", ""),
        user.get("api_key_provider", "openrouter"),
        build_user_provider_keys(user),
        check_availability=check_availability,
        show_free_only=show_free_only,
    )
    if err:
        return web.json_response({"ok": False, "error": f"❌ {err}"}, status=502)

    category = "free" if (provider == "openrouter" or provider == "gemini" or provider == "venice") else "all"
    return web.json_response({"ok": True, "provider": provider, "category": category, "models": models})


async def api_models_ping(request: web.Request) -> web.Response:
    """Ping the FREE models of a provider to verify they actually answer.

    Only free models are pinged (paid pings cost money and are skipped). Returns
    per-model status so the client can mark working models. This can take a
    while for long lists, so the client should show a spinner.
    """
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = await _require_settings_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    provider = payload.get("provider") or "openrouter"
    if provider not in ("openrouter", "gemini", "venice"):
        provider = "openrouter"

    user = await get_user(user_id)
    api_key = user.get("api_key", "")
    api_key_provider = user.get("api_key_provider", "openrouter")
    db_keys = build_user_provider_keys(user)

    # Берём свежий список бесплатных моделей провайдера.
    models, err = await fetch_provider_models(
        provider, api_key, api_key_provider, db_keys,
        check_availability=False, show_free_only=(provider == "openrouter"),
    )
    if err:
        return web.json_response({"ok": False, "error": f"❌ {err}"}, status=502)

    results = []
    for m in models:
        mid = m.get("id") or m.get("model_id")
        if not mid:
            continue
        try:
            ping_id = model_id_for_provider(provider, mid)
            status, info = await ping_model(
                api_key, ping_id, user.get("system_prompt") or "",
                user_api_key_provider=api_key_provider, db_provider_keys=db_keys,
            )
        except Exception as exc:  # одна упавшая модель не ломает весь пинг
            status, info = "error", f"❌ {exc}"
        results.append({"model_id": mid, "status": status, "info": info})

    working = [r["model_id"] for r in results if r["status"] == "ok"]
    failed = [r["model_id"] for r in results if r["status"] != "ok"]
    return web.json_response({
        "ok": True,
        "provider": provider,
        "pinged_at": int(time.time()),
        "total": len(results),
        "working": len(working),
        "failed": len(failed),
        "results": results,
    })


async def api_favorites(request: web.Request) -> web.Response:
    """Return the caller's saved (favourite) models, grouped by provider, oldest first."""
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = await _require_settings_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    favorites = await get_user_favorites(user_id)
    for m in favorites:
        mid = m.get("model_id", "")
        low = mid.lower()
        if low.startswith("openai:"):
            prov = "openai"
        elif low.startswith("gemini:") or low.startswith("gemini-") or low.startswith("models/gemini-"):
            prov = "gemini"
        elif low.startswith("groq:"):
            prov = "groq"
        elif low.startswith("hf:"):
            prov = "huggingface"
        elif low.startswith("venice:"):
            prov = "venice"
        else:
            prov = "openrouter"
        m["provider"] = prov
    return web.json_response({"ok": True, "models": favorites})


async def api_favorite_add(request: web.Request) -> web.Response:
    """Add a model to the caller's favourites."""
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = await _require_settings_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    model_id = (payload.get("model_id") or "").strip()
    if not model_id:
        return web.json_response({"ok": False, "error": "❌ Не указан model_id."}, status=400)
    display_name = (payload.get("display_name") or model_id).strip()
    meta = payload.get("meta") or None
    context = payload.get("context")
    mod_in = payload.get("mod_in")
    mod_out = payload.get("mod_out")
    price_prompt = payload.get("price_prompt")
    price_completion = payload.get("price_completion")
    description = payload.get("description")
    is_free = payload.get("is_free")
    await add_user_model(
        user_id, model_id, display_name, meta,
        context, mod_in, mod_out, price_prompt, price_completion, description, is_free,
    )
    return web.json_response({"ok": True, "model_id": model_id})


async def api_favorite_remove(request: web.Request) -> web.Response:
    """Remove a model from the caller's favourites."""
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    user_id, error = await _require_settings_user(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    model_id = (payload.get("model_id") or "").strip()
    if not model_id:
        return web.json_response({"ok": False, "error": "❌ Не указан model_id."}, status=400)
    removed = await remove_user_model(user_id, model_id)
    return web.json_response({"ok": True, "removed": removed, "model_id": model_id})


# --- Admin API -------------------------------------------------------------

_PROVIDER_KEY_COLS = {
    "openrouter": "api_key_openrouter",
    "openai": "api_key_openai",
    "gemini": "api_key_gemini",
    "groq": "api_key_groq",
    "huggingface": "api_key_huggingface",
    "venice": "api_key_venice",
}


def _user_keys_map(user: dict) -> dict:
    keys: dict = {}
    for provider, col in _PROVIDER_KEY_COLS.items():
        raw = (user.get(col) or "").strip()
        if not raw and provider == (user.get("api_key_provider") or "openrouter"):
            raw = (user.get("api_key") or "").strip()
        # Никогда не возвращаем сам секретный ключ — только факт наличия.
        keys[provider] = {"has": bool(raw)}
    return keys


async def api_admin_summary(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    admin_id, error = await _require_admin(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    now = int(time.time())
    stats_24h = await get_all_api_stats(now - 86400)
    stats_7d = await get_all_api_stats(now - 7 * 86400)
    return web.json_response({
        "ok": True,
        "users_total": await count_users(),
        "whitelisted": len(await get_whitelist_with_details()),
        "messages_total": await get_total_message_count(),
        "tokens_total": await get_total_token_count(),
        "stats_24h": stats_24h,
        "stats_7d": stats_7d,
    })


async def api_admin_users(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    admin_id, error = await _require_admin(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    users = await get_all_users()
    result = []
    for u in users:
        uid = u.get("user_id")
        _, tokens = await get_api_stats(uid, 0)
        result.append({
            "user_id": uid,
            "is_admin": uid == admin_id,
            "provider": u.get("api_key_provider") or "openrouter",
            "model": u.get("selected_model") or "",
            "context_limit": u.get("context_limit"),
            "message_count": await get_message_count(uid),
            "tokens_total": tokens,
            "keys": _user_keys_map(u),
        })
    return web.json_response({"ok": True, "users": result})


async def api_admin_whitelist(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    admin_id, error = await _require_admin(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    action = (payload.get("action") or "").strip().lower()
    if action not in ("add", "remove", "note"):
        return web.json_response({"ok": False, "error": "❌ Неизвестное действие."}, status=400)

    if action == "add":
        try:
            target = int(str(payload.get("user_id")).strip())
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "❌ user_id должен быть числом."}, status=400)
        access_type = (payload.get("access_type") or "permanent").strip().lower()
        if access_type not in ("permanent", "temporary"):
            access_type = "permanent"
        days = None
        if access_type == "temporary":
            try:
                days = int(payload.get("days") or 0)
            except (TypeError, ValueError):
                days = None
        await add_to_whitelist_with_access(target, access_type=access_type, days=days)
        if await get_user(target) is None:
            await ensure_user(target)
        note = (payload.get("note") or "").strip()
        if note:
            await update_whitelist_note(target, note)
    elif action == "remove":
        try:
            target = int(str(payload.get("user_id")).strip())
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "❌ user_id должен быть числом."}, status=400)
        if target == admin_id:
            return web.json_response({"ok": False, "error": "❌ Нельзя удалить себя."}, status=400)
        removed = await remove_from_whitelist(target)
        if not removed:
            return web.json_response({"ok": False, "error": "⚠️ Пользователь не в белом списке."}, status=400)
    elif action == "note":
        try:
            target = int(str(payload.get("user_id")).strip())
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "❌ user_id должен быть числом."}, status=400)
        await update_whitelist_note(target, (payload.get("note") or "").strip())

    whitelist = await get_whitelist_with_details()
    return web.json_response({"ok": True, "whitelist": whitelist})


async def api_admin_user(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "❌ Неверный JSON."}, status=400)

    admin_id, error = await _require_admin(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)

    action = (payload.get("action") or "").strip().lower()
    if action not in ("clear", "reset"):
        return web.json_response({"ok": False, "error": "❌ Неизвестное действие."}, status=400)
    try:
        target = int(str(payload.get("user_id")).strip())
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "error": "❌ user_id должен быть числом."}, status=400)

    if action == "clear":
        await clear_messages(target)
        return web.json_response({"ok": True, "message": f"✅ История пользователя {target} очищена."})
    if action == "reset":
        if target == admin_id:
            return web.json_response({"ok": False, "error": "❌ Сброс себя запрещён."}, status=400)
        await reset_user_state(target)
        return web.json_response({"ok": True, "message": f"✅ Пользователь {target} сброшен."})


async def api_admin_reset_all(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    admin_id, error = await _require_admin(request, payload)
    if error:
        return web.json_response({"ok": False, "error": error}, status=403)
    await reset_all_users_state()
    return web.json_response({"ok": True, "message": "✅ Все пользователи сброшены."})


def build_routes(static_dir: Path) -> list[Any]:
    # Reserved for additional static routes if needed.
    return []
