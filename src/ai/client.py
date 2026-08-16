"""HTTP client for AI providers."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback

import aiohttp
from urllib.parse import urlencode

from src.ai.models import is_openrouter_free_model, normalize_provider_model
from src.ai.providers import (
    API_ENDPOINTS,
    build_gemini_contents,
    build_openai_messages,
    build_user_provider_keys,
    detect_provider,
    extract_gemini_content,
    extract_openai_content,
    extract_usage,
    get_provider_api_key,
    model_id_for_provider,
    model_supports_vision,
    normalize_model_id,
    provider_label,
)


async def post_json_with_retries(
    url: str,
    payload: dict,
    headers: dict,
    provider: str,
    max_attempts: int = 3,
    timeout_total: float = 300.0,
) -> tuple[int | None, dict | str]:
    base_delay = 1.0

    for attempt in range(1, max_attempts + 1):
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout_total),
                ) as response:
                    raw_text = await response.text()
                    try:
                        data = await response.json()
                    except Exception:
                        logging.error("%s returned non-JSON response: status=%s body=%s", provider, response.status, raw_text[:2000] if raw_text else "")
                        if response.status != 200:
                            return response.status, raw_text or f"HTTP {response.status}"
                        return response.status, "❌ Неверный формат ответа от API."

                    if response.status != 200:
                        error = data.get("error", {}) if isinstance(data, dict) else {}
                        if isinstance(error, dict):
                            message = error.get("message", str(data))
                        else:
                            message = str(error) or str(data)

                        if response.status == 429 and attempt < max_attempts:
                            retry_after = None
                            if isinstance(error, dict):
                                metadata = error.get("metadata", {})
                                retry_after = metadata.get("retry_after_seconds") or metadata.get("retry_after_seconds_raw")
                            retry_after = retry_after or response.headers.get("Retry-After")
                            try:
                                delay = float(retry_after) if retry_after is not None else base_delay * (2 ** (attempt - 1))
                            except Exception:
                                delay = base_delay * (2 ** (attempt - 1))
                            logging.info("%s 429 received, attempt %s/%s, sleeping %s seconds", provider, attempt, max_attempts, delay)
                            await asyncio.sleep(delay)
                            continue

                        return response.status, message

                    return 200, data

        except asyncio.TimeoutError:
            logging.error("Timeout when calling %s (attempt %s/%s)", provider, attempt, max_attempts)
            if attempt >= max_attempts:
                return None, "❌ Запрос к API превысил таймаут. Попробуй позже."
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
        except aiohttp.ClientError as e:
            logging.error("aiohttp ClientError when calling %s (attempt %s/%s): %s", provider, attempt, max_attempts, e)
            if attempt >= max_attempts:
                return None, "❌ Не удалось подключиться к API. Проверь интернет, VPN/прокси и доступность сервиса."
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
        except Exception as e:
            logging.exception("Unexpected error when calling %s: %s", provider, e)
            return None, "❌ Произошла непредвиденная ошибка при запросе к API."

    return None, "❌ Неизвестная ошибка при запросе к API."


async def call_ai_api(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
    user_api_key_provider: str = "openrouter",
    db_provider_keys: dict | None = None,
    max_attempts: int = 3,
    timeout_total: float = 300.0,
) -> tuple[str | None, int | None, str | None, dict, list[str]]:
    provider = detect_provider(model)
    normalized_model = normalize_model_id(provider, model)
    provider_key = get_provider_api_key(provider, api_key, user_api_key_provider, db_provider_keys)

    if not provider_key:
        if provider == "openai":
            hint = "укажи OPENAI_API_KEY в .env"
        elif provider == "gemini":
            hint = "укажи GEMINI_API_KEY в .env"
        elif provider == "groq":
            hint = "укажи GROQ_API_KEY в .env"
        elif provider == "huggingface":
            hint = "укажи HF_API_KEY в .env"
        elif provider == "venice":
            hint = "укажи VENICE_API_KEY в .env"
        else:
            hint = "отправь API-ключ OpenRouter через /start"
        return None, 401, f"❌ Не указан API-ключ для {provider}. {hint}.", {}

    if provider == "gemini":
        url = API_ENDPOINTS.gemini_chat.format(model=normalized_model)
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": provider_key,
        }
        payload = {
            "contents": build_gemini_contents(messages, provider, normalized_model),
            "system_instruction": {"parts": [{"text": system_prompt}]},
        }
    elif provider == "openai":
        url = API_ENDPOINTS.openai_chat
        headers = {
            "Authorization": f"Bearer {provider_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": normalized_model,
            "messages": build_openai_messages(system_prompt, messages, provider, normalized_model),
        }
    elif provider == "groq":
        url = API_ENDPOINTS.groq_chat
        headers = {
            "Authorization": f"Bearer {provider_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": normalized_model,
            "messages": build_openai_messages(system_prompt, messages, provider, normalized_model),
        }
    elif provider == "huggingface":
        url = "https://router.huggingface.co/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": normalized_model,
            "messages": build_openai_messages(system_prompt, messages, provider, normalized_model),
            "max_tokens": 2048,
            "temperature": 0.7,
        }
    elif provider == "venice":
        url = API_ENDPOINTS.venice_chat
        headers = {
            "Authorization": f"Bearer {provider_key}",
            "Content-Type": "application/json",
        }
        built_messages = build_openai_messages(system_prompt, messages, provider, normalized_model)
        payload = {
            "model": normalized_model,
            "messages": built_messages,
        }
    else:
        url = API_ENDPOINTS.openrouter_chat
        headers = {
            "Authorization": f"Bearer {provider_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://t.me/openrouter_bot",
            "X-Title": "OpenRouter Telegram Bot",
        }
        built_messages = build_openai_messages(system_prompt, messages, provider, normalized_model)
        payload = {
            "model": normalized_model,
            "messages": built_messages,
        }

    status, result = await post_json_with_retries(url, payload, headers, provider, max_attempts=max_attempts, timeout_total=timeout_total)
    if status != 200:
        logging.error("API error for model %s: status=%s error=%s", normalized_model, status, str(result)[:500])
        return None, status, f"❌ Ошибка API {provider.upper()} ({status}): {result}", {}, []

    if provider == "gemini":
        content = extract_gemini_content(result)
        images = []
    elif provider == "huggingface":
        content = extract_openai_content(result)[0]
        images = []
    else:
        content, images = extract_openai_content(result)

    if not content and not images:
        logging.warning("%s returned empty content: %s", provider, result)
        return None, 200, "❌ Модель вернула пустой ответ.", {}, []

    return content, 200, None, extract_usage(result, provider), images


async def get_json_with_retries(url: str, headers: dict, provider: str) -> tuple[int | None, dict | str]:
    max_attempts = 3
    base_delay = 1.0
    timeout_total = 120

    for attempt in range(1, max_attempts + 1):
        try:
            async with aiohttp.ClientSession(trust_env=True) as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout_total),
                ) as response:
                    raw_text = await response.text()
                    try:
                        data = await response.json()
                    except Exception:
                        logging.error("%s returned non-JSON response: status=%s body=%s", provider, response.status, raw_text[:2000] if raw_text else "")
                        if response.status != 200:
                            return response.status, raw_text or f"HTTP {response.status}"
                        return response.status, "❌ Неверный формат ответа от API."

                    if response.status != 200:
                        error = data.get("error", {}) if isinstance(data, dict) else {}
                        if isinstance(error, dict):
                            message = error.get("message", str(data))
                        else:
                            message = str(error) or str(data)
                        return response.status, message

                    return 200, data
        except asyncio.TimeoutError:
            logging.error("Timeout when GET calling %s (attempt %s/%s)", provider, attempt, max_attempts)
            if attempt >= max_attempts:
                return None, "❌ Запрос к API превысил таймаут. Попробуй позже."
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
        except aiohttp.ClientError as e:
            logging.error("aiohttp ClientError when GET calling %s (attempt %s/%s): %s", provider, attempt, max_attempts, e)
            if attempt >= max_attempts:
                return None, "❌ Не удалось подключиться к API. Проверь интернет, VPN/прокси и доступность сервиса."
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
        except Exception as e:
            logging.exception("Unexpected error when GET calling %s: %s", provider, e)
            return None, "❌ Произошла непредвиденная ошибка при запросе к API."

    return None, "❌ Неизвестная ошибка при запросе к API."


def gemini_model_id(raw_model: dict) -> str:
    return str(
        raw_model.get("baseModelId")
        or raw_model.get("id")
        or raw_model.get("name")
        or raw_model.get("model")
        or ""
    )


def gemini_model_supports_generate_content(raw_model: dict) -> bool:
    methods = raw_model.get("supportedGenerationMethods") or raw_model.get("supported_generation_methods") or []
    actions = raw_model.get("supportedActions") or raw_model.get("supported_actions") or []
    capabilities = [*methods, *actions]
    if capabilities:
        return "generateContent" in capabilities

    model_id = gemini_model_id(raw_model).lower()
    return not model_id.startswith(("embedding", "text-embedding", "aqa"))


async def fetch_gemini_models(key: str, check_availability: bool = False) -> tuple[list[dict], str | None]:
    all_raw_models: list[dict] = []
    page_token = ""
    url = API_ENDPOINTS.gemini_models
    headers = {"x-goog-api-key": key}

    while True:
        params = {"pageSize": "1000"}
        if page_token:
            params["pageToken"] = page_token

        status, result = await get_json_with_retries(f"{url}?{urlencode(params)}", headers, "gemini")
        if status != 200:
            return [], f"Ошибка API Gemini ({status}): {result}"
        if not isinstance(result, dict):
            return [], "API Gemini вернул неожиданный формат ответа."

        raw_models = result.get("models") or result.get("data", [])
        if not isinstance(raw_models, list):
            return [], "API Gemini вернул models не списком."

        all_raw_models.extend(model for model in raw_models if isinstance(model, dict))
        page_token = str(result.get("nextPageToken") or "")
        if not page_token:
            break

    # Normalize models
    normalized_all = []
    for raw_model in all_raw_models:
        if not gemini_model_supports_generate_content(raw_model):
            continue
        model = normalize_provider_model("gemini", raw_model)
        if model:
            normalized_all.append(model)

    if not check_availability:
        normalized_all.sort(key=lambda item: item["id"].lower())
        return normalized_all, None

    # Ping models to verify availability (limit to first 30 to avoid long wait)
    working_models = []
    for model in normalized_all[:30]:
        model_id = model_id_for_provider("gemini", model["id"])
        _, _, error, _, _ = await call_ai_api(
            api_key=key,
            model=model_id,
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Ping"}],
            user_api_key_provider="gemini",
            max_attempts=1,
            timeout_total=5.0,
        )
        if not error:
            working_models.append(model)

    working_models.sort(key=lambda item: item["id"].lower())
    return working_models, None


async def fetch_provider_models(provider: str, api_key: str, api_key_provider: str, db_provider_keys: dict | None = None, check_availability: bool = False, show_free_only: bool = False) -> tuple[list[dict], str | None]:
    key = get_provider_api_key(provider, api_key, api_key_provider, db_provider_keys)
    if not key:
        return [], f"Не указан API-ключ {provider_label(provider)}."

    if provider == "gemini":
        return await fetch_gemini_models(key, check_availability=check_availability)

    headers: dict[str, str] = {}
    url = ""

    if provider == "openrouter":
        url = API_ENDPOINTS.openrouter_models
        headers = {
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://t.me/openrouter_bot",
            "X-Title": "OpenRouter Telegram Bot",
        }
    elif provider == "openai":
        url = API_ENDPOINTS.openai_models
        headers = {"Authorization": f"Bearer {key}"}
    elif provider == "groq":
        url = API_ENDPOINTS.groq_models
        headers = {"Authorization": f"Bearer {key}"}
    elif provider == "huggingface":
        url = API_ENDPOINTS.huggingface_models
        headers = {"Authorization": f"Bearer {key}"}
    elif provider == "venice":
        url = API_ENDPOINTS.venice_models
        headers = {"Authorization": f"Bearer {key}"}

    status, result = await get_json_with_retries(url, headers, provider)
    if status != 200:
        return [], f"Ошибка API {provider_label(provider)} ({status}): {result}"
    if not isinstance(result, dict):
        return [], "API вернул неожиданный формат ответа."

    raw_models = result.get("data", [])
    if not isinstance(raw_models, list):
        return [], "API вернул data не списком."

    normalized = []
    for raw_model in raw_models:
        model = normalize_provider_model(provider, raw_model)
        if model:
            if show_free_only and provider == "openrouter" and not is_openrouter_free_model(raw_model):
                continue
            normalized.append(model)

    normalized.sort(key=lambda item: item["id"].lower())

    if provider == "gemini":
        return normalized, None

    return normalized, None


async def fetch_provider_model_detail(
    provider: str,
    model_id: str,
    api_key: str,
    api_key_provider: str = "openrouter",
    db_provider_keys: dict | None = None,
) -> tuple[dict | None, str | None]:
    """Fetch details for a single model by searching the provider model list and normalizing the match."""
    if provider != "openrouter":
        return None, None

    models, err = await fetch_provider_models(provider, api_key, api_key_provider, db_provider_keys)
    if err:
        return None, None

    for m in models:
        if m.get("id") == model_id:
            return m, None

    if "/" not in model_id:
        for m in models:
            mid = m.get("id", "")
            if mid.endswith(f"/{model_id}"):
                return m, None

    return None, None


async def ping_model(api_key: str, model_id: str, system_prompt: str, user_api_key_provider: str = "openrouter", db_provider_keys: dict | None = None) -> tuple[str, str]:
    import time

    provider = detect_provider(model_id)
    if provider == "openrouter" and not model_id.endswith(":free"):
        return "skip", "⚠️ За проверку платных моделей взымается плата. Модель не проверялась."
    if provider == "venice":
        return "skip", "⚠️ Все модели Venice AI платные. Проверка не проводится."

    start_ts = time.monotonic()
    _, status, error_message, _, _ = await call_ai_api(
        api_key=api_key,
        model=model_id,
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": "Ping"}],
        user_api_key_provider=user_api_key_provider,
        db_provider_keys=db_provider_keys,
        max_attempts=1,
        timeout_total=10.0,
    )
    elapsed = time.monotonic() - start_ts
    if error_message:
        return "error", f"{error_message} ({round(elapsed, 1)}s)"
    return "ok", f"✅ OK ({round(elapsed, 1)}s)"


async def call_venice_image_api(
    api_key: str,
    model: str,
    prompt: str,
    user_api_key_provider: str = "openrouter",
    db_provider_keys: dict | None = None,
    size: str = "1024x1024",
) -> tuple[str | None, int | None, str | None, dict, list[str]]:
    provider = "venice"
    normalized_model = normalize_model_id(provider, model)
    provider_key = get_provider_api_key(provider, api_key, user_api_key_provider, db_provider_keys)

    if not provider_key:
        return None, 401, "❌ Не указан VENICE_API_KEY для генерации изображений. Укажи ключ в настройках.", {}, []

    url = API_ENDPOINTS.venice_images
    headers = {
        "Authorization": f"Bearer {provider_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": normalized_model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json",
    }
    status, result = await post_json_with_retries(url, payload, headers, "venice", timeout_total=120.0)
    if status != 200:
        logging.error("Venice image API error for model %s: status=%s error=%s", normalized_model, status, str(result)[:500])
        return None, status, f"❌ Ошибка генерации изображения Venice ({status}): {result}", {}, []

    images = []
    data = result.get("data") if isinstance(result, dict) else None
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("b64_json"):
                images.append(item["b64_json"])

    if not images:
        return None, 200, "❌ Модель не вернула изображение.", {}, []

    return "[Изображение сгенерировано]", 200, None, {}, images


async def _iter_sse_lines(response: aiohttp.ClientResponse):
    """Yield raw `data:` payloads from a Server-Sent-Events stream."""
    buffer = b""
    async for chunk in response.content.iter_chunked(4096):
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.strip()
            if not line or not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                return
            yield data


async def stream_ai_api(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
    user_api_key_provider: str = "openrouter",
    db_provider_keys: dict | None = None,
    timeout_total: float = 300.0,
) -> "asyncio.AsyncIterator[dict]":
    """Stream tokens as they arrive.

    Yields dicts:
      {"type": "delta", "text": "<token>"}
      {"type": "error", "message": "<text>"}
      {"type": "done", "usage": {...}}
    The accumulated content is reassembled by the caller.
    """
    provider = detect_provider(model)
    normalized_model = normalize_model_id(provider, model)
    provider_key = get_provider_api_key(provider, api_key, user_api_key_provider, db_provider_keys)

    if not provider_key:
        if provider == "openai":
            hint = "укажи OPENAI_API_KEY в .env"
        elif provider == "gemini":
            hint = "укажи GEMINI_API_KEY в .env"
        elif provider == "groq":
            hint = "укажи GROQ_API_KEY в .env"
        elif provider == "huggingface":
            hint = "укажи HF_API_KEY в .env"
        elif provider == "venice":
            hint = "укажи VENICE_API_KEY в .env"
        else:
            hint = "отправь API-ключ OpenRouter через /start"
        yield {"type": "error", "message": f"❌ Не указан API-ключ для {provider}. {hint}."}
        return

    if provider == "gemini":
        url = API_ENDPOINTS.gemini_chat.format(model=normalized_model).replace(":generateContent", ":streamGenerateContent") + "?alt=sse"
        headers = {"Content-Type": "application/json", "x-goog-api-key": provider_key}
        payload = {
            "contents": build_gemini_contents(messages, provider, normalized_model),
            "system_instruction": {"parts": [{"text": system_prompt}]},
        }
    else:
        url = {
            "openai": API_ENDPOINTS.openai_chat,
            "groq": API_ENDPOINTS.groq_chat,
            "huggingface": "https://router.huggingface.co/v1/chat/completions",
            "venice": API_ENDPOINTS.venice_chat,
        }.get(provider, API_ENDPOINTS.openrouter_chat)
        auth_header = {"Authorization": f"Bearer {provider_key}", "Content-Type": "application/json"}
        if provider == "openrouter":
            auth_header["HTTP-Referer"] = "https://t.me/openrouter_bot"
            auth_header["X-Title"] = "OpenRouter Telegram Bot"
        headers = auth_header
        payload = {
            "model": normalized_model,
            "messages": build_openai_messages(system_prompt, messages, provider, normalized_model),
            "stream": True,
            "stream_options": {"include_usage": True},
        }

    timeout = aiohttp.ClientTimeout(total=timeout_total)
    async with aiohttp.ClientSession(trust_env=True) as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                if response.status != 200:
                    raw = await response.text()
                    yield {"type": "error", "message": f"❌ Ошибка API {provider.upper()} ({response.status}): {raw[:500]}"}
                    return

                usage: dict = {}
                prev_text = ""
                async for data in _iter_sse_lines(response):
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue

                    if provider == "gemini":
                        text_now = extract_gemini_content(obj)
                        # Gemini SSE chunks may be cumulative (full text each
                        # time) OR incremental (only the new tail). Handle both
                        # robustly so we never drop or duplicate content.
                        if text_now.startswith(prev_text):
                            delta = text_now[len(prev_text):]
                            prev_text = text_now
                        elif text_now and not prev_text:
                            delta = text_now
                            prev_text = text_now
                        else:
                            # Incremental chunk: take the fresh text as-is.
                            # Gemini already includes the separating space in
                            # the chunk when needed, so we must NOT invent one
                            # (that caused duplicated/extra spaces) nor drop one.
                            delta = text_now
                            prev_text = prev_text + delta
                    else:
                        choices = obj.get("choices") or []
                        delta = (choices[0].get("delta") or {}).get("content") or "" if choices else ""

                    if delta:
                        yield {"type": "delta", "text": delta}

                    if provider == "gemini" and "usageMetadata" in obj:
                        usage = extract_usage(obj, "gemini")
                    elif "usage" in obj and obj.get("usage"):
                        usage = obj["usage"]
        except asyncio.TimeoutError:
            yield {"type": "error", "message": "❌ Запрос к API превысил таймаут. Попробуй позже."}
            return
        except aiohttp.ClientError as e:
            yield {"type": "error", "message": f"❌ Не удалось подключиться к API: {e}"}
            return

    yield {"type": "done", "usage": usage}
