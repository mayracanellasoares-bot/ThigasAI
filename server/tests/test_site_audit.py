import unittest
from unittest.mock import patch

from test_app import gateway
import web_search


class SiteSecurityAuditTests(unittest.TestCase):
    def setUp(self):
        gateway.app.config["TESTING"] = True
        self.client = gateway.app.test_client()
        login = self.client.post("/auth/login", data={"password": "teste-senha-unica-123456789"})
        self.assertEqual(login.status_code, 303)

    def test_authenticated_endpoints_have_security_headers_and_no_public_cors(self):
        response = self.client.get("/api")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("microphone=(self)", response.headers["Permissions-Policy"])

    def test_cross_origin_post_is_rejected_even_when_logged_in(self):
        response = self.client.post("/chat", json={"message": "Ola"},
                                    headers={"Origin": "https://evil.example"})
        self.assertEqual(response.status_code, 403)

    def test_malformed_wikipedia_and_brave_responses_report_search_error(self):
        cases = [
            ({"query": ["invalid"]}, False),
            ({"query": None}, False),
            ({"web": "invalid"}, True),
            ({"web": []}, True),
        ]
        for payload, brave in cases:
            with self.subTest(provider="brave" if brave else "wikipedia"), \
                 patch.object(web_search, "_get_json", return_value=payload):
                with self.assertRaises(web_search.WebSearchError):
                    web_search.search_web("consulta", brave_enabled=brave, brave_key="fake-test")

    def test_search_urls_reject_invalid_private_or_control_addresses(self):
        invalid = [
            "javascript:alert(1)", "http://example.org/",
            "https://localhost/", "https://127.0.0.1/",
            "https://user:pass@example.org/", "https://example.org:9443/",
            "https://[::1]/", "https://example.org/\nInjected",
            "https://router.internal/",
        ]
        for url in invalid:
            with self.subTest(url=url):
                self.assertIsNone(web_search._safe_link(url))
        self.assertEqual(web_search._safe_link("https://docs.example.org/path"),
                         "https://docs.example.org/path")

    def test_search_snippets_are_normalized_to_one_line(self):
        self.assertEqual(web_search._clean_text("Linha\n<script>alert(1)</script> fim", 80),
                         "Linha alert(1) fim")
        self.assertEqual(web_search._clean_text("Primeira\t segunda", 80),
                         "Primeira segunda")


if __name__ == "__main__":
    unittest.main()
