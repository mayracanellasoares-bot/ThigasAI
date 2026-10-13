"""NVIDIA NIM: isolated API keys and cooldown, never mixed with Groq."""
from __future__ import annotations

import os
from typing import Mapping
from urllib.parse import urlsplit

from groq_key_pool import KeyPool, post_with_failover

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_KEYS = (
    ("NVIDIA_API_KEY", "THIGAS_NVIDIA_API_KEY"),
    ("NVIDIA_API_KEY_2", "NVIDIA_API_KEY2", "THIGAS_NVIDIA_API_KEY_2", "THIGAS_NVIDIA_API_KEY2"),
    ("NVIDIA_API_KEY_3", "NVIDIA_API_KEY3", "THIGAS_NVIDIA_API_KEY_3", "THIGAS_NVIDIA_API_KEY3"),
)
nvidia_keys = KeyPool()


def is_nvidia_endpoint(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and parsed.hostname == "integrate.api.nvidia.com" and parsed.path == "/v1/chat/completions"
    except ValueError:
        return False


def configured_nvidia_keys(*, environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    env = os.environ if environ is None else environ
    output: list[str] = []
    for names in NVIDIA_KEYS:
        for name in names:
            candidate = (env.get(name) or "").strip()
            if candidate:
                if candidate not in output:
                    output.append(candidate)
                break
    return tuple(output)


def post_nvidia(post, payload: dict, keys: tuple[str, ...], *, url: str = NVIDIA_URL):
    if not is_nvidia_endpoint(url):
        raise ValueError("Endpoint NVIDIA não autorizado.")
    return post_with_failover(post, url, payload, keys, pool=nvidia_keys)
