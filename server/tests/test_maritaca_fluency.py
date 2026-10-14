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
            'data: {"choices":[{"delta":{"role":"assistant","content":"Olá, "}}]}',
            'data: {"choices":[{"delta":{"content":"**mundo**!"},"finish_reason":"stop"}]}',
            'data: {"choices":[],"usage":{"prompt_tokens":9,"completion_tokens":11,"total_tokens":20}}',
            "data: [DONE]",
        ]
        provider = upstream_chunks(chunks)
        with patch.object(gateway, "MARITACA_API_KEY", "test-secret"), patch.object(gateway.requests, "post", return_value=provider) as post:
            result = self.client.post("/chat/stream", json={"message": "Saudação", "mode": "fast"}, buffered=True)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.mimetype.startswith("text/event-stream"))
        events = [json.loads(piece.split("data: ", 1)[1]) for piece in result.get_data(as_text=True).split("\n\n") if piece.startswith("event: delta\ndata: ")]
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


    def test_public_modes_reject_all_retired_cloud_adapters_without_network_calls(self):
        from unittest.mock import Mock
        with patch.object(gateway, "THIGAS_LEGACY_PROVIDERS_ENABLED", False), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_NVIDIA_ENABLED", True), \
             patch.object(gateway, "THIGAS_AION_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "retired-groq"), \
             patch.dict(gateway.os.environ, {
                 "NVIDIA_API_KEY": "retired-nvidia",
                 "AION_API_KEY": "retired-aion",
             }, clear=False), \
             patch.object(gateway.requests, "post") as sender:
            metadata = self.client.get("/api").get_json()
            self.assertEqual(set(metadata["models"].keys()), {"fast", "balanced", "thinking"})
            for field in ("cloud_enabled", "nvidia_enabled", "aion_enabled",
                          "nvidia_thinking_enabled", "aion_thinking_enabled",
                          "thinking_effort_high"):
                self.assertNotIn(field, metadata)
            for mode in ("cloud", "nvidia", "nvidia_thinking", "aion", "aion_thinking"):
                with self.subTest(mode=mode):
                    response = self.client.post("/chat", json={
                        "message": "Teste de modo aposentado", "mode": mode,
                    })
                    self.assertEqual(response.status_code, 400)
            sender.assert_not_called()

    def test_only_three_modes_are_selectable_with_trusted_engine(self):
        with patch.object(gateway, "THIGAS_LEGACY_PROVIDERS_ENABLED", False), \
             patch.object(gateway, "THIGAS_ENABLE_THINKING", True), \
             patch.object(gateway, "MARITACA_API_KEY", "configured-server-key"):
            self.assertEqual(gateway.choose_model("fast"), gateway.MARITACA_FAST_MODEL)
            self.assertEqual(gateway.choose_model("balanced"), gateway.MARITACA_MODEL)
            self.assertEqual(gateway.choose_model("thinking"), gateway.MARITACA_THINKING_MODEL)
            self.assertTrue(self.client.get("/api").get_json()["thinking_enabled"])
        with patch.object(gateway, "THIGAS_LEGACY_PROVIDERS_ENABLED", False), \
             patch.object(gateway, "THIGAS_ENABLE_THINKING", False), \
             patch.object(gateway, "THIGAS_CLOUD_ENABLED", True), \
             patch.object(gateway, "THIGAS_CLOUD_API_KEY", "legacy-key"):
            with self.assertRaises(gateway.GatewayError) as exc:
                gateway.choose_model("thinking")
            self.assertEqual(exc.exception.status_code, 403)


    def test_code_generation_prompt_includes_app_and_game_requirements(self):
        for request in ("Crie um jogo 2D em HTML", "Faça um aplicativo responsivo",
                        "Desenvolva um site completo", "Corrija esta interface"):
            with self.subTest(request=request):
                system = gateway.build_messages(request, [])[0]["content"]
                self.assertIn("REQUISITOS DE ENTREGA DE CÓDIGO", system)
                self.assertIn("cercas Markdown", system)
        self.assertNotIn("REQUISITOS DE ENTREGA DE CÓDIGO",
                         gateway.build_messages("Como está o tempo?", [])[0]["content"])

    def test_stream_syntax_and_unfinished_fence_are_flagged_for_review(self):
        from generation_quality import inspect_generation
        provider = upstream_chunks([
            'data: {"choices":[{"delta":{"content":"```python\\nif True print(1)\\n```"},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ])
        events = "".join(relay_maritaca_stream(provider, model="sabia-4", max_tokens=32768))
        frames = [json.loads(frame.split("data: ", 1)[1])
                  for frame in events.split("\n\n") if frame.startswith("event: done")]
        self.assertEqual(len(frames), 1)
        self.assertIn("possible_python_syntax_error", frames[0]["quality_flags"])
        self.assertNotIn("output_limit", frames[0]["quality_flags"])

        cutoff = upstream_chunks([
            'data: {"choices":[{"delta":{"content":"```python\\nprint(2)"},"finish_reason":"length"}]}',
            "data: [DONE]",
        ])
        cut_events = "".join(relay_maritaca_stream(cutoff, model="sabia-4", max_tokens=32768))
        cut_frames = [json.loads(frame.split("data: ", 1)[1])
                      for frame in cut_events.split("\n\n") if frame.startswith("event: done")]
        self.assertEqual(cut_frames[0]["quality_flags"], inspect_generation("```python\nprint(2)", "length"))
        self.assertIn("output_limit", cut_frames[0]["quality_flags"])
        self.assertIn("unclosed_code_block", cut_frames[0]["quality_flags"])

    def test_longer_output_budget_is_within_provider_documented_maximum(self):
        self.assertEqual(gateway.MARITACA_MAX_TOKENS, 32768)


if __name__ == "__main__":
    unittest.main()