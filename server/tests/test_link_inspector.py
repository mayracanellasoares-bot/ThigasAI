import unittest
from unittest.mock import patch
import socket
import link_inspector


class FakeResponse:
    status = 200
    def getheader(self, name, default=None):
        return "text/html; charset=utf-8" if name.lower() == "content-type" else default
    def read(self, limit):
        return b"<html><head><title>Pagina real</title></head><body><h1>Artigo</h1><p>Conteudo publico</p><script>ignorar</script></body></html>"


class FakeConnection:
    def __init__(self, *args, **kwargs):
        pass
    def request(self, *args, **kwargs):
        pass
    def getresponse(self):
        return FakeResponse()
    def close(self):
        pass


class LinkTests(unittest.TestCase):
    def test_block_private_and_unsafe_links(self):
        for url in (
            "http://localhost", "file:///etc/passwd", "http://127.0.0.1",
            "http://192.168.1.1", "https://example.com:8080",
            "https://user:secret@example.com",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                link_inspector.fetch_public_page(url)

    def test_public_page_returns_real_text(self):
        result_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with patch.object(link_inspector.socket, "getaddrinfo", return_value=result_addr), \
             patch.object(link_inspector.http.client, "HTTPSConnection", FakeConnection):
            result = link_inspector.fetch_public_page("https://example.com/demo")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["title"], "Pagina real")
        self.assertIn("Conteudo publico", result["text"])
        self.assertNotIn("ignorar", result["text"])

    def test_dns_private_addresses_are_rejected(self):
        records = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 443))]
        with patch.object(link_inspector.socket, "getaddrinfo", return_value=records):
            with self.assertRaisesRegex(ValueError, "privado"):
                link_inspector.fetch_public_page("https://example.com/")


if __name__ == "__main__":
    unittest.main()
