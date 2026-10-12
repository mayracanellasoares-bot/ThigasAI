"""Controle de acesso compartilhado do THIGAS AI, sem senhas no repositório."""
import hmac
import os
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from flask import jsonify, redirect, request, session, url_for

_FAILED_LOGINS = {}
_FAILED_LOCK = threading.Lock()
_WINDOW_SECONDS = 600
_MAX_ATTEMPTS = 5


def access_enabled():
    return os.getenv("THIGAS_ACCESS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _configured(app):
    return (
        bool(os.getenv("THIGAS_ACCESS_USERNAME", "").strip())
        and len(os.getenv("THIGAS_ACCESS_PASSWORD", "")) >= 12
        and bool(app.secret_key)
        and len(str(app.secret_key)) >= 32
    )


def _same_origin():
    origin = request.headers.get("Origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or parsed.netloc != request.host:
            return False
    return request.headers.get("Sec-Fetch-Site", "") not in ("cross-site",)


def _failed_attempt(ip):
    now = time.monotonic()
    with _FAILED_LOCK:
        recent = [t for t in _FAILED_LOGINS.get(ip, []) if now - t < _WINDOW_SECONDS]
        _FAILED_LOGINS[ip] = recent
        if len(_FAILED_LOGINS) > 2048:
            _FAILED_LOGINS.clear()
        return len(recent) >= _MAX_ATTEMPTS


def _record_failure(ip):
    now = time.monotonic()
    with _FAILED_LOCK:
        recent = [t for t in _FAILED_LOGINS.get(ip, []) if now - t < _WINDOW_SECONDS]
        recent.append(now)
        _FAILED_LOGINS[ip] = recent


def _clear_failures(ip):
    with _FAILED_LOCK:
        _FAILED_LOGINS.pop(ip, None)


def install_access_gate(app):
    # O segredo é instalado pelo módulo web_workspace no bootstrap da aplicação.
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_REFRESH_EACH_REQUEST=False,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )

    @app.before_request
    def require_access():
        if not access_enabled():
            return None
        path = request.path
        # Os ativos estáticos são públicos; informações, inferências e documentos não.
        if (path.startswith("/static/") and not path.endswith(".html")) or path in {
            "/login", "/health", "/sw.js", "/manifest.webmanifest", "/telegram/webhook"
        }:
            return None
        if not _configured(app):
            return jsonify(error="Controle de acesso não configurado no servidor."), 503
        if session.get("thigas_authenticated") is not True:
            if request.method in ("GET", "HEAD") and not (
                path.startswith("/api") or path.startswith("/workspace/api/")
            ):
                return redirect(url_for("thigas_login"), code=302)
            return jsonify(error="Sessão não autenticada.", login="/login"), 401
        if request.method not in ("GET", "HEAD", "OPTIONS") and not _same_origin():
            return jsonify(error="Origem não autorizada."), 403
        return None

    @app.get("/login")
    def thigas_login():
        if not access_enabled():
            return redirect(url_for("index"))
        if not _configured(app):
            return jsonify(error="Configure THIGAS_ACCESS_USERNAME, THIGAS_ACCESS_PASSWORD (12+ caracteres) e THIGAS_SESSION_SECRET (32+ caracteres)."), 503
        if session.get("thigas_authenticated") is True:
            return redirect(url_for("index"))
        return _login_page(app)

    @app.post("/login")
    def thigas_login_submit():
        if not access_enabled():
            return jsonify(error="Controle de acesso desabilitado."), 404
        if not _configured(app):
            return jsonify(error="Controle de acesso não configurado no servidor."), 503
        if not _same_origin():
            return jsonify(error="Origem não autorizada."), 403
        visitor = request.remote_addr or "unknown"
        if _failed_attempt(visitor):
            response = _login_page(app, "Muitas tentativas. Tente novamente em alguns minutos.", 429)
            response.headers["Retry-After"] = str(_WINDOW_SECONDS)
            return response
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if len(username) > 128 or len(password) > 512:
            _record_failure(visitor)
            return _login_page(app, "Usuário ou senha inválidos.", 401)
        expected_username = os.getenv("THIGAS_ACCESS_USERNAME", "").strip()
        expected_password = os.getenv("THIGAS_ACCESS_PASSWORD", "")
        valid = (
            hmac.compare_digest(username.encode("utf-8"), expected_username.encode("utf-8"))
            and hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8"))
        )
        if not valid:
            _record_failure(visitor)
            return _login_page(app, "Usuário ou senha inválidos.", 401)
        _clear_failures(visitor)
        session.clear()
        session["thigas_authenticated"] = True
        session.permanent = True
        return redirect(url_for("index"), code=303)

    @app.post("/logout")
    def thigas_logout():
        if not _same_origin():
            return jsonify(error="Origem não autorizada."), 403
        session.clear()
        response = redirect(url_for("thigas_login") if access_enabled() else url_for("index"), code=303)
        response.headers["Clear-Site-Data"] = '"cache"'
        return response

    @app.after_request
    def private_cache(response):
        if access_enabled() and not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Vary"] = "Cookie"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Frame-Options"] = "DENY"
        return response


def _login_page(app, message="", status=200):
    html = (Path(app.static_folder) / "login.html").read_text(encoding="utf-8")
    # Somente mensagens fixas, nunca refletir valores do formulário.
    error = '<p class="error" role="alert">' + message + '</p>' if message else ""
    html = html.replace("<!--THIGAS-ERROR-->", error)
    response = app.response_class(html, status=status, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store"
    return response
