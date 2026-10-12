#!/usr/bin/env python3
"""Compara respostas realmente coletadas do mesmo benchmark entre duas versões.

Não faz chamadas ao provedor e não preenche medições ausentes com estimativas.
"""
import argparse
import json
from pathlib import Path

from evaluate_cognition import load_cases, grade


def load_results(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    mapped = {}
    for row in rows:
        if row["id"] in mapped:
            raise ValueError("ID duplicado em " + str(path) + ": " + row["id"])
        mapped[row["id"]] = row
    return mapped


def compare(split, before, after):
    cases = load_cases(split)
    pairs = []
    for case in cases:
        left, right = before.get(case["id"]), after.get(case["id"])
        if left is None or right is None or not isinstance(left.get("answer"), str) or not isinstance(right.get("answer"), str):
            continue
        pairs.append((case, left, right))

    def summary(index):
        total_correct = sum(grade(case, (left, right)[index]["answer"]) for case, left, right in pairs)
        times = []
        prompt_tokens = completion_tokens = 0
        counted = 0
        for _, left, right in pairs:
            row = (left, right)[index]
            duration = row.get("elapsed_seconds")
            if type(duration) in (int, float) and duration > 0:
                times.append(duration)
            usage = row.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}
            p, c = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if type(p) is int and p >= 0 and type(c) is int and c >= 0:
                prompt_tokens += p
                completion_tokens += c
                counted += 1
        return {
            "correct": total_correct,
            "accuracy_on_paired_cases": total_correct / len(pairs) if pairs else None,
            "mean_request_seconds": sum(times)/len(times) if times else None,
            "latency_measured_cases": len(times),
            "tokens_reported_by_provider_cases": counted,
            "prompt_tokens_reported_total": prompt_tokens if counted else None,
            "completion_tokens_reported_total": completion_tokens if counted else None,
        }
    old, new = summary(0), summary(1)
    return {
        "split": split,
        "test_cases": len(cases),
        "paired_usable_cases": len(pairs),
        "incomplete": len(pairs) != len(cases),
        "old": old,
        "new": new,
        "accuracy_delta_percentage_points": (
            100 * (new["accuracy_on_paired_cases"] - old["accuracy_on_paired_cases"])
            if pairs else None
        ),
        "note": "Somente casos pareados com respostas reais; nenhuma medição é inventada. Acurácia automática é apenas aproximação.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["train", "val", "test"], default="test")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.split, load_results(args.before), load_results(args.after)),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
