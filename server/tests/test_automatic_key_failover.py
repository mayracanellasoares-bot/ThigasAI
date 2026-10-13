"""Regressões de troca automática de chaves, sem usar APIs reais."""
import unittest
from unittest.mock import Mock, patch

import requests
import groq_key_pool
import nvidia_key_pool
from test_app import gateway


def response(status, content="Resposta recuperada"):
    obj = Mock()
    obj.status_code = status
    obj.headers = {"Retry-After": "15"} if status == 429 else {}
    obj.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 9, "total_tokens": 17},
    }
    return obj


class AutomaticKeyFailoverTests(unittest.TestCase):
    def setUp(self):
        patch_groq = patch.object(groq_key_pool, "groq_keys", groq_key_pool.KeyPool())
        patch_nvidia = patch.object(nvidia_key_pool, "nvidia_keys", groq_key_pool.KeyPool())
        patch_groq.start()
        patch_nvidia.start()
        self.addCleanup(patch_groq.stop)
        self.addCleanup(patch_nvidia.stop)

    def test_connection_failure_selects_next_groq_key_and_recovers(self):
        sender = Mock(side_effect=[requests.ConnectTimeout("unreachable"), response(200)])
        attempts = []
        result = groq_key_pool.post_with_failover(sender,
            "https://api.groq.com/openai/v1/chat/completions",
            {"model": "openai/gpt-oss-20b"}, ("first", "second"),
            attempts=attempts)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(attempts, ["connect_timeout", "200"])
        self.assertEqual(sender.call_count, 2)
        self.assertEqual(sender.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer first")
        self.assertEqual(sender.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer second")

        # A chave temporariamente desconectada não é repetida na próxima chamada.
        sender2 = Mock(return_value=response(200))
        groq_key_pool.post_with_failover(sender2, "https://api.groq.com/openai/v1/chat/completions",
                                         {}, ("first", "second"))
        self.assertEqual(sender2.call_args.kwargs["headers"]["Authorization"], "Bearer second")

    def test_nvidia_gateway_switches_key_after_connection_failure(self):
        with patch.dict(gateway.os.environ, {
            "NVIDIA_API_KEY": "nvidia-one", "NVIDIA_API_KEY_2": "nvidia-two",
        }, clear=True), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", True), \
             patch.object(gateway.requests, "post",
                          side_effect=[requests.ConnectTimeout("connect failed"), response(200)]) as sender:
            result = gateway.ask_maritaca_result("Ajude a revisar Python", [], mode="nvidia_thinking")
        self.assertEqual(sender.call_count, 2)
        self.assertEqual(result["answer"], "Resposta recuperada")
        self.assertTrue(result["provider_failover_used"])
        self.assertEqual(result["provider_attempt_count"], 2)
        self.assertEqual(result["reasoning_effort"], "high")
        self.assertEqual(result["usage"]["total_tokens"], 17)
        self.assertEqual(sender.call_args_list[0].kwargs["headers"]["Authorization"], "Bearer nvidia-one")
        self.assertEqual(sender.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer nvidia-two")

    def test_groq_gateway_switches_after_http_503(self):
        with patch.dict(gateway.os.environ, {
            "THIGAS_CLOUD_API_KEY_2": "groq-second",
        }, clear=True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "groq-first"), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_URL", "https://api.groq.com/openai/v1/chat/completions"), \
             patch.object(gateway.requests, "post",
                          side_effect=[response(503), response(200)]) as sender:
            result = gateway.ask_maritaca_result("Explique", [], mode="cloud")
        self.assertEqual(sender.call_count, 2)
        self.assertTrue(result["provider_failover_used"])
        self.assertEqual(result["provider_attempt_count"], 2)

    def test_normal_success_does_not_claim_failover(self):
        sender = Mock(return_value=response(200))
        attempts = []
        self.assertEqual(groq_key_pool.post_with_failover(
            sender, "https://api.groq.com/openai/v1/chat/completions",
            {}, ("one", "two"), attempts=attempts).status_code, 200)
        sender.assert_called_once()
        self.assertEqual(attempts, ["200"])

    def test_read_timeout_does_not_retry_maybe_billable_request(self):
        sender = Mock(side_effect=requests.ReadTimeout("response lost"))
        attempts = []
        with self.assertRaises(requests.ReadTimeout):
            groq_key_pool.post_with_failover(
                sender, "https://api.groq.com/openai/v1/chat/completions",
                {}, ("one", "two"), attempts=attempts)
        sender.assert_called_once()
        self.assertEqual(attempts, [])

    def test_unknown_connection_error_does_not_retry(self):
        sender = Mock(side_effect=requests.ConnectionError("request may have been accepted"))
        with self.assertRaises(requests.ConnectionError):
            groq_key_pool.post_with_failover(
                sender, "https://api.groq.com/openai/v1/chat/completions",
                {}, ("one", "two"))
        sender.assert_called_once()

    def test_all_connect_timeouts_return_error_and_pause_keys(self):
        sender = Mock(side_effect=[requests.ConnectTimeout("first"),
                                   requests.ConnectTimeout("second")])
        with self.assertRaises(requests.ConnectTimeout):
            groq_key_pool.post_with_failover(sender,
                "https://api.groq.com/openai/v1/chat/completions", {}, ("a", "b"))
        self.assertEqual(sender.call_count, 2)
        self.assertIsNone(groq_key_pool.post_with_failover(sender,
            "https://api.groq.com/openai/v1/chat/completions", {}, ("a", "b")))
        self.assertEqual(sender.call_count, 2)

    def test_cooldown_recovers_after_expiration(self):
        pool = groq_key_pool.KeyPool()
        with patch.object(groq_key_pool.time, "monotonic", return_value=100.0):
            self.assertEqual(pool.select(("a", "b")), ("a", "b"))
            pool.cooldown("a", None)
            self.assertEqual(pool.select(("a", "b")), ("b",))
        with patch.object(groq_key_pool.time, "monotonic", return_value=111.0):
            self.assertEqual(set(pool.select(("a", "b"))), {"a", "b"})

    def test_provider_keys_never_appear_in_response_metadata(self):
        with patch.dict(gateway.os.environ, {
            "NVIDIA_API_KEY": "PRIVATE-NEVER-RETURN",
            "NVIDIA_API_KEY_2": "ANOTHER-PRIVATE-KEY",
        }, clear=True), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", True), \
             patch.object(gateway.requests, "post", side_effect=[response(503), response(200)]):
            with gateway.app.test_client() as client:
                login = client.post("/auth/login", data={"password": "teste-senha-unica-123456789"})
                self.assertEqual(login.status_code, 303)
                received = client.post("/chat", json={"message": "Uma pergunta", "mode": "nvidia"})
                self.assertEqual(received.status_code, 200)
                data = received.get_json()
        self.assertTrue(data["provider_failover_used"])
        self.assertEqual(data["provider_attempt_count"], 2)
        self.assertNotIn("PRIVATE-NEVER-RETURN", str(data))
        self.assertNotIn("ANOTHER-PRIVATE-KEY", str(data))


if __name__ == "__main__":
    unittest.main()
