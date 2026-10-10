"""Runs one plugin function in its own process (started by plugins.run). Only the standard library before the
plugin is imported: the plugin's folder and its '.deps' come first on sys.path.

stdin:  the job as JSON {dir, entry, args, kwargs, callbacks, cancel}. Cancel = the file job["cancel"] is there.
        (Not a "cancel" line on stdin: on Windows a thread that waits on the stdin pipe stops imports like numpy.)
stdout: JSON lines {"p": frac, "m": msg} | {"log": line} | {"done": {...}} | {"error": msg}.
        (What the plugin prints goes to stderr: the app keeps it in logs/plugin-<id>.log.)
"""
import importlib
import json
import os
import sys
import threading
import traceback


def main():
    job = json.loads(sys.stdin.read())
    out = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr
    lock = threading.Lock()

    def send(**k):
        with lock:
            out.write(json.dumps(k) + "\n")
            out.flush()

    flag = job.get("cancel") or ""

    def cancelled():
        return bool(flag) and os.path.exists(flag)

    d = job["dir"]
    sys.path[:0] = [d, os.path.join(d, ".deps")]
    if sys.platform == "win32" and os.path.isdir(os.path.join(d, ".deps")):
        os.add_dll_directory(os.path.join(d, ".deps"))
    kw = dict(job.get("kwargs") or {})
    cb = job.get("callbacks") or {}
    if cb.get("progress"):
        kw[cb["progress"]] = lambda f, m="": send(p=float(f), m=str(m or ""))
    if cb.get("log"):
        kw[cb["log"]] = lambda line: send(log=str(line))
    if cb.get("cancel"):
        kw[cb["cancel"]] = cancelled
    try:
        mod, fn = job["entry"].split(":", 1)
        f = getattr(importlib.import_module(mod), fn)
        r = f(*job.get("args") or [], **kw)
        w = getattr(r, "warnings", None) if not isinstance(r, dict) else r.get("warnings")
        send(done={"warnings": [str(x) for x in (w or [])]})
    except BaseException as e:  # noqa: BLE001
        traceback.print_exc()
        name = type(e).__name__
        if cancelled() or "cancel" in name.lower():
            send(error="Cancelled", cancelled=True)
        elif isinstance(e, FileNotFoundError):
            send(error=f"A file is missing: {e}. Copy the whole plugin folder again.")
        elif isinstance(e, MemoryError) or "out of memory" in str(e).lower() or "E_OUTOFMEMORY" in str(e):
            send(error="Not enough memory (GPU or RAM). Close other apps, or turn off the plugin's ML option.")
        else:
            send(error=(str(e) or name)[:400])


if __name__ == "__main__":
    main()
    sys.stderr.flush()
    os._exit(0)          # (fast: no clean-up of the plugin's models)
