import json
import unittest
from unittest.mock import Mock, patch

from test_app import gateway
from maritaca_stream import relay_maritaca_stream, measured_usage


def upstream_chunks(lines, status=200):
    response = Mock()
    response.status_code = status
    response.iter_lines.return_value = [line.encode("utf-8") for line in lines]
    return response


class MaritacaFluencyTests(unittest.TestCase):
    def setUp(self):
        gateway.app.config["TESTING"] = True
        self.client = gateway.app.test_client()

    def test_three_maritaca_models_are_distinct(self):
        with patch.object(gateway, "MARITACA_API_KEY", "private"), patch.object(gateway, "THIGAS_ENABLE_THINKING", True):
            self.assertEqual(gateway.choose_model("fast"), "sabiazinho-4")
            self.assertEqual(gateway.choose_model("balanced"), gateway.MARITACA_MODEL)
            self.assertEqual(gateway.choose_model("thinking"), gateway.MARITACA_THINKING_MODEL)
            data = self.client.get("/api").get_json()
            self.assertTrue(data["maritaca_fast_enabled"])
            self.assertTrue(data["maritaca_balanced_enabled"])
            self.assertTrue(data["maritaca_stream_enabled"])
            self.assertTrue(data["maritaca_thinking_stream_enabled"])
            self.assertEqual(data["models"]["fast"], "sabiazinho-4")
            self.assertEqual(data["models"]["balanced"], gateway.MARITACA_MODEL)

    def test_streamed_response_progress_and_real_token_counts(self):
        chunks = [
            'data: {"choices":[{"delta":{"role":"assistant","content":"Olá, "}}]}\',
            'data: {"choices":[{"delta":{"content":"**mundo**!"},"finish_reason":"stop"}]}\',
            'data: {"choices":[],"usage":{"prompt_tokens":9,"completion_tokens":11,"total_tokens":20}}\',
            "data: [DONE]",
        ]
        provider = upstream_chunks(chunks)
        with patch.object(gateway, "MARITACA_API_KEY", "test-secret"), patch.object(gateway.requests, "post", return_value=provider) as post:
            result = self.client.post("/chat/stream", json={"message": "Saudação", "mode": "fast"}, buffered=True)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.mimetype.startswith("text/event-stream"))
        events = [json.loads(piece[6:]) for piece in result.get_data(as_text=True).split("\n\n") if piece.startswith("event: delta\ndata: ")]
        self.assertEqual([e["text"] for e in events], ["Olá, ", "**mundo**!"])
        done = [json.loads(piece.split("data: ", 1)[1]) for piece in result.get_data(as_text=True).split("\n\n") if piece.startswith("event: done")]
        self.assertEqual(done[0]["answer"], "Olá, **mundo**!")
        self.assertEqual(done[0]["usage"]["total_tokens"], 20)
        self.assertEqual(done[0]["model"], "sabiazinho-4")
        self.assertNotIn("test-secret", result.get_data(as_text=True))
        provider.close.assert_called_once()
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "sabiazinho-4")
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["stream_options"], {"include_usage": True})
        self.assertIs(post.call_args.kwargs["stream"], True)

    def test_thinking_stream_model_remains_private_and_explicit(self):
        provider = upstream_chunks(['data: {"choices":[{"delta":{"content":"Pensamento concluído"}}]}', "data: [DONE]"])
        with patch.object(gateway, "MARITACA_API_KEY", "private"), patch.object(gateway, "THIGAS_ENABLE_THINKING", True), patch.object(gateway.requests, "post", return_value=provider) as post:
            result = self.client.post("/chat/stream", json={"message": "Analise", "mode": "thinking"}, buffered=True)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(post.call_args.kwargs["json"]["model"], gateway.MARITACA_THINKING_MODEL)
        self.assertIn("event: done", result.get_data(as_text=True))

    def test_never_stream_other_providers_or_web_search(self):
        with patch.object(gateway.requests, "post") as post:
            for mode in ("nvidia", "aion", "cloud", "nvidia_thinking"):
                self.assertEqual(self.client.post("/chat/stream", json={"message": "Teste", "mode": mode}).status_code, 400)
            self.assertEqual(self.client.post("/chat/stream", json={"message": "Teste", "web_search": True}).status_code, 400)
            post.assert_not_called()

    def test_empty_or_truncated_stream_cannot_be_reported_as_success(self):
        provider = upstream_chunks(['data: {"choices":[{"delta":{"content":"Incompleto"}}]}'])
        events = "".join(relay_maritaca_stream(provider, model="sabia-4", max_tokens=100))
        self.assertIn("event: delta", events)
        self.assertIn("event: error", events)
        self.assertNotIn("event: done", events)
        self.assertEqual(measured_usage({"prompt_tokens": "5", "total_tokens": 4})["prompt_tokens"], None)
        provider.close.assert_called_once()

    def test_private_reasoning_and_markup_are_not_sent_as_hidden_fields(self):
        provider = upstream_chunks(['data: {"choices":[{"delta":{"reasoning":"secret thought","content":"Resposta visível"}}]}', "data: [DONE]"])
        events = "".join(relay_maritaca_stream(provider, model="sabia-4", max_tokens=100))
        self.assertIn("Resposta visível", events)
        self.assertNotIn("secret thought", events)


if __name__ == "__main__":
    unittest.main()