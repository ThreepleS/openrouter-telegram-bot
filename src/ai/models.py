"""External model discovery helpers."""

import hashlib

from src.ai.providers import provider_label

OPENROUTER_PARAMETER_EMOJIS = {
    "image": "🖼️",
    "audio": "🔊",
    "tools": "🛠️",
    "video": "🎬",
}


def _format_openrouter_price(price_str: str | None) -> str | None:
    if not price_str:
        return None
    try:
        price = float(price_str)
        per_m = price * 100000
        if per_m == 0:
            return "Free"
        if per_m >= 1:
            return f"${per_m:.2f}/M"
        return f"${per_m:.4f}/M"
    except (ValueError, TypeError):
        return None


def _format_price_compact(price_str: str | None) -> str | None:
    """Return compact price string like '0.05/M' without $ prefix."""
    if not price_str:
        return None
    try:
        price = float(price_str)
        per_m = price * 100000
        if per_m == 0:
            return "Free"
        s = f"{per_m:.4f}".rstrip('0').rstrip('.')
        return f"{s}/M"
    except (ValueError, TypeError):
        return None


def _compact_context(ctx: int) -> str:
    if ctx >= 1000000:
        return f"{ctx // 1000000}M ctx"
    if ctx >= 1000:
        return f"{ctx // 1000}k ctx"
    return f"{ctx} ctx"


_MODALITY_NAMES = {"I": "image", "T": "text", "A": "audio", "V": "video"}


def _format_modalities_plain(in_str: str, out_str: str) -> str:
    """Render modality codes (I/T/A/V) as human text: 'Input: image, text TO text'."""
    def names(codes: str) -> str:
        if not codes:
            return "—"
        return ", ".join(_MODALITY_NAMES.get(c, c.lower()) for c in codes)

    return f"Input: {names(in_str)} TO {names(out_str)}"


def _plain_mod_names(codes: str) -> str:
    if not codes or codes == "—":
        return ""
    return ", ".join(_MODALITY_NAMES.get(c, c.lower()) for c in codes)


def is_openrouter_free_model(model: dict) -> bool:
    model_id = str(model.get("id") or "")
    pricing = model.get("pricing") or {}
    prompt_price = pricing.get("prompt")
    return model_id.endswith(":free") or str(prompt_price).lower() == "0"


def is_openrouter_paid_model(model: dict) -> bool:
    model_id = str(model.get("id") or "")
    return not model_id.endswith(":free")


def normalize_provider_model_id(provider: str, model_id: str) -> str:
    if provider == "gemini":
        return model_id.removeprefix("models/")
    if provider == "venice":
        # Remove venice: prefix if present (in any case)
        lower_id = model_id.lower()
        while lower_id.startswith("venice:"):
            model_id = model_id[7:]  # Remove "venice:" prefix (7 chars)
            lower_id = model_id.lower()
        return model_id
    return model_id


def normalize_provider_model(provider: str, model: dict) -> dict:
    if provider == "gemini":
        raw_id = str(model.get("baseModelId") or model.get("id") or model.get("name") or model.get("model") or "")
    elif provider == "venice":
        # Venice API may return id/name with venice: prefix - extract the actual model id
        raw_id = str(model.get("id") or model.get("name") or model.get("model") or "")
        # Also clean the raw_id in case it contains venice: prefix
    else:
        raw_id = model.get("id") or model.get("name") or model.get("model") or ""
    model_id = normalize_provider_model_id(provider, str(raw_id))
    if not model_id:
        return {}

    display_id = model_id
    if provider == "gemini":
        display_id = display_id.removeprefix("models/")
    elif provider == "venice":
        lower_display = display_id.lower()
        if lower_display.startswith("venice:"):
            display_id = display_id[7:]  # Remove venice: prefix (7 chars)

    context = None
    mod_in = None
    mod_out = None
    price_prompt = None
    price_completion = None
    description = ""

    is_free = (provider == "openrouter" and is_openrouter_free_model(model)) or provider == "gemini"

    meta_parts = []
    if provider == "openrouter":
        context_length = model.get("context_length")
        if context_length:
            context = int(context_length)
            meta_parts.append(_compact_context(context_length))
        architecture = model.get("architecture") or {}
        input_modalities = architecture.get("input_modalities") or []
        output_modalities = architecture.get("output_modalities") or []
        if input_modalities or output_modalities:
            in_str = "".join(m[0].upper() for m in input_modalities) if input_modalities else "—"
            out_str = "".join(m[0].upper() for m in output_modalities) if output_modalities else "—"
            mod_in = _plain_mod_names(in_str)
            mod_out = _plain_mod_names(out_str)
            meta_parts.append(_format_modalities_plain(in_str, out_str))
        pricing = model.get("pricing") or {}
        price_prompt = _format_openrouter_price(pricing.get("prompt"))
        price_completion = _format_openrouter_price(pricing.get("completion"))
    elif provider == "gemini":
        context_tokens = model.get("inputTokenLimit") or model.get("input_token_limit")
        if context_tokens:
            context = int(context_tokens)
            meta_parts.append(_compact_context(context_tokens))
        model_name = (model.get("name") or model.get("baseModelId") or "").lower()
        if "vision" in model_name or "flash" in model_name or "pro" in model_name:
            mod_in = _plain_mod_names("IT"); mod_out = _plain_mod_names("T")
            meta_parts.append(_format_modalities_plain("IT", "T"))
        else:
            mod_in = _plain_mod_names("T"); mod_out = _plain_mod_names("T")
            meta_parts.append(_format_modalities_plain("T", "T"))
    elif provider == "venice":
        spec = model.get("model_spec") or {}
        context_length = model.get("context_length") or spec.get("availableContextTokens")
        if context_length:
            context = int(context_length)
            meta_parts.append(_compact_context(context_length))
        # Модальности: тип модели + возможности из model_spec.capabilities
        caps = spec.get("capabilities") or {}
        model_type = str(model.get("type") or "").lower()
        in_codes, out_codes = ["T"], ["T"]
        if model_type == "image" or "image" in str(spec.get("name") or "").lower() or "flux" in str(model.get("id") or "").lower():
            out_codes = ["I"]
        if caps.get("supportsVision"):
            in_codes = ["I", "T"]
        if caps.get("supportsAudioInput"):
            in_codes.append("A")
        if caps.get("supportsVideoInput"):
            in_codes.append("V")
        in_str = "".join(dict.fromkeys(in_codes))
        out_str = "".join(dict.fromkeys(out_codes))
        mod_in = _plain_mod_names(in_str)
        mod_out = _plain_mod_names(out_str)
        meta_parts.append(_format_modalities_plain(in_str, out_str))
        # Цена за 1M токенов (Venice уже даёт USD за 1M токенов)
        pricing = spec.get("pricing") or {}
        pin = (pricing.get("input") or {}).get("usd")
        pout = (pricing.get("output") or {}).get("usd")
        try:
            if pin is not None:
                price_prompt = f"${float(pin):.2f}/M"
            if pout is not None:
                price_completion = f"${float(pout):.2f}/M"
        except (ValueError, TypeError):
            pass

    return {
        "id": model_id,
        "name": f"{provider_label(provider)} · {display_id}",
        "description": description or model.get("description") or model.get("summary") or "",
        "meta": " | ".join(part for part in meta_parts if part),
        "hash": hashlib.sha1(f"{provider}:{model_id}".encode()).hexdigest()[:16],
        "provider": provider,
        "is_free": is_free,
        "context": context,
        "mod_in": mod_in,
        "mod_out": mod_out,
        "price_prompt": price_prompt,
        "price_completion": price_completion,
    }

