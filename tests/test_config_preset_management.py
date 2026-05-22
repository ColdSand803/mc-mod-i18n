from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from mc_mod_i18n.web import (
    delete_config_preset,
    list_config_presets,
    read_config_preset,
    write_config_preset,
)


class ConfigPresetManagementTest(unittest.TestCase):
    def test_config_preset_roundtrip_normalizes_name_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "provider": "openai",
                "model": "gpt-4",
                "api_concurrency": "5",
                "overwrite_existing": True,
                "api_key": "should-be-stripped",
            }
            preset = write_config_preset(root, " My Preset ", config)

            self.assertEqual(preset["name"], "My Preset")
            self.assertNotIn("api_key", preset["config"])
            self.assertEqual(preset["config"]["provider"], "openai")
            self.assertEqual(preset["config"]["model"], "gpt-4")
            self.assertEqual(preset["config"]["api_concurrency"], 5)

            loaded = read_config_preset(root, "My Preset")
            self.assertEqual(loaded["name"], "My Preset")
            self.assertEqual(loaded["config"]["provider"], "openai")
            self.assertEqual(loaded["config"]["model"], "gpt-4")
            self.assertNotIn("api_key", loaded["config"])

    def test_empty_preset_list_when_no_presets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual([], list_config_presets(root))

    def test_write_and_list_multiple_presets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config_preset(root, "Charlie", {"provider": "openai"})
            write_config_preset(root, "Alpha", {"model": "gpt-4"})
            write_config_preset(root, "bravo", {"api_concurrency": 3})

            presets = list_config_presets(root)
            self.assertEqual(3, len(presets))
            names = [p["name"] for p in presets]
            self.assertEqual(names, sorted(names, key=str.lower))

    def test_overwrite_existing_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config_preset(root, "test", {"provider": "openai"})
            write_config_preset(root, "test", {"provider": "anthropic", "model": "claude"})

            loaded = read_config_preset(root, "test")
            self.assertEqual(loaded["config"]["provider"], "anthropic")
            self.assertEqual(loaded["config"]["model"], "claude")

    def test_delete_nonexistent_preset_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError) as ctx:
                delete_config_preset(root, "no-such-preset")
            self.assertIn("预设不存在", str(ctx.exception))

    def test_legacy_presets_json_imported_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            presets_dir = root / "presets"
            presets_dir.mkdir(parents=True)
            legacy = {
                "name": "Legacy",
                "config": {"provider": "openai", "model": "gpt-3.5-turbo"},
            }
            (presets_dir / "legacy.json").write_text(
                json.dumps(legacy, ensure_ascii=False), encoding="utf-8"
            )

            first = list_config_presets(root)
            self.assertEqual(1, len(first))
            self.assertEqual(first[0]["name"], "Legacy")
            self.assertEqual(first[0]["config"]["provider"], "openai")

            second = list_config_presets(root)
            self.assertEqual(first, second)

    def test_write_preset_rejects_empty_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                write_config_preset(root, "", {"provider": "openai"})


if __name__ == "__main__":
    unittest.main()
