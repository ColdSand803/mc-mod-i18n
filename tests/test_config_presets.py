from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mc_mod_i18n.web import (
    delete_config_preset,
    list_config_presets,
    preset_path,
    read_config_preset,
    write_config_preset,
)


class ConfigPresetsTest(unittest.TestCase):
    def test_write_preset_filters_plaintext_api_key(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)

            preset = write_config_preset(
                workdir,
                "OpenAI 高并发",
                {
                    "provider": "openai-compatible",
                    "api_url": "https://api.openai.com/v1",
                    "model": "gpt-4o-mini",
                    "api_key": "sk-should-not-be-saved",
                    "api_key_env": "OPENAI_API_KEY",
                    "api_concurrency": "4",
                    "ignore_cache": True,
                },
            )

            raw = json.loads(preset_path(workdir, preset["name"]).read_text(encoding="utf-8"))
            self.assertNotIn("api_key", raw["config"])
            self.assertEqual("OPENAI_API_KEY", raw["config"]["api_key_env"])
            self.assertEqual(4, raw["config"]["api_concurrency"])
            self.assertTrue(raw["config"]["ignore_cache"])

    def test_list_read_and_delete_presets(self) -> None:
        with TemporaryDirectory() as tmp:
            workdir = Path(tmp)

            write_config_preset(workdir, "B", {"provider": "copy"})
            write_config_preset(workdir, "A", {"provider": "glossary"})

            self.assertEqual(["A", "B"], [item["name"] for item in list_config_presets(workdir)])
            self.assertEqual("glossary", read_config_preset(workdir, "A")["config"]["provider"])

            delete_config_preset(workdir, "A")

            self.assertEqual(["B"], [item["name"] for item in list_config_presets(workdir)])


if __name__ == "__main__":
    unittest.main()
