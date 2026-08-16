"""Environment loading and typed application settings."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_id: int
    db_path: Path
    supabase_url: str
    supabase_service_role_key: str
    use_supabase_db: bool
    proxy: str | None
    openai_api_key: str
    gemini_api_key: str
    groq_api_key: str
    huggingface_api_key: str
    venice_api_key: str
    web_app_host: str
    web_app_port: int
    web_app_url: str
    web_app_dev: bool


def load_environment() -> None:
    """Load .env once. Repeated calls are safe because dotenv does not override by default."""
    load_dotenv()


def _get_int(name: str, default: int = 0) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw_value!r}") from exc


def get_settings() -> Settings:
    load_environment()
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        admin_id=_get_int("ADMIN_ID"),
        db_path=Path(os.getenv("DB_PATH", "bot.db").strip() or "bot.db"),
        supabase_url=os.getenv("SUPABASE_URL", "https://amhszfvqruzpydqyjlya.supabase.co").strip(),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        use_supabase_db=os.getenv("USE_SUPABASE_DB", "0").strip().lower() in ("1", "true", "yes"),
        proxy=os.getenv("PROXY") or None,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        huggingface_api_key=os.getenv("HF_API_KEY", "").strip(),
        venice_api_key=os.getenv("VENICE_API_KEY", "").strip(),
        web_app_host=os.getenv("WEB_APP_HOST", "0.0.0.0").strip() or "0.0.0.0",
        web_app_port=_get_int("WEB_APP_PORT", 8080),
        web_app_url=os.getenv("WEB_APP_URL", "").strip(),
        web_app_dev=os.getenv("WEB_APP_DEV", "").strip().lower() in ("1", "true", "yes"),
    )
