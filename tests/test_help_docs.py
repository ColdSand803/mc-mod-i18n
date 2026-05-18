from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mc_mod_i18n.web import (
    HELP_DOCS_DIRNAME,
    HELP_DOCS_INDEX_FILENAME,
    bundled_resource_root,
    help_docs_dir,
    localized_help_docs_dir,
    list_help_docs,
    read_help_doc,
    render_help_doc_html,
)


class HelpDocsTest(unittest.TestCase):
    def test_help_docs_dir_points_to_docs_help(self) -> None:
        root = Path("D:/demo").resolve()
        self.assertEqual(root / HELP_DOCS_DIRNAME, help_docs_dir(root))
        self.assertEqual(root / HELP_DOCS_DIRNAME / "en_us", localized_help_docs_dir(root, "en_us"))

    def test_bundled_resource_root_uses_pyinstaller_meipass(self) -> None:
        import mc_mod_i18n.web as web

        old_meipass = getattr(web.sys, "_MEIPASS", None)
        old_has_meipass = hasattr(web.sys, "_MEIPASS")
        try:
            web.sys._MEIPASS = "D:/bundle-root"
            self.assertEqual(Path("D:/bundle-root"), bundled_resource_root())
        finally:
            if old_has_meipass:
                web.sys._MEIPASS = old_meipass
            else:
                delattr(web.sys, "_MEIPASS")

    def test_list_help_docs_reads_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "quick-start.md").write_text("# Quick Start\n\nHello", encoding="utf-8")
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps(
                    {
                        "docs": [
                            {
                                "slug": "quick-start",
                                "title": "快速开始",
                                "summary": "第一次使用",
                                "category": "start",
                                "keywords": ["start"],
                                "related_topics": ["faq"],
                                "applies_to": ["workspace"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            docs = list_help_docs(root)

            self.assertEqual(1, len(docs))
            self.assertEqual("quick-start", docs[0]["slug"])
            self.assertEqual("快速开始", docs[0]["title"])
            self.assertEqual(["faq"], docs[0]["related_topics"])
            self.assertEqual(["workspace"], docs[0]["applies_to"])

    def test_list_help_docs_prefers_locale_index_and_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "quick-start.md").write_text("# 快速开始\n\n你好", encoding="utf-8")
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps(
                    {
                        "docs": [
                            {
                                "slug": "quick-start",
                                "title": "快速开始",
                                "summary": "中文说明",
                                "category": "start",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            en_root = localized_help_docs_dir(root, "en_us")
            en_root.mkdir(parents=True, exist_ok=True)
            (en_root / "quick-start.md").write_text("# Quick Start\n\nHello", encoding="utf-8")
            (en_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps(
                    {
                        "docs": [
                            {
                                "slug": "quick-start",
                                "title": "Quick Start",
                                "summary": "English guide",
                                "category": "start",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual("Quick Start", list_help_docs(root, "en_us")[0]["title"])
            self.assertEqual("快速开始", list_help_docs(root, "missing_locale")[0]["title"])

    def test_list_help_docs_can_match_any_locale_and_language_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "quick-start.md").write_text("# 快速开始\n\n你好", encoding="utf-8")
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "quick-start", "title": "快速开始"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            ja_root = help_docs_dir(root) / "ja"
            ja_root.mkdir(parents=True, exist_ok=True)
            (ja_root / "quick-start.md").write_text("# はじめに\n\nこんにちは", encoding="utf-8")
            (ja_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "quick-start", "title": "はじめに"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            fr_root = localized_help_docs_dir(root, "fr_fr")
            fr_root.mkdir(parents=True, exist_ok=True)
            (fr_root / "quick-start.md").write_text("# Demarrage\n\nBonjour", encoding="utf-8")
            (fr_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "quick-start", "title": "Demarrage"}]}),
                encoding="utf-8",
            )

            self.assertEqual("はじめに", list_help_docs(root, "ja_jp")[0]["title"])
            self.assertEqual("Demarrage", list_help_docs(root, "fr_fr")[0]["title"])

    def test_list_help_docs_prefers_ui_locale_extension_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, "bundle")
            extension_root = Path(tmp, "extensions", "ui-locales")
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "quick-start.md").write_text("# 快速开始\n\n你好", encoding="utf-8")
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "quick-start", "title": "快速开始"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            ja_root = help_docs_dir(extension_root) / "ja"
            ja_root.mkdir(parents=True, exist_ok=True)
            (ja_root / "quick-start.md").write_text("# はじめに\n\nこんにちは", encoding="utf-8")
            (ja_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "quick-start", "title": "拡張ヘルプ"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            self.assertEqual("拡張ヘルプ", list_help_docs(root, "ja_jp", extension_root)[0]["title"])
            self.assertEqual("快速开始", list_help_docs(root, "missing_locale", extension_root)[0]["title"])

    def test_read_help_doc_returns_index_metadata_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "providers.md").write_text("# Providers\n\nUse Azure.", encoding="utf-8")
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps(
                    {
                        "docs": [
                            {
                                "slug": "providers",
                                "title": "翻译器选择",
                                "summary": "选择 provider",
                                "category": "providers",
                                "keywords": ["provider", "azure"],
                                "related_topics": ["quick-start", "faq"],
                                "applies_to": ["workspace", "provider:azure-translator"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            doc = read_help_doc(root, "providers")

            self.assertEqual("providers", doc["slug"])
            self.assertEqual("翻译器选择", doc["title"])
            self.assertIn("# Providers", doc["content"])
            self.assertEqual(["quick-start", "faq"], doc["related_topics"])
            self.assertEqual(["workspace", "provider:azure-translator"], doc["applies_to"])

    def test_read_help_doc_prefers_locale_markdown_and_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "providers.md").write_text("# 翻译器\n\n中文内容", encoding="utf-8")
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "providers", "title": "翻译器", "summary": "中文说明"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            en_root = localized_help_docs_dir(root, "en_us")
            en_root.mkdir(parents=True, exist_ok=True)
            (en_root / "providers.md").write_text("# Providers\n\nEnglish content", encoding="utf-8")
            (en_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "providers", "title": "Providers", "summary": "English guide"}]}),
                encoding="utf-8",
            )

            self.assertIn("English content", read_help_doc(root, "providers", "en_us")["content"])
            self.assertIn("中文内容", read_help_doc(root, "providers", "missing_locale")["content"])

    def test_read_help_doc_can_match_any_locale_and_language_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "providers.md").write_text("# 翻译器\n\n中文内容", encoding="utf-8")
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "providers", "title": "翻译器"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            ja_root = help_docs_dir(root) / "ja"
            ja_root.mkdir(parents=True, exist_ok=True)
            (ja_root / "providers.md").write_text("# 翻訳プロバイダー\n\n日本語の内容", encoding="utf-8")
            (ja_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "providers", "title": "翻訳プロバイダー"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            doc = read_help_doc(root, "providers", "ja_jp")

            self.assertEqual("翻訳プロバイダー", doc["title"])
            self.assertIn("日本語の内容", doc["content"])

    def test_read_help_doc_prefers_ui_locale_extension_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, "bundle")
            extension_root = Path(tmp, "extensions", "ui-locales")
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / "providers.md").write_text("# 翻译器\n\n中文内容", encoding="utf-8")
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "providers", "title": "翻译器"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            ja_root = help_docs_dir(extension_root) / "ja"
            ja_root.mkdir(parents=True, exist_ok=True)
            (ja_root / "providers.md").write_text("# 拡張プロバイダー\n\n拡張ディレクトリの内容", encoding="utf-8")
            (ja_root / HELP_DOCS_INDEX_FILENAME).write_text(
                json.dumps({"docs": [{"slug": "providers", "title": "拡張プロバイダー"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            doc = read_help_doc(root, "providers", "ja_jp", extension_root)

            self.assertEqual("拡張プロバイダー", doc["title"])
            self.assertIn("拡張ディレクトリの内容", doc["content"])

    def test_read_help_doc_rejects_unknown_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = help_docs_dir(root)
            docs_root.mkdir(parents=True, exist_ok=True)
            (docs_root / HELP_DOCS_INDEX_FILENAME).write_text('{"docs":[]}', encoding="utf-8")

            with self.assertRaises(ValueError):
                read_help_doc(root, "missing")

    def test_render_help_doc_html_supports_code_blocks_and_links(self) -> None:
        html = render_help_doc_html(
            "# Demo\n\nUse `deep-free` first.\n\n```powershell\npython -m mc_mod_i18n serve\n```\n\n- Read [快速开始](#/docs/quick-start)\n"
        )

        self.assertIn("<h1>Demo</h1>", html)
        self.assertIn("<code>deep-free</code>", html)
        self.assertIn("<pre><code class=\"language-powershell\">", html)
        self.assertIn("python -m mc_mod_i18n serve", html)
        self.assertIn('<a href="#/docs/quick-start">快速开始</a>', html)

    def test_render_help_doc_html_supports_ordered_lists(self) -> None:
        html = render_help_doc_html("## Steps\n\n1. First\n2. Second\n")

        self.assertIn("<h2>Steps</h2>", html)
        self.assertIn("<ol>", html)
        self.assertIn("<li>First</li>", html)
        self.assertIn("<li>Second</li>", html)


if __name__ == "__main__":
    unittest.main()
