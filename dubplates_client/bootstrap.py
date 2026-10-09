"""First start: installs the stem engine (PyTorch + audio-separator) with pip, into this app's own Python.

The installer is small; PyTorch is big (CUDA build about 3 GB), so it comes here, with the build that fits this
computer: NVIDIA GPU → CUDA, Mac → Apple GPU (MPS, normal build), else CPU.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .config import app_dir

TORCH = "2.11.0"                      # (the CUDA 12.8 builds of this version are tested with the engine)
HERE = Path(__file__).parent
VARIANTS = {
    "cuda": {"label": "NVIDIA GPU (fast)", "size": "about 3 GB", "index": "https://download.pytorch.org/whl/cu128"},
    "cpu": {"label": "CPU only (slow)", "size": "about 300 MB", "index": "https://download.pytorch.org/whl/cpu"},
    "mps": {"label": "Apple GPU", "size": "about 200 MB", "index": None},
}


def engine_ready() -> bool:
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "audio_separator"))


def nvidia_gpu() -> str:
    """The NVIDIA GPU name, or '' when there is none (nvidia-smi comes with the driver)."""
    exe = shutil.which("nvidia-smi") or (r"C:\Windows\System32\nvidia-smi.exe" if sys.platform == "win32" else None)
    if not exe or not Path(exe).exists():
        return ""
    try:
        out = subprocess.run([exe, "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else ""
    except Exception:  # noqa: BLE001
        return ""


def detect() -> dict:
    if sys.platform == "darwin":
        rec, gpu = "mps", "Apple GPU"
    else:
        gpu = nvidia_gpu()
        rec = "cuda" if gpu else "cpu"
    opts = ["mps"] if sys.platform == "darwin" else (["cuda", "cpu"] if gpu else ["cpu"])
    return {"gpu": gpu, "recommended": rec, "options": [{"id": o, **{k: v for k, v in VARIANTS[o].items() if k != "index"}} for o in opts]}


class Setup:
    def __init__(self):
        self.lock = threading.Lock()
        self.st = {"running": False, "done": False, "error": "", "step": "", "pct": 0, "msg": "", "log": []}

    def state(self) -> dict:
        with self.lock:
            s = dict(self.st)
            s["log"] = s["log"][-40:]
            return s

    def start(self, variant: str):
        if variant not in VARIANTS:
            raise ValueError("Unknown choice")
        with self.lock:
            if self.st["running"]:
                return
            self.st.update(running=True, done=False, error="", pct=0, msg="", log=[])
        threading.Thread(target=self._run, args=(variant,), daemon=True).start()

    def _log(self, line: str):
        with self.lock:
            self.st["log"].append(line)

    def _pip(self, step: str, args: list[str], weight: tuple[float, float]):
        """Runs pip; progress lines ('Progress x of y', pip --progress-bar raw) move pct inside weight=(from, to)."""
        self.st.update(step=step, msg="Starting…")
        cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location",
               "--progress-bar", "raw", *args]
        self._log("> pip install " + " ".join(args))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        a, b = weight
        for line in p.stdout:
            line = line.rstrip()
            m = re.match(r"Progress (\d+) of (\d+)", line)
            if m:
                done, total = int(m.group(1)), int(m.group(2)) or 1
                if total > 20e6:                            # (only big files move the bar: torch; small ones would make it jump back)
                    self.st["pct"] = max(self.st["pct"], round((a + (b - a) * done / total) * 100, 1))
                self.st["msg"] = f"{self.st['dl']} · {done / 1e6:.0f} of {total / 1e6:.0f} MB"
                continue
            if not line:
                continue
            m = re.match(r"\s*(Downloading|Collecting|Installing collected packages:)\s*(.*)", line)
            if m:
                what = m.group(2).split("/")[-1].split(" (")[0] if m.group(1) == "Downloading" else m.group(2)
                self.st["dl"] = what[:60]
                self.st["msg"] = f"{m.group(1).replace(' collected packages:', '')} {what[:70]}"
            self._log(line[:300])
        if p.wait() != 0:
            raise RuntimeError(f"pip stopped (exit {p.returncode}). See the log below.")
        self.st["pct"] = round(b * 100, 1)

    def _run(self, variant: str):
        try:
            v = VARIANTS[variant]
            self.st["dl"] = "PyTorch"
            torch_args = [f"torch=={TORCH}", f"torchaudio=={TORCH}"] + (["--index-url", v["index"]] if v["index"] else [])
            self._pip("Downloading PyTorch", torch_args, (0.0, 0.8))
            cons = app_dir() / "constraints.txt"
            cons.write_text(f"torch=={TORCH}\ntorchaudio=={TORCH}\n", encoding="utf-8")
            self._pip("Installing the stem engine", ["-r", str(HERE / "engine-requirements.txt"), "-c", str(cons)], (0.8, 1.0))
            (app_dir() / "engine.json").write_text(json.dumps({"variant": variant, "torch": TORCH, "at": time.time()}), encoding="utf-8")
            self.st.update(done=True, step="Done", msg="The engine is ready", pct=100)
        except Exception as e:  # noqa: BLE001
            self.st.update(error=str(e))
            self._log("ERROR: " + str(e))
        finally:
            self.st["running"] = False
