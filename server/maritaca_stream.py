"""Maritaca Chat Completions SSE relay.

Only content tokens and provider-reported usage are sent to the browser.
Rationale/reasoning fields, keys and upstream headers never leave the server.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

MAX_STREAM_CHARS = 500_000


def sse_event(name: str, payload: dict) -> str:
    return "event: " + name + "\ndata: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def measured_usage(data: Any) -> dict[str, int | None]:
    values = data if isinstance(data, dict) else {}
    return {
        key: val if type(val) is int and val >= 0 else None
        for key, val in (
            ("prompt_tokens", values.get("prompt_tokens")),
            ("completion_tokens", values.get("completion_tokens")),
            ("total_tokens", values.get("total_tokens")),
        )
    }


def relay_maritaca_stream(upstream, *, model: str, max_tokens: int) -> Iterator[str]:
    """Stream sanitized content chunks; emit done only for a complete upstream SSE.

    A partial stream with a transport error is **never** marked complete.
    This prevents incomplete answers from silently entering chat history.
    """
    fragments: list[str] = []
    total = 0
    finished = False
    finish_reason = None
    usage = measured_usage(None)
    try:
        for line in upstream.iter_lines(decode_unicode=True):
            if isinstance(line, bytes):
                line = line.decode("utf-8", "replace")
            if not isinstance(line, str):
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            content = line[5:].strip()
            if content == "[DONE]":
                finished = True
                break
            if not content or len(content) > 500_000:
                continue
            try:
                packet = json.loads(content)
            except (ValueError, TypeError):
                continue
            if not isinstance(packet, dict):
                continue
            if packet.get("error"):
                yield sse_event("error", {"error": "O provedor interrompeu a geração. Tente novamente."})
                return
            if isinstance(packet.get("usage"), dict):
                usage = measured_usage(packet["usage"])
            choices = packet.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                continue
            choice = choices[0]
            if isinstance(choice.get("finish_reason"), str):
                finish_reason = choice["finish_reason"]
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            # Never relay reasoning, role, tool calls or hidden fields.
            text = delta.get("content")
            if isinstance(text, str) and text:
                total += len(text)
                if total > MAX_STREAM_CHARS:
                    yield sse_event("error", {"error": "A resposta excedeu o limite seguro de tamanho."})
                    return
                fragments.append(text)
                yield sse_event("delta", {"text": text})
        answer = "".join(fragments).strip()
        if not finished or not answer:
            yield sse_event("error", {"error": "A transmissão terminou antes de completar a resposta."})
            return
        yield sse_event("done", {
            "answer": answer, "model": model,
            "usage": usage, "finish_reason": finish_reason,
            "max_output_tokens": max_tokens,
            "provider_attempt_count": 1,
            "provider_failover_used": False,
            "reasoning_effort": None,
            "search_provider": None, "sources": [],
        })
    except Exception:
        # Untrusted upstream exceptions may contain URLs/headers: no stringification.
        yield sse_event("error", {"error": "Conexão interrompida durante a resposta. Ela pode ter consumido créditos."})
    finally:
        upstream.close()
