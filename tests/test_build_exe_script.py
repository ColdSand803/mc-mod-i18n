from __future__ import annotations

from pathlib import Path
import unittest


class BuildExeScriptTest(unittest.TestCase):
    def _script_text(self) -> str:
        root = Path(__file__).resolve().parents[1]
        return (root / "scripts" / "build_exe.ps1").read_text(encoding="utf-8")

    def _spec_text(self) -> str:
        root = Path(__file__).resolve().parents[1]
        return (root / "mc-mod-i18n.spec").read_text(encoding="utf-8")

    def test_build_script_prefers_repo_local_python(self) -> None:
        script = self._script_text()

        self.assertIn('.tools\\python-3.12.10\\python.exe', script)
        self.assertIn("Get-Command python", script)
        self.assertIn("Write-Host \"Using Python: $Python\"", script)

    def test_build_script_checks_pywebview_before_packaging(self) -> None:
        script = self._script_text()

        self.assertIn("import webview", script)
        self.assertIn("-InstallDesktopDeps", script)
        self.assertIn(".[desktop]", script)
        self.assertLess(script.index("import webview"), script.rindex("PyInstaller"))

    def test_build_script_uses_valid_powershell_quotes_for_desktop_hint(self) -> None:
        script = self._script_text()

        self.assertIn('`".[desktop]`"', script)
        self.assertNotIn('`"".[desktop]`""', script)

    def test_build_script_has_helpful_clean_failure_message(self) -> None:
        script = self._script_text()

        self.assertIn("Failed to clean build artifact path", script)
        self.assertIn("Close any running mc-mod-i18n.exe", script)

    def test_build_script_generates_exe_icon_from_selected_brand_logo(self) -> None:
        script = self._script_text()

        self.assertIn("logo\\branding.json", script)
        self.assertIn("logo\\png\\co1dsand_logo_cat.png", script)
        self.assertIn("logo\\png\\minecraft.png", script)
        self.assertIn("logo\\png\\co1dsand_logo_sign.png", script)
        self.assertIn("logo\\app.ico", script)
        self.assertIn("System.Drawing", script)
        self.assertLess(script.index("branding.json"), script.rindex("PyInstaller"))

    def test_pyinstaller_spec_uses_selected_brand_logo_icon(self) -> None:
        spec = self._spec_text()

        self.assertIn('icon=str(root / "logo" / "app.ico")', spec)

    def test_pyinstaller_spec_bundles_runtime_assets(self) -> None:
        spec = self._spec_text()

        self.assertIn('root / "docs" / "help"', spec)
        self.assertIn('"docs/help"', spec)
        self.assertIn('root / "logo"', spec)
        self.assertIn('"logo"', spec)
        self.assertNotIn('root / "ui优化方案" / "logo" / "minecraft.svg"', spec)
        self.assertNotIn('root / "co1dsand_logo_cat.png"', spec)
        self.assertNotIn('co1dsand_logo_sing.png', spec)


if __name__ == "__main__":
    unittest.main()
