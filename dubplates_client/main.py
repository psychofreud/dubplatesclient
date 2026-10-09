"""Starts the window. UI = ui/dist (built), or a dev server when DUBPLATES_UI is set (e.g. http://localhost:5174)."""
from __future__ import annotations

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import app_dir, ensure_ffmpeg


def ui_entry() -> str:
    dev = os.environ.get("DUBPLATES_UI")
    if dev:
        return dev
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return str(base / "ui" / "dist" / "index.html")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), RotatingFileHandler(app_dir() / "client.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")])
    ensure_ffmpeg()
    import webview
    from webview.dom import DOMEventHandler

    from .api import Api

    api = Api()
    win = webview.create_window("Dubplates.net Client", ui_entry(), js_api=api, width=1280, height=820, min_size=(960, 640),
                                background_color="#060607", text_select=False)
    api._attach(win)

    def on_drop(e):
        paths = [f.get("pywebviewFullPath") for f in (e.get("dataTransfer") or {}).get("files", []) if f.get("pywebviewFullPath")]
        if paths:
            win.evaluate_js(f"window.__dpDrop && window.__dpDrop({json.dumps(paths)})")

    def on_loaded():
        win.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True)
        win.dom.document.events.drop += DOMEventHandler(on_drop, True, True)

    win.events.loaded += on_loaded
    webview.start(debug=bool(os.environ.get("DUBPLATES_DEBUG")), private_mode=False, storage_path=str(app_dir() / "webview"))


if __name__ == "__main__":
    main()
