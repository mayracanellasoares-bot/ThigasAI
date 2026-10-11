import importlib.util
import os
import sys
import struct
from pathlib import Path
from io import BytesIO
import unittest
from unittest.mock import patch


SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SERVER))
spec = importlib.util.spec_from_file_location("thigas_test_app", SERVER / "app.py")
gateway = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gateway
# Não registra webhooks nem lê credenciais reais durante a suíte.
with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "MARITACA_API_KEY": ""}):
    spec.loader.exec_module(gateway)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        gateway.app.config["TESTING"] = True
        self.client = gateway.app.test_client()

    def get(self, path):
        response = self.client.get(path)
        self.addCleanup(response.close)
        return response

    def test_url_pasted_in_chat_is_inspected_automatically(self):
        page = {"status": 200, "title": "Página pública", "text": "Exemplo de página para análise",
                "note": "", "redirect": None}
        answer = {"answer": "Resumo da página", "usage": {"prompt_tokens": 10,
                  "completion_tokens": 5, "total_tokens": 15}, "finish_reason": "stop",
                  "model": gateway.MARITACA_MODEL}
        with patch.object(gateway.link_inspector, "fetch_public_page", return_value=page) as check, \
             patch.object(gateway, "ask_maritaca_result", return_value=answer) as call:
            response = self.client.post("/chat", json={"message": "https://example.org/novidades"})
        self.assertEqual(response.status_code, 200)
        check.assert_called_once_with("https://example.org/novidades")
        prompt = call.call_args.args[0]
        self.assertIn("Exemplo de página para análise", prompt)
        self.assertIn("FONTE WEB", prompt)
        self.assertEqual(response.get_json()["answer"], "Resumo da página")

    def test_chat_with_private_url_does_not_fetch(self):
        with patch.object(gateway.link_inspector, "fetch_public_page", side_effect=ValueError("Endereço privado bloqueado")), \
             patch.object(gateway, "ask_maritaca_result", return_value={
                 "answer": "Não posso abrir esse endereço", "usage": {},
                 "finish_reason": "stop", "model": gateway.MARITACA_MODEL
             }) as call:
            response = self.client.post("/chat", json={"message": "http://localhost/admin"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("não foi possível consultar", call.call_args.args[0])

    def test_image_upload_requires_configured_visual_model(self):
        with patch.dict(gateway.os.environ, {"THIGAS_VISION_MODEL": "", "THIGAS_VISION_API_KEY": ""}), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", ""):
            response = self.client.post("/image/describe")
        self.assertEqual(response.status_code, 503)

    def test_image_upload_rejects_invalid_data_without_provider_call(self):
        with patch.dict(gateway.os.environ, {"THIGAS_VISION_MODEL": "vision-test",
                                              "THIGAS_VISION_API_KEY": "private-test-token"}):
            with patch.object(gateway.requests, "post") as external:
                response = self.client.post("/image/describe",
                    data={"image": (BytesIO(b"not an image"), "test.png", "image/png")},
                    content_type="multipart/form-data")
        self.assertEqual(response.status_code, 415)
        external.assert_not_called()

    def test_root_serves_real_chat_layout(self):
        response = self.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/html")
        self.assertEqual(response.headers["Cache-Control"], "no-cache")
        html = response.get_data(as_text=True)
        for marker in ('lang="pt-BR"', 'id="chat-form"', 'id="file-input"'):
            self.assertIn(marker, html)
        self.assertNotIn("cdn.tailwindcss.com", html)
        self.assertNotIn("PixelWizard", html)

    def test_assets_exist_and_are_safe_paths(self):
        for asset in ("chat.js", "chat.css"):
            with self.subTest(asset=asset):
                self.assertEqual(self.get("/static/" + asset).status_code, 200)
        self.assertEqual(self.get("/static/../app.py").status_code, 404)

    def test_pwa_manifest_and_installation_metadata(self):
        response = self.get("/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/manifest+json")
        manifest = response.get_json()
        self.assertEqual(manifest["name"], "THIGAS AI")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertFalse(manifest["prefer_related_applications"])
        self.assertTrue({"192x192", "512x512"}.issubset({icon["sizes"] for icon in manifest["icons"]}))
        self.assertIn("any", {icon["sizes"] for icon in manifest["icons"]})
        html = self.get("/").get_data(as_text=True)
        self.assertIn('rel="manifest" href="/manifest.webmanifest"', html)
        self.assertIn('id="btn-install"', html)

    def test_pwa_png_icons_match_manifest_dimensions(self):
        for size in (192, 512):
            response = self.get(f"/static/icons/icon-{size}.png")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "image/png")
            data = response.get_data()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (size, size))

    def test_worker_scope_and_freshness_headers(self):
        response = self.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/javascript")
        self.assertEqual(response.headers["Service-Worker-Allowed"], "/")
        self.assertEqual(response.headers["Cache-Control"], "no-cache")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("thigas-pwa-", response.get_data(as_text=True))

    def test_document_upload_limit_is_20_mib(self):
        self.assertEqual(gateway.MAX_DOCUMENT_BYTES, 20 * 1024 * 1024)
        self.assertEqual(gateway.app.config["MAX_CONTENT_LENGTH"], 22 * 1024 * 1024)
        # Mock only the upload byte threshold so the test stays lightweight.
        with patch.object(gateway, "MAX_DOCUMENT_BYTES", 10), \
             patch.object(gateway, "extract_document_text", return_value=("Texto", False)):
            accepted = self.client.post(
                "/document/extract",
                data={"file": (BytesIO(b"x" * 10), "relatorio.pdf")},
                content_type="multipart/form-data",
            )
            self.assertEqual(accepted.status_code, 200)
            over_limit = self.client.post(
                "/document/extract",
                data={"file": (BytesIO(b"x" * 11), "relatorio.pdf")},
                content_type="multipart/form-data",
            )
            self.assertEqual(over_limit.status_code, 413)

    def test_document_endpoint_rejects_missing_and_unsupported_files(self):
        self.assertEqual(self.client.post("/document/extract").status_code, 400)
        response = self.client.post(
            "/document/extract",
            data={"file": (BytesIO(b"abc"), "arquivo.zip")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 415)

    def test_metadata_moved_without_changing_contract(self):
        data = self.get("/api").get_json()
        self.assertEqual(data["endpoint"], "/chat")
        self.assertEqual(data["telegram_webhook"], "/telegram/webhook")

    def test_health_and_cors_preserved(self):
        response = self.get("/health")
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(self.client.options("/chat").status_code, 204)

    def test_chat_contract_for_browser_and_apk(self):
        history = [{"role": "user", "content": "Olá"}, {"role": "assistant", "content": "Olá!"}]
        with patch.object(gateway, "ask_maritaca_result", return_value={
            "answer": "```python\nprint(1)\n```",
            "usage": {"prompt_tokens": 31, "completion_tokens": 42, "total_tokens": 73},
            "finish_reason": "stop",
        }) as ask:
            response = self.client.post("/chat", json={"message": " Ajude ", "history": history})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["answer"], "```python\nprint(1)\n```")
        self.assertIn("model", response.get_json())
        self.assertEqual(response.get_json()["usage"], {"prompt_tokens": 31, "completion_tokens": 42, "total_tokens": 73})
        self.assertEqual(response.get_json()["max_output_tokens"], 16384)
        self.assertEqual(response.get_json()["finish_reason"], "stop")
        ask.assert_called_once_with("Ajude", history)

    def test_legacy_question_field_preserved(self):
        with patch.object(gateway, "ask_maritaca_result", return_value={
            "answer": "OK",
            "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
            "finish_reason": None,
        }) as ask:
            self.assertEqual(self.client.post("/chat", json={"question": "teste"}).status_code, 200)
        ask.assert_called_once_with("teste", [])

    def test_chat_rejects_empty_and_oversized_messages_without_api_call(self):
        with patch.object(gateway, "ask_maritaca_result") as ask:
            self.assertEqual(self.client.post("/chat", json={"message": " "}).status_code, 400)
            self.assertEqual(self.client.post("/chat", json={"message": "a" * 60001}).status_code, 413)
            self.assertEqual(self.client.post("/chat", data="not-json").status_code, 400)
        ask.assert_not_called()

    def test_provider_errors_keep_status(self):
        for status in (429, 502, 503, 504):
            with self.subTest(status=status), patch.object(gateway, "ask_maritaca_result", side_effect=gateway.GatewayError("Falha", status)):
                response = self.client.post("/chat", json={"message": "teste"})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.get_json(), {"error": "Falha"})

    def test_server_never_sends_secret_to_browser(self):
        with patch.object(gateway, "MARITACA_API_KEY", "fake-secret-test"), patch.object(gateway, "TELEGRAM_BOT_TOKEN", "fake-telegram-test"):
            for path in ("/", "/api", "/health", "/static/chat.js"):
                response = self.get(path)
                self.assertNotIn("fake-secret-test", response.get_data(as_text=True))
                self.assertNotIn("fake-telegram-test", response.get_data(as_text=True))

    def test_maritaca_usage_comes_from_provider_not_character_estimates(self):
        fake_response = unittest.mock.Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "Saída real"}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 128, "completion_tokens": 819, "total_tokens": 947},
        }
        with patch.object(gateway, "MARITACA_API_KEY", "fake-secret"), \
             patch.object(gateway.requests, "post", return_value=fake_response) as request_post:
            data = self.client.post("/chat", json={"message": "Olá"}).get_json()
        self.assertEqual(data["usage"], {"prompt_tokens": 128, "completion_tokens": 819, "total_tokens": 947})
        self.assertEqual(data["finish_reason"], "length")
        self.assertEqual(data["answer"], "Saída real")
        self.assertEqual(request_post.call_args.kwargs["json"]["max_tokens"], 16384)
        self.assertEqual(request_post.call_args.kwargs["timeout"], (10, 300))

    def test_missing_or_invalid_usage_is_null_not_fabricated(self):
        for provided in (None, {}, {"prompt_tokens": "123", "completion_tokens": True, "total_tokens": -1}):
            fake_response = unittest.mock.Mock()
            fake_response.status_code = 200
            fake_response.json.return_value = {
                "choices": [{"message": {"content": "Resposta"}}],
                **({"usage": provided} if provided is not None else {}),
            }
            with self.subTest(usage=provided), \
                 patch.object(gateway, "MARITACA_API_KEY", "fake-secret"), \
                 patch.object(gateway.requests, "post", return_value=fake_response):
                data = self.client.post("/chat", json={"message": "Teste"}).get_json()
                self.assertEqual(data["usage"], {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None})
                self.assertIsNone(data["finish_reason"])

    def test_telegram_and_document_text_only_contract_preserved(self):
        fake_response = unittest.mock.Mock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "Apenas texto"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
        }
        with patch.object(gateway, "MARITACA_API_KEY", "fake-secret"), \
             patch.object(gateway.requests, "post", return_value=fake_response):
            self.assertEqual(gateway.ask_maritaca("teste", []), "Apenas texto")

    def test_telegram_missing_configuration(self):
        self.assertEqual(self.client.post("/telegram/webhook", json={}).status_code, 503)

    def test_telegram_secret_validation_and_background_dispatch_preserved(self):
        update = {"message": {"chat": {"id": 1}, "text": "teste"}}
        with patch.object(gateway, "TELEGRAM_BOT_TOKEN", "fake"), patch.object(gateway, "TELEGRAM_WEBHOOK_SECRET", "secret"), patch.object(gateway.telegram_executor, "submit") as submit:
            self.assertEqual(self.client.post("/telegram/webhook", json=update).status_code, 403)
            response = self.client.post("/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "secret"})
            self.assertEqual(response.get_json(), {"ok": True})
            submit.assert_called_once_with(gateway.process_telegram_update, update)

    def test_telegram_start_does_not_call_provider(self):
        update = {"message": {"chat": {"id": 100}, "text": "/start"}}
        with patch.object(gateway, "telegram_send_message") as send, patch.object(gateway, "ask_maritaca") as ask:
            gateway.process_telegram_update(update)
        send.assert_called_once()
        ask.assert_not_called()


    def test_mode_selection_uses_cloud_for_thinking(self):
        self.assertEqual(gateway.choose_model("fast"), gateway.MARITACA_MODEL)
        with patch.object(gateway, "THIGAS_CLOUD_ENABLED", False):
            response = self.client.post("/chat", json={"message": "Teste", "mode": "thinking"})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(self.get("/api").get_json()["thinking_enabled"], False)
        with patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), patch.object(gateway, "THIGAS_CLOUD_API_KEY", "fake-secret"):
            self.assertEqual(gateway.choose_model("thinking"), gateway.THIGAS_CLOUD_MODEL)
            upstream = unittest.mock.Mock()
            upstream.status_code = 200
            upstream.json.return_value = {
                "choices": [{"message": {"content": "Resposta avançada"}, "finish_reason": "stop"}],
            }
            with patch.object(gateway.requests, "post", return_value=upstream) as post:
                response = self.client.post("/chat", json={"message": "Teste", "mode": "thinking"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["model"], gateway.THIGAS_CLOUD_MODEL)
            self.assertEqual(post.call_args.kwargs["json"]["model"], gateway.THIGAS_CLOUD_MODEL)
            self.assertEqual(post.call_args.args[0], gateway.THIGAS_CLOUD_URL)
            self.assertIn(gateway.THIGAS_CLOUD_MODEL, post.call_args.kwargs["json"]["messages"][0]["content"])

    def test_brittech_identity_in_system_prompt(self):
        self.assertIn("Brittech inc.", gateway.SYSTEM_PROMPT)
        self.assertIn("Como posso ajudar você hoje?", gateway.SYSTEM_PROMPT)

    def test_cloud_20b_requires_server_opt_in_and_a_real_key(self):
        with patch.object(gateway, "THIGAS_CLOUD_ENABLED", False), patch.object(gateway, "THIGAS_CLOUD_API_KEY", "example-test-key"):
            response = self.client.post("/chat", json={"message": "Olá", "mode": "cloud"})
            self.assertEqual(response.status_code, 403)
            self.assertFalse(self.get("/api").get_json()["cloud_enabled"])
        with patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), patch.object(gateway, "THIGAS_CLOUD_API_KEY", ""):
            response = self.client.post("/chat", json={"message": "Olá", "mode": "cloud"})
            self.assertEqual(response.status_code, 403)

    def test_cloud_20b_uses_private_credential_and_correct_endpoint(self):
        upstream = unittest.mock.Mock()
        upstream.status_code = 200
        upstream.json.return_value = {
            "model": "openai/gpt-oss-20b",
            "choices": [{"message": {"content": "Resposta do 20B"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        with (patch.object(gateway, "THIGAS_CLOUD_ENABLED", True),
              patch.object(gateway, "THIGAS_CLOUD_API_KEY", "example-cloud-key"),
              patch.object(gateway, "MARITACA_API_KEY", ""),
              patch.object(gateway.requests, "post", return_value=upstream) as post):
            response = self.client.post("/chat", json={"message": "Explique Python", "mode": "cloud"})
            metadata = self.get("/api").get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["model"], gateway.THIGAS_CLOUD_MODEL)
        self.assertEqual(response.get_json()["usage"]["total_tokens"], 30)
        self.assertTrue(metadata["cloud_enabled"])
        self.assertNotIn("example-cloud-key", str(metadata))
        self.assertEqual(post.call_args.args[0], gateway.THIGAS_CLOUD_URL)
        self.assertEqual(post.call_args.kwargs["json"]["model"], gateway.THIGAS_CLOUD_MODEL)
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer example-cloud-key")
        self.assertIn(gateway.THIGAS_CLOUD_MODEL, post.call_args.kwargs["json"]["messages"][0]["content"])

    def test_client_cannot_inject_arbitrary_model(self):
        with patch.object(gateway, "ask_maritaca_result") as ask:
            response = self.client.post("/chat", json={"message": "Teste", "mode": "private-model", "model": "arbitrary"})
        self.assertEqual(response.status_code, 400)
        ask.assert_not_called()

    def test_malformed_provider_response_returns_gateway_error(self):
        upstream = unittest.mock.Mock()
        upstream.status_code = 200
        for malformed in ([], {"choices": [{}]}, {"choices": [None]}, {"choices": [{"message": "invalid"}]}):
            upstream.json.return_value = malformed
            with self.subTest(payload=malformed), patch.object(gateway, "MARITACA_API_KEY", "fake"), patch.object(gateway.requests, "post", return_value=upstream):
                response = self.client.post("/chat", json={"message": "Olá"})
            self.assertEqual(response.status_code, 502)

if __name__ == "__main__":
    unittest.main()
