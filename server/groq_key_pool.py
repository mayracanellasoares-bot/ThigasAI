"""Chaves Groq privadas: até três credenciais, alternância e failover limitado.

Sem URLs ou chaves no cliente; sem repetição automática após timeout,
falhas de rede ou respostas de sucesso com conteúdo inválido.
"""
from __future__ import annotations

import os
import threading
import time
from urllib.parse import urlsplit
from typing import Mapping

from requests import Response

# Nomes compatíveis com configuração antiga e novas variáveis no Render.
KEY_GROUPS = (
    ("THIGAS_CLOUD_API_KEY", "GROQ_API_KEY"),
    ("THIGAS_CLOUD_API_KEY_2", "GROQ_API_KEY_2", "GROQ_API_KEY2", "THIGAS_CLOUD_API_KEY2"),
    ("THIGAS_CLOUD_API_KEY_3", "GROQ_API_KEY_3", "GROQ_API_KEY3", "THIGAS_CLOUD_API_KEY3"),
)
RETRYABLE_STATUSES = frozenset({401, 403, 429, 498, 500, 502, 503, 504})


def is_groq_endpoint(url: str) -> bool:
    try:
        value = urlsplit(url)
        return value.scheme == "https" and value.hostname == "api.groq.com"
    except ValueError:
        return False


def configured_keys(primary: str, *, environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Retorna 1–3 chaves únicas. A chave primária legada continua prioritária."""
    env = os.environ if environ is None else environ
    keys: list[str] = []
    for group_index, aliases in enumerate(KEY_GROUPS):
        candidate = primary.strip() if group_index == 0 and isinstance(primary, str) else ""
        if not candidate:
            for name in aliases:
                candidate = (env.get(name) or "").strip()
                if candidate:
                    break
        if candidate and candidate not in keys:
            keys.append(candidate)
    return tuple(keys)


class KeyPool:
    """Pool por processo; cooldown impede insistência em chave limitada.

    O limite do provedor pode ser compartilhado por organização; mais chaves
    não significam necessariamente maior quota.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cursor = 0
        self._cooldown_until: dict[str, float] = {}

    def select(self, keys: tuple[str, ...]) -> tuple[str, ...]:
        if not keys:
            return ()
        now = time.monotonic()
        with self._lock:
            order = self._cursor % len(keys)
            self._cursor += 1
            # Mantém apenas chaves configuradas e ainda com bloqueio vigente.
            self._cooldown_until = {
                key: until for key, until in self._cooldown_until.items()
                if key in keys and until > now
            }
            candidates = keys[order:] + keys[:order]
            return tuple(key for key in candidates if self._cooldown_until.get(key, 0) <= now)

    def cooldown(self, key: str, response: Response) -> None:
        code = response.status_code
        if code in (401, 403):
            delay = 300.0
        elif code == 429:
            # Groq documenta Retry-After em segundos no 429.
            try:
                delay = float(response.headers.get("Retry-After", "20"))
            except (ValueError, TypeError, AttributeError):
                delay = 20.0
            delay = max(1.0, min(60.0, delay))
        else:
            delay = 5.0
        with self._lock:
            self._cooldown_until[key] = time.monotonic() + delay


groq_keys = KeyPool()


def post_with_failover(post, url: str, payload: dict, keys: tuple[str, ...], *,
                       timeout: tuple[int, int] = (10, 300), pool: KeyPool | None = None) -> Response | None:
    """No máximo uma solicitação por chave elegível, sem revelar credenciais.

    Retorna a última resposta HTTP se todas as chaves forem recusadas.
    Retorna None quando todas as chaves estiverem em cooldown.
    Propaga timeout/erro de transporte: repetir uma requisição de estado
    desconhecido poderia gerar cobranças ou respostas duplicadas.
    """
    active_pool = pool if pool is not None else groq_keys
    candidate_keys = active_pool.select(keys)
    if not candidate_keys:
        return None

    last_response = None
    for key in candidate_keys:
        response = post(
            url,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        last_response = response
        if response.status_code not in RETRYABLE_STATUSES:
            return response
        active_pool.cooldown(key, response)
    return last_response
