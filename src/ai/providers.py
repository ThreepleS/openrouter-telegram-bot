"""Provider detection, model ID normalization and request payload helpers."""

from src.config import (
    API_ENDPOINTS,
    DEFAULT_MODEL_MAX_TOKENS,
    MODEL_MAX_TOKENS,
    MODEL_PRICING_PER_1K,
    Settings,
)
from src.config.env import get_settings


def get_settings_cached() -> Settings:
    return get_settings()


def provider_label(provider: str) -> str:
    from src.config.constants import PROVIDER_LABELS

    return PROVIDER_LABELS.get(provider, provider)


def provider_env_key(provider: str) -> str:
    settings = get_settings_cached()
    env_keys = {
        "openai": settings.openai_api_key,
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "huggingface": settings.huggingface_api_key,
        "venice": settings.venice_api_key,
    }
    return env_keys.get(provider, "")


def provider_key_hint(provider: str) -> str:
    env_key = provider_env_key(provider)
    if env_key:
        from src.utils.text import shorten_key

        return f"В .env уже задан ключ {provider_label(provider)} {shorten_key(env_key)}, но можно указать другой личный ключ."
    if provider == "openrouter":
        return "Отправь OpenRouter API-ключ."
    return f"Отправь API-ключ {provider_label(provider)}."


def model_id_for_provider(provider: str, model_id: str) -> str:
    prefixes = {
        "openai": "openai:",
        "gemini": "gemini:",
        "groq": "groq:",
        "huggingface": "hf:",
        "venice": "venice:",
    }
    prefix = prefixes.get(provider)
    if prefix and model_id.lower().startswith(prefix):
        return model_id
    if prefix:
        return f"{prefix}{model_id}"
    return model_id


def ensure_model_id_for_provider(provider: str, model_id: str) -> str:
    prefixes = {
        "openai": "openai:",
        "gemini": "gemini:",
        "groq": "groq:",
        "huggingface": "hf:",
        "venice": "venice:",
    }
    prefix = prefixes.get(provider)
    if prefix and model_id.lower().startswith(prefix):
        return model_id
    return model_id_for_provider(provider, model_id)


def model_page_url(provider: str, model_id: str) -> str:
    from urllib.parse import quote

    if provider == "openrouter":
        return f"https://openrouter.ai/{quote(model_id, safe='/:')}"
    if provider == "openai":
        return f"https://platform.openai.com/docs/models/{quote(model_id, safe='/:')}"
    if provider == "gemini":
        return "https://ai.google.dev/gemini-api/docs/models/gemini"
    if provider == "groq":
        return "https://console.groq.com/docs/models"
    if provider == "huggingface":
        return f"https://huggingface.co/{quote(model_id, safe='/')}"
    if provider == "venice":
        return "https://venice.ai/settings/api"
    return ""


def detect_provider(model_id: str) -> str:
    lower = model_id.lower()
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
    if lower.startswith(("gpt-", "o1", "o3", "chatgpt-")):
        return "openai"
    return "openrouter"


def normalize_model_id(provider: str, model_id: str) -> str:
    prefixes = {
        "openai": "openai:",
        "gemini": "gemini:",
        "groq": "groq:",
        "huggingface": "hf:",
        "venice": "venice:",
    }
    prefix = prefixes.get(provider)
    if prefix and model_id.lower().startswith(prefix):
        return model_id[len(prefix):]
    if provider == "gemini" and model_id.lower().startswith("models/"):
        return model_id[7:]
    return model_id


def get_provider_api_key(provider: str, user_api_key: str, user_api_key_provider: str = "openrouter", db_provider_keys: dict | None = None) -> str:
    settings = get_settings_cached()
    env_keys = {
        "openai": settings.openai_api_key,
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "huggingface": settings.huggingface_api_key,
        "venice": settings.venice_api_key,
    }
    env_key = env_keys.get(provider, "")
    if env_key:
        return env_key
    db_key = (db_provider_keys or {}).get(provider)
    if db_key:
        return db_key
    if user_api_key and user_api_key_provider == provider:
        return user_api_key
    return ""


def build_user_provider_keys(user: dict) -> dict[str, str]:
    if not user:
        return {}
    return {
        "openai": user.get("api_key_openai", "") or "",
        "gemini": user.get("api_key_gemini", "") or "",
        "groq": user.get("api_key_groq", "") or "",
        "huggingface": user.get("api_key_huggingface", "") or "",
        "venice": user.get("api_key_venice", "") or "",
    }


