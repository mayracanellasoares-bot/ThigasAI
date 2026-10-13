"""Aion Labs API integration: private keys, official endpoint and safe parameters.

The provider is strictly opt-in through user-selected modes in the chat.
"""
from __future__ import annotations

import os
from typing import Mapping
from urllib.parse import urlsplit

from groq_key_pool import KeyPool, post_with_failover

AION_URL = "https://api.aionlabs.ai/v1/chat/completions"
AION_DEFAULT_MODEL = "aion-labs/aion-3.5-mini"
AION_KEYS = (
    ("AION_API_KEY", "AION_LABS_API_KEY", "AIONLABS_API_KEY", "THIGAS_AION_API_KEY", "AION_KEY"),
    ("AION_API_KEY_2", "AION_API_KEY2", "THIGAS_AION_API_KEY_2", "AION_LABS_API_KEY_2"),
    ("AION_API_KEY_3", "AION_API_KEY3", "THIGAS_AION_API_KEY_3", "AION_LABS_API_KEY_3"),
)
# The Aion 3.5 models support low/high/max; 2.0 and 3.0 support
# none/low/medium/high/max. The 8B roleplay model has no reasoning_effort.
REASONING_MODELS = frozenset({
    "aion-labs/aion-2.0", "aion-labs/aion-3.0", "aion-labs/aion-3.0-mini",
    "aion-labs/aion-3.5", "aion-labs/aion-3.5-mini",
})
aion_keys = KeyPool()


def is_aion_endpoint(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.netloc == "api.aionlabs.ai"
                and parsed.path == "/v1/chat/completions"
                and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def configured_aion_keys(*, environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    env = os.environ if environ is None else environ
    result: list[str] = []
    for names in AION_KEYS:
        for name in names:
            key = (env.get(name) or "").strip()
            if key:
                if key not in result:
                    result.append(key)
                break
    return tuple(result)


def reasoning_effort_for_mode(model: str, mode: str) -> str | None:
    """Aion only receives supported reasoning values, never Groq/NVIDIA fields."""
    if model not in REASONING_MODELS:
        return None
    return "high" if mode == "aion_thinking" else "low"


def post_aion(post, payload: dict, keys: tuple[str, ...], *,
              url: str = AION_URL, attempts: list[str] | None = None):
    if not is_aion_endpoint(url):
        raise ValueError("Endpoint Aion não autorizado.")
    return post_with_failover(post, url, payload, keys, pool=aion_keys,
                              attempts=attempts)
