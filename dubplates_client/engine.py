"""The stem engine: audio-separator with progress, cancel, safe downloads and custom models."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path

import requests
import yaml

from . import VERSION, catalog
from .config import Config, app_dir

log = logging.getLogger("dubplates")
_local = threading.local()            # per thread: progress callback + cancel flag
CUSTOM_EXT = (".ckpt", ".pth", ".safetensors")
STEM_NAMES = {"hh": "Hi-Hat", "noreverb": "No Reverb", "no reverb": "No Reverb"}   # nicer file names


class Cancelled(BaseException):
    """(BaseException: the `except Exception` blocks inside audio-separator do not catch it)"""


def _check_cancel():
    ev = getattr(_local, "cancel", None)
    if ev is not None and ev.is_set():
        raise Cancelled()


def _report(frac: float, msg: str | None = None):
    _check_cancel()
    cb = getattr(_local, "cb", None)
    if cb:
        cb(max(0.0, min(1.0, frac)), msg)


def bind(cb=None, cancel: threading.Event | None = None):
    """Send progress of work done in this thread to cb(frac, msg); stop it when cancel is set."""
    _local.cb, _local.cancel = cb, cancel


class Bar:
    """Takes the place of tqdm inside audio-separator: gives progress to the UI, stops on cancel."""

    def __init__(self, iterable=None, total=None, *a, **k):
        self.it = iterable
        self.total = total if total is not None else (len(iterable) if hasattr(iterable, "__len__") else None)
        self.n = 0

    def __iter__(self):
        for x in self.it:
            yield x
            self.update(1)

    def update(self, n=1):
        self.n += n
        if self.total:
            _report(self.n / self.total)
        else:
            _check_cancel()

    def close(self):
        pass

    def set_description(self, *a, **k):
        pass

    set_postfix = refresh = set_description

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_progress():
    import importlib
    for name in ("separator.separator", "separator.architectures.mdxc_separator", "separator.architectures.mdx_separator",
                 "separator.architectures.vr_separator"):
        try:
            importlib.import_module("audio_separator." + name).tqdm = Bar
        except Exception:  # noqa: BLE001
            pass


from audio_separator.separator import Separator  # noqa: E402

_patch_progress()


class Sep(Separator):
    """Separator with: downloads to a .part file (a stopped download never looks installed), and custom models."""
    custom: dict = {}

    def download_file_if_not_exists(self, url, output_path):
        if os.path.isfile(output_path):
            return
        name = os.path.basename(output_path)
        tmp = output_path + ".part"
        with requests.get(url, stream=True, timeout=60) as r:
            if r.status_code != 200:
                raise RuntimeError(f"Failed to download file from {url}, response code: {r.status_code}")
            total, done, t0 = int(r.headers.get("content-length") or 0), 0, 0.0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if time.monotonic() - t0 > 0.2:
                        t0 = time.monotonic()
                        _report(done / total if total else 0, f"Downloading {name} · {done / 1e6:.0f} MB" + (f" of {total / 1e6:.0f} MB" if total else ""))
        os.replace(tmp, output_path)

    def download_model_files(self, model_filename):
        c = self.custom.get(model_filename)
        if c:
            return model_filename, "MDXC", c["name"], os.path.join(self.model_file_dir, model_filename), c["yaml"]
        return super().download_model_files(model_filename)


def device_info() -> dict:
    import torch
    if torch.cuda.is_available():
        return {"kind": "cuda", "name": torch.cuda.get_device_name(0), "memGB": round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1)}
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return {"kind": "mps", "name": "Apple GPU (Metal)"}
    return {"kind": "cpu", "name": "CPU only (slow)"}


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def safe_name(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip(" .") or "track"


class Engine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.Lock()          # one separation at a time
        self._sep = None
        self._sep_key = None
        self._known = None
        self.work = app_dir() / "work"

    # ---------- models ----------
    def known(self, refresh: bool = False) -> dict:
        """Every model audio-separator knows. The list file is cached in the model folder; refresh gets it again."""
        md = self.cfg.model_dir()
        if refresh:
            (md / "download_checks.json").unlink(missing_ok=True)
            self._known = None
        if self._known is None:
            try:
                self._known = Sep(info_only=True, log_level=logging.WARNING, model_file_dir=str(md)).list_supported_model_files()
            except Exception as e:  # noqa: BLE001  (offline: only the suggested and custom models)
                log.warning("model list: %s", e)
                return {}
        return self._known

    def models(self, refresh: bool = False) -> list[dict]:
        return catalog.build(self.known(refresh), self.cfg["custom"], self.cfg.model_dir())

    def _custom_map(self) -> dict:
        return {c["file"]: c for c in self.cfg["custom"]}

    def install(self, model_file: str):
        """Downloads the files of one model (runs in a worker thread; progress via bind())."""
        if model_file in self._custom_map():
            raise ValueError("Custom models are added with “Add model”")
        s = Sep(info_only=True, log_level=logging.WARNING, model_file_dir=str(self.cfg.model_dir()))
        s.download_model_files(model_file)

    def remove(self, model_file: str):
        rows = self.models()
        me = next((r for r in rows if r["file"] == model_file), None)
        if not me:
            raise ValueError("Unknown model")
        shared = {f for r in rows if r["installed"] and r["file"] != model_file for f in r["files"]}
        md = self.cfg.model_dir()
        for f in me["files"]:
            if f not in shared:
                (md / f).unlink(missing_ok=True)
        if me.get("custom"):
            self.cfg.update({"custom": [c for c in self.cfg["custom"] if c["file"] != model_file]})
        if self._sep_key and self._sep is not None and self._sep._loaded_model_filename == model_file:
            self._sep = None

    def add_custom(self, name: str, model: str, config: str, sha256: str = ""):
        """A custom Roformer / MDX23C model: model file (.ckpt/.pth/.safetensors) + its .yaml config.
        model and config are https URLs or files on this computer. The model is loaded in safe mode (weights only)."""
        name = (name or "").strip()[:80]
        if not name:
            raise ValueError("Give the model a name")
        md = self.cfg.model_dir()
        known_files = {f for r in self.models() for f in r["files"]}

        def fetch(src: str, exts: tuple, what: str) -> str:
            src = (src or "").strip()
            base = safe_name(src.split("?")[0].replace("\\", "/").rsplit("/", 1)[-1])
            if not base.lower().endswith(exts):
                raise ValueError(f"The {what} must be a {' / '.join(exts)} file")
            fn = "custom_" + base
            if fn in known_files:
                raise ValueError(f"{fn} is already in the list")
            dst = md / fn
            if src.lower().startswith("https://"):
                Sep.download_file_if_not_exists(_Dl(), src, str(dst))
            elif src.lower().startswith("http://"):
                raise ValueError("Use an https:// link")
            elif Path(src).is_file():
                shutil.copyfile(src, dst)
            else:
                raise ValueError(f"{what.capitalize()} not found: {src}")
            return fn

        cfg_file = fetch(config, (".yaml", ".yml"), "config")
        try:
            data = yaml.safe_load((md / cfg_file).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "model" not in data:
                raise ValueError
        except Exception:  # noqa: BLE001
            (md / cfg_file).unlink(missing_ok=True)
            raise ValueError("The config is not a valid model .yaml (no “model:” section)")
        model_file = fetch(model, CUSTOM_EXT, "model file")
        if sha256 and file_sha256(md / model_file) != sha256.strip().lower():
            (md / model_file).unlink(missing_ok=True)
            (md / cfg_file).unlink(missing_ok=True)
            raise ValueError("The SHA-256 of the file does not match: file removed")
        tr = data.get("training") or {}
        stems = [str(s).title() for s in (tr.get("instruments") or [])]
        entry = {"file": model_file, "yaml": cfg_file, "name": name, "stems": stems,
                 "url": model if "://" in model else "", "yamlUrl": config if "://" in config else ""}
        self.cfg.update({"custom": [c for c in self.cfg["custom"] if c["file"] != model_file] + [entry]})
        return entry

    # ---------- separation ----------
    def _separator(self) -> Sep:
        c = self.cfg
        fmt = c["format"]
        key = (str(c.model_dir()), fmt, c["mp3Bitrate"], c["device"])
        if self._sep is None or self._sep_key != key:
            self.work.mkdir(parents=True, exist_ok=True)
            s = Sep(log_level=logging.WARNING, model_file_dir=str(c.model_dir()), output_dir=str(self.work), output_format=fmt,
                    output_bitrate=c["mp3Bitrate"] if fmt == "MP3" else None, use_soundfile=fmt in ("WAV", "FLAC"))
            if c["device"] == "cpu":
                s.torch_device = s.torch_device_cpu
                s.onnx_execution_provider = ["CPUExecutionProvider"]
            self._sep, self._sep_key = s, key
        Sep.custom = self._custom_map()
        return self._sep

    def out_folder(self, src: Path) -> Path:
        base = Path(self.cfg["outDir"]) if self.cfg["outMode"] == "folder" and self.cfg["outDir"] else src.parent
        folder = base / f"{safe_name(src.stem)} Stems"
        if self.cfg["overwrite"] or not folder.exists():
            return folder
        n = 2
        while (base / f"{safe_name(src.stem)} Stems ({n})").exists():
            n += 1
        return base / f"{safe_name(src.stem)} Stems ({n})"

    def _split(self, src: Path, model_file: str, folder: Path, prefix: str, root: Path) -> list[dict]:
        """One model on one file: the stems go to folder as '<prefix> - <Stem>.<ext>'."""
        with self.lock:
            _report(0, "Loading the model…")
            s = self._separator()
            s.load_model(model_file)
            shutil.rmtree(self.work, ignore_errors=True)
            self.work.mkdir(parents=True, exist_ok=True)
            s.output_dir = str(self.work)
            if s.model_instance is not None:
                s.model_instance.output_dir = str(self.work)
            _report(0, "Making stems…")
            files = s.separate(str(src))
        _check_cancel()
        folder.mkdir(parents=True, exist_ok=True)
        stems = []
        for f in files:
            p = Path(f) if os.path.isabs(f) else self.work / f
            m = re.findall(r"_\(([^)]+)\)", p.stem)
            stem = (m[-1] if m else p.stem).replace("_", " ").title()
            stem = STEM_NAMES.get(stem.lower(), stem)
            dst = folder / f"{prefix} - {stem}{p.suffix.lower()}"
            shutil.move(str(p), dst)
            stems.append({"name": stem, "file": dst.relative_to(root).as_posix()})
        return stems

    def run(self, src: Path, steps: list[dict]) -> dict:
        """A chain of steps on one track. steps[0] = {model, name}: makes the stems of the track.
        Later steps = {model, name, on: "Drums"}: split that stem again; its parts go in '<Stem> parts/'
        and are listed under that stem ("parts") in dubplates.json. Progress via bind(), spread over the steps.
        Returns {folder, stems}."""
        outer = getattr(_local, "cb", None)
        n = len(steps)

        def scoped(i, label):
            def cb(frac, msg):
                if outer:
                    outer((i + frac) / n, f"{label}: {msg}" if msg and n > 1 else msg)
            return cb

        folder = self.out_folder(src)
        track = safe_name(src.stem)
        _local.cb = scoped(0, steps[0]["name"])
        try:
            stems = self._split(src, steps[0]["model"], folder, track, folder)
            done = [{"model": steps[0]["model"], "name": steps[0]["name"]}]
            for i, st in enumerate(steps[1:], 1):
                tgt = next((s for s in stems if s["name"].lower() == st["on"].lower()), None)
                if not tgt:
                    continue                        # (this model made no such stem)
                _local.cb = scoped(i, f"{st['on']} → {st['name']}")
                tgt["parts"] = self._split(folder / tgt["file"], st["model"], folder / f"{tgt['name']} parts", f"{track} - {tgt['name']}", folder)
                done.append({"model": st["model"], "name": st["name"], "on": tgt["name"]})
        finally:
            _local.cb = outer
        meta = {"app": "Dubplates.net Client", "version": VERSION, "schema": 1, "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "source": {"name": src.name, "size": src.stat().st_size, "sha256": file_sha256(src)},
                "model": done[0], "steps": done, "format": self.cfg["format"], "stems": stems}
        (folder / "dubplates.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return {"folder": str(folder), "stems": stems}


class _Dl:
    """Lets add_custom() use Sep.download_file_if_not_exists without a Separator."""
