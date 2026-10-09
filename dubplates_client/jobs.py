"""Work queues: stem jobs (one at a time, in order) and model installs (one thread each)."""
from __future__ import annotations

import itertools
import logging
import threading
import time
import traceback
from pathlib import Path

from .engine import Cancelled, Engine, bind, process_stem

log = logging.getLogger("dubplates")
AUDIO = (".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".aif", ".aiff", ".opus", ".wma")
_ids = itertools.count(1)


class Jobs:
    def __init__(self, engine: Engine, library=None):
        self.eng = engine
        self.lib = library                              # finished sets go into the user's library
        self.lock = threading.Lock()
        self.jobs: list[dict] = []
        self.cancels: dict[int, threading.Event] = {}
        self.wake = threading.Event()
        threading.Thread(target=self._loop, daemon=True, name="stems").start()

    def add(self, paths: list[str], steps: list[dict]) -> int:
        n, ids = 0, []
        with self.lock:
            for p in paths:
                p = Path(p)
                if p.is_dir():
                    files = sorted(f for f in p.rglob("*") if f.suffix.lower() in AUDIO and " Stems" not in str(f.parent))
                else:
                    files = [p] if p.suffix.lower() in AUDIO and p.is_file() else []
                for f in files:
                    jid = next(_ids)
                    self.cancels[jid] = threading.Event()
                    self.jobs.append({"id": jid, "path": str(f), "name": f.name, "steps": steps, "modelName": " → ".join(s["name"] for s in steps),
                                      "state": "queued", "pct": 0, "msg": "Waiting", "folder": "", "stems": [], "err": "",
                                      "added": time.time(), "secs": 0})
                    n += 1
                    ids.append(jid)
            self.last_ids = ids
        self.wake.set()
        return n

    def add_stem_work(self, folder: str, stem: str, model_file: str, model_name: str) -> int:
        """More work on one stem of a set (see engine.process_stem)."""
        with self.lock:
            jid = next(_ids)
            self.cancels[jid] = threading.Event()
            self.jobs.append({"id": jid, "kind": "stem", "path": folder, "name": f"{Path(folder).name} › {stem}", "stem": stem,
                              "model": model_file, "modelName": model_name, "state": "queued", "pct": 0, "msg": "Waiting",
                              "folder": "", "stems": [], "err": "", "added": time.time(), "secs": 0})
            self.last_ids = [jid]
        self.wake.set()
        return jid

    def get(self, jid: int) -> dict | None:
        with self.lock:
            j = next((j for j in self.jobs if j["id"] == jid), None)
            return dict(j) if j else None

    def cancel(self, jid: int):
        with self.lock:
            for j in self.jobs:
                if j["id"] == jid and j["state"] in ("queued", "running"):
                    self.cancels[jid].set()
                    if j["state"] == "queued":
                        j["state"], j["msg"] = "cancelled", "Cancelled"

    def clear(self):
        with self.lock:
            self.jobs = [j for j in self.jobs if j["state"] in ("queued", "running")]

    def state(self) -> list[dict]:
        with self.lock:
            return [dict(j) for j in self.jobs]

    def _next(self):
        with self.lock:
            return next((j for j in self.jobs if j["state"] == "queued"), None)

    def _loop(self):
        while True:
            j = self._next()
            if not j:
                self.wake.wait(1)
                self.wake.clear()
                continue
            ev = self.cancels[j["id"]]
            j.update(state="running", msg="Starting…", pct=0)
            t0 = time.monotonic()

            def cb(frac, msg, j=j):
                j["pct"] = round(frac * 100, 1)
                if msg:
                    j["msg"] = msg
                j["secs"] = round(time.monotonic() - t0)

            bind(cb, ev)
            try:
                if j.get("kind") == "stem":
                    out = process_stem(self.eng, Path(j["path"]), j["stem"], j["model"], j["modelName"])
                else:
                    out = self.eng.run(Path(j["path"]), j["steps"])
                if self.lib:
                    try:
                        self.lib.add(out["folder"])
                    except Exception:  # noqa: BLE001
                        pass
                j.update(state="done", pct=100, msg="Done", folder=out["folder"], stems=out["stems"])
            except Cancelled:
                j.update(state="cancelled", msg="Cancelled")
            except Exception as e:  # noqa: BLE001
                log.error("job %s: %s", j["name"], traceback.format_exc())
                j.update(state="error", msg="Failed", err=_short_err(e))
            finally:
                bind(None, None)
                j["secs"] = round(time.monotonic() - t0)


class Installs:
    """Model downloads. state(): {model_file: {pct, msg, err, done}}."""

    def __init__(self, engine: Engine):
        self.eng = engine
        self.lock = threading.Lock()
        self.items: dict[str, dict] = {}
        self.cancels: dict[str, threading.Event] = {}

    def start(self, model_file: str):
        with self.lock:
            cur = self.items.get(model_file)
            if cur and not cur["done"]:
                return
            self.items[model_file] = {"pct": 0, "msg": "Starting…", "err": "", "done": False}
            self.cancels[model_file] = threading.Event()
        threading.Thread(target=self._run, args=(model_file,), daemon=True).start()

    def cancel(self, model_file: str):
        ev = self.cancels.get(model_file)
        if ev:
            ev.set()

    def _run(self, model_file: str):
        it = self.items[model_file]

        def cb(frac, msg):
            it["pct"] = round(frac * 100, 1)
            if msg:
                it["msg"] = msg

        bind(cb, self.cancels[model_file])
        try:
            self.eng.install(model_file)
            it.update(pct=100, msg="Installed")
        except Cancelled:
            it.update(msg="Cancelled", err="")
            for p in self.eng.cfg.model_dir().glob("*.part"):
                p.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            log.error("install %s: %s", model_file, traceback.format_exc())
            it.update(err=_short_err(e), msg="Failed")
        finally:
            bind(None, None)
            it["done"] = True

    def state(self) -> dict:
        with self.lock:
            return {k: dict(v) for k, v in self.items.items()}


def _short_err(e: Exception) -> str:
    s = str(e) or e.__class__.__name__
    if "out of memory" in s.lower():
        return "The GPU ran out of memory. Close other apps, or use a smaller model, or set Device to CPU."
    return s[:300]
