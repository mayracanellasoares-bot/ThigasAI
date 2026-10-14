import unittest
from unittest.mock import Mock, patch

from test_app import gateway
from generation_quality import inspect_generation


class HighEffortCodingTests(unittest.TestCase):
    def setUp(self):
        legacy = patch.object(gateway, "THIGAS_LEGACY_PROVIDERS_ENABLED", True)
        legacy.start()
        self.addCleanup(legacy.stop)

    def _upstream(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{
                "message": {"role": "assistant", "content": "Código revisado"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50},
        }
        return response

    def test_groq_gpt_oss_thinking_sets_real_high_parameter(self):
        with patch.object(gateway, "THIGAS_ENABLE_THINKING", False), \
             patch.object(gateway, "MARITACA_API_KEY", ""), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "fake-only"), \
             patch.object(gateway, "THIGAS_CLOUD_MODEL", "openai/gpt-oss-20b"), \
             patch.object(gateway, "THIGAS_CLOUD_URL", "https://api.groq.com/openai/v1/chat/completions"), \
             patch.object(gateway.requests, "post", return_value=self._upstream()) as post:
            result = gateway.ask_maritaca_result("Corrija este código Python", [], mode="thinking")
            payload = post.call_args.kwargs["json"]
            self.assertEqual(payload["reasoning_effort"], "high")
            self.assertIs(payload["include_reasoning"], False)
            self.assertEqual(payload["max_completion_tokens"], 16384)
            self.assertNotIn("max_tokens", payload)
            self.assertEqual(result["reasoning_effort"], "high")
            self.assertEqual(result["usage"]["total_tokens"], 50)
            self.assertIn("CRITÉRIOS DE ENTREGA DE CÓDIGO:", payload["messages"][0]["content"])
            self.assertIn("\n- Entregue código executável", payload["messages"][0]["content"])

    def test_groq_cloud_non_high_uses_medium(self):
        with patch.object(gateway, "THIGAS_ENABLE_THINKING", False), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "fake-only"), \
             patch.object(gateway, "THIGAS_CLOUD_MODEL", "openai/gpt-oss-20b"), \
             patch.object(gateway, "THIGAS_CLOUD_URL", "https://api.groq.com/openai/v1/chat/completions"), \
             patch.object(gateway.requests, "post", return_value=self._upstream()) as post:
            result = gateway.ask_maritaca_result("Olá", [], mode="cloud")
            self.assertEqual(post.call_args.kwargs["json"]["reasoning_effort"], "medium")
            self.assertEqual(result["reasoning_effort"], "medium")

    def test_thinking_maritaca_keeps_original_payload_contract(self):
        with patch.object(gateway, "THIGAS_ENABLE_THINKING", True), \
             patch.object(gateway, "MARITACA_API_KEY", "fake-only"), \
             patch.object(gateway.requests, "post", return_value=self._upstream()) as post:
            result = gateway.ask_maritaca_result("Corrija o código", [], mode="thinking")
            sent = post.call_args.kwargs["json"]
            self.assertEqual(sent["model"], gateway.MARITACA_THINKING_MODEL)
            self.assertEqual(sent["max_tokens"], 16384)
            self.assertNotIn("reasoning_effort", sent)
            self.assertNotIn("include_reasoning", sent)
            self.assertIsNone(result["reasoning_effort"])

    def test_custom_cloud_does_not_get_groq_specific_parameters(self):
        with patch.object(gateway, "THIGAS_ENABLE_THINKING", False), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "fake-only"), \
             patch.object(gateway, "THIGAS_CLOUD_MODEL", "custom/reasoner"), \
             patch.object(gateway, "THIGAS_CLOUD_URL", "https://example.org/v1/chat/completions"), \
             patch.object(gateway.requests, "post", return_value=self._upstream()) as post:
            gateway.ask_maritaca_result("Analise", [], mode="thinking")
            sent = post.call_args.kwargs["json"]
            self.assertNotIn("reasoning_effort", sent)
            self.assertNotIn("include_reasoning", sent)

    def test_api_indicates_true_high_capability_without_secrets(self):
        with patch.object(gateway, "THIGAS_ENABLE_THINKING", False), \
             patch.object(gateway, "MARITACA_API_KEY", ""), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "fake-only"), \
             patch.object(gateway, "THIGAS_CLOUD_MODEL", "openai/gpt-oss-20b"), \
             patch.object(gateway, "THIGAS_CLOUD_URL", "https://api.groq.com/openai/v1/chat/completions"):
            with gateway.app.test_client() as client:
                client.post("/auth/login", data={"password": "teste-senha-unica-123456789"})
                data = client.get("/api").get_json()
                self.assertIs(data["thinking_effort_high"], True)
                self.assertNotIn("fake-only", str(data))

    def test_coding_detection_not_used_for_general_question(self):
        self.assertNotIn("CRITÉRIOS DE ENTREGA DE CÓDIGO:", gateway.build_messages("Bom dia", [])[0]["content"])
        self.assertIn("CRITÉRIOS DE ENTREGA DE CÓDIGO:", gateway.build_messages("Faça um script Python", [])[0]["content"])

    def test_json_code_diagnostic_is_static_only(self):
        self.assertIn("possible_json_syntax_error", inspect_generation(
            '```json\n{"a": 1,}\n```', "stop"))
        self.assertNotIn("possible_json_syntax_error", inspect_generation(
            '```json\n{"a": 1}\n```', "stop"))


if __name__ == "__main__":
    unittest.main()
