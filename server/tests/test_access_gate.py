"""Regressões da autenticação única para web e PWA."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import access_gate

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
spec = importlib.util.spec_from_file_location("thigas_auth_test_gateway", SERVER / "app.py")
gateway = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gateway
SECRET = "teste-segredo-de-sessao-maior-que-trinta-e-dois"
PASSWORD = "senha-ficticia-de-testes-123"
SETTINGS = {
    "TELEGRAM_BOT_TOKEN": "",
    "MARITACA_API_KEY": "",
    "THIGAS_ACCESS_ENABLED": "true",
    "THIGAS_ACCESS_USERNAME": "thigas",
    "THIGAS_ACCESS_PASSWORD": PASSWORD,
    "THIGAS_SESSION_SECRET": SECRET,
}
with patch.dict(os.environ, SETTINGS):
    spec.loader.exec_module(gateway)


class AccessGateTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch.dict(os.environ, SETTINGS)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        gateway.app.config["TESTING"] = True
        self.client = gateway.app.test_client()
        access_gate._FAILED_LOGINS.clear()

    def get(self, path):
        return self.client.get(path, base_url="https://thigas.test")

    def post(self, path, **kwargs):
        return self.client.post(path, base_url="https://thigas.test", **kwargs)

    def sign_in(self):
        return self.post("/login", data={"username": "thigas", "password": PASSWORD})

    def test_anonymous_visitors_cannot_use_chat_documents_or_static_html(self):
        self.assertEqual(self.get("/").status_code, 302)
        self.assertEqual(self.get("/workspace").status_code, 302)
        self.assertEqual(self.get("/static/index.html").status_code, 302)
        self.assertEqual(self.get("/static/workspace.html").status_code, 302)
        self.assertEqual(self.get("/api").status_code, 401)
        self.assertEqual(self.post("/chat", json={"message": "Olá"}).status_code, 401)
        self.assertEqual(self.post("/document/extract").status_code, 401)
        self.assertEqual(self.post("/workspace/api/upload").status_code, 403)
        self.assertEqual(self.get("/health").status_code, 200)
        self.assertEqual(self.get("/sw.js").status_code, 200)
        self.assertEqual(self.get("/manifest.webmanifest").status_code, 200)
        self.assertEqual(self.get("/static/icons/icon.svg").status_code, 200)

    def test_login_requires_correct_shared_credentials_and_sets_secure_cookie(self):
        html = self.get("/login").get_data(as_text=True)
        self.assertIn('name="password"', html)
        self.assertIn("THIGAS AI", html)
        bad = self.post("/login", data={"username": "thigas", "password": "incorreta"})
        self.assertEqual(bad.status_code, 401)
        self.assertNotIn(PASSWORD, bad.get_data(as_text=True))
        good = self.sign_in()
        self.assertEqual(good.status_code, 303)
        cookie = good.headers.get("Set-Cookie", "")
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        page = self.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Encerrar", page.get_data(as_text=True))
        self.assertEqual(page.headers["Cache-Control"], "no-store, private")
        self.assertNotIn("Access-Control-Allow-Origin", page.headers)
        self.assertEqual(self.get("/api").status_code, 200)
        self.assertEqual(self.get("/workspace/api/session").status_code, 200)

    def test_logout_ends_session_and_requires_new_login(self):
        self.sign_in()
        response = self.post("/logout")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, "/login")
        self.assertEqual(self.get("/").status_code, 302)
        self.assertEqual(self.post("/chat", json={"message": "oi"}).status_code, 401)

    def test_rejects_cross_origin_actions_even_with_valid_session(self):
        self.sign_in()
        request = self.post("/chat", json={"message": "oi"}, headers={"Origin": "https://evil.test"})
        self.assertEqual(request.status_code, 403)
        request = self.post("/logout", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(request.status_code, 403)
        self.assertEqual(self.get("/").status_code, 200)

    def test_five_wrong_passwords_activate_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.post("/login", data={"username": "thigas", "password": "x"}).status_code, 401)
        blocked = self.sign_in()
        self.assertEqual(blocked.status_code, 429)
        self.assertTrue(blocked.headers.get("Retry-After"))

    def test_missing_credentials_fail_closed_without_breaking_health(self):
        with patch.dict(os.environ, {"THIGAS_ACCESS_PASSWORD": ""}):
            self.assertEqual(self.get("/").status_code, 503)
            self.assertEqual(self.get("/login").status_code, 503)
            self.assertEqual(self.get("/health").status_code, 200)

    def test_gate_disabled_keeps_existing_public_app_unchanged(self):
        with patch.dict(os.environ, {"THIGAS_ACCESS_ENABLED": "false"}):
            page = self.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertNotIn("Encerrar", page.get_data(as_text=True))
            self.assertEqual(self.get("/api").status_code, 200)
            self.assertEqual(self.get("/login").status_code, 302)


if __name__ == "__main__":
    unittest.main()
