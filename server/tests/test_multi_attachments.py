import os
import stat
import unittest
import zipfile
from io import BytesIO
from unittest.mock import Mock, patch

from PIL import Image
from test_app import gateway
from zip_inspector import extract_zip_text


def make_zip(entries):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in entries:
            archive.writestr(name, body)
    return buffer.getvalue()


class MultiAttachmentArchiveTests(unittest.TestCase):
    def setUp(self):
        gateway.app.config["TESTING"] = True
        self.client = gateway.app.test_client()

    def test_zip_project_has_html_js_txt_but_not_executable_binary(self):
        data = make_zip([("src/index.html", "<h1>THIGAS</h1>"),
                         ("src/main.js", "console.log(123);"),
                         ("README.txt", "Documentação válida"),
                         ("programa.exe", b"\x00\x10\x20")])
        response = self.client.post("/document/extract",
                                    data={"file": (BytesIO(data), "site.zip")})
        self.assertEqual(response.status_code, 200)
        text = response.get_json()["text"]
        for name in ("src/index.html", "src/main.js", "README.txt"):
            self.assertIn(name, text)
        self.assertNotIn("programa.exe", text)

    def test_zip_path_traversal_and_corrupt_content_are_rejected(self):
        for raw in (make_zip([("../segredo.txt", "não")]), b"not a zip"):
            with self.subTest(raw=raw[:10]):
                response = self.client.post("/document/extract",
                    data={"file": (BytesIO(raw), "projeto.zip")})
                self.assertEqual(response.status_code, 422)

    def test_zip_symlinks_and_overly_many_entries_are_rejected(self):
        archive = BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            link = zipfile.ZipInfo("link.txt")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(link, "outside")
        with self.assertRaisesRegex(ValueError, "simbólicos"):
            extract_zip_text(archive.getvalue())
        with self.assertRaisesRegex(ValueError, "100 entradas"):
            extract_zip_text(make_zip([(f"{n}.txt", "x") for n in range(101)]))

    def test_zip_bomb_ratio_is_rejected(self):
        packed = make_zip([("huge.txt", "A" * 200000)])
        with self.assertRaisesRegex(ValueError, "compressão insegura"):
            extract_zip_text(packed)

    def test_zip_that_only_has_photos_reports_no_readable_text(self):
        r = self.client.post("/document/extract",
            data={"file": (BytesIO(make_zip([("image.png", b"PNG")])), "photos.zip")})
        self.assertEqual(r.status_code, 422)
        self.assertIn("texto", r.get_json()["error"].lower())

    def test_vision_normalizes_png_gif_bmp_and_tiff_to_jpeg(self):
        image = Image.new("RGBA", (8, 8), (20, 40, 90, 255))
        upstream = Mock(status_code=200)
        upstream.json.return_value = {"choices": [{"message": {"content": "Uma foto azul."}}]}
        with patch.dict(os.environ, {"THIGAS_VISION_MODEL": "vision-model-test",
                                     "THIGAS_VISION_API_KEY": "private-test",
                                     "THIGAS_VISION_URL": "https://provider.example/v1/chat/completions"}),
             patch.object(gateway.requests, "post", return_value=upstream) as post:
            for filename, mime, fmt in (("a.png", "image/png", "PNG"),
                                        ("a.gif", "image/gif", "GIF"),
                                        ("a.bmp", "image/bmp", "BMP"),
                                        ("a.tiff", "image/tiff", "TIFF")):
                with self.subTest(filename=filename):
                    data = BytesIO()
                    image.convert("RGB").save(data, format=fmt)
                    response = self.client.post("/image/describe",
                        data={"image": (BytesIO(data.getvalue()), filename, mime)})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get_json()["description"], "Uma foto azul.")
                    payload = post.call_args.kwargs["json"]
                    url = payload["messages"][0]["content"][1]["image_url"]["url"]
                    self.assertTrue(url.startswith("data:image/jpeg;base64,"))
                    self.assertNotIn("private-test", str(payload))


if __name__ == "__main__":
    unittest.main()