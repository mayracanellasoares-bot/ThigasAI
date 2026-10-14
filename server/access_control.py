"""Public THIGAS AI web access without a login or password prompt.

API credentials remain exclusively in server-side environment variables.
Telegram's secret header and workspace's anonymous session/CSRF protections
remain independent of this module.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from urllib.parse import urlsplit

from flask import jsonify, redirect, request


# Only these routes are counted against the public model/resource budget.
# Telegram is authenticated separately via its webhook secret.
METERED_PATHS = frozenset((
    "/chat", "/chat/stream", "/image/describe", "/link/check",
    "/document/extract", "/workspace/api/generate",
))


def install(app):
    app.config["SESSION_REFRESH_EACH_REQUEST"] = False
    try:
        per_minute = int(os.getenv("THIGAS_PUBLIC_RATE_LIMIT_PER_MINUTE", "12"))
    except ValueError:
        per_minute = 12
    per_minute = min(60, max(1, per_minute))

    hits: dict[str, deque[float]] = {}
    lock = threading.Lock()

    def allowed_site_origin() -> bool:
        # A browser's cross-site request must not trigger a public paid provider.
        if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            return False
        origin = request.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed = urlsplit(origin)
            if (parsed.scheme not in ("https", "http") or
                    parsed.username or parsed.password or
                    parsed.path not in ("", "/") or parsed.query or parsed.fragment):
                return False
            allowed_hosts = {request.host.lower()}
            for configured in (
                os.getenv("RENDER_EXTERNAL_URL", ""),
                os.getenv("THIGAS_SITE_URL", ""),
            ):
                if configured:
                    host = urlsplit(configured).netloc.lower()
                    if host:
                        allowed_hosts.add(host)
            return parsed.netloc.lower() in allowed_hosts
        except ValueError:
            return False

    def rate_limited() -> bool:
        # In-memory, per-process cap; does not require storage or browser login.
        # Used only for consuming endpoints; no request text is persisted.
        remote = request.remote_addr or "unknown"
        now = time.monotonic()
        with lock:
            recent = hits.setdefault(remote, deque())
            while recent and now - recent[0] >= 60:
                recent.popleft()
            if len(recent) >= per_minute:
                return True
            recent.append(now)
            if len(hits) > 4096:
                for key in list(hits)[:1024]:
                    if key != remote:
                        hits.pop(key, None)
        return False

    @app.before_request
    def public_access_guard():
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        # Telegram checks its own secret-token header and must not depend
        # on browser origin headers or public chat quotas.
        if request.path == "/telegram/webhook":
            return None
        if not allowed_site_origin():
            return jsonify(error="Origem não autorizada."), 403
        if (request.method == "POST" and request.path in METERED_PATHS
                and not app.config.get("TESTING") and rate_limited()):
            response = jsonify(error="Limite temporário de uso público. Aguarde um minuto e tente novamente.")
            response.status_code = 429
            response.headers["Retry-After"] = "60"
            return response
        return None

    @app.after_request
    def browser_security(response):
        if (not request.path.startswith("/static/") and
                request.path not in ("/health", "/manifest.webmanifest", "/sw.js")):
            response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Origin"
        return response

    # Backward compatible with installed PWAs and old links: no password is
    # checked, no authenticated session is created or required.
    @app.get("/entrar")
    def legacy_login_page():
        return redirect("/", code=303)

    @app.post("/auth/login")
    def legacy_login():
        return redirect("/", code=303)

    @app.post("/auth/logout")
    def legacy_logout():
        return redirect("/", code=303)
