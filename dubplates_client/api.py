"""The methods the UI calls: window.pywebview.api.<name>(...). Each returns plain JSON data.
Errors go back as {"error": "..."} so the UI can show them."""
from __future__ import annotations

import functools
import json
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
        from .library import Library
        self._lib = Library()
        self._jobs = Jobs(self._eng, self._lib)
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
        return {"jobs": self._jobs.state(), "installs": self._inst.state(), "queue": self._jobs.summary()}

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
    def add_jobs(self, paths, model_file, drum_model="", skip=None):
        """drum_model: also split the Drums stem with this model (when the first model makes one).
        skip: skip tracks that have stems already (default: the setting)."""
        steps = self._steps(model_file, drum_model)
        self._cfg.update({"model": model_file, "drumSplit": drum_model or ""})
        return {"added": self._jobs.add(list(paths or []), steps, self._cfg["skipDone"] if skip is None else bool(skip))}

    @safe
    def preview_add(self, paths, mode=None, out_dir=None):
        """Before a big add: how many tracks, how the folders look, and where the stems of a few of them would go
        with this layout (mode / out_dir: the choice in the Add window, not saved yet)."""
        from .layout import has_stems, scan, stems_dir, structure
        found = scan(list(paths or []))
        cfg = {**self._cfg.data, "outMode": mode or self._cfg["outMode"], "outDir": self._cfg["outDir"] if out_dir is None else out_dir}
        pick = found[:2] + found[len(found) // 2:len(found) // 2 + 1] + found[-1:] if len(found) > 4 else found
        seen, ex = set(), []
        for f, base in pick:
            if str(f) not in seen:
                seen.add(str(f))
                ex.append({"src": str(f), "out": str(stems_dir(cfg, f, base))})
        return {"count": len(found), "structure": structure(found), "examples": ex,
                "have": sum(1 for f, b in found if has_stems(cfg, f, b)) if len(found) <= 20000 else None,
                "folders": len({f.parent for f, _ in found})}

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

    @safe
    def pause_queue(self, on):
        self._jobs.set_paused(on)
        return True

    @safe
    def cancel_all(self):
        self._jobs.cancel_all()
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

    # ---------- library: the user's stem sets ----------
    @safe
    def library(self):
        return self._lib.list()

    @safe
    def library_detail(self, lid):
        d = self._lib.detail(lid)
        d["media"] = getattr(self, "_media", None)        # base URL to play files (bridge.py)
        # a version per file: the player's URL changes when a file changes (effects, plugin, restore). Else the
        # player mixes parts of the old file from its cache with the new file: that stem is silent after a jump.
        f, m, ver = Path(d["folder"]), d["meta"], {}
        rels = [s["file"] for s in m["stems"]] + [p["file"] for s in m["stems"] for p in s.get("parts") or []] + [
            p["file"] for s in m["stems"] for x in s.get("derived") or [] for p in x.get("stems") or []]
        for key, p in [(d["folder"] + "/" + r, f / r) for r in rels] + ([(d["sourceFile"], Path(d["sourceFile"]))] if d.get("sourceFile") else []):
            try:
                st = p.stat()
                ver[key] = f"{st.st_mtime_ns:x}{st.st_size:x}"
            except OSError:
                pass
        d["ver"] = ver
        return d

    @safe
    def peaks(self, path, n=1600):
        """The waveform of a file for the stem view: n pairs [min, max] (mono), and the length in seconds.
        Kept in <app dir>/peaks/ (by file, size and time), so a set opens fast the next time."""
        import hashlib
        import json as _json
        import numpy as np
        import soundfile as sf
        from .config import app_dir
        f = Path(path)
        if not self._lib.allowed(f):
            return {"error": "Not in the library"}
        st = f.stat()
        key = hashlib.sha1(f"{f.resolve()}|{st.st_size}|{st.st_mtime_ns}|{n}".encode()).hexdigest()[:20]
        cache = app_dir() / "peaks" / f"{key}.json"
        try:
            return _json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        info = sf.info(str(f))
        total = max(1, info.frames)
        step = max(1, total // n)
        lo, hi = np.zeros(n, np.float32), np.zeros(n, np.float32)
        i = 0
        for block in sf.blocks(str(f), blocksize=step * 64, dtype="float32", always_2d=True):
            m = block.mean(axis=1)
            k = len(m) // step
            if k:
                b = m[:k * step].reshape(k, step)
                j = min(n, i + k)
                lo[i:j], hi[i:j] = b.min(axis=1)[:j - i], b.max(axis=1)[:j - i]
                i = j
            if i >= n:
                break
        out = {"dur": round(info.frames / info.samplerate, 3), "peaks": [[round(float(a), 3), round(float(b), 3)] for a, b in zip(lo, hi)]}
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(_json.dumps(out), encoding="utf-8")
        return out

    @safe
    def library_add(self):
        f = self.pick_folder()
        if not f:
            return {"cancelled": True}
        return self._lib.add(f)

    @safe
    def library_remove(self, lid):
        self._lib.remove(lid)
        return True

    @safe
    def stem_work(self, lid, stem, model_file):
        """Run another model on one stem of a set."""
        f = self._lib.folder(lid)
        m = next((r for r in self.models() if r["file"] == model_file), None)
        if not f or not m or not m["installed"]:
            return {"error": "Install the model first (Models page)"}
        return {"job": self._jobs.add_stem_work(str(f), stem, model_file, m["name"])}

    # ---------- effects on a stem (fx.py) ----------
    def _need_fx(self):
        """Installs made before 0.1.7 have no pedalboard: get it once (small) with this app's own pip."""
        import importlib.util
        if importlib.util.find_spec("pedalboard") is None:
            log.info("installing pedalboard (effects)")
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "pedalboard>=0.9"],
                               capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0:
                raise RuntimeError("Could not install the effects engine (pedalboard): " + (r.stderr or r.stdout)[-300:])
            importlib.invalidate_caches()

    @safe
    def fx_catalog(self):
        self._need_fx()
        from . import fx
        if getattr(self, "_vsts", None) is None:
            self._vsts = fx.scan_vst()
        return {**fx.catalog(), "vsts": self._vsts}

    @safe
    def fx_rescan(self):
        from . import fx
        self._vsts = fx.scan_vst()
        return self._vsts

    @safe
    def fx_chain(self, lid, stem):
        """The chain saved on this stem (from the last Apply), else the suggested one for its name."""
        from . import fx
        f = self._lib.folder(lid)
        meta = self._lib.detail(lid)["meta"]
        s = next((s for s in meta["stems"] if s["name"].lower() == stem.lower()), {})
        orig = (f / ".originals" / Path(s.get("file", "")).name).exists()
        if s.get("fx"):
            return {"chain": s["fx"], "applied": True, "original": orig}
        name = fx.SUGGEST.get(stem.lower(), "Natural cleanup")
        return {"chain": fx.chain_preset(name), "applied": False, "original": orig, "suggested": name}

    @safe
    def fx_module(self, kind, preset=None):
        from . import fx
        return fx.module(kind, preset)

    @safe
    def fx_preset(self, name):
        from . import fx
        return fx.chain_preset(name)

    @safe
    def fx_preview(self, lid, stem, chain, start=0, dur=20):
        """A short part of the stem through the chain (and the same part without it, for A/B)."""
        import hashlib
        from . import fx
        from .config import app_dir
        f = self._lib.folder(lid)
        start = max(0.0, float(start))
        key = hashlib.sha1(f"{f}|{stem}|{start:.2f}|{dur}|{json.dumps(chain, sort_keys=True)}".encode()).hexdigest()[:16]
        d = app_dir() / "preview"
        if d.exists():
            for old_f in sorted(d.glob("*.wav"), key=lambda x: x.stat().st_mtime)[:-12]:
                old_f.unlink(missing_ok=True)                # (keep the last few)
        out = d / f"{key}.wav"
        if not out.exists():
            fx.preview(f, stem, chain, start, float(dur), out)
        dry = d / f"{key}-dry.wav"
        if not dry.exists():
            fx.preview(f, stem, [], start, float(dur), dry)
        return {"wet": str(out), "dry": str(dry), "start": start, "media": getattr(self, "_media", None)}

    @safe
    def fx_apply(self, lid, stem, chain):
        f = self._lib.folder(lid)
        return {"job": self._jobs.add_fx(str(f), stem, chain)}

    @safe
    def fx_restore(self, lid, stem):
        from . import fx
        return fx.restore(self._lib.folder(lid), stem)

    @safe
    def vst_params(self, path):
        from . import fx
        return fx.vst_params(path)

    @safe
    def vst_editor(self, path, state=None):
        from . import fx
        return fx.vst_editor(path, state or {})

    # ---------- plugins (plugins.py) ----------
    @safe
    def plugins(self):
        from . import plugins
        inst = getattr(self, "_pinst", {})
        return {"dir": str(plugins.plugins_dir()), "items": [{**m, "install": inst.get(m["id"])} for m in plugins.scan()],
                "saved": self._cfg["pluginInputs"], "getting": {k: v for k, v in inst.items() if not v["done"] or v["err"]}}

    @safe
    def plugin_install(self, pid):
        """Installs the packages of a plugin (in a thread; plugins() shows the progress)."""
        from . import plugins
        plugins.get(pid)
        self._pinst = getattr(self, "_pinst", {})
        cur = self._pinst.get(pid)
        if cur and not cur["done"]:
            return True
        it = self._pinst[pid] = {"pct": 0, "msg": "Starting…", "err": "", "done": False}

        def work():
            try:
                plugins.install(pid, lambda f, m: it.update(pct=round(f * 100), msg=m))
            except Exception as e:  # noqa: BLE001
                log.exception("plugin install %s", pid)
                it.update(err=str(e)[:400], msg="Failed")
            finally:
                it["done"] = True

        threading.Thread(target=work, daemon=True).start()
        return True

    @safe
    def plugin_catalog(self):
        from . import plugins
        return {"items": plugins.catalog(), "canInstall": bool(plugins.TRUST_KEYS)}

    @safe
    def plugin_get(self, pid):
        """Install (or update) a plugin from dubplates.net, then its packages and models."""
        from . import plugins
        self._pinst = getattr(self, "_pinst", {})
        cur = self._pinst.get(pid)
        if cur and not cur["done"]:
            return True
        it = self._pinst[pid] = {"pct": 0, "msg": "Starting…", "err": "", "done": False}

        def work():
            try:
                plugins.install_catalog(pid, lambda f, m: it.update(pct=round(f * 100), msg=m))
                plugins.install(pid, lambda f, m: it.update(pct=round(5 + f * 95), msg=m))
            except Exception as e:  # noqa: BLE001
                log.exception("plugin get %s", pid)
                it.update(err=str(e)[:400], msg="Failed")
            finally:
                it["done"] = True

        threading.Thread(target=work, daemon=True).start()
        return True

    @safe
    def plugin_remove(self, pid):
        from . import plugins
        if any(j.get("plugin") == pid and j["state"] in ("queued", "running") for j in self._jobs.state()):
            return {"error": "This plugin has a job in the queue: wait for it, or cancel it"}
        plugins.remove(pid)
        return True

    @safe
    def plugin_add(self):
        from . import plugins
        f = self.pick_folder()
        if not f:
            return {"cancelled": True}
        return plugins.add_folder(f)

    @safe
    def plugin_folder(self):
        from . import plugins
        return self.open_path(str(plugins.plugins_dir()))

    @safe
    def plugin_run(self, lid, stem, pid, inputs=None, options=None):
        from . import plugins
        m = plugins.get(pid)
        if m.get("problem"):
            return {"error": m["problem"]}
        if not m["ready"]:
            return {"error": "Install the plugin first (Models › Plugins › Install)"}
        inputs, options = dict(inputs or {}), dict(options or {})
        saved = dict(self._cfg["pluginInputs"])
        keep = {i["id"] for i in m.get("inputs") or [] if i.get("remember")} | {o["id"] for o in m.get("options") or []}
        saved[pid] = {**saved.get(pid, {}), **{k: v for k, v in {**inputs, **options}.items() if k in keep}}
        self._cfg.update({"pluginInputs": saved})
        return {"job": self._jobs.add_plugin(str(self._lib.folder(lid)), stem, m, inputs, options)}

    @safe
    def pick_audio(self):
        r = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                                            file_types=("Audio files (" + ";".join("*" + e for e in AUDIO) + ")", "All files (*.*)"))
        return (r[0] if isinstance(r, (list, tuple)) else r) if r else ""

    # ---------- send a stem set to a deck on dubplates.net (bridge.py: the site asks /v1/inbox) ----------
    @safe
    def site_link(self):
        """Is a dubplates.net mixer (signed in) open in a browser on this computer? (It asks the bridge every 2 s.)"""
        import time as _t
        seen = getattr(self, "_site_seen", 0)
        return {"connected": _t.time() - seen < 6, "user": getattr(self, "_site_user", "")}

    @safe
    def send_deck(self, lid, deck):
        import time as _t
        if deck not in ("A", "B"):
            return {"error": "Deck A or B"}
        if not self.site_link()["connected"]:
            return {"error": "Open the dubplates.net mixer (signed in) in your browser on this computer first."}
        d = self._lib.detail(lid)
        f, meta = Path(d["folder"]), d["meta"]
        stems = [{"name": s["name"], "file": s["file"]} for s in meta["stems"] if (f / s["file"]).is_file()]
        if not stems:
            return {"error": "This set has no stem files"}
        title = Path((meta.get("source") or {}).get("name") or f.name).stem
        self._sends = [x for x in getattr(self, "_sends", []) if _t.time() - x["at"] < 600]
        sid = max([x["id"] for x in self._sends], default=0) + 1
        self._sends.append({"id": sid, "deck": deck, "title": title, "folder": str(f), "stems": stems, "at": _t.time(), "taken": False})
        return {"sent": sid}

    def _inbox(self, user: str = "") -> list[dict]:
        import time as _t
        self._site_seen, self._site_user = _t.time(), user[:80]
        out = []
        for x in getattr(self, "_sends", []):
            if not x["taken"]:
                x["taken"] = True
                out.append({k: x[k] for k in ("id", "deck", "title", "stems")})
        return out

    def _send_file(self, sid: int, n: int) -> Path | None:
        x = next((x for x in getattr(self, "_sends", []) if x["id"] == sid), None)
        if not x or not 0 <= n < len(x["stems"]):
            return None
        base = Path(x["folder"]).resolve()
        f = (base / x["stems"][n]["file"]).resolve()
        return f if f.is_file() and base in f.parents else None

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
