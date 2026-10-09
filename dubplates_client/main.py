"""Starts the window. UI = ui/dist (built), or a dev server when DUBPLATES_UI is set (e.g. http://localhost:5174).
When the stem engine is not installed yet (first start after the installer), the window shows the setup page."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import VERSION
from .config import app_dir, ensure_ffmpeg

HERE = Path(__file__).resolve().parent
ICON = HERE / "assets" / "icon.ico"


def ui_entry() -> str:
    dev = os.environ.get("DUBPLATES_UI")
    if dev:
        return dev
    base = Path(getattr(sys, "_MEIPASS", HERE.parent))
    return str(base / "ui" / "dist" / "index.html")


class SetupApi:
    """The UI calls this while the engine is not installed (see bootstrap.py)."""

    def __init__(self):
        from .bootstrap import Setup, detect
        self._setup = Setup()
        self._info = detect()
        self._window = None

    def hello(self):
        return {"version": VERSION, "platform": sys.platform, "setup": self._info}

    def setup_start(self, variant):
        try:
            self._setup.start(variant)
            return True
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    def setup_state(self):
        return self._setup.state()

    def restart(self):
        """Starts the app again (now with the engine) and closes this window."""
        subprocess.Popen([sys.executable, "-m", "dubplates_client.main"], cwd=str(HERE.parent),
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        self._window.destroy()
        return True

    def open_url(self, url):
        if str(url).startswith("https://"):
            import webbrowser
            webbrowser.open(url)
        return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), RotatingFileHandler(app_dir() / "client.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")])
    if sys.platform == "win32":                     # own taskbar group and icon (not Python's)
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("net.dubplates.client")
        except Exception:  # noqa: BLE001
            pass
    import webview
    from webview.dom import DOMEventHandler

    from .bootstrap import engine_ready
    ready = engine_ready()
    if ready:
        ensure_ffmpeg()
        from .api import Api
        api = Api()
    else:
        logging.info("engine not installed: setup mode")
        api = SetupApi()

    win = webview.create_window("Dubplates.net Client", ui_entry(), js_api=api, width=1280, height=820, min_size=(960, 640),
                                background_color="#060607", text_select=False)
    api._window = win

    def on_drop(e):
        paths = [f.get("pywebviewFullPath") for f in (e.get("dataTransfer") or {}).get("files", []) if f.get("pywebviewFullPath")]
        if paths:
            win.evaluate_js(f"window.__dpDrop && window.__dpDrop({json.dumps(paths)})")

    def on_loaded():
        win.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True)
        win.dom.document.events.drop += DOMEventHandler(on_drop, True, True)

    if ready:
        win.events.loaded += on_loaded
    webview.start(debug=bool(os.environ.get("DUBPLATES_DEBUG")), private_mode=False, storage_path=str(app_dir() / "webview"),
                  icon=str(ICON) if ICON.exists() else None)


if __name__ == "__main__":
    main()
