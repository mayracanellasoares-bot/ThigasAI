"""Small encrypted PostgreSQL store. No persistent secrets live on Render's disk."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
import psycopg


SCHEMA = """
CREATE TABLE IF NOT EXISTS octonous_records (
    kind text NOT NULL,
    id text NOT NULL,
    data bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS octonous_events (
    event_key text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS octonous_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    data bytea NOT NULL
);
"""


class Store:
    def __init__(self, dsn=None, encryption_key=None):
        self.dsn = dsn or os.getenv("OCTONOUS_DATABASE_URL", "")
        key = encryption_key or os.getenv("OCTONOUS_ENCRYPTION_KEY", "")
        if not self.dsn or not key:
            raise RuntimeError("Configure OCTONOUS_DATABASE_URL e OCTONOUS_ENCRYPTION_KEY.")
        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        self._initialized = False

    @contextmanager
    def connection(self):
        with psycopg.connect(self.dsn, connect_timeout=5) as conn:
            if not self._initialized:
                for statement in SCHEMA.strip().split(";"):
                    if statement.strip():
                        conn.execute(statement)
                self._initialized = True
            yield conn

    def seal(self, value):
        return self.cipher.encrypt(json.dumps(value, ensure_ascii=False).encode())

    def open(self, value):
        try:
            return json.loads(self.cipher.decrypt(bytes(value)))
        except (InvalidToken, ValueError) as exc:
            raise RuntimeError("Chave de criptografia inválida para os dados persistidos.") from exc

    def put(self, kind, key, value):
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO octonous_records(kind,id,data) VALUES(%s,%s,%s)
                ON CONFLICT(kind,id) DO UPDATE SET data=EXCLUDED.data, updated_at=now()""",
                (kind, key, self.seal(value)),
            )

    def get(self, kind, key):
        with self.connection() as conn:
            row = conn.execute(
                "SELECT data FROM octonous_records WHERE kind=%s AND id=%s",
                (kind, key),
            ).fetchone()
        return self.open(row[0]) if row else None

    def all(self, kind, limit=100):
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id,data FROM octonous_records WHERE kind=%s ORDER BY updated_at DESC LIMIT %s",
                (kind, limit),
            ).fetchall()
        return [{"id": key, **self.open(data)} for key, data in rows]

    def delete(self, kind, key):
        with self.connection() as conn:
            row = conn.execute(
                "DELETE FROM octonous_records WHERE kind=%s AND id=%s RETURNING data",
                (kind, key),
            ).fetchone()
        return self.open(row[0]) if row else None

    def transition(self, kind, key, expected, change):
        """Atomic status change; only one concurrent approval can dispatch."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT data FROM octonous_records WHERE kind=%s AND id=%s FOR UPDATE",
                (kind, key),
            ).fetchone()
            if not row:
                return None
            value = self.open(row[0])
            if value.get("status") != expected:
                return None
            value.update(change)
            conn.execute(
                "UPDATE octonous_records SET data=%s,updated_at=now() WHERE kind=%s AND id=%s",
                (self.seal(value), kind, key),
            )
        return value

    def once(self, event_key):
        with self.connection() as conn:
            row = conn.execute(
                "INSERT INTO octonous_events(event_key) VALUES(%s) ON CONFLICT DO NOTHING RETURNING event_key",
                (event_key,),
            ).fetchone()
        return bool(row)

    def audit(self, run_id, tool, operation, input_data, output_data, status):
        record = {
            "run_id": run_id, "tool": tool, "operation": operation,
            "input": input_data, "output": output_data, "status": status,
        }
        with self.connection() as conn:
            conn.execute("INSERT INTO octonous_audit(data) VALUES(%s)", (self.seal(record),))

    def logs(self, limit=80):
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id,occurred_at,data FROM octonous_audit ORDER BY id DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return [
            {"id": row_id, "at": at.isoformat(), **self.open(data)}
            for row_id, at, data in rows
        ]


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid4())
