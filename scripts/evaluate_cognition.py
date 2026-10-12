#!/usr/bin/env python3
"""Avaliação cognitiva PT-BR reproduzível. --live exige consentimento explícito.

Sem --live apenas valida os conjuntos ou avalia respostas já coletadas.
Não executa código gerado, não estima tokens e não presume acesso aos pesos.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import http.cookiejar
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ('train', 'val', 'test')
NUMBERS = re.compile(r'(?<![\w])[-+]?\d+(?:[,.]\d+)?(?![\w])')


def load_cases(split: str):
    cases = []
    for raw in (ROOT / 'eval' / (split + '.jsonl')).read_text(encoding='utf-8').splitlines():
        if raw.strip():
            cases.append(json.loads(raw))
    for case in cases:
        if not all(key in case for key in ('id', 'category', 'prompt', 'grading', 'expected')):
            raise ValueError('Caso incompleto em ' + split)
    return cases


def validate_splits():
    all_ids, all_prompts, counts = set(), set(), {}
    for split in SPLITS:
        cases = load_cases(split)
        counts[split] = len(cases)
        for case in cases:
            prompt = case['prompt'].casefold().strip()
            if case['id'] in all_ids or prompt in all_prompts:
                raise ValueError('ID ou prompt duplicado: ' + case['id'])
            all_ids.add(case['id'])
            all_prompts.add(prompt)
            if case['grading'] not in ('exact', 'contains_all', 'last_number', 'regex'):
                raise ValueError('Critério desconhecido: ' + case['id'])
    return counts


def grade(case, answer: str) -> bool:
    answer = ' '.join(str(answer).casefold().split())
    expected = case['expected']
    grading = case['grading']
    if grading == 'exact':
        return answer == ' '.join(str(expected).casefold().split())
    if grading == 'contains_all':
        return isinstance(expected, list) and all(str(piece).casefold() in answer for piece in expected)
    if grading == 'regex':
        return re.search(str(expected), answer, flags=re.IGNORECASE) is not None
    if grading == 'last_number':
        found = NUMBERS.findall(answer.replace('**', ''))
        if not found:
            return False
        try:
            return Decimal(found[-1].replace(',', '.')) == Decimal(str(expected).replace(',', '.'))
        except InvalidOperation:
            return False
    raise ValueError('Critério desconhecido')


def score_responses(split, responses):
    cases = load_cases(split)
    by_id = {row['id']: row for row in responses if isinstance(row, dict) and 'id' in row}
    per_category, correct_category = Counter(), Counter()
    results, latency, speeds = [], [], []
    for case in cases:
        response = by_id.get(case['id'], {})
        answer = response.get('answer')
        correct = grade(case, answer) if isinstance(answer, str) else None
        if correct is not None:
            per_category[case['category']] += 1
            correct_category[case['category']] += int(correct)
        duration = response.get('elapsed_seconds')
        if type(duration) in (int, float) and duration > 0:
            latency.append(duration)
            usage = response.get('usage') or {}
            completion = usage.get('completion_tokens') if isinstance(usage, dict) else None
            if type(completion) is int and completion >= 0:
                speeds.append(completion / duration)
        results.append({'id': case['id'], 'category': case['category'], 'correct': correct})
    measured = sum(per_category.values())
    total_ok = sum(correct_category.values())
    return {
        'split': split, 'cases': len(cases), 'evaluated': measured,
        'missing': len(cases) - measured,
        'accuracy': total_ok / measured if measured else None,
        'accuracy_by_category': {
            key: {'correct': correct_category[key], 'evaluated': count,
                  'accuracy': correct_category[key] / count}
            for key, count in sorted(per_category.items())
        },
        'median_request_seconds': statistics.median(latency) if latency else None,
        'median_provider_tokens_per_second': statistics.median(speeds) if speeds else None,
        'memory': None,
        'note': 'Critérios automáticos são proxies; revisão humana é necessária para código e qualidade.',
        'items': results,
    }


def run_live(cases, url, mode):
    password = os.getenv('THIGAS_ACCESS_PASSWORD', '')
    if not password:
        raise ValueError('THIGAS_ACCESS_PASSWORD não definida no ambiente local.')
    if not url.startswith(('http://127.0.0.1:', 'http://localhost:', 'https://')):
        raise ValueError('Use HTTPS ou HTTP apenas em localhost.')
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    login = urllib.parse.urlencode({'password': password}).encode('utf-8')
    with opener.open(urllib.request.Request(url.rstrip('/') + '/auth/login', data=login, method='POST'), timeout=30) as response:
        if '/entrar' in response.url:
            raise ValueError('Login recusado.')
    output = []
    for case in cases:
        begin = time.perf_counter()
        payload = json.dumps({'message': case['prompt'], 'history': [], 'mode': mode}).encode('utf-8')
        row = {'id': case['id'], 'answer': None, 'usage': None, 'model': None}
        try:
            req = urllib.request.Request(url.rstrip('/') + '/chat', data=payload,
                                         headers={'Content-Type': 'application/json'}, method='POST')
            with opener.open(req, timeout=360) as response:
                data = json.load(response)
            row.update(answer=data.get('answer'), usage=data.get('usage'), model=data.get('model'),
                       finish_reason=data.get('finish_reason'))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            row['error'] = type(exc).__name__
        row['elapsed_seconds'] = round(time.perf_counter() - begin, 6)
        output.append(row)
        print(case['id'], 'ok' if row['answer'] is not None else 'erro', file=sys.stderr)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=SPLITS, default='test')
    parser.add_argument('--responses', type=Path, help='JSONL com id e answer das execuções anteriores')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--allow-provider-costs', action='store_true')
    parser.add_argument('--url', default='http://127.0.0.1:7860')
    parser.add_argument('--mode', choices=('fast', 'thinking', 'cloud'), default='fast')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print('Dataset:', json.dumps(validate_splits(), ensure_ascii=False))
    if args.live and args.responses:
        parser.error('Escolha --live ou --responses, não ambos.')
    if args.live and not args.allow_provider_costs:
        parser.error('--live exige --allow-provider-costs para evitar consumo involuntário.')
    if args.live:
        if not args.output:
            parser.error('--live exige --output para guardar evidências.')
        rows = run_live(load_cases(args.split), args.url, args.mode)
    elif args.responses:
        rows = [json.loads(line) for line in args.responses.read_text(encoding='utf-8').splitlines() if line.strip()]
    else:
        print('Conjuntos válidos. Nenhuma inferência executada; acurácia ainda não medida.')
        return
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    print(json.dumps(score_responses(args.split, rows), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
