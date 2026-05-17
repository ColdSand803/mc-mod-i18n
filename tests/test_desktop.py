from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from mc_mod_i18n.cli import build_parser


class DesktopModeTest(unittest.TestCase):
    def test_desktop_command_is_available(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["desktop", "--port", "0", "--workdir", "C:/tmp/mc-data"])

        self.assertEqual("desktop", args.command)
        self.assertEqual(0, args.port)
        self.assertEqual("C:/tmp/mc-data", args.workdir)

    def test_default_app_data_dir_uses_localappdata_on_windows(self) -> None:
        from mc_mod_i18n import desktop

        with tempfile.TemporaryDirectory() as tmp:
            old_value = os.environ.get("LOCALAPPDATA")
            old_platform = desktop.sys.platform
            os.environ["LOCALAPPDATA"] = tmp
            desktop.sys.platform = "win32"
            try:
                self.assertEqual(Path(tmp) / "mc-mod-i18n", desktop.default_app_data_dir())
            finally:
                desktop.sys.platform = old_platform
                if old_value is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = old_value

    def test_prepare_app_data_dir_creates_expected_children(self) -> None:
        from mc_mod_i18n.desktop import prepare_app_data_dir

        with tempfile.TemporaryDirectory() as tmp:
            root = prepare_app_data_dir(Path(tmp) / "app-data")

            self.assertTrue((root / "jobs").is_dir())
            self.assertTrue((root / "cache").is_dir())
            self.assertTrue((root / "outputs").is_dir())
            self.assertTrue((root / "extensions").is_dir())
            self.assertTrue((root / "logs").is_dir())

    def test_build_desktop_server_binds_ephemeral_port(self) -> None:
        from mc_mod_i18n.desktop import build_desktop_server

        with tempfile.TemporaryDirectory() as tmp:
            server = build_desktop_server("127.0.0.1", 0, Path(tmp))
            try:
                host, port = server.server_address
                self.assertEqual("127.0.0.1", host)
                self.assertGreater(port, 0)
            finally:
                server.server_close()


if __name__ == "__main__":
    unittest.main()
