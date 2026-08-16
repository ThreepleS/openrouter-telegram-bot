"""Telegram WebApp initData validation.

Telegram signs `initData` with HMAC-SHA256 using a secret key derived from the
bot token. The client passes this string to us; we must verify it before
trusting the contained user id.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()


def _string_to_sign(data: dict[str, str]) -> str:
    # `hash` is the signature itself and must be excluded from the check string.
    check_pairs = {k: v for k, v in data.items() if k != "hash"}
    return "\n".join(f"{k}={v}" for k, v in sorted(check_pairs.items()))


def parse_init_data(init_data: str) -> dict[str, str]:
    """Parse the raw initData query string into an ordered dict."""
    return dict(parse_qsl(init_data, keep_blank_values=True))


def verify_init_data(init_data: str, bot_token: str) -> bool:
    """Return True when the initData signature is valid."""
    if not init_data or not bot_token:
        return False

    data = parse_init_data(init_data)
    received_hash = data.get("hash")
    if not received_hash:
        return False

    computed = hmac.new(_secret_key(bot_token), _string_to_sign(data).encode("utf-8"), hashlib.sha256)
    return hmac.compare_digest(computed.hexdigest(), received_hash)


def extract_user(init_data: str) -> dict | None:
    """Extract the `user` payload (Telegram user JSON) from initData."""
    data = parse_init_data(init_data)
    raw_user = data.get("user")
    if not raw_user:
        return None
    try:
        return json.loads(raw_user)
    except (json.JSONDecodeError, TypeError):
        return None
