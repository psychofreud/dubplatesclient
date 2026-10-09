"""Where the stems go. The user chooses one layout (Settings, or the Add window that shows examples from their files):

  next    next to each track:      <track folder>/<Track> Stems/          (works for one folder per track, and for
                                                                            many tracks in one folder)
  mirror  one folder, same tree:   <out>/<sub folders of the track>/<Track> Stems/
  flat    one folder, flat:        <out>/<Track> Stems/

base = the folder the user added (mirror keeps the tree below it); a single file: its own folder.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

AUDIO = (".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".aif", ".aiff", ".opus", ".wma")
MODES = ("next", "mirror", "flat")


def safe_name(s: str) -> str:
    import re
    return re.sub(r'[<>:"/\|?*\x00-\x1f]', "_", s).strip(" .") or "track"


def is_stem_file(f: Path) -> bool:
    """Files the client made (inside '<x> Stems' folders): never stems of stems by accident."""
    return any(p.name.endswith(" Stems") or " Stems (" in p.name for p in f.parents)


def scan(paths: list[str], limit: int = 100000) -> list[tuple[Path, Path]]:
    """(file, base) for every audio file in paths (folders: all sub folders too). Sorted, no stem files."""
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*"), key=lambda x: str(x).lower()):
                if f.suffix.lower() in AUDIO and f.is_file() and not is_stem_file(f.relative_to(p.parent)):
                    out.append((f, p))
                    if len(out) >= limit:
                        return out
        elif p.suffix.lower() in AUDIO and p.is_file():
            out.append((p, p.parent))
    return out


def structure(files: list[tuple[Path, Path]]) -> str:
    """'per-track' (most folders hold one track), 'shared' (many tracks per folder), or 'mixed'."""
    if not files:
        return "shared"
    per = Counter(f.parent for f, _ in files)
    one = sum(1 for n in per.values() if n == 1)
    if one >= 0.8 * len(per) and len(per) > 1:
        return "per-track"
    if one <= 0.2 * len(per):
        return "shared"
    return "mixed"


def stems_dir(cfg, src: Path, base: Path | None) -> Path:
    """The '<Track> Stems' folder for src (without the ' (2)' for a second run)."""
    mode = cfg["outMode"] if cfg["outMode"] in MODES else "next"
    out = Path(cfg["outDir"]) if cfg["outDir"] else None
    if mode == "next" or not out:
        parent = src.parent
    elif mode == "mirror":
        try:
            parent = out / src.parent.relative_to(base or src.parent)
        except ValueError:
            parent = out
    else:
        parent = out
    return parent / f"{safe_name(src.stem)} Stems"


def has_stems(cfg, src: Path, base: Path | None) -> bool:
    d = stems_dir(cfg, src, base)
    return (d / "dubplates.json").exists()
