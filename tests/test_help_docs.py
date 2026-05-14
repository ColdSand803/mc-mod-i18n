from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mc_mod_i18n.web import (
    HELP_DOCS_DIRNAME,
    HELP_DOCS_INDEX_FILENAME,
    help_docs_dir,
    list_help_docs,
    read_help_doc,
    render_help_doc_html,
)


class HelpDocsTest(unittest.TestCase):
    def test_help_docs_dir_points_to_docs_help(self) -> None:
        root = Path("D:/demo").resolve()
        self.assertEqual(root / HELP_DOCS_DIRNAME, help_docs_dir(root))

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
