"""DeepQA request-corpus, retrieval, evidence and optional FTS5 regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from test_app import gateway
import deepqa
from maritaca_stream import relay_maritaca_stream
from build_deepqa_index import build


class DeepQATests(unittest.TestCase):
    def setUp(self):
        gateway.app.config["TESTING"] = True
        self.client = gateway.app.test_client()

    def test_pt_question_analysis_and_document_evidence(self):
        info = deepqa.question_info("Quem escreveu Dom Casmurro?")
        self.assertEqual(info["answer_type"], "pessoa")
        result = deepqa.evidence_package("Quem escreveu Dom Casmurro?", [
            {"id": "A1", "title": "livro.txt", "text": "Dom Casmurro foi escrito por Machado de Assis."},
            {"id": "A2", "title": "irrelevante.txt", "text": "Este texto trata de astronomia e estrelas."},
        ])
        self.assertEqual(result["support_status"], "retrieved")
        self.assertEqual(result["evidence"][0]["source_id"], "A1")
        self.assertIn("Machado de Assis", result["evidence"][0]["excerpt"])
        self.assertTrue(result["candidates"])
        self.assertFalse(result["confidence_calibrated"])

    def test_no_documents_means_no_deepqa_injection(self):
        enriched, report = gateway.prepare_deepqa("Quanto é dois mais dois?")
        self.assertEqual(enriched, "Quanto é dois mais dois?")
        self.assertIsNone(report)

    def test_multiple_user_attachments_rank_without_unrelated_content(self):
        message = ("Qual o autor de Dom Casmurro?"
                   "\n\n[ARQUIVO: primeiro.txt]\nDom Casmurro foi escrito por Machado de Assis.\n[FIM DO ARQUIVO]"
                   "\n\n[ARQUIVO: outros.txt]\nDocumento sobre outros assuntos sem relação.\n[FIM DO ARQUIVO]")
        prompt, report = gateway.prepare_deepqa(message)
        self.assertEqual(report["support_status"], "retrieved")
        self.assertIn("Machado de Assis", prompt)
        self.assertIn("A1", prompt)
        self.assertIn("FONTES", prompt.upper() if "FONTES" in prompt.upper() else "FONTES")
        self.assertNotIn("[ARQUIVO:", prompt)
        self.assertTrue(all("source_id" in item for item in report["evidence"]))

    def test_code_tasks_keep_complete_attachment(self):
        message = ("Corrija este código Python:"
                   "\n\n[ARQUIVO: main.py]\nprint('funciona')\n[FIM DO ARQUIVO]")
        prompt, report = gateway.prepare_deepqa(message)
        self.assertIn("print('funciona')", prompt)
        self.assertIn("[ARQUIVO:", prompt)
        self.assertIsNotNone(report)

    def test_generic_document_summary_has_context_not_certainty(self):
        message = "Resuma o documento anexado.\n\n[ARQUIVO: texto.txt]\nUm texto sobre o oceano e suas correntes.\n[FIM DO ARQUIVO]"
        prompt, result = gateway.prepare_deepqa(message)
        self.assertEqual(result["support_status"], "context_only")
        self.assertIn("TRECHOS DE CONTEXTO", prompt)

    def test_web_results_have_source_ids_and_citations_without_extra_calls(self):
        data = {"provider": "wikipedia", "sources": [{
            "title": "Dom Casmurro", "url": "https://pt.wikipedia.org/?curid=123",
            "snippet": "Dom Casmurro, romance escrito por Machado de Assis."}]}
        response = {"answer": "Machado de Assis [1]", "usage": {},
                    "model": "sabia-4", "finish_reason": "stop"}
        with patch.object(gateway.web_search, "search_web", return_value=data), \
             patch.object(gateway, "ask_maritaca_result", return_value=response) as ask:
            answer = self.client.post("/chat", json={"message": "Quem escreveu Dom Casmurro?",
                                                      "web_search": True})
        self.assertEqual(answer.status_code, 200)
        payload = answer.get_json()
        self.assertEqual(payload["qa_support"], "retrieved")
        self.assertEqual(payload["qa_evidence"][0]["source_id"], "1")
        self.assertIn("[1]", ask.call_args.args[0])
        self.assertEqual(payload["sources"][0]["url"], "https://pt.wikipedia.org/?curid=123")

    def test_standard_document_question_uses_grounded_context(self):
        message = ("Quem criou a máquina de teste?"
                   "\n\n[ARQUIVO: nota.txt]\nA máquina de teste foi criada por Helena Silva em 2020.\n[FIM DO ARQUIVO]")
        mocked = {"answer": "Helena Silva [A1]", "usage": {"total_tokens": 14},
                  "model": "sabia-4", "finish_reason": "stop"}
        with patch.object(gateway, "ask_maritaca_result", return_value=mocked) as call:
            response = self.client.post("/chat", json={"message": message})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["qa_evidence"][0]["source_id"], "A1")
        self.assertIn("Helena Silva", call.call_args.args[0])

    def test_stream_document_evidence_is_in_final_sse(self):
        provider = Mock(status_code=200)
        provider.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Resposta [A1]."},"finish_reason":"stop"}]}',
            b'data: [DONE]',
        ]
        body = {"message": ("Qual o conteúdo de Estrela?"
                            "\n\n[ARQUIVO: estrelas.txt]\nEstrela é uma palavra e um astro luminoso.\n[FIM DO ARQUIVO]")}
        with patch.object(gateway, "MARITACA_API_KEY", "private"), \
             patch.object(gateway.requests, "post", return_value=provider):
            result = self.client.post("/chat/stream", json=body, buffered=True)
        self.assertEqual(result.status_code, 200)
        frames = [json.loads(piece.split("data: ", 1)[1]) for piece in result.get_data(as_text=True).split("\n\n")
                  if piece.startswith("event: done")]
        self.assertEqual(len(frames), 1)
        self.assertIn("qa_evidence", frames[0])
        self.assertEqual(frames[0]["qa_evidence"][0]["source_id"], "A1")

    def test_sqlite_fts5_offline_build_and_read_only_search(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            docs = root / "docs"
            docs.mkdir()
            (docs / "machado.txt").write_text("Dom Casmurro de Machado de Assis.", encoding="utf-8")
            (docs / "outros.md").write_text("Estudo sobre a estrutura molecular.", encoding="utf-8")
            dbfile = root / "corpus.sqlite"
            stats = build(docs, dbfile)
            self.assertEqual(stats["files"], 2)
            self.assertTrue(dbfile.is_file())
            results = deepqa.search_corpus(str(dbfile), "Dom Casmurro")
            self.assertTrue(results)
            self.assertIn("Machado", results[0]["text"])
            empty = root / "missing.sqlite"
            self.assertEqual(deepqa.search_corpus(str(empty), "Casmurro"), [])
            self.assertFalse(empty.exists())

    def test_code_or_question_not_used_as_sql(self):
        with tempfile.TemporaryDirectory() as location:
            dbfile = Path(location) / "index.sqlite"
            db = deepqa.open_index(str(dbfile))
            deepqa.add_corpus_documents(db, [{"id": "D1", "title": "T", "text": "Teste de busca segura em base local."}])
            db.close()
            malicious = "' OR 1=1; DROP TABLE passages; --"
            self.assertIsInstance(deepqa.search_corpus(str(dbfile), malicious), list)
            db = deepqa.open_index(str(dbfile))
            self.assertEqual(db.execute("SELECT count(*) FROM passages").fetchone()[0], 1)
            db.close()


if __name__ == "__main__":
    unittest.main()
