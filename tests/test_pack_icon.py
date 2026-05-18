from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from mc_mod_i18n.web import (
    normalize_brand_logo_choice,
    read_co1dsand_pack_icon,
    read_system_settings,
    write_system_settings,
)


class PackIconTest(unittest.TestCase):
    def _write_branding_assets(self, root: Path) -> None:
        logo_root = root / "logo" / "png"
        logo_root.mkdir(parents=True, exist_ok=True)
        (logo_root / "co1dsand_logo_cat.png").write_bytes(b"cat-logo")
        (logo_root / "minecraft.png").write_bytes(b"grass-logo")
        (logo_root / "co1dsand_logo_sign.png").write_bytes(b"sign-logo")

    def test_normalize_brand_logo_choice_defaults_to_cat(self) -> None:
        self.assertEqual("cat", normalize_brand_logo_choice(""))
        self.assertEqual("cat", normalize_brand_logo_choice(None))
        self.assertEqual("cat", normalize_brand_logo_choice("python"))
        self.assertEqual("grass", normalize_brand_logo_choice("grass"))
        self.assertEqual("sign", normalize_brand_logo_choice("sign"))

    def test_system_settings_default_to_cat_brand_logo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = read_system_settings(Path(tmp))

        self.assertEqual("cat", settings["brand_logo"])

    def test_system_settings_persist_selected_brand_logo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)

            saved = write_system_settings(workdir, brand_logo="sign")
            loaded = read_system_settings(workdir)

        self.assertEqual("sign", saved["brand_logo"])
        self.assertEqual("sign", loaded["brand_logo"])

    def test_read_co1dsand_pack_icon_uses_selected_brand_logo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workdir = root / "work"
            self._write_branding_assets(root)

            self.assertEqual(b"cat-logo", read_co1dsand_pack_icon(root=root, workdir=workdir))

            write_system_settings(workdir, brand_logo="grass")
            self.assertEqual(b"grass-logo", read_co1dsand_pack_icon(root=root, workdir=workdir))

            write_system_settings(workdir, brand_logo="sign")
            self.assertEqual(b"sign-logo", read_co1dsand_pack_icon(root=root, workdir=workdir))


if __name__ == "__main__":
    unittest.main()
