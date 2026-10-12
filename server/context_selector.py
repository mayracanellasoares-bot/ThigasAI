"""Seleção extrativa e limitada de histórico para chamadas de inferência.

Sem sumarização generativa, memória persistente ou cálculo fictício de tokens.
Recebe apenas mensagens validadas como user/assistant pelo backend.
"""
from __future__ import annotations

from collections import Counter
import re
import unicodedata
from typing import Any


STOPWORDS = frozenset("""
a ao aos as o os de da das do dos em no na nos nas um uma uns umas
e ou que para por com sem sobre como qual quais quando onde quem
meu minha meus minhas seu sua seus suas eu voce você vocês ele ela
eles elas nos nós isso isto aquilo esse essa este esta estes essas
qual foi era eram seria tem tinha tenho tenho ter está estao estão
pode poderia favor me diga explique falar falou falou perguntar
""".split())


def _terms(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return {term for term in re.findall(r"[a-z0-9_]{3,}", normalized) if term not in STOPWORDS}


def _as_exchanges(previous: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    exchanges: list[list[dict[str, str]]] = []
    for item in previous[-80:]:
        role = item["role"]
        if role == "user":
            exchanges.append([item])
        elif role == "assistant" and exchanges:
            # Várias mensagens seguidas do assistente continuam na mesma troca.
            exchanges[-1].append(item)
    return exchanges


def select_relevant_history(
    question: str, previous: list[dict[str, str]], *,
    budget_chars: int = 60000, limit_messages: int = 12,
) -> list[dict[str, str]]:
    """Conserva trocas recentes e recupera trocas antigas pela relevância lexical.

    Mantém ordem cronológica, pares íntegros e os limites estritos de caracteres
    e mensagens. O resultado não inclui a pergunta atual nem system prompt.
    """
    if budget_chars <= 0 or limit_messages <= 0:
        return []
    cleaned = list(previous)
    while cleaned and cleaned[-1]["role"] == "user" and cleaned[-1]["content"] == question:
        cleaned.pop()
    exchanges = _as_exchanges(cleaned)
    if not exchanges:
        return []

    sizes = [sum(len(item["content"]) for item in exchange) for exchange in exchanges]
    count_messages = [len(exchange) for exchange in exchanges]
    chosen: set[int] = set()
    used_chars = used_messages = 0

    def add(index: int) -> bool:
        nonlocal used_chars, used_messages
        if index in chosen or used_messages + count_messages[index] > limit_messages:
            return False
        if sizes[index] > budget_chars - used_chars:
            return False
        chosen.add(index)
        used_chars += sizes[index]
        used_messages += count_messages[index]
        return True

    # Priorizar três trocas recentes preserva instruções e correções imediatas.
    for index in range(len(exchanges) - 1, max(-1, len(exchanges) - 4), -1):
        add(index)

    requested = _terms(question)
    exchange_terms = [_terms(" ".join(x["content"] for x in exchange)) for exchange in exchanges]
    frequency = Counter(term for terms in exchange_terms for term in terms)
    scored = []
    for index in range(len(exchanges) - 3):
        overlap = requested.intersection(exchange_terms[index])
        score = sum(1 / frequency[term] for term in overlap)
        scored.append((score, index))

    # Ranking por raridade dos termos comuns, com desempate pelo mais recente.
    for score, index in sorted(scored, key=lambda pair: (pair[0], pair[1]), reverse=True):
        if score <= 0:
            break
        add(index)

    # O espaço restante recebe contexto recente mesmo sem termos em comum.
    for index in range(len(exchanges) - 4, -1, -1):
        add(index)

    result = [item for index in sorted(chosen) for item in exchanges[index]]
    return result
