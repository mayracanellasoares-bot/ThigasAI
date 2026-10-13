import json
import unittest
from unittest.mock import Mock, patch

from test_app import gateway
import web_search


class WebSearchTests(unittest.TestCase):
    def setUp(self):
        gateway.app.config["TESTING"] = True
        self.client = gateway.app.test_client()
        result = self.client.post("/auth/login", data={"password": "teste-senha-unica-123456789"})
        self.assertEqual(result.status_code, 303)

    def test_search_is_opt_in_only_and_no_extra_network_by_default(self):
        upstream = {
            "answer": "Resposta padrão", "model": gateway.MARITACA_MODEL,
            "usage": {"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9},
            "finish_reason": "stop"
        }
        with patch.object(gateway.web_search, "search_web") as search, \
             patch.object(gateway, "ask_maritaca_result", return_value=upstream):
            result = self.client.post("/chat", json={"message": "O que é ciência?"})
        self.assertEqual(result.status_code, 200)
        search.assert_not_called()
        self.assertEqual(result.get_json()["sources"], [])
        self.assertIsNone(result.get_json()["search_provider"])

    def test_requested_search_injects_untrusted_sources_and_returns_references(self):
        found = {"provider": "wikipedia", "sources": [
            {"title": "Python", "url": "https://pt.wikipedia.org/?curid=5047",
             "snippet": "Linguagem de programação"}
        ]}
        result = {
            "answer": "A linguagem está descrita na fonte [1].", "model": gateway.MARITACA_MODEL,
            "usage": {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None},
            "finish_reason": "stop"
        }
        with patch.object(gateway.web_search, "search_web", return_value=found) as search, \
             patch.object(gateway, "ask_maritaca_result", return_value=result) as call:
            response = self.client.post("/chat", json={"message": "O que é Python?", "web_search": True})
        self.assertEqual(response.status_code, 200)
        search.assert_called_once()
        prompt = call.call_args.args[0]
        self.assertIn("[RESULTADOS DE BUSCA EXTERNA", prompt)
        self.assertIn("https://pt.wikipedia.org/?curid=5047", prompt)
        self.assertIn("Linguagem de programação", prompt)
        self.assertEqual(response.get_json()["sources"], found["sources"])
        self.assertEqual(response.get_json()["search_provider"], "wikipedia")

    def test_failed_search_does_not_fabricate_answer(self):
        with patch.object(gateway.web_search, "search_web",
                          side_effect=web_search.WebSearchError("Pesquisa indisponível.")), \
             patch.object(gateway, "ask_maritaca_result") as inference:
            response = self.client.post("/chat", json={"message": "Últimas notícias", "web_search": True})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Pesquisa indisponível", response.get_json()["error"])
        inference.assert_not_called()

    def test_search_flag_must_be_boolean(self):
        with patch.object(gateway.web_search, "search_web") as search:
            response = self.client.post("/chat", json={"message": "Teste", "web_search": "true"})
        self.assertEqual(response.status_code, 400)
        search.assert_not_called()

    def test_metadata_reports_free_fallback_without_secrets(self):
        with patch.object(gateway, "THIGAS_BRAVE_SEARCH_ENABLED", False), \
             patch.object(gateway, "THIGAS_BRAVE_SEARCH_KEY", "SECRET-TEST"):
            data = self.client.get("/api").get_json()
        self.assertEqual(data["web_search_provider"], "wikipedia")
        self.assertTrue(data["web_search_enabled"])
        self.assertNotIn("SECRET-TEST", str(data))

    def test_brave_requires_explicit_opt_in_even_if_key_exists(self):
        response = {
            "query": {"search": [{"title": "Busca geral", "pageid": 12,
                                  "snippet": "<span>Resultado</span> público."}]}
        }
        with patch.object(web_search, "_get_json", return_value=response) as get_json:
            result = web_search.search_web("Busca geral", brave_key="set-but-disabled", brave_enabled=False)
        self.assertEqual(result["provider"], "wikipedia")
        self.assertEqual(result["sources"][0]["url"], "https://pt.wikipedia.org/?curid=12")
        self.assertEqual(result["sources"][0]["snippet"], "Resultado público.")
        self.assertNotIn("set-but-disabled", str(get_json.call_args))

    def test_brave_only_when_enabled_and_key_present(self):
        with patch.object(web_search, "_get_json", return_value={
            "web": {"results": [
                {"title": "API oficial", "url": "https://example.org/docs",
                 "description": "Documentação"},
                {"title": "Inválida", "url": "javascript:alert(1)", "description": "Não deve aparecer"},
            ]}
        }) as get_json:
            result = web_search.search_web("API", brave_key="FAKE", brave_enabled=True)
        self.assertEqual(result["provider"], "brave")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(get_json.call_args.args[0], web_search.BRAVE_API)

    def test_search_removes_attachment_contents_from_outbound_query(self):
        with patch.object(web_search, "_get_json", return_value={"query": {"search": [
            {"title": "Teste", "pageid": 13, "snippet": "Um resumo"}
        ]}}) as get_json:
            web_search.search_web("Explique Python\n\n[ARQUIVO: segredo.txt]\nsenha privada\n[FIM DO ARQUIVO]")
        self.assertEqual(get_json.call_args.kwargs["params"]["srsearch"], "Explique Python")

    def test_timeout_and_no_fake_results(self):
        with patch.object(web_search, "_get_json", side_effect=web_search.WebSearchError("Indisponível")):
            with self.assertRaises(web_search.WebSearchError):
                web_search.search_web("consulta")

    def test_rate_limit_prevents_seventh_request(self):
        with patch.object(gateway, "_web_search_hits", {}):
            with gateway.app.test_request_context("/chat", environ_base={"REMOTE_ADDR": "198.51.100.8"}):
                for _ in range(6):
                    gateway._enforce_web_search_rate_limit()
                with self.assertRaises(gateway.GatewayError) as error:
                    gateway._enforce_web_search_rate_limit()
        self.assertEqual(error.exception.status_code, 429)


if __name__ == "__main__":
    unittest.main()
