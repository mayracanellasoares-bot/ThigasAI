import hashlib
import hmac
import base64
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))


class MemoryStore:
    def __init__(self):
        self.records = {}
        self.events = set()
        self.entries = []

    def put(self, kind, key, value):
        self.records[kind, key] = dict(value)

    def get(self, kind, key):
        return self.records.get((kind, key))

    def all(self, kind, limit=100):
        return [{"id": key, **value} for (category, key), value in self.records.items()
                if category == kind][:limit]

    def delete(self, kind, key):
        return self.records.pop((kind, key), None)

    def transition(self, kind, key, expected, change):
        value = self.get(kind, key)
        if not value or value.get("status") != expected:
            return None
        value = {**value, **change}
        self.put(kind, key, value)
        return value

    def once(self, event_key):
        if event_key in self.events:
            return False
        self.events.add(event_key)
        return True

    def audit(self, *args):
        self.entries.append(args)

    def logs(self, limit=80):
        return []


class OctonousTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = patch.dict(os.environ, {
            "OCTONOUS_OWNER_PASSWORD": "a-secure-owner-password-for-test",
            "OCTONOUS_SESSION_SECRET": "a-session-secret-longer-than-32-characters",
            "OCTONOUS_DATABASE_URL": "postgresql://test:fake@localhost:5432/test",
            "OCTONOUS_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "OCTONOUS_GITHUB_WEBHOOK_SECRET": "a-very-long-github-webhook-secret",
            "TELEGRAM_BOT_TOKEN": "", "MARITACA_API_KEY": "",
        })
        cls.env.start()
        spec = importlib.util.spec_from_file_location("octonous_test_app", SERVER / "app.py")
        cls.gateway = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.gateway
        spec.loader.exec_module(cls.gateway)
        cls.routes = sys.modules["octonous.routes"]

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()

    def setUp(self):
        self.store = MemoryStore()
        self.db_patch = patch.object(self.routes, "db", return_value=self.store)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.gateway.app.config["TESTING"] = True
        self.client = self.gateway.app.test_client()

    def owner(self):
        login = self.client.post("/octonous/api/login",
                                 json={"password": "a-secure-owner-password-for-test"},
                                 base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(login.status_code, 200)
        session = self.client.get("/octonous/api/session",
                                  base_url="https://thigas-coder-gateway.onrender.com").get_json()
        self.assertTrue(session["authenticated"])
        return {"X-Octonous-CSRF": session["csrf"]}

    def test_private_area_and_csrf_do_not_change_public_chat(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/octonous").status_code, 200)
        self.assertEqual(self.client.get("/octonous/api/approvals").status_code, 401)
        bad = self.client.post("/octonous/api/login", json={"password": "wrong"},
                               base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(bad.status_code, 401)
        self.owner()
        missing_csrf = self.client.post("/octonous/api/workflows", json={},
                                        base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(missing_csrf.status_code, 403)

    def test_approval_executes_once_and_rejection_does_not_write(self):
        headers = self.owner()
        self.store.put("approval", "one", {"status": "pending", "action": "gmail.send",
                                           "payload": {"to": "x@example.org", "body": "Oi"},
                                           "run_id": "run-one"})
        with patch.object(self.routes, "execute_action", return_value={"id": "sent"}) as execute:
            first = self.client.post("/octonous/api/approvals/one/decision",
                                     json={"decision": "approve"}, headers=headers,
                                     base_url="https://thigas-coder-gateway.onrender.com")
            second = self.client.post("/octonous/api/approvals/one/decision",
                                      json={"decision": "approve"}, headers=headers,
                                      base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        execute.assert_called_once()
        self.store.put("approval", "two", {"status": "pending", "action": "gmail.send",
                                           "payload": {}, "run_id": "run-two"})
        with patch.object(self.routes, "execute_action") as execute:
            rejected = self.client.post("/octonous/api/approvals/two/decision",
                                        json={"decision": "reject"}, headers=headers,
                                        base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(rejected.status_code, 200)
        execute.assert_not_called()

    def test_oauth_callback_checks_state_and_owner_cookie(self):
        headers = self.owner()
        with patch.object(self.routes, "authorize_url", return_value="https://example.org/authorize"):
            started = self.client.post("/octonous/api/connections/github/start", json={},
                                       headers=headers,
                                       base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(started.status_code, 200)
        state = next(key for kind, key in self.store.records if kind == "oauth_state")
        other = self.gateway.app.test_client()
        blocked = other.get("/octonous/oauth/github/callback?state=" + state + "&code=test",
                            base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(blocked.status_code, 401)
        with patch.object(self.routes, "exchange_code", return_value={"access_token": "private"}) as exchange:
            result = self.client.get("/octonous/oauth/github/callback?state=" + state + "&code=test",
                                     base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(result.status_code, 303)
        self.assertEqual(self.store.get("connection", "github")["access_token"], "private")
        exchange.assert_called_once()
        replay = self.client.get("/octonous/oauth/github/callback?state=" + state + "&code=test",
                                 base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(replay.status_code, 403)
        self.assertNotIn("private", result.get_data(as_text=True))

    def test_github_webhook_signature_and_delivery_deduplication(self):
        self.store.put("workflow", "flow", {"enabled": True, "trigger": "github.pr_merged",
            "prompt": "Resumir PR", "apps": ["github"], "actions": [], "skill": ""})
        payload = json.dumps({"action": "closed", "pull_request": {
            "merged": True, "title": "Fix", "html_url": "https://github.com/acme/r/pull/1"},
            "repository": {"full_name": "acme/r"}}).encode()
        bad = self.client.post("/octonous/hooks/github", data=payload,
                               headers={"X-GitHub-Event": "pull_request",
                                        "X-GitHub-Delivery": "event-1",
                                        "X-Hub-Signature-256": "sha256=wrong"})
        self.assertEqual(bad.status_code, 403)
        signature = "sha256=" + hmac.new(os.environ["OCTONOUS_GITHUB_WEBHOOK_SECRET"].encode(),
                                          payload, hashlib.sha256).hexdigest()
        headers = {"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "event-1",
                   "X-Hub-Signature-256": signature}
        with patch.object(self.routes, "run_task", return_value={"run_id": "run-1"}) as run:
            first = self.client.post("/octonous/hooks/github", data=payload, headers=headers)
            second = self.client.post("/octonous/hooks/github", data=payload, headers=headers)
        self.assertEqual(first.get_json()["runs"], [{"run_id": "run-1"}])
        self.assertEqual(second.get_json()["runs"], [])
        run.assert_called_once()

    def test_model_origin_cannot_scan_arbitrary_hosts(self):
        from octonous.agent import validate_model
        with self.assertRaises(ValueError):
            validate_model({"provider": "ollama", "model": "local",
                            "origin": "http://169.254.169.254"})

    def test_email_action_cannot_inject_headers(self):
        from octonous.providers import execute_action
        with patch("octonous.providers.api", return_value={"id": "sent"}) as send:
            execute_action(self.store, "gmail.send", {
                "to": "pessoa@example.org", "subject": "Assunto\r\nBcc: outro@example.org",
                "body": "Conteúdo para revisão",
            })
        encoded = send.call_args.kwargs["payload"]["raw"]
        wire = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        self.assertIn("Subject: Assunto Bcc: outro@example.org", wire)
        self.assertNotIn("\r\nBcc:", wire)
