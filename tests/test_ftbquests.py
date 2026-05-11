from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from mc_mod_i18n.ftbquests import (
    FTBQuestsSource,
    collect_string_leaves,
    load_ftbquests_source,
    parse_snbt,
    process_ftbquests_source,
    render_snbt,
    write_ftbquests_outputs,
)


class PrefixTranslator:
    def translate_batch_with_failures(self, items):
        return {item.id: f"ZH {item.text}" for item in items}, {}


def args(**overrides):
    values = {
        "source_locale": "en_us",
        "target_locale": "zh_cn",
        "overwrite_existing": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class FTBQuestsTest(unittest.TestCase):
    def test_parse_and_render_lang_snbt(self) -> None:
        root = parse_snbt(
            """
            {
              "chapter.title": "Getting Started",
              quest: {
                description: "Welcome {player}"
              },
              lines: ["Line one", "Line two"]
            }
            """
        )

        leaves = collect_string_leaves(root)

        self.assertEqual(
            ["chapter.title", "quest.description", "lines[0]", "lines[1]"],
            [leaf.key for leaf in leaves],
        )
        rendered = render_snbt(root)
        self.assertIn('"chapter.title": "Getting Started"', rendered)
        self.assertIn('"description": "Welcome {player}"', rendered)

    def test_parse_ftbquests_snbt_without_entry_commas(self) -> None:
        root = parse_snbt(
            """
            {
              quest.A.title: "Welcome"
              quest.A.quest_desc: ["Line one"]
              task.B.title: "Claiming Chunks"
            }
            """
        )

        self.assertEqual(
            ["quest.A.title", "quest.A.quest_desc[0]", "task.B.title"],
            [leaf.key for leaf in collect_string_leaves(root)],
        )

    def test_process_new_lang_file_generates_target_locale(self) -> None:
        source = FTBQuestsSource(
            label="pack.zip",
            root_prefix="config/ftbquests/quests",
            files={
                "lang/en_us.snbt": """
                {
                  "chapter.title": "Getting Started",
                  "quest.description": "Welcome {player}",
                  "item.id": "minecraft:stone"
                }
                """,
                "lang/zh_cn.snbt": """
                {
                  "chapter.title": "已有章节"
                }
                """,
            },
        )

        result = process_ftbquests_source(source, args(), PrefixTranslator())

        self.assertEqual("lang", result.mode)
        self.assertEqual(1, len(result.output_files))
        self.assertEqual("config/ftbquests/quests/lang/zh_cn.snbt", result.output_files[0].path)
        target = parse_snbt(result.output_files[0].content)
        values = {leaf.key: leaf.text for leaf in collect_string_leaves(target)}
        self.assertEqual("已有章节", values["chapter.title"])
        self.assertEqual("ZH Welcome {player}", values["quest.description"])
        self.assertEqual("minecraft:stone", values["item.id"])
        statuses = {entry.key: entry.status for entry in result.report_entries}
        self.assertEqual("existing", statuses["chapter.title"])
        self.assertEqual("translated", statuses["quest.description"])
        self.assertEqual("skipped", statuses["item.id"])

    def test_process_split_lang_directory_generates_matching_target_tree(self) -> None:
        source = FTBQuestsSource(
            label="atm10",
            root_prefix="config/ftbquests/quests",
            files={
                "lang/en_us/chapter.snbt": '{ chapter.title: "Guide" }',
                "lang/en_us/chapters/welcome.snbt": '{ quest.title: "Welcome" }',
            },
        )

        result = process_ftbquests_source(source, args(), PrefixTranslator())

        self.assertEqual("split_lang", result.mode)
        self.assertEqual(
            [
                "config/ftbquests/quests/lang/zh_cn/chapter.snbt",
                "config/ftbquests/quests/lang/zh_cn/chapters/welcome.snbt",
            ],
            [item.path for item in result.output_files],
        )
        self.assertEqual(2, sum(1 for entry in result.report_entries if entry.status == "translated"))

    def test_lang_root_directory_input_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lang_root = Path(tmp) / "lang"
            (lang_root / "en_us" / "chapters").mkdir(parents=True)
            (lang_root / "en_us" / "chapters" / "welcome.snbt").write_text('{ quest.title: "Welcome" }', encoding="utf-8")

            source = load_ftbquests_source(lang_root, "en_us")
            result = process_ftbquests_source(source, args(), PrefixTranslator())

            self.assertEqual("config/ftbquests/quests/lang", source.root_prefix)
            self.assertEqual("config/ftbquests/quests/lang/zh_cn/chapters/welcome.snbt", result.output_files[0].path)

    def test_locale_root_directory_input_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "en_us" / "chapters").mkdir(parents=True)
            (root / "en_us" / "chapter.snbt").write_text('{ chapter.title: "Guide" }', encoding="utf-8")
            (root / "en_us" / "chapters" / "welcome.snbt").write_text('{ quest.title: "Welcome" }', encoding="utf-8")

            source = load_ftbquests_source(root, "en_us")
            result = process_ftbquests_source(source, args(), PrefixTranslator())

            self.assertEqual("split_lang", result.mode)
            self.assertEqual("config/ftbquests/quests/lang", source.root_prefix)
            self.assertEqual(
                [
                    "config/ftbquests/quests/lang/zh_cn/chapter.snbt",
                    "config/ftbquests/quests/lang/zh_cn/chapters/welcome.snbt",
                ],
                [item.path for item in result.output_files],
            )

    def test_zip_of_en_us_folder_is_treated_as_split_lang(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "en_us.zip"
            with ZipFile(zip_path, "w") as zf:
                zf.writestr("en_us/chapter.snbt", '{ chapter.title: "Guide" }')
                zf.writestr("en_us/chapters/welcome.snbt", '{ quest.title: "Welcome" }')

            source = load_ftbquests_source(zip_path, "en_us")
            result = process_ftbquests_source(source, args(), PrefixTranslator())

            self.assertEqual("split_lang", result.mode)
            self.assertEqual("config/ftbquests/quests/lang", source.root_prefix)
            self.assertEqual(2, len(result.output_files))

    def test_zip_of_en_us_folder_contents_is_treated_as_split_lang(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "en_us_contents.zip"
            with ZipFile(zip_path, "w") as zf:
                zf.writestr("chapter.snbt", '{ chapter.title: "Guide" }')
                zf.writestr("chapters/welcome.snbt", '{ quest.title: "Welcome" }')

            source = load_ftbquests_source(zip_path, "en_us")
            result = process_ftbquests_source(source, args(), PrefixTranslator())

            self.assertEqual("split_lang", result.mode)
            self.assertEqual("config/ftbquests/quests/lang", source.root_prefix)
            self.assertEqual("config/ftbquests/quests/lang/zh_cn/chapter.snbt", result.output_files[0].path)

    def test_legacy_without_lang_is_reported_not_rewritten(self) -> None:
        source = FTBQuestsSource(
            label="legacy",
            root_prefix="config/ftbquests/quests",
            files={"chapters/start.snbt": '{ title: "Start" }'},
        )

        result = process_ftbquests_source(source, args(), PrefixTranslator())

        self.assertEqual("legacy_detected", result.mode)
        self.assertEqual([], result.output_files)
        self.assertIn("chapters/start.snbt", result.legacy_files)
        self.assertEqual("skipped", result.report_entries[0].status)

    def test_zip_input_detects_config_quests_root_and_writes_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            zip_path = tmp_path / "pack.zip"
            with ZipFile(zip_path, "w") as zf:
                zf.writestr(
                    "config/ftbquests/quests/lang/en_us.snbt",
                    '{ "quest.title": "First Quest" }',
                )

            source = load_ftbquests_source(zip_path, "en_us")
            result = process_ftbquests_source(source, args(), PrefixTranslator())
            _, patch = write_ftbquests_outputs(tmp_path / "out", result, "both")

            self.assertIsNotNone(patch)
            with ZipFile(patch) as zf:
                names = zf.namelist()
                self.assertEqual(["config/ftbquests/quests/lang/zh_cn.snbt"], names)
                self.assertIn("ZH First Quest", zf.read(names[0]).decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
