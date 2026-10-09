"""The methods the UI calls: window.pywebview.api.<name>(...). Each returns plain JSON data.
Errors go back as {"error": "..."} so the UI can show them."""
from __future__ import annotations

import functools
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import webview

from . import VERSION
from .config import Config
from .engine import Engine, device_info
from .jobs import AUDIO, Installs, Jobs

log = logging.getLogger("dubplates")


def safe(fn):
    @functools.wraps(fn)
    def w(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001
            log.exception("api %s", fn.__name__)
            return {"error": str(e) or e.__class__.__name__}
    return w


class Api:
    def __init__(self):
        self._cfg = Config()
        self._eng = Engine(self._cfg)
        self._jobs = Jobs(self._eng)
        self._inst = Installs(self._eng)
        self._window = None
        self._device = None
        self._models = None
        self._models_lock = threading.Lock()

    def _attach(self, window):
        self._window = window

    # ---------- state ----------
    @safe
    def hello(self):
        if self._device is None:
            self._device = device_info()
        return {"version": VERSION, "device": self._device, "config": self._cfg.public(), "platform": sys.platform}

    @safe
    def state(self):
        return {"jobs": self._jobs.state(), "installs": self._inst.state()}

    @safe
    def models(self, refresh=False):
        with self._models_lock:
            if refresh or self._models is None or self._inst_changed():
                self._models = self._eng.models(bool(refresh))
                self._seen = self._inst_key()
            return self._models

    def _inst_key(self):
        return tuple(sorted((k, v["done"], v["err"]) for k, v in self._inst.state().items()))

    def _inst_changed(self):
        return getattr(self, "_seen", None) != self._inst_key()

    # ---------- models ----------
    @safe
    def install(self, model_file):
        self._inst.start(model_file)
        return True

    @safe
    def cancel_install(self, model_file):
        self._inst.cancel(model_file)
        return True

    @safe
    def remove(self, model_file):
        self._eng.remove(model_file)
        self._models = None
        return True

    @safe
    def add_custom(self, name, model, config, sha256=""):
        e = self._eng.add_custom(name, model, config, sha256)
        self._models = None
        return e

    # ---------- jobs ----------
    @safe
    def add_jobs(self, paths, model_file, drum_model=""):
        """drum_model: also split the Drums stem with this model (when the first model makes one)."""
        rows = {r["file"]: r for r in self.models()}
        m = rows.get(model_file)
        if not m or not m["installed"]:
            return {"error": "Install the model first (Models page)"}
        steps = [{"model": model_file, "name": m["name"]}]
        d = rows.get(drum_model) if drum_model else None
        if drum_model and (not d or not d["installed"]):
            return {"error": "Install the drum model first (Models page)"}
        if d and any(s.lower() == "drums" for s in m["stems"]):
            steps.append({"model": drum_model, "name": d["name"], "on": "Drums"})
        self._cfg.update({"model": model_file, "drumSplit": drum_model or ""})
        return {"added": self._jobs.add(list(paths or []), steps)}

    @safe
    def cancel_job(self, jid):
        self._jobs.cancel(int(jid))
        return True

    @safe
    def clear_jobs(self):
        self._jobs.clear()
        return True

    # ---------- settings ----------
    @safe
    def set_config(self, patch):
        old = self._cfg["modelDir"]
        out = self._cfg.update(patch or {})
        if self._cfg["modelDir"] != old:
            self._models = None
            self._eng._known = None
        return out

    # ---------- files ----------
    @safe
    def pick_files(self):
        r = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                                            file_types=("Audio files (" + ";".join("*" + e for e in AUDIO) + ")", "All files (*.*)"))
        return list(r or [])

    @safe
    def pick_folder(self):
        r = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return (r[0] if isinstance(r, (list, tuple)) else r) if r else ""

    @safe
    def pick_model_file(self, kind):
        types = ("Model config (*.yaml;*.yml)",) if kind == "config" else ("Model file (*.ckpt;*.pth;*.safetensors)",)
        r = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=types)
        return r[0] if r else ""

    @safe
    def open_path(self, path):
        p = Path(path)
        if not p.exists():
            return {"error": "Not found: " + path}
        if sys.platform == "win32":
            os.startfile(p)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return True

    @safe
    def open_url(self, url):
        if not str(url).startswith("https://"):
            return {"error": "Only https links"}
        import webbrowser
        webbrowser.open(url)
        return True
