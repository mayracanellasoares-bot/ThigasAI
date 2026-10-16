import sys
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as gateway
from code_bundle import make_code_zip


class CodeBundleTests(unittest.TestCase):
    def test_utf8_roundtrip_and_download(self):
        files = [
            {"name": "app.py", "content": 'print("Olá!")\n'},
            {"name": "index.html", "content": "<main>Conteúdo</main>"},
        ]
        client = gateway.app.test_client()
        response = client.post("/code/bundle", json={"files": files})
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        with ZipFile(BytesIO(response.data)) as archive:
            self.assertEqual(archive.namelist(), ["app.py", "index.html"])
            self.assertEqual(archive.read("app.py").decode("utf-8"), files[0]["content"])

    def test_rejects_invalid_payloads_and_traversal(self):
        cases = (
            {}, {"files": "invalid"}, {"files": []},
            {"files": [{"name": "../escape.py", "content": "code"}]},
            {"files": [{"name": "sub/a.py", "content": "code"}]},
            {"files": [{"name": "a.py", "content": "\x00"}]},
            {"files": [{"name": "a.py", "content": "x" * 350001}]},
            {"files": [{"name": "a.py", "content": "1"}, {"name": "A.PY", "content": "2"}]},
            {"files": [{"name": "a.py", "content": 123}]},
        )
        client = gateway.app.test_client()
        for payload in cases:
            with self.subTest(payload=str(payload)[:150]):
                result = client.post("/code/bundle", json=payload)
                self.assertIn(result.status_code, (400, 422))

    def test_limits_total_input(self):
        with self.assertRaisesRegex(ValueError, "1 MB"):
            make_code_zip([
                {"name": "a.py", "content": "x" * 340000},
                {"name": "b.py", "content": "x" * 340000},
                {"name": "c.py", "content": "x" * 340000},
            ])


if __name__ == "__main__":
    unittest.main()
