"""SQLite repository for user settings, messages and models.

This is the original local-file backend, kept for backward compatibility when
USE_SUPABASE_DB is not enabled.
"""

from __future__ import annotations

import hashlib
import time

import aiosqlite

from src.config import (
    DEFAULT_CONTEXT_LIMIT,
    DEFAULT_MODEL,
    DEFAULT_STATS_DISPLAY,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_THEME,
)
from src.config.env import get_settings


def _db_path() -> str:
    return str(get_settings().db_path)


async def init_db() -> None:
    db_path = _db_path()
    settings = get_settings()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                api_key TEXT,
                api_key_provider TEXT NOT NULL DEFAULT 'openrouter',
                api_key_openrouter TEXT,
                api_key_openai TEXT,
                api_key_gemini TEXT,
                api_key_groq TEXT,
                api_key_huggingface TEXT,
                api_key_venice TEXT,
                selected_model TEXT NOT NULL DEFAULT '{DEFAULT_MODEL}',
                system_prompt TEXT NOT NULL DEFAULT 'Ты — полезный и дружелюбный AI-ассистент.',
                context_limit INTEGER NOT NULL DEFAULT {DEFAULT_CONTEXT_LIMIT},
                stats_display TEXT NOT NULL DEFAULT '{DEFAULT_STATS_DISPLAY}',
                theme TEXT NOT NULL DEFAULT '{DEFAULT_THEME}',
                notify_sound INTEGER NOT NULL DEFAULT 0,
                notify_vibrate INTEGER NOT NULL DEFAULT 0,
                notify_sound_id TEXT NOT NULL DEFAULT 'chime',
                vib_strength INTEGER NOT NULL DEFAULT 40
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS api_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tokens_used INTEGER NOT NULL,
                timestamp INTEGER NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_models (
                user_id INTEGER NOT NULL,
                model_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                meta TEXT,
                short_id TEXT,
                added_at INTEGER,
                PRIMARY KEY (user_id, model_id)
            )
            """
        )

        await db.commit()

        cursor = await db.execute("PRAGMA table_info(user_models)")
        cols = await cursor.fetchall()
        col_names = [c[1] for c in cols]
        if "short_id" not in col_names:
            try:
                await db.execute("ALTER TABLE user_models ADD COLUMN short_id TEXT")
                await db.commit()
            except Exception:
                pass
        if "added_at" not in col_names:
            try:
                await db.execute("ALTER TABLE user_models ADD COLUMN added_at INTEGER")
                await db.commit()
            except Exception:
                pass
        for _col, _type in (
            ("context", "INTEGER"),
            ("mod_in", "TEXT"),
            ("mod_out", "TEXT"),
            ("price_prompt", "TEXT"),
            ("price_completion", "TEXT"),
            ("description", "TEXT"),
            ("is_free", "INTEGER"),
        ):
            if _col not in col_names:
                try:
                    await db.execute(f"ALTER TABLE user_models ADD COLUMN {_col} {_type}")
                    await db.commit()
                except Exception:
                    pass

        cursor = await db.execute("PRAGMA table_info(users)")
        cols = await cursor.fetchall()
        col_names = [c[1] for c in cols]
        if "stats_display" not in col_names:
            try:
                await db.execute(
                    f"ALTER TABLE users ADD COLUMN stats_display TEXT NOT NULL DEFAULT '{DEFAULT_STATS_DISPLAY}'"
                )
                await db.commit()
            except Exception:
                pass
        if "theme" not in col_names:
            try:
                await db.execute(
                    f"ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT '{DEFAULT_THEME}'"
                )
                await db.commit()
            except Exception:
                pass
        if "notify_sound" not in col_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN notify_sound INTEGER NOT NULL DEFAULT 0")
                await db.commit()
            except Exception:
                pass
        if "notify_vibrate" not in col_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN notify_vibrate INTEGER NOT NULL DEFAULT 0")
                await db.commit()
            except Exception:
                pass
        if "notify_sound_id" not in col_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN notify_sound_id TEXT NOT NULL DEFAULT 'chime'")
                await db.commit()
            except Exception:
                pass
        if "vib_strength" not in col_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN vib_strength INTEGER NOT NULL DEFAULT 40")
                await db.commit()
            except Exception:
                pass
        if "api_key_provider" not in col_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN api_key_provider TEXT NOT NULL DEFAULT 'openrouter'")
                await db.commit()
            except Exception:
                pass
        if "key_mode" not in col_names:
            try:
                await db.execute("ALTER TABLE users ADD COLUMN key_mode TEXT NOT NULL DEFAULT 'manual'")
                await db.commit()
            except Exception:
                pass
        for col in ("api_key_openrouter", "api_key_openai", "api_key_gemini", "api_key_groq", "api_key_huggingface", "api_key_venice"):
            if col not in col_names:
                try:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
                    await db.commit()
                except Exception:
                    pass

        cursor = await db.execute("PRAGMA table_info(messages)")
        cols = await cursor.fetchall()
        col_names = [c[1] for c in cols]
        if "image_url" not in col_names:
            try:
                await db.execute("ALTER TABLE messages ADD COLUMN image_url TEXT")
                await db.commit()
            except Exception:
                pass

        await db.execute(
            "UPDATE users SET api_key_openrouter = COALESCE(NULLIF(api_key, ''), api_key_openrouter) WHERE api_key_provider = 'openrouter' AND api_key_openrouter IS NULL"
        )
        await db.execute(
            "UPDATE users SET api_key_openai = COALESCE(NULLIF(api_key, ''), api_key_openai) WHERE api_key_provider = 'openai' AND api_key_openai IS NULL"
        )
        await db.execute(
            "UPDATE users SET api_key_gemini = COALESCE(NULLIF(api_key, ''), api_key_gemini) WHERE api_key_provider = 'gemini' AND api_key_gemini IS NULL"
        )
        await db.execute(
            "UPDATE users SET api_key_groq = COALESCE(NULLIF(api_key, ''), api_key_groq) WHERE api_key_provider = 'groq' AND api_key_groq IS NULL"
        )
        await db.execute(
            "UPDATE users SET api_key_huggingface = COALESCE(NULLIF(api_key, ''), api_key_huggingface) WHERE api_key_provider = 'huggingface' AND api_key_huggingface IS NULL"
        )
        await db.execute(
            "UPDATE users SET api_key_venice = COALESCE(NULLIF(api_key, ''), api_key_venice) WHERE api_key_provider = 'venice' AND api_key_venice IS NULL"
        )
        await db.commit()

        cursor = await db.execute("PRAGMA table_info(messages)")


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_user(user_id: int, api_key: str, api_key_provider: str = "openrouter") -> None:
    provider_col_map = {
        "openai": "api_key_openai",
        "gemini": "api_key_gemini",
        "groq": "api_key_groq",
        "huggingface": "api_key_huggingface",
        "venice": "api_key_venice",
    }
    provider_col = provider_col_map.get(api_key_provider)
    cols = ["user_id", "api_key", "api_key_provider", "selected_model", "system_prompt", "context_limit", "stats_display", "theme", "notify_sound", "notify_vibrate"]
    vals = [user_id, api_key, api_key_provider, DEFAULT_MODEL, DEFAULT_SYSTEM_PROMPT, DEFAULT_CONTEXT_LIMIT, DEFAULT_STATS_DISPLAY, DEFAULT_THEME, 0, 0]
    if provider_col:
        cols.append(provider_col)
        vals.append(api_key)
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            f"INSERT INTO users ({', '.join(cols)}) VALUES ({', '.join('?' * len(vals))})",
            vals,
        )
        await db.commit()


async def ensure_user(user_id: int) -> None:
    """Create the user row with defaults if it does not exist yet."""
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()


async def update_provider_key(user_id: int, provider: str, api_key: str) -> None:
    """Set or clear a per-provider API key column for the user."""
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
    async with aiosqlite.connect(_db_path()) as db:
        await ensure_user(user_id)
        if api_key:
            await db.execute(
                f"UPDATE users SET {col} = ? WHERE user_id = ?",
                (api_key, user_id),
            )
        else:
            await db.execute(
                f"UPDATE users SET {col} = NULL WHERE user_id = ?",
                (user_id,),
            )
        await db.commit()


async def update_api_key(user_id: int, api_key: str, api_key_provider: str = "openrouter", set_personal_key: bool = True) -> None:
    provider_col_map = {
        "openrouter": "api_key_openrouter",
        "openai": "api_key_openai",
        "gemini": "api_key_gemini",
        "groq": "api_key_groq",
        "huggingface": "api_key_huggingface",
        "venice": "api_key_venice",
    }
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "UPDATE users SET api_key = ?, api_key_provider = ? WHERE user_id = ?",
            (api_key, api_key_provider, user_id),
        )
        if set_personal_key:
            provider_col = provider_col_map.get(api_key_provider)
            if provider_col:
                await db.execute(
                    f"UPDATE users SET {provider_col} = ? WHERE user_id = ?",
                    (api_key, user_id),
                )
        await db.commit()


async def update_selected_model(user_id: int, model_id: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET selected_model = ? WHERE user_id = ?", (model_id, user_id))
        await db.commit()


async def update_system_prompt(user_id: int, system_prompt: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET system_prompt = ? WHERE user_id = ?", (system_prompt, user_id))
        await db.commit()


async def update_context_limit(user_id: int, context_limit: int) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET context_limit = ? WHERE user_id = ?", (context_limit, user_id))
        await db.commit()


async def update_theme(user_id: int, theme: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET theme = ? WHERE user_id = ?", (theme, user_id))
        await db.commit()


async def update_notify_sound(user_id: int, enabled: bool) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET notify_sound = ? WHERE user_id = ?", (1 if enabled else 0, user_id))
        await db.commit()


async def update_notify_vibrate(user_id: int, enabled: bool) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET notify_vibrate = ? WHERE user_id = ?", (1 if enabled else 0, user_id))
        await db.commit()


async def update_notify_sound_id(user_id: int, sound_id: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET notify_sound_id = ? WHERE user_id = ?", (sound_id, user_id))
        await db.commit()


async def update_vib_strength(user_id: int, strength: int) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET vib_strength = ? WHERE user_id = ?", (strength, user_id))
        await db.commit()



async def add_message(user_id: int, role: str, content: str, image_url: str | None = None) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "INSERT INTO messages (user_id, role, content, image_url) VALUES (?, ?, ?, ?)",
            (user_id, role, content, image_url),
        )
        await db.commit()


async def get_recent_messages(user_id: int, limit: int) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT role, content, image_url FROM messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [{**dict(row), "image_url": row["image_url"]} for row in reversed(rows)]


async def clear_messages(user_id: int) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        await db.commit()


async def reset_user_state(user_id: int) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM api_stats WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM user_models WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM dialogs WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()


async def reset_all_users_state() -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("DELETE FROM messages")
        await db.execute("DELETE FROM api_stats")
        await db.execute("DELETE FROM user_models")
        await db.execute("DELETE FROM dialogs")
        await db.execute("DELETE FROM users")
        await db.commit()


async def get_user_models(user_id: int) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT model_id, display_name, meta, short_id, added_at, context, mod_in, mod_out, price_prompt, price_completion, description, is_free FROM user_models WHERE user_id = ? ORDER BY added_at ASC, display_name ASC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if not d.get("short_id") and d.get("model_id"):
                d["short_id"] = hashlib.sha1(d["model_id"].encode()).hexdigest()[:16]
            if d.get("added_at") is None:
                d["added_at"] = 0
            result.append(d)
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
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        if prefix:
            cursor = await db.execute(
                "SELECT model_id, display_name, meta, short_id, added_at, context, mod_in, mod_out, price_prompt, price_completion, description, is_free FROM user_models WHERE user_id = ? AND model_id LIKE ? ORDER BY added_at ASC, display_name ASC",
                (user_id, f"{prefix}%"),
            )
        else:
            cursor = await db.execute(
                "SELECT model_id, display_name, meta, short_id, added_at, context, mod_in, mod_out, price_prompt, price_completion, description, is_free FROM user_models WHERE user_id = ? AND model_id NOT LIKE 'openai:%' AND model_id NOT LIKE 'gemini:%' AND model_id NOT LIKE 'groq:%' AND model_id NOT LIKE 'hf:%' AND model_id NOT LIKE 'venice:%' ORDER BY added_at ASC, display_name ASC",
                (user_id,),
            )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if not d.get("short_id") and d.get("model_id"):
                d["short_id"] = hashlib.sha1(d["model_id"].encode()).hexdigest()[:16]
            if d.get("added_at") is None:
                d["added_at"] = 0
            result.append(d)
        return result


async def get_user_model(user_id: int, model_id: str) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT model_id, display_name, meta, short_id, context, mod_in, mod_out, price_prompt, price_completion, description, is_free FROM user_models WHERE user_id = ? AND model_id = ?",
            (user_id, model_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        if not d.get("short_id") and d.get("model_id"):
            d["short_id"] = hashlib.sha1(d["model_id"].encode()).hexdigest()[:16]
        return d


async def get_user_model_by_short(user_id: int, short_id: str) -> dict | None:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT model_id, display_name, meta, short_id, context, mod_in, mod_out, price_prompt, price_completion, description, is_free FROM user_models WHERE user_id = ? AND short_id = ?",
            (user_id, short_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


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
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            """
            INSERT INTO user_models (
                user_id, model_id, display_name, meta, short_id, added_at,
                context, mod_in, mod_out, price_prompt, price_completion, description, is_free
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, model_id) DO UPDATE SET
                display_name = excluded.display_name,
                meta = excluded.meta,
                short_id = excluded.short_id,
                context = excluded.context,
                mod_in = excluded.mod_in,
                mod_out = excluded.mod_out,
                price_prompt = excluded.price_prompt,
                price_completion = excluded.price_completion,
                description = excluded.description,
                is_free = excluded.is_free
            """,
            (
                user_id, model_id, display_name, meta, short_id, now,
                context, mod_in, mod_out, price_prompt, price_completion, description, is_free_val,
            ),
        )
        await db.commit()


async def update_user_model_meta(user_id: int, model_id: str, meta: str | None) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "UPDATE user_models SET meta = ? WHERE user_id = ? AND model_id = ?",
            (meta, user_id, model_id),
        )
        await db.commit()


async def remove_user_model(user_id: int, model_id: str) -> bool:
    async with aiosqlite.connect(_db_path()) as db:
        cursor = await db.execute("DELETE FROM user_models WHERE user_id = ? AND model_id = ?", (user_id, model_id))
        await db.commit()
        return cursor.rowcount > 0


async def remove_user_model_by_short(user_id: int, short_id: str) -> bool:
    async with aiosqlite.connect(_db_path()) as db:
        cursor = await db.execute("DELETE FROM user_models WHERE user_id = ? AND short_id = ?", (user_id, short_id))
        await db.commit()
        return cursor.rowcount > 0


async def get_stats_display(user_id: int) -> str:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT stats_display FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row is None:
                return DEFAULT_STATS_DISPLAY
            return row["stats_display"]
        except Exception:
            return DEFAULT_STATS_DISPLAY


async def update_stats_display(user_id: int, stats_display: str) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("UPDATE users SET stats_display = ? WHERE user_id = ?", (stats_display, user_id))
        await db.commit()


async def log_api_call(user_id: int, tokens_used: int) -> None:
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("INSERT INTO api_stats (user_id, tokens_used, timestamp) VALUES (?, ?, ?)", (user_id, tokens_used, int(time.time())))
        await db.commit()


async def get_api_stats(user_id: int, since_ts: int) -> tuple[int, int]:
    async with aiosqlite.connect(_db_path()) as db:
        cursor = await db.execute(
            "SELECT COUNT(*), COALESCE(SUM(tokens_used), 0) FROM api_stats WHERE user_id = ? AND timestamp >= ?",
            (user_id, since_ts),
        )
        row = await cursor.fetchone()
        return row[0], row[1]


async def get_all_api_stats(since_ts: int) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, COUNT(*) as message_count, COALESCE(SUM(tokens_used), 0) as total_tokens FROM api_stats WHERE timestamp >= ? GROUP BY user_id",
            (since_ts,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_message_count(user_id: int) -> int:
    async with aiosqlite.connect(_db_path()) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_total_message_count() -> int:
    async with aiosqlite.connect(_db_path()) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_total_token_count() -> int:
    async with aiosqlite.connect(_db_path()) as db:
        cursor = await db.execute("SELECT COALESCE(SUM(tokens_used), 0) FROM api_stats")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def count_users() -> int:
    async with aiosqlite.connect(_db_path()) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users ORDER BY user_id")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
