"""Heurísticas auditáveis para sinalizar possíveis defeitos na geração.

Sinalização, não correção automática nem prova de erro factual.
Não executa trechos de código, não consome tokens de um segundo modelo.
"""
from __future__ import annotations

import ast
import re


FENCED = re.compile(r"(?ms)^\x60{3}([^\n]*)\n(.*?)^\x60{3}[ \t]*$", re.MULTILINE)
WORDS = re.compile(r"\b\w+\b", re.UNICODE)
MAX_SCAN_CHARS = 80000


def _repetition_detected(text: str) -> bool:
    # Código, listas numeradas e prompts de repetição deliberada geram falsos
    # positivos. Exigir blocos extensos e REPETIÇÃO CONTÍGUA reduz o risco.
    paragraphs = re.split(r"\n\s*\n", text)
    canonical = [" ".join(p.casefold().split()) for p in paragraphs]
    for a, b, c in zip(canonical, canonical[1:], canonical[2:]):
        if len(a) >= 45 and a == b == c:
            return True

    # Também identifica loops sem quebras de linha.
    words = WORDS.findall(" ".join(text.casefold().split()))
    for window in (12, 20):
        if len(words) < window * 3:
            continue
        # As três cópias devem aparecer juntas e conter diversidade lexical.
        for i in range(len(words) - window * 3 + 1):
            segment = words[i:i + window]
            if len(set(segment)) < 5:
                continue
            if segment == words[i + window:i + 2 * window] == words[i + 2 * window:i + 3 * window]:
                return True
    return False


def inspect_generation(answer: str, finish_reason: str | None) -> list[str]:
    """Retorna códigos públicos estáveis, sempre em ordem determinística."""
    flags: list[str] = []
    if finish_reason == "length":
        flags.append("output_limit")
    if not isinstance(answer, str) or not answer.strip():
        return flags

    answer = answer[:MAX_SCAN_CHARS]
    matches = list(FENCED.finditer(answer))
    without_fences = FENCED.sub("", answer)
    if _repetition_detected(without_fences):
        flags.append("possible_repetition")

    # Indício, não prova de truncamento: só conta cercas na margem esquerda.
    if len(re.findall(r"(?m)^\x60{3}", answer)) % 2:
        flags.append("unclosed_code_block")

    for match in matches[:4]:
        language = match.group(1).strip().casefold()
        if language not in ("python", "py") or len(match.group(2)) > 16000:
            continue
        try:
            ast.parse(match.group(2))
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            flags.append("possible_python_syntax_error")
            break
    return flags
