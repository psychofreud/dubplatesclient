"""User settings, saved on this computer only (never sent anywhere).

Windows: %APPDATA%\\Dubplates Client   macOS: ~/Library/Application Support/Dubplates Client   Linux: ~/.config/dubplates-client
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from pathlib import Path

APP = "Dubplates Client"
FORMATS = ("FLAC", "WAV", "MP3")
DEVICES = ("auto", "gpu", "cpu")
DEFAULT_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"


def app_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        d = base / APP
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / APP
    else:
        d = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "dubplates-client"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULTS = {
    "outMode": "next",          # where stems go (layout.py): next | mirror | flat (mirror and flat use outDir)
    "layoutChosen": False,      # the user chose a layout (else the Add window asks first)
    "skipDone": True,           # skip tracks that have stems already
    "outDir": "",
    "format": "FLAC",
    "mp3Bitrate": "320k",
    "device": "auto",
    "modelDir": "",             # empty = <app dir>/models
    "model": DEFAULT_MODEL,     # the model selected on the Separate page
    "drumSplit": "",            # a drum model: split the Drums stem again (empty = off)
    "overwrite": False,         # False = a second run makes "<Track> Stems (2)"
    "custom": [],               # custom models: [{file, yaml, name, stems, url, yamlUrl, sha256}]
    "trustSite": False,         # True = jobs from dubplates.net start without asking
    "roots": {},                # dubplates.net music folders: {folder name in the browser: full path on this computer}
}


class Config:
    def __init__(self):
        self.path = app_dir() / "config.json"
        self.lock = threading.Lock()
        self.data = dict(DEFAULTS)
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                self.data.update({k: v for k, v in saved.items() if k in DEFAULTS})
                if self.data["outMode"] == "folder":                # (0.1.x: "one folder" = flat)
                    self.data["outMode"] = "flat"
        except (OSError, ValueError):
            pass

    def __getitem__(self, k):
        return self.data[k]

    def public(self) -> dict:
        d = dict(self.data)
        d["modelDirUsed"] = str(self.model_dir())
        d["appDir"] = str(app_dir())
        return d

    def update(self, patch: dict) -> dict:
        """Takes only known keys with valid values."""
        with self.lock:
            for k, v in (patch or {}).items():
                if k == "outMode" and v in ("next", "mirror", "flat"):
                    self.data[k] = v
                elif k in ("outDir", "modelDir") and isinstance(v, str):
                    self.data[k] = v.strip()
                elif k == "format" and v in FORMATS:
                    self.data[k] = v
                elif k == "mp3Bitrate" and v in ("192k", "256k", "320k"):
                    self.data[k] = v
                elif k == "device" and v in DEVICES:
                    self.data[k] = v
                elif k == "model" and isinstance(v, str) and v:
                    self.data[k] = v
                elif k == "drumSplit" and isinstance(v, str):
                    self.data[k] = v
                elif k in ("overwrite", "trustSite", "layoutChosen", "skipDone") and isinstance(v, bool):
                    self.data[k] = v
                elif k == "roots" and isinstance(v, dict):
                    self.data[k] = {str(a)[:200]: str(b) for a, b in v.items()}
                elif k == "custom" and isinstance(v, list):
                    self.data[k] = v
            self.save()
        return self.public()

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def model_dir(self) -> Path:
        d = Path(self.data["modelDir"]) if self.data["modelDir"] else app_dir() / "models"
        d.mkdir(parents=True, exist_ok=True)
        return d


def ensure_ffmpeg():
    """audio-separator needs `ffmpeg` on PATH. Use the one on this computer, else the bundled one (imageio-ffmpeg)."""
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
        src = Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:  # noqa: BLE001
        return
    bin_dir = app_dir() / "bin"
    bin_dir.mkdir(exist_ok=True)
    dst = bin_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
        if sys.platform != "win32":
            dst.chmod(0o755)
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
