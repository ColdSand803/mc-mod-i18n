from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "neoforge-hardcoded-patch"


class PatchModTemplateTest(unittest.TestCase):
    def test_neoforge_patch_template_documents_runtime_mapping_contract(self) -> None:
        readme = (TEMPLATE / "README.md").read_text(encoding="utf-8")

        self.assertIn("NeoForge 1.21.1", readme)
        self.assertIn("config/mc-mod-i18n/hardcoded-map.json", readme)
        self.assertIn('"Copper": "铜"', readme)
        self.assertIn('"translation": "铜"', readme)
        self.assertIn("ItemTooltipEvent", readme)

    def test_neoforge_patch_template_contains_build_and_mod_metadata(self) -> None:
        build_gradle = (TEMPLATE / "build.gradle").read_text(encoding="utf-8")
        gradle_properties = (TEMPLATE / "gradle.properties").read_text(encoding="utf-8")
        mods_toml = (TEMPLATE / "src" / "main" / "resources" / "META-INF" / "neoforge.mods.toml").read_text(encoding="utf-8")

        self.assertIn("net.neoforged.moddev", build_gradle)
        self.assertIn("JavaLanguageVersion.of(21)", build_gradle)
        self.assertIn("minecraft_version=1.21.1", gradle_properties)
        self.assertIn("neo_version=21.1.", gradle_properties)
        self.assertIn('modId="mc_mod_i18n_hardcoded_patch"', mods_toml)

    def test_neoforge_patch_template_loads_map_and_rewrites_tooltips(self) -> None:
        source_root = TEMPLATE / "src" / "main" / "java" / "com" / "coldsand" / "mcmodi18npatch"
        mod_source = (source_root / "HardcodedPatchMod.java").read_text(encoding="utf-8")
        translations_source = (source_root / "HardcodedTranslations.java").read_text(encoding="utf-8")
        tooltip_source = (source_root / "ClientTooltipTranslator.java").read_text(encoding="utf-8")

        self.assertIn("NeoForge.EVENT_BUS.addListener", mod_source)
        self.assertIn("FMLPaths.CONFIGDIR.get()", translations_source)
        self.assertIn('resolve("mc-mod-i18n")', translations_source)
        self.assertIn('resolve("hardcoded-map.json")', translations_source)
        self.assertIn("translationValue(entry.getValue())", translations_source)
        self.assertIn("value.isJsonObject()", translations_source)
        self.assertIn('object.get("translation")', translations_source)
        self.assertIn("ItemTooltipEvent", tooltip_source)
        self.assertIn("Component.literal(replacement).withStyle(line.getStyle())", tooltip_source)


if __name__ == "__main__":
    unittest.main()
