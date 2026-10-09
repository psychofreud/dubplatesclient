"""The models: our suggested list (catalog.json), every model audio-separator knows, and the user's custom models."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent


def suggested() -> list[dict]:
    return json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))["models"]


def file_names(info: dict) -> list[str]:
    """The files on disk for one model (URLs become their last part)."""
    out = []
    for f in info.get("download_files") or [info["filename"]]:
        n = f.rsplit("/", 1)[-1]
        if n not in out:
            out.append(n)
    return out


def build(known: dict, custom: list[dict], model_dir: Path) -> list[dict]:
    """One list for the UI. known = Separator.list_supported_model_files() (may be {} when offline)."""
    flat = {}
    for arch, models in (known or {}).items():
        for name, info in models.items():
            flat[info["filename"]] = (arch, name, info)
    have = {p.name for p in model_dir.iterdir()} if model_dir.exists() else set()
    out, seen = [], set()

    def row(fn, arch, name, info, extra):
        files = file_names(info) if info else [fn]
        r = {"file": fn, "arch": arch, "name": name, "files": files, "installed": all(f in have for f in files),
             "stems": [s.title() for s in (info or {}).get("stems") or []], "sdr": _sdr(info), "vip": "VIP" in name}
        r.update(extra)
        return r

    for m in suggested():
        arch, name, info = flat.get(m["file"], ("MDXC", m["name"], None))
        r = row(m["file"], arch, m["name"], info, {"group": m["group"], "desc": m.get("desc", ""), "suggested": True, "badge": m.get("badge", "")})
        if m.get("stems"):
            r["stems"] = m["stems"]
        r["known"] = info is not None
        out.append(r)
        seen.add(m["file"])
    for c in custom:
        info = {"filename": c["file"], "download_files": [c["file"], c["yaml"]], "stems": c.get("stems") or []}
        out.append(row(c["file"], "MDXC", c["name"], info, {"group": "custom", "desc": c.get("url", ""), "custom": True, "known": True}))
        seen.add(c["file"])
    for fn, (arch, name, info) in sorted(flat.items(), key=lambda x: x[1][1].lower()):
        if fn in seen:
            continue
        out.append(row(fn, arch, _short(name), info, {"group": "all", "desc": "", "known": True}))
    return out


def _sdr(info) -> float | None:
    sc = (info or {}).get("scores") or {}
    v = [s.get("SDR") for s in sc.values() if isinstance(s, dict) and s.get("SDR")]
    return round(max(v), 2) if v else None


def _short(name: str) -> str:
    """'Roformer Model: MelBand Roformer | Vocals by X' -> 'MelBand Roformer | Vocals by X'."""
    return name.split(": ", 1)[1] if ": " in name else name