def normalize_content(content) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif "content" in item:
                    parts.append(str(item["content"]))
        return "\n".join(part for part in parts if part).strip()
    return str(content or "").strip()


def model_supports_vision(provider: str, model_id: str) -> bool:
    """Check if model supports image input based on provider and model ID patterns."""
    lower_id = model_id.lower()
    clean_id = lower_id

    # Remove provider prefixes for pattern matching
    for prefix in ["openrouter:", "openai:", "gemini:", "groq:", "hf:", "venice:", "models/"]:
        clean_id = clean_id.removeprefix(prefix)

    # Remove common prefixes that appear in OpenRouter model IDs
    for prefix in ["openai/", "anthropic/", "google/", "meta/", "mistralai/", "qwen/"]:
        clean_id = clean_id.removeprefix(prefix)

    # Image generation models - these do NOT support vision input
    image_gen_patterns = ["flux", "sd-xl", "sd3", "dall-e", "gptimage", "imagen", "anything-v", "kandinsky", "playground", "grok-imagine"]
    if any(pattern in lower_id for pattern in image_gen_patterns):
        return False

    # OpenRouter/OpenAI models - check for vision-capable model patterns
    if provider in {"openrouter", "openai"}:
        vision_patterns = [
            "gpt-4-vision", "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-turbo-2024",
            "claude-3", "claude-sonet", "claude-opus", "claude-v",
            "gemini-1.5", "gemini-2.0", "gemini-flash", "gemini-pro", "gemini-vision",
            "gemma-3", "gemma-4",
            "qwen-vl", "qwen2-vl", "llava", "bakllava", "vl",
            "pixtral", "mistral-vision",
        ]
        return any(pattern in clean_id for pattern in vision_patterns)

    # Venice AI - most recent chat models support vision
    if provider == "venice":
        vision_patterns = [
            "claude", "gpt", "gemini", "kimi", "llama", "mistral", "qwen", "pixtral", "llava", "bakllava"
        ]
        return any(pattern in clean_id for pattern in vision_patterns)

    # Gemini models - all recent Gemini models support vision
    if provider == "gemini":
        return True

    # Groq - limited vision support (Llama 3.2 vision)
    if provider == "groq":
        return "llama-3.2" in clean_id

    # HuggingFace - depends on specific model, conservatively false for most
    if provider == "huggingface":
        vision_models = ["llava", "qwen-vl", "qwen2-vl", "bakllava", "cogvlm", "deepseek-vl", "pixtral"]
        return any(vm in clean_id for vm in vision_models)

    return False


def requires_anthropic_format(provider: str, model_id: str) -> bool:
    """Check if model uses Anthropic-compatible format instead of OpenAI."""
    if provider != "openrouter":
        return False
    lower_id = model_id.lower()
    return "claude" in lower_id


def build_openai_messages(system_prompt: str, messages: list[dict], provider: str = "openrouter", model_id: str = "") -> list[dict]:
    converted = [{"role": "system", "content": system_prompt}]
    for message in messages:
        content = message.get("content") or ""
        image_bytes = message.get("image_bytes") or message.get("image_url")
        if image_bytes:
            mime = message.get("image_mime") or "image/jpeg"
            converted.append({
                "role": message.get("role", "user"),
                "content": [
                    {"type": "text", "text": content},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_bytes}"}},
                ],
            })
        elif content:
            converted.append({"role": message.get("role", "user"), "content": content})
    return converted


