from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from mc_mod_i18n.web import help_docs_dir, make_handler
from http.server import ThreadingHTTPServer


class HelpDocsApiTest(unittest.TestCase):
    def test_docs_api_lists_and_reads_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            docs_root = help_docs_dir(Path(__file__).resolve().parents[1])
            self.assertTrue((docs_root / "index.json").is_file())

            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"

                with urlopen(f"{base_url}/api/docs") as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                self.assertGreaterEqual(len(payload["docs"]), 1)
                self.assertTrue(any(item.get("slug") == "faq" for item in payload["docs"]))

                slug = payload["docs"][0]["slug"]
                with urlopen(f"{base_url}/api/docs/{slug}") as response:
                    detail = json.loads(response.read().decode("utf-8"))
                self.assertTrue(detail["ok"])
                self.assertEqual(slug, detail["slug"])
                self.assertIn("html", detail)
                self.assertIn("content", detail)
                self.assertIn("related_topics", detail)
                self.assertIn("applies_to", detail)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_docs_api_returns_404_for_missing_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(f"{base_url}/api/docs/not-found")
                self.assertEqual(404, ctx.exception.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
