"""Senha única de acesso ao site e ao PWA, sem cadastro de usuários.

Configure THIGAS_ACCESS_PASSWORD e THIGAS_SESSION_SECRET somente no servidor.
O webhook Telegram mantém sua autenticação independente.
"""
import hashlib
import hmac
import os
import threading
import time
from urllib.parse import urlsplit

from flask import jsonify, redirect, request, session


def install(app):
    # Sessões autenticadas têm duração fixa: chamadas ao chat não renovam indefinidamente o cookie.
    app.config["SESSION_REFRESH_EACH_REQUEST"] = False
    password = os.getenv("THIGAS_ACCESS_PASSWORD", "")
    secret = os.getenv("THIGAS_SESSION_SECRET", "")
    ready = 12 <= len(password) <= 256 and len(secret) >= 32
    # A troca da senha invalida cookies autenticados anteriormente.
    session_marker = hashlib.sha256(
        ("thigas-access-v1:" + password + ":" + secret).encode("utf-8")
    ).hexdigest()
    stored_digest = hashlib.sha256(password.encode("utf-8")).digest()
    attempts = {}
    lock = threading.Lock()
    public_routes = {
        "/health", "/telegram/webhook", "/manifest.webmanifest",
        "/sw.js", "/entrar", "/auth/login",
    }

    def authenticated():
        value = session.get("thigas_access_v1")
        return ready and isinstance(value, str) and hmac.compare_digest(value, session_marker)

    def same_origin():
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        origin = request.headers.get("Origin")
        if not origin:
            return True
        parsed = urlsplit(origin)
        return parsed.scheme in ("http", "https") and parsed.netloc == request.host

    def throttled(identity, failed=False):
        now = time.monotonic()
        with lock:
            # Janela de 5 minutos, com limite de dez tentativas incorretas.
            recent = [t for t in attempts.get(identity, []) if now - t < 300]
            if failed:
                recent.append(now)
            if recent:
                attempts[identity] = recent
            else:
                attempts.pop(identity, None)
            # Evita crescimento ilimitado do dicionário.
            if len(attempts) > 2048:
                for key in list(attempts)[:512]:
                    attempts.pop(key, None)
            return len(recent) >= 10

    @app.before_request
    def require_access():
        path = request.path
        if (path in public_routes or path.startswith("/static/icons/")
                or path == "/static/login.js"):
            return None
        if request.method == "OPTIONS":
            return None
        if not ready:
            if request.method in ("GET", "HEAD") and request.accept_mimetypes.accept_html:
                return redirect("/entrar?erro=config", code=303)
            return jsonify(error="A senha de acesso ainda não foi configurada no servidor."), 503
        if authenticated():
            return None
        if request.method in ("GET", "HEAD") and request.accept_mimetypes.accept_html:
            return redirect("/entrar", code=303)
        return jsonify(error="Acesso restrito. Informe a senha para continuar."), 401

    @app.after_request
    def disable_private_cache(response):
        if request.path not in ("/health", "/manifest.webmanifest", "/sw.js") and (
            not request.path.startswith("/static/") or
            request.path not in ("/static/login.js",)
        ):
            response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Cookie"
        return response

    @app.get("/entrar")
    def login_page():
        # Deve servir sempre a tela pública: o service worker armazena /entrar.
        # Redirecionar para / em sessão ativa armazenaria HTML privado no cache.
        return app.send_static_file("login.html")

    @app.post("/auth/login")
    def login():
        if not ready:
            return redirect("/entrar?erro=config", code=303)
        if not same_origin():
            return jsonify(error="Origem não autorizada."), 403
        identity = request.remote_addr or "unknown"
        if throttled(identity):
            return redirect("/entrar?erro=limite", code=303)
        candidate = request.form.get("password", "")
        if not isinstance(candidate, str) or len(candidate) > 256:
            candidate = ""
        candidate_digest = hashlib.sha256(candidate.encode("utf-8")).digest()
        if not hmac.compare_digest(candidate_digest, stored_digest):
            throttled(identity, failed=True)
            return redirect("/entrar?erro=senha", code=303)
        with lock:
            attempts.pop(identity, None)
        # Limpa o estado anônimo anterior e evita reaproveitar dados da sessão pré-login.
        session.clear()
        session["thigas_access_v1"] = session_marker
        session.permanent = True
        return redirect("/", code=303)

    @app.post("/auth/logout")
    def logout():
        if not same_origin():
            return jsonify(error="Origem não autorizada."), 403
        session.clear()
        return redirect("/entrar", code=303)
