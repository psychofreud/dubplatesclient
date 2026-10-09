"""Starts the window. UI = ui/dist (built), or a dev server when DUBPLATES_UI is set (e.g. http://localhost:5174).
When the stem engine is not installed yet (first start after the installer), the window shows the setup page."""
from __future__ import annotations

import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import threading
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


INSTANCE = app_dir() / "instance.json"     # the running window: {port, token} (a second start sends its link there)


def link_arg() -> str | None:
    return next((a for a in sys.argv[1:] if a.lower().startswith("dubplates://")), None)


def forward(url: str | None) -> bool:
    """Another window is open: give it the link (or just bring it to the front) and stop here."""
    try:
        info = json.loads(INSTANCE.read_text(encoding="utf-8"))
        with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=2) as s:
            s.sendall((json.dumps({"token": info["token"], "url": url or ""}) + "\n").encode())
            return s.recv(16).startswith(b"ok")
    except Exception:  # noqa: BLE001
        return False


def listen(on_link):
    """Waits for links from later starts (local only, with a random token)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    token = secrets.token_urlsafe(24)
    INSTANCE.write_text(json.dumps({"port": srv.getsockname()[1], "token": token, "pid": os.getpid()}), encoding="utf-8")

    def loop():
        while True:
            c, _ = srv.accept()
            try:
                c.settimeout(3)
                msg = json.loads(c.makefile().readline() or "{}")
                if secrets.compare_digest(str(msg.get("token", "")), token):
                    c.sendall(b"ok")
                    on_link(msg.get("url") or None)
            except Exception:  # noqa: BLE001
                pass
            finally:
                c.close()
    threading.Thread(target=loop, daemon=True, name="instance").start()


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
    url = link_arg()
    if forward(url):
        logging.info("the client is already open: link sent to it")
        return
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
    api._pending = url

    def on_link(u):
        """A link (or a second start) while the window is open: bring the window to the front, the UI asks."""
        api._pending = u or getattr(api, "_pending", None)
        try:
            win.restore()
            win.show()
            win.on_top = True
            win.on_top = False
            if ready and u:
                win.evaluate_js("window.__dpLink && window.__dpLink()")
        except Exception:  # noqa: BLE001
            pass

    listen(on_link)

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
