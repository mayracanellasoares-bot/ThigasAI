import hashlib
import hmac
import base64
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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

    def test_api_auth_errors_are_readable_json(self):
        response = self.client.get("/octonous/api/workflows")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.is_json)
        self.assertTrue(response.get_json()["error"])

    def test_malformed_workflow_permissions_are_rejected_without_saving(self):
        headers = self.owner()
        valid = {"title": "Teste", "prompt": "Preparar resumo", "trigger": "manual",
                 "apps": ["github"], "actions": []}
        for change in ({"apps": [{}]}, {"actions": [[]]}, {"trigger": {}}):
            with self.subTest(change=change):
                response = self.client.post("/octonous/api/workflows", json={**valid, **change},
                    headers=headers, base_url="https://thigas-coder-gateway.onrender.com")
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.is_json)
        self.assertEqual(self.store.all("workflow"), [])

    def test_malformed_model_action_does_not_break_chat(self):
        from octonous.agent import model_answer
        for action_type in ([], {}, None):
            with self.subTest(action_type=action_type):
                upstream = Mock()
                upstream.json.return_value = {"choices": [{"message": {"content": json.dumps({
                    "answer": "Preciso de mais detalhes.",
                    "proposed_action": {"type": action_type, "payload": {}},
                })}}]}
                with patch("octonous.agent.requests.post", return_value=upstream):
                    result = model_answer({"provider": "openai", "model": "test",
                                           "api_key": "fake"}, "Preparar resumo", "{}")
                self.assertIsNone(result["proposed_action"])

    def test_notion_action_preserves_approved_page_content(self):
        from octonous.providers import execute_action
        content = "Resumo aprovado. " * 180
        with patch("octonous.providers.api", return_value={"id": "page"}) as create:
            execute_action(self.store, "notion.page.create", {
                "parent_id": "a" * 32, "title": "Acompanhamento", "body": content,
            })
        blocks = create.call_args.kwargs["payload"]["children"]
        actual = "".join(x["paragraph"]["rich_text"][0]["text"]["content"] for x in blocks)
        self.assertEqual(actual, content)
        self.assertTrue(all(len(x["paragraph"]["rich_text"][0]["text"]["content"]) <= 2000
                            for x in blocks))

    def test_maritaca_uses_existing_render_key_and_preserves_approval_boundary(self):
        from octonous.agent import model_answer, validate_model
        with patch.dict(os.environ, {"MARITACA_API_KEY": "secret-from-render"}):
            config = validate_model({"provider": "maritaca", "model": "sabia-4"})
            self.assertEqual(config["api_key"], "")
            upstream = Mock()
            upstream.json.return_value = {"choices": [{"message": {"content": json.dumps({
                "answer": "Prepararei o resumo.",
                "proposed_action": None,
            })}}]}
            with patch("octonous.agent.requests.post", return_value=upstream) as post:
                answer = model_answer(config, "Preparar resumo", "{}")
        self.assertEqual(answer["answer"], "Prepararei o resumo.")
        self.assertIsNone(answer["proposed_action"])
        self.assertEqual(post.call_args.args[0],
                         "https://chat.maritaca.ai/api/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"],
                         "Bearer secret-from-render")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "sabia-4")

    def test_maritaca_without_key_is_rejected(self):
        from octonous.agent import validate_model
        with patch.dict(os.environ, {"MARITACA_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "MARITACA_API_KEY"):
                validate_model({"provider": "maritaca", "model": "sabia-4"})

    def test_maritaca_becomes_default_when_render_has_key(self):
        with patch.dict(os.environ, {"MARITACA_API_KEY": "server-key",
                                      "MARITACA_MODEL": "sabia-4"}):
            headers = self.owner()
            model = self.client.get("/octonous/api/model", headers=headers,
                base_url="https://thigas-coder-gateway.onrender.com").get_json()["model"]
        self.assertEqual(model["provider"], "maritaca")
        self.assertEqual(model["model"], "sabia-4")
        self.assertTrue(model["configured"])
        self.assertNotIn("api_key", model)

    def test_database_name_is_not_treated_as_connection_url(self):
        from octonous.storage import Store
        with self.assertRaisesRegex(ValueError, "Internal Database URL"):
            Store(dsn="thigas_octonous_db", encryption_key=Fernet.generate_key().decode())

    def test_drive_oauth_requests_scoped_access_and_escapes_search(self):
        from octonous.providers import authorize_url, search_one
        from urllib.parse import parse_qs, urlsplit
        with patch.dict(os.environ, {"OCTONOUS_GOOGLE_CLIENT_ID": "test-client",
                                      "OCTONOUS_GOOGLE_CLIENT_SECRET": "test-secret"}):
            url = authorize_url("google_drive", "safe-state")
        params = parse_qs(urlsplit(url).query)
        self.assertIn("https://www.googleapis.com/auth/drive.file", params["scope"][0])
        self.assertIn("https://www.googleapis.com/auth/drive.readonly", params["scope"][0])
        self.assertEqual(params["redirect_uri"][0],
                         "https://thigas-coder-gateway.onrender.com/octonous/oauth/google_drive/callback")
        with patch("octonous.providers.api", return_value={
            "files": [{"name": "Notas", "mimeType": "application/vnd.google-apps.document",
                       "webViewLink": "https://docs.google.com/document/d/test-file"}]}) as call:
            result = search_one(self.store, "google_drive", "quinn's")
        self.assertEqual(result[0]["title"], "Notas")
        self.assertIn(r"quinn\'s", call.call_args.kwargs["params"]["q"])

    def test_drive_document_requires_approval_and_is_written_once(self):
        headers = self.owner()
        self.store.put("approval", "drive-doc", {
            "status": "pending", "action": "google_drive.document.create",
            "payload": {"title": "Relatório", "body": "Texto revisado."}, "run_id": "run-doc"})
        calls = []
        def mock_google_api(store, provider, method, url, **kwargs):
            calls.append((provider, method, url, kwargs))
            return {"documentId": "doc_12345678"} if url.endswith("/documents") else {}
        with patch("octonous.providers.api", side_effect=mock_google_api):
            first = self.client.post("/octonous/api/approvals/drive-doc/decision",
                json={"decision": "approve"}, headers=headers,
                base_url="https://thigas-coder-gateway.onrender.com")
            again = self.client.post("/octonous/api/approvals/drive-doc/decision",
                json={"decision": "approve"}, headers=headers,
                base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(first.get_json()["result"]["url"],
                         "https://docs.google.com/document/d/doc_12345678/edit")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][3]["payload"]["requests"][0]["insertText"]["text"],
                         "Texto revisado.")

    def test_drive_spreadsheet_uses_raw_cells_not_formula_evaluation(self):
        from octonous.providers import execute_action, ProviderError
        calls = []
        def mock_google_api(store, provider, method, url, **kwargs):
            calls.append((method, url, kwargs))
            return {"spreadsheetId": "sheet_12345678"} if method == "POST" else {}
        with patch("octonous.providers.api", side_effect=mock_google_api):
            result = execute_action(self.store, "google_drive.spreadsheet.create",
                                    {"title": "Custos", "csv": "Item,Valor\nExemplo,=1+1"})
        self.assertIn("spreadsheets/d/sheet_12345678", result["url"])
        self.assertEqual(calls[1][2]["params"]["valueInputOption"], "RAW")
        self.assertEqual(calls[1][2]["payload"]["values"][1][1], "=1+1")
        with patch("octonous.providers.api") as api_call:
            with self.assertRaises(ProviderError):
                execute_action(self.store, "google_drive.spreadsheet.create",
                               {"title": "Limite", "csv": "x\n" * 101})
            api_call.assert_not_called()

    def test_drive_presentation_creates_text_shapes_without_code_execution(self):
        from octonous.providers import execute_action
        calls = []
        def mock_google_api(store, provider, method, url, **kwargs):
            calls.append((method, url, kwargs))
            return {"presentationId": "deck_12345678"} if method == "POST" and url.endswith("/presentations") else {}
        with patch("octonous.providers.api", side_effect=mock_google_api):
            result = execute_action(self.store, "google_drive.presentation.create",
                {"title": "Plano", "outline": "# Abertura\nDescrição\n---\n# Etapas\nTarefa 1"})
        self.assertIn("deck_12345678", result["url"])
        requests_list = calls[1][2]["payload"]["requests"]
        self.assertEqual(sum("createSlide" in x for x in requests_list), 2)
        self.assertTrue(any(x.get("insertText", {}).get("text") == "Etapas" for x in requests_list))

    def test_google_drive_requires_connection_before_queueing(self):
        response = {"type": "google_drive.document.create",
                    "payload": {"title": "Teste", "body": "Documento"}}
        self.assertIsNone(self.routes.queue_approval(self.store, "run", response))
        self.store.put("connection", "google_drive", {"access_token": "test-token"})
        self.assertIsNotNone(self.routes.queue_approval(self.store, "run", response))

    def test_apps_script_requires_fixed_google_url_and_secret(self):
        from octonous.providers import drive_script_configured, drive_script_request, ProviderError
        valid = {"OCTONOUS_DRIVE_SCRIPT_URL":
                 "https://script.google.com/macros/s/AKfycb_12345/exec",
                 "OCTONOUS_DRIVE_SCRIPT_SECRET": "q" * 48}
        with patch.dict(os.environ, valid):
            self.assertTrue(drive_script_configured())
        for url, key in (("https://example.org/exec", "q" * 48),
                         ("http://script.google.com/macros/s/AKfycb_12345/exec", "q" * 48),
                         (valid["OCTONOUS_DRIVE_SCRIPT_URL"], "weak")):
            with self.subTest(url=url, key=key):
                with patch.dict(os.environ, {"OCTONOUS_DRIVE_SCRIPT_URL": url,
                                              "OCTONOUS_DRIVE_SCRIPT_SECRET": key}):
                    self.assertFalse(drive_script_configured())
                    with patch("octonous.providers.requests.post") as post:
                        with self.assertRaises(ProviderError):
                            drive_script_request("search", {"query": "teste"})
                    post.assert_not_called()

    def test_apps_script_search_without_google_oauth_and_fixed_secret(self):
        from octonous.providers import search_one, drive_script_request, ProviderError
        url = "https://script.google.com/macros/s/AKfycb_12345/exec"
        with patch.dict(os.environ, {"OCTONOUS_DRIVE_SCRIPT_URL": url,
                                      "OCTONOUS_DRIVE_SCRIPT_SECRET": "secret-" + "q" * 48}):
            response = Mock(status_code=200, ok=True)
            response.json.return_value = {"ok": True, "data": [
                {"title": "Pasta de projetos", "summary": "Pasta autorizada",
                 "detail": "Pasta", "url": "https://drive.google.com/drive/folders/1234567890"}]}
            with patch("octonous.providers.requests.post", return_value=response) as post:
                matches = search_one(self.store, "google_drive", "pastas")
            self.assertEqual(matches[0]["title"], "Pasta de projetos")
            self.assertEqual(post.call_args.args[0], url)
            self.assertFalse(post.call_args.kwargs["allow_redirects"])
            self.assertEqual(post.call_args.kwargs["json"]["action"], "search")
            self.assertEqual(post.call_args.kwargs["json"]["payload"], {"query": "pastas"})
            with patch("octonous.providers.requests.post", return_value=response):
                with self.assertRaises(ProviderError):
                    drive_script_request("delete", {"file_id": "1234567890"})

    def test_apps_script_redirect_is_constrained_to_googleusercontent(self):
        from octonous.providers import drive_script_request, ProviderError
        url = "https://script.google.com/macros/s/AKfycb_12345/exec"
        with patch.dict(os.environ, {"OCTONOUS_DRIVE_SCRIPT_URL": url,
                                      "OCTONOUS_DRIVE_SCRIPT_SECRET": "q" * 48}):
            redirected = Mock(status_code=302, headers={
                "Location": "https://script.googleusercontent.com/macros/echo?user_content_key=ok"})
            completed = Mock(status_code=200, ok=True)
            completed.json.return_value = {"ok": True, "data": {"id": "test-doc-id"}}
            with patch("octonous.providers.requests.post", return_value=redirected):
                with patch("octonous.providers.requests.get", return_value=completed) as get:
                    self.assertEqual(drive_script_request("document.create",
                        {"title": "Teste", "body": "Conteúdo"})["id"], "test-doc-id")
                    get.assert_called_once()
            redirected.headers["Location"] = "https://attacker.example/token"
            with patch("octonous.providers.requests.post", return_value=redirected):
                with patch("octonous.providers.requests.get") as get:
                    with self.assertRaisesRegex(ProviderError, "Redirecionamento"):
                        drive_script_request("search", {"query": "teste"})
                    get.assert_not_called()

    def test_apps_script_connection_and_approval_work_without_oauth(self):
        url = "https://script.google.com/macros/s/AKfycb_12345/exec"
        with patch.dict(os.environ, {"OCTONOUS_DRIVE_SCRIPT_URL": url,
                                      "OCTONOUS_DRIVE_SCRIPT_SECRET": "q" * 48}):
            headers = self.owner()
            connections = self.client.get("/octonous/api/connections",
                base_url="https://thigas-coder-gateway.onrender.com").get_json()["connections"]
            drive = next(item for item in connections if item["provider"] == "google_drive")
            self.assertEqual(drive["mode"], "script")
            self.assertTrue(drive["connected"])
            self.assertNotIn("q" * 48, json.dumps(connections))
            proposal = {"type": "google_drive.document.create",
                        "payload": {"title": "Relatório", "body": "Texto revisado."}}
            self.assertIsNotNone(self.routes.queue_approval(self.store, "run", proposal))
            start = self.client.post("/octonous/api/connections/google_drive/start",
                headers=headers, json={}, base_url="https://thigas-coder-gateway.onrender.com")
            self.assertEqual(start.status_code, 409)
            with patch.object(self.routes, "search_one", return_value=[{
                    "title": "Planos", "summary": "Arquivo", "url": "https://drive.google.com"}]):
                found = self.routes.search_all(self.store, "planos", "run")
            self.assertIn("google_drive", found)

    def test_apps_script_execution_preserves_explicit_approval(self):
        from octonous.providers import execute_action
        url = "https://script.google.com/macros/s/AKfycb_12345/exec"
        with patch.dict(os.environ, {"OCTONOUS_DRIVE_SCRIPT_URL": url,
                                      "OCTONOUS_DRIVE_SCRIPT_SECRET": "q" * 48}):
            with patch("octonous.providers.drive_script_request", return_value={
                    "url": "https://docs.google.com/document/d/test-doc/edit"}) as request:
                result = execute_action(self.store, "google_drive.document.create",
                                        {"title": "Plano", "body": "Texto", "folder_id": "allowed_id"})
            request.assert_called_once_with("document.create", {
                "title": "Plano", "body": "Texto", "folder_id": "allowed_id"})
            self.assertIn("docs.google.com", result["url"])

    def test_apps_script_source_uses_an_allowlist_and_no_embedded_secret(self):
        source = (SERVER.parent / "integrations/google_apps_script/Code.gs").read_text()
        self.assertIn("ALLOWED_FOLDER_IDS", source)
        self.assertIn("getScriptProperties()", source)
        self.assertIn("authorizedFolder_(roots, payload.folder_id)", source)
        self.assertIn("sameSecret_(message.secret, key)", source)
        self.assertNotIn("OCTONOUS_DRIVE_SCRIPT_SECRET=", source)

    def test_database_status_requires_owner_and_rejects_invalid_uri(self):
        self.assertEqual(self.client.get("/octonous/api/database/status", base_url="https://thigas-coder-gateway.onrender.com").status_code, 401)
        with patch("octonous.routes.login_allowed", return_value=True):
            self.owner()
        with patch.dict(os.environ, {"OCTONOUS_DATABASE_URL": "thigas_octonous_db"}):
            with patch("octonous.routes.psycopg.connect") as connect:
                result = self.client.get("/octonous/api/database/status", base_url="https://thigas-coder-gateway.onrender.com")
        self.assertFalse(result.get_json()["ok"])
        self.assertEqual(result.get_json()["code"], "configuration")
        connect.assert_not_called()

    def test_database_status_checks_read_only_select(self):
        with patch("octonous.routes.login_allowed", return_value=True):
            self.owner()
        with patch("octonous.routes.psycopg.connect") as connect:
            result = self.client.get("/octonous/api/database/status", base_url="https://thigas-coder-gateway.onrender.com")
        self.assertTrue(result.get_json()["ok"])
        connect.assert_called_once()
        connect.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")

    def test_database_status_handles_connection_failure_without_traceback(self):
        import psycopg
        with patch("octonous.routes.login_allowed", return_value=True):
            self.owner()
        with patch("octonous.routes.psycopg.connect",
                   side_effect=psycopg.OperationalError("Connection error")):
            result = self.client.get("/octonous/api/database/status", base_url="https://thigas-coder-gateway.onrender.com")
        self.assertFalse(result.get_json()["ok"])
        self.assertEqual(result.get_json()["code"], "connection")
        self.assertNotIn("Traceback", result.get_data(as_text=True))

    def test_database_api_error_is_503(self):
        import psycopg
        with patch("octonous.routes.login_allowed", return_value=True):
            self.owner()
        with patch.object(self.routes, "db", side_effect=psycopg.OperationalError("Connection error")):
            result = self.client.get("/octonous/api/workflows", base_url="https://thigas-coder-gateway.onrender.com")
        self.assertEqual(result.status_code, 503)
        self.assertTrue(result.is_json)

    def test_postgres_schema_initialization_is_thread_safe_and_once_per_database(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Lock
        from uuid import uuid4
        from octonous.storage import Store
        statements = []
        sync = Lock()

        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, trace):
                return False

            def execute(self, sql, *args):
                with sync:
                    statements.append(sql)
                return self

            def fetchone(self):
                return None

            def commit(self):
                with sync:
                    statements.append("COMMIT")

        dsn = "postgresql://user:private@localhost/test_" + uuid4().hex
        secret = Fernet.generate_key().decode()

        def read_record(_):
            store = Store(dsn=dsn, encryption_key=secret)
            return store.get("config", "model")

        with patch("octonous.storage.psycopg.connect",
                   side_effect=lambda *args, **kwargs: FakeConnection()):
            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(list(pool.map(read_record, range(20))), [None] * 20)
        self.assertEqual(sum(q.lstrip().startswith("CREATE TABLE") for q in statements), 3)
        self.assertEqual(statements.count("SELECT pg_advisory_xact_lock(81753024)"), 1)
        self.assertEqual(statements.count("COMMIT"), 1)
        self.assertEqual(sum(q.startswith("SELECT data FROM octonous_records")
                             for q in statements), 20)

    def test_missing_google_drive_blocks_task_instead_of_claiming_completion(self):
        proposal = {"answer": "Vou criar o documento.",
                    "proposed_action": {"type": "google_drive.document.create",
                                         "payload": {"title": "Relatório", "body": "Conteúdo"}}}
        with patch.object(self.routes, "model_answer", return_value=proposal), \
             patch.object(self.routes, "drive_script_configured", return_value=False):
            result = self.routes.run_task(self.store, "Criar documento", search_enabled=False)
        self.assertIn("Tarefa não executada:", result["answer"])
        self.assertIn("Google Drive", result["answer"])
        self.assertIsNone(result["approval_id"])
        self.assertEqual(self.store.get("run", result["run_id"])["status"], "blocked")
        self.assertEqual(self.store.all("approval"), [])

    def test_authorized_google_drive_proposal_still_requires_human_approval(self):
        proposal = {"answer": "Documento preparado.",
                    "proposed_action": {"type": "google_drive.document.create",
                                         "payload": {"title": "Relatório", "body": "Conteúdo"}}}
        self.store.put("connection", "google_drive", {"access_token": "test"})
        with patch.object(self.routes, "model_answer", return_value=proposal), \
             patch.object(self.routes, "drive_script_configured", return_value=False):
            result = self.routes.run_task(self.store, "Criar documento", search_enabled=False)
        self.assertIsNotNone(result["approval_id"])
        self.assertEqual(self.store.get("run", result["run_id"])["status"], "awaiting_approval")
        self.assertEqual(self.store.get("approval", result["approval_id"])["status"], "pending")

    def test_workflow_without_permission_cannot_claim_action_completed(self):
        proposal = {"answer": "O e-mail foi enviado.",
                    "proposed_action": {"type": "gmail.send",
                                        "payload": {"to": "test@example.org", "body": "Oi"}}}
        self.store.put("connection", "gmail", {"access_token": "test"})
        workflow = {"id": "workflow1", "apps": ["gmail"], "actions": []}
        with patch.object(self.routes, "model_answer", return_value=proposal):
            result = self.routes.run_task(self.store, "Enviar aviso", workflow=workflow,
                                          search_enabled=False)
        self.assertIn("não executada", result["answer"])
        self.assertEqual(self.store.get("run", result["run_id"])["status"], "blocked")
        self.assertEqual(self.store.all("approval"), [])
