"""The user's stem sets: every "<Track> Stems" folder the client made (or the user added). Kept in <app dir>/library.json.
The folder's dubplates.json is the truth (stems, parts, models); the list only remembers where the folders are."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from .config import app_dir


def _id(folder: str) -> str:
    return hashlib.sha1(os.path.normcase(str(Path(folder).resolve())).encode()).hexdigest()[:16]


def read_meta(folder: Path) -> dict | None:
    try:
        m = json.loads((folder / "dubplates.json").read_text(encoding="utf-8"))
        return m if isinstance(m, dict) and isinstance(m.get("stems"), list) else None
    except (OSError, ValueError):
        return None


class Library:
    def __init__(self):
        self.path = app_dir() / "library.json"
        self.lock = threading.Lock()
        try:
            self.items = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.items, list):
                self.items = []
        except (OSError, ValueError):
            self.items = []
            self._seed()

    def _seed(self):
        """First start of the library: the sets made from dubplates.net tracks are already known."""
        d = app_dir() / "From dubplates.net"
        for f in sorted(d.glob("* Stems*")) if d.exists() else []:
            if (f / "dubplates.json").exists():
                self.items.append({"id": _id(str(f)), "folder": str(f), "added": f.stat().st_mtime})
        if self.items:
            self._save()

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(self, folder: str) -> dict:
        f = Path(folder)
        meta = read_meta(f)
        if meta is None:
            raise ValueError("This folder has no dubplates.json (it is not a stem folder made by the client)")
        e = {"id": _id(folder), "folder": str(f), "added": time.time()}
        with self.lock:
            self.items = [x for x in self.items if x["id"] != e["id"]] + [e]
            self._save()
        return e

    def remove(self, lid: str):
        with self.lock:
            self.items = [x for x in self.items if x["id"] != lid]
            self._save()

    def folder(self, lid: str) -> Path | None:
        with self.lock:
            e = next((x for x in self.items if x["id"] == lid), None)
        return Path(e["folder"]) if e else None

    def allowed(self, file: Path) -> bool:
        """May the stem view play this file? Only files in a library set, or a set's source track."""
        try:
            file = file.resolve()
        except OSError:
            return False
        for f in self.folders():
            f = f.resolve()
            if f in file.parents:
                return True
            m = read_meta(f) or {}
            s = m.get("source") or {}
            for c in (s.get("path"), str(f.parent / s.get("name", "")) if s.get("name") else None):
                if c and Path(c).resolve() == file:
                    return True
        return False

    def folders(self) -> list[Path]:
        with self.lock:
            return [Path(x["folder"]) for x in self.items]

    def list(self) -> list[dict]:
        """Newest first. missing = the folder is gone (moved or deleted)."""
        out = []
        with self.lock:
            items = list(self.items)
        for e in items:
            f = Path(e["folder"])
            m = read_meta(f) if f.exists() else None
            src = (m or {}).get("source") or {}
            stems = (m or {}).get("stems") or []
            out.append({"id": e["id"], "folder": e["folder"], "missing": m is None, "added": e["added"],
                        "name": (src.get("name") or f.name).rsplit(".", 1)[0], "created": (m or {}).get("created", ""),
                        "model": ((m or {}).get("model") or {}).get("name", ""), "stems": [s.get("name") for s in stems],
                        "parts": sum(len(s.get("parts") or []) + sum(len(d.get("stems") or []) for d in s.get("derived") or []) for s in stems)})
        return sorted(out, key=lambda x: x["added"], reverse=True)

    def detail(self, lid: str) -> dict:
        """Everything to show one set: the source (when it is still there), stems, parts, results of more work."""
        f = self.folder(lid)
        m = read_meta(f) if f else None
        if not m:
            raise ValueError("The stem folder is not there any more")
        s = m.get("source") or {}
        src = next((str(c) for c in (Path(s["path"]) if s.get("path") else None, f.parent / s.get("name", ""))
                    if c and s.get("name") and c.is_file()), None)
        return {"id": lid, "folder": str(f), "meta": m, "sourceFile": src}
