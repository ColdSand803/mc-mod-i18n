from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mc_mod_i18n.web import (
    clear_translation_memory,
    compact_translation_memory,
    translation_memory_path,
    translation_memory_stats,
)


class TranslationMemoryManagementTest(unittest.TestCase):
    def test_stats_clear_and_compact_translation_memory(self) -> None:
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            path = translation_memory_path(cache_root)
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"scope": "a", "source": "Start", "target": "开始"}, ensure_ascii=False),
                        json.dumps({"scope": "a", "source": "Start", "target": "启动"}, ensure_ascii=False),
                        json.dumps({"scope": "b", "source": "Start", "target": "开始"}, ensure_ascii=False),
                        "{bad",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            stats = translation_memory_stats(cache_root)
            removed = compact_translation_memory(cache_root)
            compacted_stats = translation_memory_stats(cache_root)
            cleared = clear_translation_memory(cache_root)

        self.assertEqual(3, stats["entries"])
        self.assertEqual(1, removed)
        self.assertEqual(2, compacted_stats["entries"])
        self.assertEqual(2, cleared)


if __name__ == "__main__":
    unittest.main()
