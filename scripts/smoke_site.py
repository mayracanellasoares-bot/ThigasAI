#!/usr/bin/env python3
"""Verificação pública, sem login e sem consumo de tokens, do site THIGAS AI.

Não envia mensagem ao modelo; nunca solicita nem imprime senhas. Um resultado
bem-sucedido comprova somente endpoints públicos e restrição de acesso.
"""
from __future__ import annotations

import argparse
import sys
import time

import requests


def check(base: str) -> int:
    base = base.rstrip("/")
    if not base.startswith("https://") or not base.endswith(".onrender.com"):
        print("SITE_SMOKE=INVALID_TARGET (somente domínio Render HTTPS)", flush=True)
        return 2

    session = requests.Session()
    checks = [
        ("/health", 200, {"Accept": "application/json"}),
        ("/entrar", 200, {"Accept": "text/html"}),
        ("/static/login.js", 200, {"Accept": "text/javascript"}),
        ("/api", 401, {"Accept": "application/json"}),
        ("/", 303, {"Accept": "text/html"}),
    ]

    good = True
    for path, expected, headers in checks:
        actual = None
        try:
            response = session.get(base + path, headers=headers,
                                   timeout=(6, 35), allow_redirects=False)
            actual = response.status_code
            # Um serviço Render gratuito pode iniciar somente após a primeira tentativa.
            if path == "/health" and actual in (502, 503, 504):
                time.sleep(3)
                response = session.get(base + path, headers=headers,
                                       timeout=(6, 35), allow_redirects=False)
                actual = response.status_code
        except requests.RequestException as exc:
            print(f"CHECK {path}: NETWORK_ERROR {type(exc).__name__}", flush=True)
            good = False
            continue
        print(f"CHECK {path}: HTTP {actual}; esperado {expected}",
              "OK" if actual == expected else "FAIL", flush=True)
        good = good and actual == expected

    print("SITE_SMOKE=" + ("PASS" if good else "FAIL"), flush=True)
    return 0 if good else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://thigas-coder-gateway.onrender.com")
    args = parser.parse_args()
    return check(args.url)


if __name__ == "__main__":
    sys.exit(main())
