from __future__ import annotations

import os
import sys
from pathlib import Path
from threading import Thread

from http.server import ThreadingHTTPServer

from .web import make_handler


APP_DIRNAME = "mc-mod-i18n"
APP_DATA_CHILDREN = ("jobs", "cache", "outputs", "extensions", "logs")


def default_app_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_DIRNAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIRNAME
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIRNAME


def prepare_app_data_dir(root: Path | None = None) -> Path:
    app_root = (root or default_app_data_dir()).expanduser()
    app_root.mkdir(parents=True, exist_ok=True)
    for child in APP_DATA_CHILDREN:
        (app_root / child).mkdir(parents=True, exist_ok=True)
    return app_root


def build_desktop_server(host: str, port: int, workdir: Path) -> ThreadingHTTPServer:
    workdir = prepare_app_data_dir(workdir).resolve()
    handler = make_handler(workdir)
    return ThreadingHTTPServer((host, port), handler)


def run_desktop(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    workdir: Path | None = None,
    width: int = 1280,
    height: int = 860,
    title: str = "mc-mod-i18n",
) -> int:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("桌面模式需要安装 pywebview：python -m pip install pywebview") from exc

    server = build_desktop_server(host, port, workdir or default_app_data_dir())
    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}"
    thread = Thread(target=server.serve_forever, name="mc-mod-i18n-web", daemon=True)
    thread.start()
    try:
        webview.create_window(title, url, width=width, height=height)
        webview.start()
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="mc-mod-i18n desktop")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--workdir", default="", help="desktop app data directory; defaults to the user app data folder")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=860)
    args = parser.parse_args(argv)
    return run_desktop(
        host=args.host,
        port=args.port,
        workdir=Path(args.workdir) if args.workdir else None,
        width=args.width,
        height=args.height,
    )
