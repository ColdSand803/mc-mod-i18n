from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import quote
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mc_mod_i18n.web import help_docs_dir, make_handler, write_system_settings
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

    def test_docs_api_uses_ui_locale_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"

                with urlopen(f"{base_url}/api/docs?ui_locale=en_us") as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                titles = {item.get("slug"): item.get("title") for item in payload["docs"]}
                self.assertEqual("Quick Start", titles.get("quick-start"))
                self.assertEqual("Choosing a Provider", titles.get("providers"))
                self.assertEqual("Output Strategy", titles.get("output-strategy"))
                self.assertEqual("FAQ", titles.get("faq"))

                with urlopen(f"{base_url}/api/docs/quick-start?ui_locale=en_us") as response:
                    detail = json.loads(response.read().decode("utf-8"))
                self.assertTrue(detail["ok"])
                self.assertEqual("Quick Start", detail["title"])
                self.assertIn("Quick Start", detail["html"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_docs_api_falls_back_for_unknown_ui_locale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"

                with urlopen(f"{base_url}/api/docs/quick-start?ui_locale=missing_locale") as response:
                    detail = json.loads(response.read().decode("utf-8"))
                self.assertTrue(detail["ok"])
                self.assertEqual("快速开始", detail["title"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_docs_api_uses_ui_locale_extension_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp, "work")
            extension_root = Path(tmp, "extensions", "ui-locales")
            ja_root = help_docs_dir(extension_root) / "ja"
            ja_root.mkdir(parents=True, exist_ok=True)
            (ja_root / "quick-start.md").write_text("# 拡張ヘルプ\n\n言語拓展包目录中的文档。", encoding="utf-8")
            (ja_root / "index.json").write_text(
                json.dumps(
                    {
                        "docs": [
                            {
                                "slug": "quick-start",
                                "title": "拡張ヘルプ",
                                "summary": "外部ディレクトリ",
                                "category": "start",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                query = f"ui_locale=ja_jp&ui_locale_dir={quote(str(extension_root))}"

                with urlopen(f"{base_url}/api/docs?{query}") as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                self.assertEqual("拡張ヘルプ", payload["docs"][0]["title"])

                with urlopen(f"{base_url}/api/docs/quick-start?{query}") as response:
                    detail = json.loads(response.read().decode("utf-8"))
                self.assertTrue(detail["ok"])
                self.assertEqual("拡張ヘルプ", detail["title"])
                self.assertIn("言語拓展包目录中的文档", detail["html"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_ui_locale_api_lists_only_builtin_and_imported_locales(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"

                with urlopen(f"{base_url}/api/ui-locales") as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                locales = {item["code"]: item for item in payload["locales"]}
                self.assertEqual({"zh_cn", "en_us"}, set(locales))
                self.assertNotIn("ja_jp", locales)
                self.assertNotIn("tok", locales)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_ui_locale_export_uses_target_language_name_without_listing_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"

                with urlopen(f"{base_url}/api/ui-locales/export/ja_jp") as response:
                    package = json.loads(response.read().decode("utf-8"))
                self.assertEqual("ja_jp", package["locale"])
                self.assertEqual("日本語", package["name"])
                self.assertEqual("日本語", package["native_name"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_imported_ui_locale_package_can_install_help_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp, "work")
            extension_root = Path(tmp, "extensions", "ui-locales")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                package = {
                    "schema_version": 1,
                    "locale": "ja_jp",
                    "name": "Japanese",
                    "native_name": "日本語",
                    "messages": {"app.brand.name": "翻訳ワークベンチ"},
                    "docs": [
                        {
                            "slug": "quick-start",
                            "title": "導入ガイド",
                            "summary": "インポートされた文書",
                            "category": "start",
                            "content": "# 導入ガイド\n\n言語包 JSON から入った文書。",
                        }
                    ],
                }
                boundary = "----mcmodi18ntest"
                body = (
                    f"--{boundary}\r\n"
                    'Content-Disposition: form-data; name="ui_locale_dir"\r\n\r\n'
                    f"{extension_root}\r\n"
                    f"--{boundary}\r\n"
                    'Content-Disposition: form-data; name="ui_locale_file"; filename="ja_jp.json"\r\n'
                    "Content-Type: application/json\r\n\r\n"
                    f"{json.dumps(package, ensure_ascii=False)}\r\n"
                    f"--{boundary}--\r\n"
                ).encode("utf-8")
                request = Request(
                    f"{base_url}/api/ui-locales/import",
                    data=body,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                    method="POST",
                )
                with urlopen(request) as response:
                    imported = json.loads(response.read().decode("utf-8"))
                self.assertTrue(imported["ok"])
                self.assertEqual("ja_jp", imported["locale"])
                self.assertEqual(1, imported["docs_count"])

                query = f"ui_locale=ja_jp&ui_locale_dir={quote(str(extension_root))}"
                with urlopen(f"{base_url}/api/docs/quick-start?{query}") as response:
                    detail = json.loads(response.read().decode("utf-8"))
                self.assertTrue(detail["ok"])
                self.assertEqual("導入ガイド", detail["title"])
                self.assertIn("言語包 JSON から入った文書", detail["html"])
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

    def test_legacy_sidebar_logo_asset_is_served(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                with urlopen(f"{base_url}/assets/logo/minecraft.svg") as response:
                    body = response.read().decode("utf-8")
                self.assertEqual(200, response.status)
                self.assertIn("<svg", body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_current_branding_assets_and_favicon_are_served(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            write_system_settings(workdir, brand_logo="sign")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                with urlopen(f"{base_url}/assets/logo/current") as response:
                    logo_body = response.read()
                self.assertEqual(200, response.status)
                self.assertEqual("image/png", response.headers.get_content_type())
                self.assertGreater(len(logo_body), 100)

                for path in (
                    "/assets/logo/current.ico",
                    "/assets/logo/current-favicon",
                    "/assets/logo/co1dsand_logo_cat.ico",
                    "/assets/logo/co1dsand_logo_sign.ico",
                    "/assets/logo/minecraft.ico",
                    "/favicon.ico",
                ):
                    with urlopen(f"{base_url}{path}") as response:
                        icon_body = response.read()
                    self.assertEqual(200, response.status)
                    self.assertEqual(b"\x00\x00\x01\x00", icon_body[:4])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_current_favicon_serves_grass_svg_for_browser_tabs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            write_system_settings(workdir, brand_logo="grass")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                with urlopen(f"{base_url}/assets/logo/current-favicon") as response:
                    body = response.read().decode("utf-8")
                self.assertEqual(200, response.status)
                self.assertEqual("image/svg+xml", response.headers.get_content_type())
                self.assertIn("<svg", body)
                self.assertIn("id=\"minecraft\"", body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_system_settings_api_reads_and_updates_brand_logo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workdir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                with urlopen(f"{base_url}/api/system-settings") as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                self.assertEqual("cat", payload["brand_logo"])
                self.assertEqual(["cat", "grass", "sign"], [item["id"] for item in payload["brand_options"]])
                self.assertEqual(str(workdir.resolve()), payload["data_dir"])
                self.assertEqual(str((workdir / "cache").resolve()), payload["default_cache_dir"])
                self.assertEqual(str((workdir / "extensions" / "ui-locales").resolve()), payload["default_ui_locale_dir"])

                request = Request(
                    f"{base_url}/api/system-settings",
                    data=json.dumps({"brand_logo": "grass"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request) as response:
                    updated = json.loads(response.read().decode("utf-8"))
                self.assertTrue(updated["ok"])
                self.assertEqual("grass", updated["brand_logo"])

                with urlopen(f"{base_url}/api/system-settings") as response:
                    reloaded = json.loads(response.read().decode("utf-8"))
                self.assertEqual("grass", reloaded["brand_logo"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
