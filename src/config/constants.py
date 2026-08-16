"""Shared constants that do not contain secrets."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiEndpoints:
    openrouter_chat: str = "https://openrouter.ai/api/v1/chat/completions"
    openai_chat: str = "https://api.openai.com/v1/chat/completions"
    gemini_chat: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    groq_chat: str = "https://api.groq.com/openai/v1/chat/completions"
    huggingface_chat: str = "https://router.huggingface.co/v1/chat/completions"
    venice_chat: str = "https://api.venice.ai/api/v1/chat/completions"
    venice_images: str = "https://api.venice.ai/api/v1/images/generations"

    openrouter_models: str = "https://openrouter.ai/api/v1/models"
    openai_models: str = "https://api.openai.com/v1/models"
    gemini_models: str = "https://generativelanguage.googleapis.com/v1beta/models"
    groq_models: str = "https://api.groq.com/openai/v1/models"
    huggingface_models: str = "https://router.huggingface.co/v1/models"
    venice_models: str = "https://api.venice.ai/api/v1/models"


@dataclass(frozen=True)
class ModelPricing:
    prompt: float | None
    completion: float | None


API_ENDPOINTS = ApiEndpoints()

PROVIDER_LABELS: dict[str, str] = {
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "groq": "Groq",
    "venice": "Venice AI",
    "huggingface": "HuggingFace",
}

PROVIDER_LIST_ENABLED: dict[str, bool] = {
    "openrouter": True,
    "openai": False,  # Проверка не проводилась, убери комментарий что бы появилась кнопка
    "gemini": True,
    "groq": False,  # Проверка не проводилась, убери комментарий что бы появилась кнопка
    "venice": False,  # Все модели платные, только ручной ввод
    "huggingface": False,
}

TELEGRAM_MAX_MESSAGE_LENGTH: int = 4096

MODEL_MAX_TOKENS: dict[str, int] = {
    "gpt-4": 8192,
    "gpt-4o": 8192,
    "gpt-3.5": 4096,
    "claude-opus": 200000,
    "claude-sonnet": 200000,
    "claude-haiku": 200000,
    "gemini": 1000000,
    "llama": 8192,
    "kimi-k2": 256000,
}

DEFAULT_MODEL_MAX_TOKENS: int = 4096

MODEL_PRICING_PER_1K: dict[str, ModelPricing] = {
    "gpt-4": ModelPricing(prompt=0.03, completion=0.06),
    "gpt-3.5": ModelPricing(prompt=0.0015, completion=0.002),
}


class StatsDisplay:
    DISABLED = "disabled"
    COMPACT = "compact"
    FULL = "full"


DEFAULT_STATS_DISPLAY = StatsDisplay.FULL
STATS_DISPLAY_OPTIONS = [StatsDisplay.DISABLED, StatsDisplay.COMPACT, StatsDisplay.FULL]

DEFAULT_MODEL: str = ""
DEFAULT_SYSTEM_PROMPT: str = "Ты — полезный и дружелюбный AI-ассистент."
DEFAULT_CONTEXT_LIMIT: int = 10
CONTEXT_LIMIT_OPTIONS: list[int] = [5, 10, 20]
DEFAULT_THEME: str = "dark"
THEME_OPTIONS: list[str] = ["dark", "light", "midnight", "aurora", "sunset", "custom"]
