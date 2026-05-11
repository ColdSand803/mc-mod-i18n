from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from mc_mod_i18n.cli import main


def write_lang_jar(path: Path) -> None:
    with ZipFile(path, "w") as zf:
        zf.writestr(
            "assets/example/lang/en_us.json",
            '{"item.example.copper": "Copper Ingot", "item.example.crystal": "Crystal"}',
        )


class CliDryRunTest(unittest.TestCase):
    def test_dry_run_reports_counts_without_writing_outputs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            jar_path = root / "example.jar"
            out_dir = root / "out"
            write_lang_jar(jar_path)

            stdout = StringIO()
            with redirect_stdout(stdout):
                code = main([
                    "translate",
                    str(jar_path),
                    "--out",
                    str(out_dir),
                    "--provider",
                    "copy",
                    "--dry-run",
                ])

            output = stdout.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("Dry run: yes", output)
            self.assertIn("Processed JARs: 1", output)
            self.assertIn("Source language files: 1", output)
            self.assertIn("Entries to translate: 2", output)
            self.assertIn("Estimated API batches: 0", output)
            self.assertFalse((out_dir / "example.zip").exists())
            self.assertFalse((out_dir / ".checkpoints").exists())


if __name__ == "__main__":
    unittest.main()
