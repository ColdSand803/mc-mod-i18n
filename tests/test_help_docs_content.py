from __future__ import annotations

import json
from pathlib import Path
import unittest


class HelpDocsContentTest(unittest.TestCase):
    def test_help_docs_index_has_expected_topics_and_valid_related_references(self) -> None:
        index_path = Path(__file__).resolve().parents[1] / "docs" / "help" / "index.json"
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        docs = payload["docs"]
        slugs = {item["slug"] for item in docs}

        self.assertTrue({"history-and-report", "faq", "translation-memory", "hardcoded"} <= slugs)

        for item in docs:
            with self.subTest(slug=item["slug"]):
                self.assertTrue(item.get("title"))
                self.assertTrue(item.get("summary"))
                self.assertTrue(item.get("keywords"))
                self.assertTrue(item.get("applies_to"))
                for related in item.get("related_topics", []):
                    self.assertIn(related, slugs)

        history_doc = next(item for item in docs if item["slug"] == "history-and-report")
        self.assertIn("api-log", history_doc["applies_to"])
        self.assertIn("report", history_doc["applies_to"])


if __name__ == "__main__":
    unittest.main()
