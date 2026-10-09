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
        steps = self._steps(model_file, drum_model)
        self._cfg.update({"model": model_file, "drumSplit": drum_model or ""})
        return {"added": self._jobs.add(list(paths or []), steps)}

    def _steps(self, model_file, drum_model=""):
        rows = {r["file"]: r for r in self.models()}
        m = rows.get(model_file)
        if not m or not m["installed"]:
            raise ValueError("Install a model first (Models page)")
        steps = [{"model": model_file, "name": m["name"]}]
        d = rows.get(drum_model) if drum_model else None
        if drum_model and (not d or not d["installed"]):
            raise ValueError("Install the drum model first (Models page)")
        if d and any(s.lower() == "drums" for s in m["stems"]):
            steps.append({"model": drum_model, "name": d["name"], "on": "Drums"})
        return steps

    # ---------- jobs from dubplates.net (bridge.py) ----------
    def _start_job(self, file: str) -> dict:
        """A job for the site: the model (and drum split) chosen in the client."""
        rows = [r for r in self.models() if r["installed"]]
        model = self._cfg["model"] if any(r["file"] == self._cfg["model"] for r in rows) else (rows[0]["file"] if rows else "")
        self._jobs.add([file], self._steps(model, self._cfg["drumSplit"]))
        return {"job": self._jobs.last_ids[0]}

    def _job(self, jid):
        return self._jobs.get(jid)

    def _ask_site(self, rid):
        """The site asks for a job: the window comes to the front and the UI asks (LinkAsk.jsx)."""
        cb = getattr(self, "_front", None)
        if cb:
            cb()

    @safe
    def site_pending(self):
        """Site requests that wait for the user (oldest first)."""
        s = getattr(self, "_site", None)
        if not s:
            return []
        with s.lock:
            return [dict(r) for r in s.items.values() if r["state"] in ("asking", "needRoot")]

    @safe
    def site_accept(self, rid, trust=False):
        if trust:
            self._cfg.update({"trustSite": True})
        self._site.accept(int(rid))
        return True

    @safe
    def site_cancel(self, rid):
        self._site.cancel(int(rid))
        return True

    @safe
    def site_root(self, rid):
        """The user shows where the site's music folder is; then the request asks to start."""
        r = self._site.get(int(rid))
        out = self.set_root(r["root"], r["path"])
        if out.get("file"):
            r.update(file=out["file"], state="asking")
            if self._cfg["trustSite"]:
                self._site.accept(r["id"])
        return out

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

    # ---------- dubplates:// links from the site ----------
    def _link(self, url: str) -> dict:
        """dubplates://open  |  dubplates://separate?root=<music folder name>&path=<file in it>.
        Only reads the link: nothing starts before the user says yes in the window."""
        from urllib.parse import parse_qs, urlsplit
        u = urlsplit(url)
        action = (u.netloc or u.path.strip("/")).lower()
        if action != "separate":
            return {"action": "open"}
        q = parse_qs(u.query)
        return self._link_info((q.get("root") or [""])[0], (q.get("path") or [""])[0])

    def _link_info(self, root: str, rel: str) -> dict:
        """A track in the site's music folder <root> (its name in the browser) at <rel>: where is it on this computer?"""
        root, rel = root[:200], rel[:1000]
        parts = [p for p in rel.replace("\\", "/").split("/") if p]
        if not root or not parts or any(p in (".", "..") or ":" in p for p in parts) or Path(parts[-1]).suffix.lower() not in AUDIO:
            return {"action": "error", "error": "This link is not a track in your music folder."}
        out = {"action": "separate", "root": root, "path": "/".join(parts), "name": parts[-1]}
        base = self._cfg["roots"].get(root)
        f = Path(base, *parts) if base else None
        if f and f.is_file():
            out["file"] = str(f)
        else:
            out["needRoot"] = True
            out["tried"] = base or ""
        return out

    @safe
    def pending_link(self):
        """The link that started the app / came from a second start (the UI asks for it once)."""
        u, self._pending = getattr(self, "_pending", None), None
        return self._link(u) if u else None

    @safe
    def set_root(self, root, path_in_root):
        """The user shows where the music folder <root> is; the track must be in it."""
        r = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        d = (r[0] if isinstance(r, (list, tuple)) else r) if r else ""
        if not d:
            return {"cancelled": True}
        f = Path(d, *path_in_root.split("/"))
        if not f.is_file():
            return {"error": f"“{path_in_root}” is not in that folder. Choose the folder that you chose as music folder on dubplates.net."}
        self._cfg.update({"roots": {**self._cfg["roots"], root: d}})
        return {"file": str(f)}

    @safe
    def check_update(self):
        from . import updates
        return updates.check()

    @safe
    def open_url(self, url):
        if not str(url).startswith("https://"):
            return {"error": "Only https links"}
        import webbrowser
        webbrowser.open(url)
        return True
