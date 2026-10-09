"""Work queues: stem jobs (one at a time, in order) and model installs (one thread each)."""
from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import time
import traceback
from collections import Counter
from pathlib import Path

from .awake import set_awake
from .config import app_dir
from .engine import Cancelled, Engine, bind, process_stem
from .layout import AUDIO, has_stems, scan, stems_dir

log = logging.getLogger("dubplates")
_ids = itertools.count(1)


class Jobs:
    """The stem queue: one job at a time, in order. Saved in <app dir>/queue.json: after a restart (or a crash) the
    waiting jobs go on. While it works the computer stays awake (a whole library overnight)."""

    KEEP = ("kind", "path", "base", "name", "steps", "modelName", "stem", "model", "skip", "added", "chain")

    def __init__(self, engine: Engine, library=None):
        self.eng = engine
        self.lib = library                              # finished sets go into the user's library
        self.lock = threading.Lock()
        self.jobs: list[dict] = []
        self.cancels: dict[int, threading.Event] = {}
        self.wake = threading.Event()
        self.paused = False
        self.qfile = app_dir() / "queue.json"
        self._restore()
        threading.Thread(target=self._loop, daemon=True, name="stems").start()

    # ---------- saved queue ----------
    def _save(self):
        try:
            todo = [{k: j[k] for k in self.KEEP if k in j} for j in self.jobs if j["state"] in ("queued", "running")]
            tmp = self.qfile.with_suffix(".tmp")
            tmp.write_text(json.dumps(todo), encoding="utf-8")
            os.replace(tmp, self.qfile)
        except OSError as e:
            log.warning("queue save: %s", e)

    def _restore(self):
        try:
            todo = json.loads(self.qfile.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for x in todo if isinstance(todo, list) else []:
            if not Path(x.get("path", "")).exists():
                continue
            jid = next(_ids)
            self.cancels[jid] = threading.Event()
            self.jobs.append({"added": time.time(), **x, "id": jid, "state": "queued", "pct": 0, "msg": "Waiting (from the last session)",
                              "folder": "", "stems": [], "err": "", "secs": 0})
        if self.jobs:
            log.info("queue: %d jobs from the last session", len(self.jobs))

    # ---------- add ----------
    def add(self, paths: list[str], steps: list[dict], skip: bool = False) -> int:
        """Every audio file in paths (folders: with all sub folders). skip: tracks that have stems already are skipped."""
        found = scan(paths)
        ids = []
        with self.lock:
            have = {j["path"] for j in self.jobs if j["state"] in ("queued", "running") and j.get("kind") != "stem"}
            for f, base in found:
                if str(f) in have:
                    continue                            # (already waiting)
                jid = next(_ids)
                self.cancels[jid] = threading.Event()
                self.jobs.append({"id": jid, "path": str(f), "base": str(base), "name": f.name, "steps": steps, "skip": skip,
                                  "modelName": " → ".join(s["name"] for s in steps), "state": "queued", "pct": 0, "msg": "Waiting",
                                  "folder": "", "stems": [], "err": "", "added": time.time(), "secs": 0})
                ids.append(jid)
            self.last_ids = ids
            self._save()
        self.wake.set()
        return len(ids)

    def add_stem_work(self, folder: str, stem: str, model_file: str, model_name: str) -> int:
        """More work on one stem of a set (see engine.process_stem)."""
        with self.lock:
            jid = next(_ids)
            self.cancels[jid] = threading.Event()
            self.jobs.append({"id": jid, "kind": "stem", "path": folder, "name": f"{Path(folder).name} › {stem}", "stem": stem,
                              "model": model_file, "modelName": model_name, "state": "queued", "pct": 0, "msg": "Waiting",
                              "folder": "", "stems": [], "err": "", "added": time.time(), "secs": 0})
            self.last_ids = [jid]
            self._save()
        self.wake.set()
        return jid

    def add_fx(self, folder: str, stem: str, chain: list) -> int:
        """Apply an effects chain to one stem of a set (fx.apply): the stem file is replaced, the original kept."""
        with self.lock:
            jid = next(_ids)
            self.cancels[jid] = threading.Event()
            self.jobs.append({"id": jid, "kind": "fx", "path": folder, "name": f"{Path(folder).name} › {stem}", "stem": stem, "chain": chain,
                              "modelName": "Effects", "state": "queued", "pct": 0, "msg": "Waiting", "folder": "", "stems": [],
                              "err": "", "added": time.time(), "secs": 0})
            self.last_ids = [jid]
            self._save()
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
            self._save()

    def cancel_all(self):
        with self.lock:
            for j in self.jobs:
                if j["state"] in ("queued", "running"):
                    self.cancels[j["id"]].set()
                    if j["state"] == "queued":
                        j["state"], j["msg"] = "cancelled", "Cancelled"
            self._save()

    def set_paused(self, on: bool):
        self.paused = bool(on)
        self.wake.set()

    def clear(self):
        with self.lock:
            self.jobs = [j for j in self.jobs if j["state"] in ("queued", "running")]

    def state(self) -> list[dict]:
        with self.lock:
            return [dict(j) for j in self.jobs[-400:]]       # (a whole library: the UI shows the last 400)

    def summary(self) -> dict:
        """For the queue header: counts and the time left (from the average time per track so far)."""
        with self.lock:
            c = Counter(j["state"] for j in self.jobs)
            done = [j["secs"] for j in self.jobs if j["state"] == "done" and not j.get("kind") and j["secs"]]
            run = next((j for j in self.jobs if j["state"] == "running"), None)
        last = done[-20:]
        avg = sum(last) / len(last) if last else None
        left = c["queued"] + (1 if run else 0)
        eta = round(avg * left - (run["secs"] if run else 0)) if avg and left else None
        return {"total": len(self.jobs), "done": c["done"], "skipped": c["skipped"], "error": c["error"], "queued": c["queued"],
                "running": bool(run), "paused": self.paused, "eta": max(0, eta) if eta is not None else None}

    def _next(self):
        with self.lock:
            return None if self.paused else next((j for j in self.jobs if j["state"] == "queued"), None)

    def _loop(self):
        awake = False
        while True:
            j = self._next()
            if not j:
                if awake:
                    set_awake(False)
                    awake = False
                self.wake.wait(1)
                self.wake.clear()
                continue
            if not awake:
                set_awake(True)
                awake = True
            ev = self.cancels[j["id"]]
            base = Path(j["base"]) if j.get("base") else None
            if j.get("kind") not in ("stem", "fx") and j.get("skip") and has_stems(self.eng.cfg, Path(j["path"]), base):
                j.update(state="skipped", msg="Has stems already", folder=str(stems_dir(self.eng.cfg, Path(j["path"]), base)))
                with self.lock:
                    self._save()
                continue
            j.update(state="running", msg="Starting…", pct=0)
            t0 = time.monotonic()

            def cb(frac, msg, j=j):
                j["pct"] = round(frac * 100, 1)
                if msg:
                    j["msg"] = msg
                j["secs"] = round(time.monotonic() - t0)

            bind(cb, ev)
            try:
                if j.get("kind") == "fx":
                    from . import fx
                    from .engine import _report
                    fx.apply(Path(j["path"]), j["stem"], j["chain"], lambda f, m: _report(f, m))
                    out = {"folder": j["path"], "stems": []}
                elif j.get("kind") == "stem":
                    out = process_stem(self.eng, Path(j["path"]), j["stem"], j["model"], j["modelName"])
                else:
                    out = self.eng.run(Path(j["path"]), j["steps"], base)
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
                with self.lock:
                    self._save()


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