def build_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Build messages for Anthropic (Claude) models using native Anthropic format."""
    formatted = []
    for message in messages:
        content = message.get("content") or ""
        image_bytes = message.get("image_bytes") or message.get("image_url")
        if image_bytes:
            parts = []
            if content:
                parts.append({"type": "text", "text": content})
            mime = message.get("image_mime") or "image/jpeg"
            parts.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": image_bytes}})
            formatted.append({"role": message.get("role", "user"), "content": parts})
        elif content:
            formatted.append({"role": message.get("role", "user"), "content": content})
    return formatted


def build_hf_input(system_prompt: str, messages: list[dict]) -> str:
    parts: list[str] = []
    if system_prompt:
        parts.append(system_prompt)
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content") or ""
        if content:
            parts.append(f"{role.capitalize()}: {content}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


def build_gemini_contents(messages: list[dict], provider: str = "gemini", model_id: str = "") -> list[dict]:
    supports_vision = model_supports_vision(provider, model_id)
    contents = []
    for message in messages:
        role = "model" if message.get("role") in ("assistant", "bot") else "user"
        parts = []
        content = message.get("content") or ""
        image_bytes = message.get("image_bytes") or message.get("image_url")
        
        if image_bytes and supports_vision:
            if content:
                parts.append({"text": content})
            mime = message.get("image_mime") or "image/jpeg"
            parts.append({"inline_data": {"mime_type": mime, "data": image_bytes}})
        elif image_bytes and not supports_vision:
            if content.strip():
                content = f"{content}\n\n[Пользователь ранее отправил изображение]"
            else:
                content = "[Пользователь отправил изображение без подписи]"
            if content:
                parts.append({"text": content})
        else:
            if content:
                parts.append({"text": content})
        
        if parts:
            contents.append({"role": role, "parts": parts})
    return contents


def extract_openai_content(data: dict) -> tuple[str | None, list[str]]:
    choices = data.get("choices") or []
    if not choices:
        return "", []
    
    message = choices[0].get("message", {})
    content = message.get("content")
    
    images = []
    raw_images = message.get("images") or []
    for img in raw_images:
        img_url = img.get("image_url", {}) if isinstance(img, dict) else {}
        if isinstance(img_url, dict):
            url = img_url.get("url", "")
            if url and url.startswith("data:image/"):
                b64_data = url.split(",", 1)[-1]
                images.append(b64_data)
    
    text = normalize_content(content)
    return text, images


def extract_gemini_content(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = []
    for part in parts:
        if isinstance(part, dict):
            if part.get("thought"):
                continue
            if "text" in part:
                texts.append(part["text"])
        elif isinstance(part, str):
            texts.append(part)
    return "\n".join(text for text in texts if text).strip()


def extract_usage(data: dict, provider: str) -> dict:
    if provider == "gemini":
        metadata = data.get("usageMetadata", {})
        return {
            "prompt_tokens": metadata.get("promptTokenCount"),
            "completion_tokens": metadata.get("candidatesTokenCount"),
            "total_tokens": metadata.get("totalTokenCount"),
        }
    return data.get("usage", {}) if isinstance(data, dict) else {}


def get_model_pricing(model_id: str):
    model_key = model_id.split(":")[0].lower()
    for known, prices in MODEL_PRICING_PER_1K.items():
        if known in model_key:
            return prices
    return None


def format_usage_stats(model_id: str, usage: dict, elapsed: float, compact: bool = False) -> str:
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    if compact:
        parts = []
        if total_tokens:
            parts.append(f"📊 {total_tokens} токен")
        parts.append(f"⏱ {elapsed:.1f}с")

        pricing = get_model_pricing(model_id)
        if pricing and prompt_tokens is not None and completion_tokens is not None:
            cost = (
                prompt_tokens / 1000 * pricing.prompt
                + completion_tokens / 1000 * pricing.completion
            )
            if cost > 0:
                parts.append(f"💰 ${cost:.6f}")
        return " | ".join(part for part in parts if part)

    lines = ["📊 Статистика запроса:"]
    if prompt_tokens is not None:
        lines.append(f"• Токенов контекста: {prompt_tokens}")
    if completion_tokens is not None:
        lines.append(f"• Токенов ответа: {completion_tokens}")
    if total_tokens is not None:
        lines.append(f"• Всего использовано: {total_tokens}")

    lines.append(f"• Время ответа: {elapsed:.1f} сек")

    pricing = get_model_pricing(model_id)
    if pricing and prompt_tokens is not None and completion_tokens is not None:
        cost = (
            prompt_tokens / 1000 * pricing.prompt
            + completion_tokens / 1000 * pricing.completion
        )
        if cost > 0:
            lines.append(f"• Стоимость: ${cost:.6f}")
    return "\n".join(lines)


def is_venice_image_model(model_id: str) -> bool:
    lower_id = model_id.lower()
    for prefix in ["venice:", "openrouter:", "openai:", "gemini:", "groq:", "hf:", "models/"]:
        lower_id = lower_id.removeprefix(prefix)
    image_gen_patterns = [
        "flux", "sd-xl", "sd3", "dall-e", "gptimage", "imagen",
        "anything-v", "kandinsky", "playground", "grok-imagine",
        "stable-diffusion", "midjourney", "ideogram",
    ]
    return any(pattern in lower_id for pattern in image_gen_patterns)


def get_model_context_limit(model_id: str) -> int:
    model_key = model_id.split(":")[0].lower()
    for known, limit in MODEL_MAX_TOKENS.items():
        if known in model_key:
            return limit
    return DEFAULT_MODEL_MAX_TOKENS
