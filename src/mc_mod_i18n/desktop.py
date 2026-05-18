from __future__ import annotations

import os
import sys
import ctypes
from pathlib import Path
from threading import Thread

from http.server import ThreadingHTTPServer

from .web import make_handler


APP_DIRNAME = "mc-mod-i18n"
APP_DATA_CHILDREN = ("jobs", "cache", "outputs", "extensions", "extensions/ui-locales", "logs")


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
    handler = make_handler(workdir, sync_branding_build_config=True)
    return ThreadingHTTPServer((host, port), handler)


def detect_windows_dpi_scale() -> float:
    if sys.platform != "win32":
        return 1.0
    try:
        scale_percent = ctypes.windll.shcore.GetScaleFactorForDevice(0)
    except Exception:
        try:
            user32 = ctypes.windll.user32
            dc = user32.GetDC(0)
            try:
                dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)
            finally:
                user32.ReleaseDC(0, dc)
            scale_percent = int(round((dpi / 96) * 100))
        except Exception:
            return 1.0
    return max(1.0, float(scale_percent) / 100.0)


def effective_desktop_zoom(override: float = 0, dpi_scale: float | None = None) -> float:
    if override and override > 0:
        return round(float(override), 4)
    scale = dpi_scale if dpi_scale is not None else detect_windows_dpi_scale()
    if scale <= 1:
        return 1.0
    return round(1.0 / scale, 4)


def desktop_zoom_script(zoom: float) -> str:
    zoom_text = f"{zoom:.4f}".rstrip("0").rstrip(".")
    return (
        f"(() => {{"
        "const root = document.documentElement;"
        "document.documentElement.style.zoom = "
        f"{zoom_text!r};"
        "document.documentElement.dataset.desktopZoom = "
        f"{zoom_text!r};"
        "const syncDesktopViewport = () => {"
        "const zoom = Number(root.dataset.desktopZoom) || 1;"
        "root.style.setProperty('--desktop-vw', `${window.innerWidth / zoom}px`);"
        "root.style.setProperty('--desktop-vh', `${window.innerHeight / zoom}px`);"
        "};"
        "syncDesktopViewport();"
        "window.addEventListener('resize', syncDesktopViewport);"
        "})();"
    )


def apply_desktop_zoom(window, zoom: float) -> None:
    if abs(zoom - 1.0) < 0.0001:
        return
    window.evaluate_js(desktop_zoom_script(zoom))


def run_desktop(
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    workdir: Path | None = None,
    width: int = 1280,
    height: int = 860,
    zoom: float = 0,
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
        desktop_zoom = effective_desktop_zoom(zoom)
        window = webview.create_window(title, url, width=width, height=height, zoomable=True)
        window.events.loaded += lambda: apply_desktop_zoom(window, desktop_zoom)
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
    parser.add_argument("--zoom", type=float, default=0, help="desktop page zoom; 0 auto-counteracts Windows DPI scaling")
    args = parser.parse_args(argv)
    return run_desktop(
        host=args.host,
        port=args.port,
        workdir=Path(args.workdir) if args.workdir else None,
        width=args.width,
        height=args.height,
        zoom=args.zoom,
    )
