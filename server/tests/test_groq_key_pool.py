import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import groq_key_pool
from test_app import gateway


def fake_response(code: int, *, retry_after=None):
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    response = Mock()
    response.status_code = code
    response.headers = headers
    response.json.return_value = {
        "choices": [{"message": {"content": "Resposta do modelo"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 8, "total_tokens": 11},
    }
    return response


class GroqThreeKeyTests(unittest.TestCase):
    def setUp(self):
        self.pool_patcher = patch.object(groq_key_pool, "groq_keys", groq_key_pool.KeyPool())
        self.pool_patcher.start()
        self.addCleanup(self.pool_patcher.stop)

    def test_read_three_unique_keys_without_exposing_values(self):
        env = {
            "GROQ_API_KEY_2": "second",
            "GROQ_API_KEY_3": "third",
        }
        self.assertEqual(groq_key_pool.configured_keys("first", environ=env),
                         ("first", "second", "third"))
        self.assertEqual(groq_key_pool.configured_keys("first", environ={
            "GROQ_API_KEY_2": "first",
            "GROQ_API_KEY_3": "third",
        }), ("first", "third"))
        self.assertEqual(groq_key_pool.configured_keys("", environ={
            "GROQ_API_KEY": "primary", "THIGAS_CLOUD_API_KEY_2": "second",
            "THIGAS_CLOUD_API_KEY_3": "third",
        }), ("primary", "second", "third"))

    def test_round_robin_uses_three_healthy_keys(self):
        sender = Mock(side_effect=[fake_response(200) for _ in range(6)])
        pool = groq_key_pool.groq_keys
        for _ in range(6):
            result = groq_key_pool.post_with_failover(
                sender, "https://api.groq.com/openai/v1/chat/completions",
                {"model": "test"}, ("one", "two", "three"))
            self.assertEqual(result.status_code, 200)
        selected = [call.kwargs["headers"]["Authorization"] for call in sender.call_args_list]
        self.assertEqual(selected, [
            "Bearer one", "Bearer two", "Bearer three",
            "Bearer one", "Bearer two", "Bearer three",
        ])

    def test_429_moves_to_next_key_and_respects_cooldown(self):
        sender = Mock(side_effect=[fake_response(429, retry_after=20), fake_response(200),
                                   fake_response(200)])
        payload = {"model": "openai/gpt-oss-20b"}
        result = groq_key_pool.post_with_failover(
            sender, "https://api.groq.com/openai/v1/chat/completions",
            payload, ("key-A", "key-B"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(sender.call_count, 2)
        self.assertEqual(sender.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer key-A")
        self.assertEqual(sender.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer key-B")
        groq_key_pool.post_with_failover(
            sender, "https://api.groq.com/openai/v1/chat/completions",
            payload, ("key-A", "key-B"))
        self.assertEqual(sender.call_count, 3)
        self.assertEqual(sender.call_args_list[2].kwargs["headers"]["Authorization"], "Bearer key-B")

    def test_invalid_primary_falls_back_to_valid_key(self):
        sender = Mock(side_effect=[fake_response(401), fake_response(200)])
        result = groq_key_pool.post_with_failover(
            sender, "https://api.groq.com/openai/v1/chat/completions",
            {}, ("invalid", "valid"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(sender.call_count, 2)

    def test_400_does_not_retry_and_preserves_error(self):
        sender = Mock(return_value=fake_response(400))
        result = groq_key_pool.post_with_failover(
            sender, "https://api.groq.com/openai/v1/chat/completions",
            {}, ("first", "second"))
        self.assertEqual(result.status_code, 400)
        sender.assert_called_once()

    def test_timeout_does_not_retry_unknown_billable_request(self):
        import requests
        sender = Mock(side_effect=requests.Timeout("fake timeout"))
        with self.assertRaises(requests.Timeout):
            groq_key_pool.post_with_failover(
                sender, "https://api.groq.com/openai/v1/chat/completions",
                {}, ("first", "second"))
        sender.assert_called_once()

    def test_all_cooldown_returns_none_without_retrying(self):
        sender = Mock(side_effect=[fake_response(429), fake_response(429)])
        self.assertEqual(groq_key_pool.post_with_failover(
            sender, "https://api.groq.com/openai/v1/chat/completions",
            {}, ("first", "second")).status_code, 429)
        self.assertIsNone(groq_key_pool.post_with_failover(
            sender, "https://api.groq.com/openai/v1/chat/completions",
            {}, ("first", "second")))
        self.assertEqual(sender.call_count, 2)

    def test_cloud_secondary_keys_work_even_without_primary(self):
        with patch.dict(os.environ, {"THIGAS_CLOUD_API_KEY_2": "secondary", "THIGAS_CLOUD_API_KEY_3": "tertiary"},
                        clear=True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", ""), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_URL", "https://api.groq.com/openai/v1/chat/completions"), \
             patch.object(gateway, "THIGAS_ENABLE_THINKING", False):
            self.assertEqual(gateway.cloud_api_keys(), ("secondary", "tertiary"))
            self.assertEqual(gateway.choose_model("thinking"), gateway.THIGAS_CLOUD_MODEL)
            with gateway.app.test_client() as client:
                client.post("/auth/login", data={"password": "teste-senha-unica-123456789"})
                result = client.get("/api").get_json()
            self.assertEqual(result["cloud_key_count"], 2)
            self.assertEqual(result["models"]["thinking"], gateway.THIGAS_CLOUD_MODEL)
            self.assertNotIn("secondary", str(result))
            self.assertNotIn("tertiary", str(result))

    def test_cloud_gateway_fails_over_and_keeps_usage_real(self):
        with patch.dict(os.environ, {
            "THIGAS_CLOUD_API_KEY_2": "spare-a",
            "THIGAS_CLOUD_API_KEY_3": "spare-b",
        }, clear=True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "primary"), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_URL", "https://api.groq.com/openai/v1/chat/completions"), \
             patch.object(gateway, "THIGAS_ENABLE_THINKING", False), \
             patch.object(gateway.requests, "post",
                          side_effect=[fake_response(429), fake_response(200)]) as sender:
            result = gateway.ask_maritaca_result("Corrija Python", [], mode="thinking")
        self.assertEqual(sender.call_count, 2)
        self.assertEqual(result["answer"], "Resposta do modelo")
        self.assertEqual(result["reasoning_effort"], "high")
        self.assertEqual(result["usage"], {
            "prompt_tokens": 3, "completion_tokens": 8, "total_tokens": 11,
        })
        self.assertEqual(sender.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer primary")
        self.assertEqual(sender.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer spare-a")

    def test_non_groq_provider_never_receives_secondary_credentials(self):
        with patch.dict(os.environ, {"GROQ_API_KEY_2": "secret-spare"}, clear=True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "first"), \
             patch.object(gateway, "THIGAS_CLOUD_URL", "https://other.example/v1/chat/completions"), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway.requests, "post", return_value=fake_response(200)) as sender:
            result = gateway.ask_maritaca_result("Teste", [], mode="cloud")
        self.assertEqual(result["answer"], "Resposta do modelo")
        sender.assert_called_once()
        self.assertEqual(sender.call_args.kwargs["headers"]["Authorization"], "Bearer first")

    def test_disabled_cloud_never_invokes_groq(self):
        with patch.object(gateway, "THIGAS_CLOUD_ENABLED", False), \
             patch.object(gateway.requests, "post") as post:
            with self.assertRaises(gateway.GatewayError) as error:
                gateway.ask_maritaca_result("Teste", [], mode="cloud")
        self.assertEqual(error.exception.status_code, 403)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
