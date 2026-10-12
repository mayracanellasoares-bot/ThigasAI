#!/usr/bin/env python3
"""Microbenchmark reproduzível APENAS do seletor de contexto, sem inferência.

A medição de recuperação textual não mede acerto do modelo neural.
Compara o corte antigo (últimas 12 mensagens) com seleção contextual nova.
"""
from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from context_selector import select_relevant_history

FACTS = [
    ("cachorro", "Meu cachorro se chama Pipoca.", "Qual é o nome do meu cachorro?"),
    ("projeto", "O projeto recebeu o nome Nebulix.", "Qual nome dei ao projeto?"),
    ("cidade", "Minha cidade favorita nesta simulação é Amora.", "Qual foi a cidade que mencionei?"),
    ("servidor", "O servidor de teste está na porta 8081.", "Qual porta usa o servidor?"),
    ("framework", "O framework desta experiência é Vite.", "Qual framework foi escolhido?"),
    ("professor", "O professor fictício se chama Mauro.", "Qual era o nome do professor?"),
    ("cor", "A cor secreta da simulação é violeta.", "Qual era a cor secreta?"),
    ("arquivo", "O arquivo de referência chama-se notes.yaml.", "Qual é o arquivo de referência?"),
]


def old_selector(question, history):
    previous = history[-12:]
    while previous and previous[-1] == {"role": "user", "content": question}:
        previous.pop()
    budget = max(0, 60000 - len(question))
    while previous and sum(len(item["content"]) for item in previous) > budget:
        previous.pop(0)
    while previous and previous[0]["role"] != "user":
        previous.pop(0)
    return previous


def run():
    examples = []
    for _tag, fact, question in FACTS:
        history = [{"role": "user", "content": fact},
                   {"role": "assistant", "content": "Anotado nesta conversa."}]
        for i in range(15):
            history.extend([
                {"role": "user", "content": f"Pergunta irrelevante sobre o clima {i}."},
                {"role": "assistant", "content": f"Resposta sobre a previsão do clima {i}."},
            ])
        examples.append((history, fact, question))
    measurements = {}
    for name, selector in (
        ("before_cutoff", old_selector),
        ("after_relevance", lambda q, h: select_relevant_history(q, h, budget_chars=60000-len(q), limit_messages=12)),
    ):
        retained = 0
        for history, fact, question in examples:
            selected = selector(question, history)
            if any(item["content"] == fact for item in selected):
                retained += 1
        times = []
        for _ in range(100):
            start = time.perf_counter_ns()
            for history, _fact, question in examples:
                selector(question, history)
            times.append((time.perf_counter_ns() - start) / 1_000_000)
        measurements[name] = {
            "fact_retained_cases": retained, "cases": len(examples),
            "median_total_selection_milliseconds_for_8_cases": statistics.median(times),
        }
    report = {
        "benchmark": "synthetic_context_selection_not_model_accuracy",
        "limitation": "Same synthetic fixtures for both algorithms; not an LLM evaluation.",
        "results": measurements,
    }
    assert measurements["before_cutoff"]["fact_retained_cases"] == 0
    assert measurements["after_relevance"]["fact_retained_cases"] == len(examples)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
