"""Aion Labs integration tests: requests are mocked; no credits or secrets used."""
import unittest
from unittest.mock import Mock, patch

from test_app import gateway
import aion_provider


def upstream(status=200, answer="Aion respondeu"):
    response = Mock()
    response.status_code = status
    response.headers = {"Retry-After": "12"} if status == 429 else {}
    response.json.return_value = {
        "model": "aion-labs/aion-3.5-mini",
        "choices": [{
            "message": {"role": "assistant", "content": answer,
                        "reasoning": "pensamento privado"},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 7, "completion_tokens": 13, "total_tokens": 20},
    }
    return response


class AionLabsTests(unittest.TestCase):
    def setUp(self):
        legacy = patch.object(gateway, "THIGAS_LEGACY_PROVIDERS_ENABLED", True)
        legacy.start()
        self.addCleanup(legacy.stop)
        patch_pool = patch.object(aion_provider, "aion_keys", aion_provider.KeyPool())
        patch_pool.start()
        self.addCleanup(patch_pool.stop)

    def test_aion_endpoint_cannot_redirect_secrets(self):
        self.assertTrue(aion_provider.is_aion_endpoint(aion_provider.AION_URL))
        for url in (
            "http://api.aionlabs.ai/v1/chat/completions",
            "https://api.aionlabs.ai.evil.example/v1/chat/completions",
            "https://api.aionlabs.ai/v1/models",
            "https://api.aionlabs.ai:444/v1/chat/completions",
            "https://api.aionlabs.ai/v1/chat/completions?debug=1",
            "https://user:secret@api.aionlabs.ai/v1/chat/completions",
        ):
            with self.subTest(url=url):
                self.assertFalse(aion_provider.is_aion_endpoint(url))
        with self.assertRaises(ValueError):
            aion_provider.post_aion(Mock(), {}, ("secret",),
                                    url="https://unknown.example/v1/chat/completions")

    def test_aion_existing_key_aliases_and_deduplication(self):
        self.assertEqual(
            aion_provider.configured_aion_keys(environ={"AION_LABS_API_KEY": "alias"}),
            ("alias",)
        )
        self.assertEqual(
            aion_provider.configured_aion_keys(environ={
                "AION_API_KEY": "one", "AION_API_KEY_2": "one",
                "AION_API_KEY_3": "third",
            }),
            ("one", "third")
        )

    def test_aion_default_model_standard_uses_low_reasoning(self):
        with patch.dict(gateway.os.environ, {"AION_API_KEY": "private-aion"}, clear=True), \
             patch.object(gateway, "THIGAS_AION_ENABLED", True), \
             patch.object(gateway, "THIGAS_AION_MODEL", "aion-labs/aion-3.5-mini"), \
             patch.object(gateway.requests, "post", return_value=upstream()) as post:
            result = gateway.ask_maritaca_result("Ajude com Python", [], mode="aion")
        self.assertEqual(post.call_args.args[0], aion_provider.AION_URL)
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer private-aion")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "aion-labs/aion-3.5-mini")
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertEqual(payload["max_tokens"], gateway.MARITACA_MAX_TOKENS)
        self.assertIs(payload["reasoning_split"], True)
        self.assertNotIn("max_completion_tokens", payload)
        self.assertNotIn("include_reasoning", payload)
        self.assertEqual(result["answer"], "Aion respondeu")
        self.assertNotIn("pensamento privado", result["answer"])
        self.assertEqual(result["reasoning_effort"], "low")
        self.assertEqual(result["usage"], {"prompt_tokens": 7, "completion_tokens": 13, "total_tokens": 20})
        self.assertFalse(result["provider_failover_used"])
        self.assertEqual(result["provider_attempt_count"], 1)

    def test_aion_high_mode_sends_supported_high(self):
        with patch.dict(gateway.os.environ, {"THIGAS_AION_API_KEY": "aion-high"}, clear=True), \
             patch.object(gateway, "THIGAS_AION_ENABLED", True), \
             patch.object(gateway, "THIGAS_AION_MODEL", "aion-labs/aion-3.5"), \
             patch.object(gateway.requests, "post", return_value=upstream()) as post:
            result = gateway.ask_maritaca_result("Explicar tecnologia", [], mode="aion_thinking")
        self.assertEqual(post.call_args.kwargs["json"]["reasoning_effort"], "high")
        self.assertEqual(result["reasoning_effort"], "high")

    def test_aion_older_models_respect_reasoning_capability(self):
        self.assertEqual(aion_provider.reasoning_effort_for_mode(
            "aion-labs/aion-3.0-mini", "aion_thinking"), "high")
        self.assertEqual(aion_provider.reasoning_effort_for_mode(
            "aion-labs/aion-2.0", "aion"), "low")
        self.assertIsNone(aion_provider.reasoning_effort_for_mode(
            "aion-labs/aion-rp-llama-3.1-8b", "aion"))
        with patch.dict(gateway.os.environ, {"AION_API_KEY": "aion-secret"}, clear=True), \
             patch.object(gateway, "THIGAS_AION_ENABLED", True), \
             patch.object(gateway, "THIGAS_AION_MODEL", "aion-labs/aion-rp-llama-3.1-8b"), \
             patch.object(gateway.requests, "post", return_value=upstream()) as post:
            gateway.ask_maritaca_result("Olá", [], mode="aion")
            self.assertNotIn("reasoning_effort", post.call_args.kwargs["json"])
            with self.assertRaises(gateway.GatewayError) as exc:
                gateway.ask_maritaca_result("Olá", [], mode="aion_thinking")
        self.assertEqual(exc.exception.status_code, 403)
        post.assert_called_once()

    def test_aion_fails_over_when_one_credential_is_rate_limited(self):
        with patch.dict(gateway.os.environ, {
            "AION_API_KEY": "first", "AION_API_KEY_2": "second",
        }, clear=True), \
             patch.object(gateway, "THIGAS_AION_ENABLED", True), \
             patch.object(gateway, "THIGAS_AION_MODEL", "aion-labs/aion-3.5-mini"), \
             patch.object(gateway.requests, "post",
                          side_effect=[upstream(429), upstream(200)]) as post:
            result = gateway.ask_maritaca_result("Teste", [], mode="aion")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer first")
        self.assertEqual(post.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer second")
        self.assertTrue(result["provider_failover_used"])
        self.assertEqual(result["provider_attempt_count"], 2)

    def test_aion_credentials_do_not_expose_other_provider(self):
        with patch.dict(gateway.os.environ, {
            "AION_API_KEY": "aion-secret",
            "NVIDIA_API_KEY": "nvidia-secret",
            "GROQ_API_KEY_2": "groq-secret",
        }, clear=True), \
             patch.object(gateway, "THIGAS_AION_ENABLED", True), \
             patch.object(gateway, "THIGAS_AION_MODEL", "aion-labs/aion-3.5-mini"), \
             patch.object(gateway.requests, "post", return_value=upstream()) as post:
            result = gateway.ask_maritaca_result("Teste", [], mode="aion")
            with gateway.app.test_client() as client:
                login = client.post("/auth/login",
                                    data={"password": "teste-senha-unica-123456789"})
                self.assertEqual(login.status_code, 303)
                public_config = client.get("/api").get_json()
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer aion-secret")
        self.assertTrue(public_config["aion_enabled"])
        self.assertTrue(public_config["aion_thinking_enabled"])
        self.assertNotIn("aion_key_count", public_config)
        self.assertEqual(public_config["models"]["aion"], "aion-labs/aion-3.5-mini")
        for secret in ("aion-secret", "nvidia-secret", "groq-secret"):
            self.assertNotIn(secret, str(public_config))
            self.assertNotIn(secret, str(result))

    def test_aion_not_configured_is_disabled_without_api_calls(self):
        with patch.dict(gateway.os.environ, {}, clear=True), \
             patch.object(gateway, "THIGAS_AION_ENABLED", True), \
             patch.object(gateway.requests, "post") as post:
            with self.assertRaises(gateway.GatewayError) as exc:
                gateway.ask_maritaca_result("Olá", [], mode="aion")
            self.assertEqual(exc.exception.status_code, 403)
            post.assert_not_called()
            with gateway.app.test_client() as client:
                client.post("/auth/login", data={"password": "teste-senha-unica-123456789"})
                data = client.get("/api").get_json()
            self.assertFalse(data["aion_enabled"])
            self.assertNotIn("aion_key_count", data)

    def test_aion_explicitly_disabled_ignores_configured_key(self):
        with patch.dict(gateway.os.environ, {"AION_API_KEY": "private"}, clear=True), \
             patch.object(gateway, "THIGAS_AION_ENABLED", False), \
             patch.object(gateway.requests, "post") as post:
            with self.assertRaises(gateway.GatewayError):
                gateway.ask_maritaca_result("Olá", [], mode="aion")
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
