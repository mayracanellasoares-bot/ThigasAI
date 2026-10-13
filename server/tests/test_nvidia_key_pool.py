import unittest
from unittest.mock import Mock, patch

import nvidia_key_pool
from test_app import gateway


def reply(status, answer="NVIDIA OK"):
    response = Mock()
    response.status_code = status
    response.headers = {"Retry-After": "15"} if status == 429 else {}
    response.json.return_value = {
        "choices": [{"message": {"content": answer}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 7, "total_tokens": 11},
    }
    return response


class NvidiaKeyTests(unittest.TestCase):
    def setUp(self):
        self.pool = patch.object(nvidia_key_pool, "nvidia_keys", nvidia_key_pool.KeyPool())
        self.pool.start()
        self.addCleanup(self.pool.stop)

    def test_exact_public_endpoint_only(self):
        self.assertTrue(nvidia_key_pool.is_nvidia_endpoint(nvidia_key_pool.NVIDIA_URL))
        for url in ("http://integrate.api.nvidia.com/v1/chat/completions",
                    "https://other.example/v1/chat/completions",
                    "https://integrate.api.nvidia.com/other"):
            with self.subTest(url=url):
                self.assertFalse(nvidia_key_pool.is_nvidia_endpoint(url))
        with self.assertRaises(ValueError):
            nvidia_key_pool.post_nvidia(Mock(), {}, ("secret",), url="https://other.example/v1/chat/completions")

    def test_reads_two_or_three_private_keys_without_duplicates(self):
        self.assertEqual(nvidia_key_pool.configured_nvidia_keys(environ={
            "NVIDIA_API_KEY_2": "n2", "NVIDIA_API_KEY_3": "n3",
        }), ("n2", "n3"))
        self.assertEqual(nvidia_key_pool.configured_nvidia_keys(environ={
            "NVIDIA_API_KEY": "n1", "NVIDIA_API_KEY_2": "n1",
            "NVIDIA_API_KEY_3": "n3",
        }), ("n1", "n3"))

    def test_nvidia_is_not_sent_to_groq(self):
        with patch.dict(gateway.os.environ, {"NVIDIA_API_KEY": "private-nvidia"}, clear=True), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", True), \
             patch.object(gateway.requests, "post", return_value=reply(200)) as sender:
            result = gateway.ask_maritaca_result("Escreva Python", [], mode="nvidia")
        self.assertEqual(sender.call_args.args[0], nvidia_key_pool.NVIDIA_URL)
        self.assertEqual(sender.call_args.kwargs["headers"]["Authorization"], "Bearer private-nvidia")
        self.assertEqual(result["model"], gateway.THIGAS_NVIDIA_MODEL)
        self.assertEqual(result["usage"]["total_tokens"], 11)
        self.assertEqual(result["reasoning_effort"], "medium")

    def test_nvidia_high_mode_uses_model_specific_supported_parameters(self):
        with patch.dict(gateway.os.environ, {"NVIDIA_API_KEY": "private-nvidia"}, clear=True), \
             patch.object(gateway, "THIGAS_NVIDIA_MODEL", "openai/gpt-oss-20b"), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", True), \
             patch.object(gateway.requests, "post", return_value=reply(200)) as sender:
            result = gateway.ask_maritaca_result("Corrija HTML", [], mode="nvidia_thinking")
        sent = sender.call_args.kwargs["json"]
        self.assertEqual(sent["model"], "openai/gpt-oss-20b")
        self.assertEqual(sent["reasoning_effort"], "high")
        self.assertEqual(sent["max_tokens"], 16384)
        self.assertNotIn("max_completion_tokens", sent)
        self.assertNotIn("include_reasoning", sent)
        self.assertEqual(result["reasoning_effort"], "high")

    def test_unrecognized_model_does_not_pretend_to_have_high_effort(self):
        with patch.dict(gateway.os.environ, {"NVIDIA_API_KEY": "private-nvidia"}, clear=True), \
             patch.object(gateway, "THIGAS_NVIDIA_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5"), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", True), \
             patch.object(gateway.requests, "post") as sender:
            with self.assertRaises(gateway.GatewayError) as error:
                gateway.ask_maritaca_result("Pergunta", [], mode="nvidia_thinking")
        self.assertEqual(error.exception.status_code, 403)
        sender.assert_not_called()

    def test_nvidia_fails_over_from_429_to_second_key(self):
        with patch.dict(gateway.os.environ, {"NVIDIA_API_KEY": "first", "NVIDIA_API_KEY_2": "second"}, clear=True), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", True), \
             patch.object(gateway.requests, "post", side_effect=[reply(429), reply(200)]) as sender:
            result = gateway.ask_maritaca_result("Teste", [], mode="nvidia")
        self.assertEqual(sender.call_count, 2)
        self.assertEqual(result["answer"], "NVIDIA OK")
        self.assertEqual(sender.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer first")
        self.assertEqual(sender.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer second")

    def test_nvidia_stays_opt_in_and_metadata_is_secret_free(self):
        with patch.dict(gateway.os.environ, {"NVIDIA_API_KEY_2": "SECRET-TWO", "NVIDIA_API_KEY_3": "SECRET-THREE"}, clear=True), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", True), \
             patch.object(gateway, "THIGAS_NVIDIA_MODEL", "openai/gpt-oss-20b"):
            with gateway.app.test_client() as client:
                client.post("/auth/login", data={"password": "teste-senha-unica-123456789"})
                info = client.get("/api").get_json()
            self.assertTrue(info["nvidia_enabled"])
            self.assertTrue(info["nvidia_thinking_enabled"])
            self.assertEqual(info["nvidia_key_count"], 2)
            self.assertNotIn("SECRET-TWO", str(info))
            self.assertNotIn("SECRET-THREE", str(info))

    def test_nvidia_disabled_mode_never_calls_upstream(self):
        with patch.dict(gateway.os.environ, {"NVIDIA_API_KEY": "secret"}, clear=True), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", False), \
             patch.object(gateway.requests, "post") as sender:
            with self.assertRaises(gateway.GatewayError) as error:
                gateway.ask_maritaca_result("Teste", [], mode="nvidia")
            self.assertEqual(error.exception.status_code, 403)
            sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()
