"""Separate owner session: the public chat stays public."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import deque

from flask import abort, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import redis

COOKIE = "thigas_octonous_owner"
_attempts = {}
_lock = threading.Lock()


def configured():
    return all(os.getenv(name) for name in (
        "OCTONOUS_OWNER_PASSWORD", "OCTONOUS_SESSION_SECRET",
        "OCTONOUS_DATABASE_URL", "OCTONOUS_ENCRYPTION_KEY",
    ))


def serializer():
    secret = os.getenv("OCTONOUS_SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("OCTONOUS_SESSION_SECRET deve ter 32 caracteres ou mais.")
    return URLSafeTimedSerializer(secret, salt="octonous-owner-v1")


def owner_session():
    token = request.cookies.get(COOKIE, "")
    if not token:
        return None
    try:
        value = serializer().loads(token, max_age=8 * 3600)
        return value if isinstance(value, dict) and value.get("sid") else None
    except (BadSignature, SignatureExpired):
        return None


def require_owner(write=False):
    session = owner_session()
    if not session:
        abort(401)
    if write:
        token = request.headers.get("X-Octonous-CSRF", "")
        if not hmac.compare_digest(token, csrf(session["sid"])):
            abort(403)
    return session


def csrf(sid):
    secret = os.environ["OCTONOUS_SESSION_SECRET"].encode()
    return hmac.new(secret, ("csrf:" + sid).encode(), hashlib.sha256).hexdigest()


def login_allowed(remote):
    redis_url = os.getenv("OCTONOUS_REDIS_URL", "")
    if redis_url:
        try:
            client = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            key = "octonous:login:" + hashlib.sha256(remote.encode()).hexdigest()
            count = client.incr(key)
            if count == 1:
                client.expire(key, 300)
            return count <= 8
        except redis.RedisError:
            # Fail closed when the distributed limiter is configured but unavailable.
            return False
    current = time.monotonic()
    with _lock:
        recent = _attempts.setdefault(remote, deque())
        while recent and current - recent[0] > 300:
            recent.popleft()
        if len(recent) >= 8:
            return False
        recent.append(current)
        if len(_attempts) > 2048:
            _attempts.clear()
        return True


def check_password(password):
    expected = os.getenv("OCTONOUS_OWNER_PASSWORD", "")
    return len(expected) >= 16 and hmac.compare_digest(
        hashlib.sha256(str(password).encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )


def new_session():
    sid = secrets.token_urlsafe(32)
    return serializer().dumps({"sid": sid})
