"""Plugins: tools from other people (or the user) that work on one stem: file in, file out.

A plugin is a folder in <app dir>/plugins/<id>/ with a plugin.json (see PLUGINS.md):

  {"id": "vocal_repair", "name": "Vocal repair", "version": "1.0", "description": "...",
   "for": ["vocals"],                              stem names it is made for (shown first there; it works on any stem)
   "entry": "audio_restore:repair_vocal",          module (a .py in the folder) : function
   "args": ["$reference", "$stem", "$output"],     positional arguments: $stem = the stem file, $output = the file to
                                                   write, $<input id> = a file the user chose
   "inputs":  [{"id": "reference", "type": "audio", "label": "...", "help": "...", "remember": true}],
   "options": [{"id": "ml", "type": "bool", "label": "...", "default": true}],      keyword arguments
   "callbacks": {"progress": "progress", "log": "log", "cancel": "should_cancel"},   names of the keyword arguments
   "output": {"ext": ".wav"},
   "requirements": "requirements.txt", "skipPackages": ["matplotlib"],
   "files": [".models/a.onnx"]}                    files that must be there (else: "reinstall the plugin")

The function runs in its own process (plugin_runner.py): its memory (also on the GPU) is free again after each job,
and a crash does not stop the app. Packages the app does not have yet go into the plugin's own '.deps' folder, so
a plugin can not break the stem engine (example: onnxruntime-directml next to the engine's onnxruntime).

The result REPLACES the stem (same length and place, like Effects): the model's stem stays in '.originals/',
the plugin's result is kept in '.plugins/' (an Effects chain then works on it), "Restore original" undoes both.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .config import app_dir

log = logging.getLogger("dubplates")
ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,60}$")


def plugins_dir() -> Path:
    d = app_dir() / "plugins"
    d.mkdir(exist_ok=True)
    return d


def _manifest(d: Path) -> dict | None:
    try:
        m = json.loads((d / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        if (d / "plugin.json").exists():
            return {"id": d.name, "name": d.name, "dir": str(d), "problem": f"plugin.json can not be read: {e}"}
        return None
    m.setdefault("id", d.name)
    m["dir"] = str(d)
    probs = []
    if not ID_RE.match(str(m["id"])):
        probs.append("bad id")
    entry = str(m.get("entry", ""))
    mod = entry.split(":")[0]
    if ":" not in entry or not (d / (mod.replace(".", "/") + ".py")).is_file():
        probs.append(f"entry “{entry}”: no such .py file in the folder")
    missing = [f for f in m.get("files") or [] if not (d / f).is_file()]
    if missing:
        probs.append("missing files: " + ", ".join(missing) + " (copy the whole plugin folder again)")
    m["problem"] = "; ".join(probs)
    m["packages"] = deps_state(m)
    return m


def scan() -> list[dict]:
    out = []
    for d in sorted(plugins_dir().iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            m = _manifest(d)
            if m:
                out.append(m)
    return out


def get(pid: str) -> dict:
    if not ID_RE.match(str(pid)):
        raise ValueError("Unknown plugin")
    m = next((m for m in scan() if m["id"] == pid), None)
    if not m:
        raise ValueError(f"No plugin “{pid}” in {plugins_dir()}")
    return m


# ---------- packages ----------
def _req_lines(m: dict) -> list[str]:
    f = Path(m["dir"]) / (m.get("requirements") or "requirements.txt")
    if not f.is_file():
        return []
    skip = {s.lower() for s in m.get("skipPackages") or []}
    out = []
    for ln in f.read_text(encoding="utf-8").splitlines():
        ln = ln.split("#", 1)[0].strip()
        if not ln or ln.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[; ]", ln, 1)[0].lower()
        if name in skip:
            continue
        if sys.platform != "win32" and name == "onnxruntime-directml":   # (DirectML is only for Windows)
            ln = "onnxruntime" + ln[len(name):]
        out.append(ln)
    return out


def _key(m: dict) -> str:
    return hashlib.sha1("\n".join(_req_lines(m)).encode()).hexdigest()[:16]


def deps_state(m: dict) -> str:
    """ok | missing (packages must be installed first)"""
    if not _req_lines(m):
        return "ok"
    try:
        return "ok" if (Path(m["dir"]) / ".deps" / ".ok").read_text().strip() == _key(m) else "missing"
    except OSError:
        return "missing"


def _requirement(s: str):
    try:
        from packaging.requirements import Requirement
    except ImportError:                                          # pragma: no cover
        from pip._vendor.packaging.requirements import Requirement
    return Requirement(s)


def _have(req, paths: list[str]) -> bool:
    import importlib.metadata as md
    for d in md.distributions(path=paths):
        if (d.metadata["Name"] or "").lower().replace("_", "-") == req.name.lower().replace("_", "-"):
            return req.specifier.contains(d.version, prereleases=True)
    return False


def install_deps(pid: str, report=None) -> None:
    """The packages the app does not have go into <plugin>/.deps (pip --target, one by one without their own
    dependencies, then the dependencies that are missing: the app's numpy etc. are never replaced)."""
    m = get(pid)
    d = Path(m["dir"]) / ".deps"
    base = [p for p in sys.path if p and Path(p).is_dir() and Path(p).resolve() != d.resolve()]
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    todo = [_requirement(s) for s in _req_lines(m)]
    todo = [r for r in todo if not r.marker or r.marker.evaluate()]
    done: set[str] = set()
    for rnd in range(6):
        need = [r for r in todo if r.name.lower() not in done and not _have(r, base) and not _have(r, [str(d)])]
        if not need:
            break
        for i, r in enumerate(need):
            if report:
                report(min(0.95, (rnd * 0.3 + i / max(1, len(need)) * 0.3)), f"Installing {r.name}…")
            _pip(["install", "--target", str(d), "--no-deps", "--upgrade", "--disable-pip-version-check", "-q", str(r)])
            done.add(r.name.lower())
        import importlib.metadata as md
        todo = []                                           # their dependencies: only the ones nobody has
        for dist in md.distributions(path=[str(d)]):
            for s in dist.requires or []:
                r = _requirement(s)
                if r.marker and not r.marker.evaluate({"extra": ""}):
                    continue
                todo.append(r)
    (d / ".ok").write_text(_key(m))
    if report:
        report(1.0, "Packages installed")


def _pip(args: list[str]):
    r = subprocess.run([sys.executable, "-m", "pip", *args], capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError("pip: " + (r.stderr or r.stdout).strip()[-400:])


# ---------- run ----------
class PluginError(Exception):
    pass


def run(m: dict, stem_file: Path, out_file: Path, inputs: dict, options: dict, report, cancelled) -> dict:
    """Runs the plugin's function in its own process. report(frac, msg); cancelled() -> bool.
    Returns {"warnings": [...], "log": [...]}. Raises PluginError (its message is for the user)."""
    if m.get("problem"):
        raise PluginError(m["problem"])
    if deps_state(m) != "ok":
        raise PluginError("Install the plugin's packages first (Models › Plugins)")
    vals = {"stem": str(stem_file), "output": str(out_file)}
    for i in m.get("inputs") or []:
        v = (inputs or {}).get(i["id"], "")
        if not v and not i.get("optional"):
            raise PluginError(f"Choose: {i.get('label', i['id'])}")
        if v and i.get("type", "audio") in ("audio", "file") and not Path(v).is_file():
            raise PluginError(f"{i.get('label', i['id'])}: file not found ({v})")
        vals[i["id"]] = v
    args = [vals.get(a[1:], "") if isinstance(a, str) and a.startswith("$") else a for a in m.get("args") or ["$stem", "$output"]]
    used = {a[1:] for a in m.get("args") or [] if isinstance(a, str) and a.startswith("$")}
    kwargs = {k: v for k, v in vals.items() if k not in used and k not in ("stem", "output")}
    for o in m.get("options") or []:
        v = (options or {}).get(o["id"], o.get("default"))
        if o.get("type") == "bool":
            v = bool(v)
        elif o.get("type") == "number":
            v = float(v)
        kwargs[o["id"]] = v
    logs = app_dir() / "logs"
    logs.mkdir(exist_ok=True)
    flag = logs / f"cancel-{m['id']}-{os.getpid()}"            # (cancel: this file is made; the plugin looks for it)
    flag.unlink(missing_ok=True)
    job = {"dir": m["dir"], "entry": m["entry"], "args": args, "kwargs": kwargs, "callbacks": m.get("callbacks") or {}, "cancel": str(flag)}
    err_f = open(logs / f"plugin-{m['id']}.log", "w", encoding="utf-8")
    runner = Path(__file__).with_name("plugin_runner.py")
    p = subprocess.Popen([sys.executable, "-I", str(runner)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err_f,
                         text=True, encoding="utf-8", cwd=m["dir"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    p.stdin.write(json.dumps(job))
    p.stdin.close()
    stop = threading.Event()

    def watch():                                  # cancel: ask the plugin to stop, after 15 s stop the process
        while not stop.wait(0.3):
            if cancelled():
                flag.touch()
                t = time.monotonic()
                while p.poll() is None and time.monotonic() - t < 15:
                    time.sleep(0.2)
                if p.poll() is None:
                    p.kill()
                return

    threading.Thread(target=watch, daemon=True).start()
    result, lines = None, []
    try:
        for ln in p.stdout:
            try:
                ev = json.loads(ln)
            except ValueError:
                continue
            if "p" in ev:
                report(float(ev["p"]), ev.get("m") or None)
            elif "log" in ev:
                lines.append(ev["log"])
                del lines[:-200]
            elif "done" in ev or "error" in ev:
                result = ev
        p.wait()
    finally:
        stop.set()
        err_f.close()
        flag.unlink(missing_ok=True)
    if cancelled():
        out_file.unlink(missing_ok=True)
        return {"cancelled": True}
    if not result:
        raise PluginError(f"The plugin stopped (exit code {p.returncode}). Details: {logs / ('plugin-' + m['id'] + '.log')}")
    if "error" in result:
        raise PluginError(result["error"])
    if not out_file.is_file():
        raise PluginError("The plugin wrote no file")
    return {"warnings": result["done"].get("warnings") or [], "log": lines}


def apply(folder: Path, stem: str, m: dict, inputs: dict, options: dict, report, cancelled) -> dict:
    """Runs a plugin on the model's stem and replaces the stem file with the result (format of the stem).
    An Effects chain that was on the stem is applied again, on the plugin's result."""
    import soundfile as sf
    from . import fx
    meta_p = folder / "dubplates.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    f, orig = fx.stem_paths(folder, meta, stem)
    if not orig.exists():
        orig.parent.mkdir(exist_ok=True)
        shutil.copy2(f, orig)
    keep = folder / ".plugins" / (f.stem + (m.get("output") or {}).get("ext", ".wav"))
    keep.parent.mkdir(exist_ok=True)
    tmp = keep.with_name(keep.stem + ".tmp" + keep.suffix)
    r = run(m, orig, tmp, inputs, options, report, cancelled)
    if r.get("cancelled"):
        return r
    for old in keep.parent.glob(f.stem + ".*"):
        if old != tmp:
            old.unlink(missing_ok=True)
    tmp.replace(keep)
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    s = next(s for s in meta["stems"] if s["name"].lower() == stem.lower())
    s["plugin"] = {"id": m["id"], "name": m.get("name", m["id"]), "version": m.get("version", ""), "file": keep.relative_to(folder).as_posix(),
                   "inputs": {k: v for k, v in (inputs or {}).items()}, "options": options or {}, "warnings": r["warnings"],
                   "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    meta_p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if s.get("fx"):
        report(0.97, "Effects again…")
        fx.apply(folder, stem, s["fx"])
    else:
        x, sr, _ = fx.read(keep)
        fx.write_like(f, x, sr, sf.info(str(orig)))
    return {"file": str(f), "warnings": r["warnings"]}


def add_folder(src: str) -> dict:
    """Copies a plugin folder (with plugin.json) into the plugins folder."""
    s = Path(src)
    if not (s / "plugin.json").is_file():
        raise ValueError("That folder has no plugin.json")
    m = json.loads((s / "plugin.json").read_text(encoding="utf-8"))
    pid = str(m.get("id") or s.name)
    if not ID_RE.match(pid):
        raise ValueError("The plugin's id is not valid")
    dst = plugins_dir() / pid
    if dst.resolve() == s.resolve():
        return get(pid)
    shutil.copytree(s, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".deps", "__pycache__", ".venv"))
    return get(pid)

