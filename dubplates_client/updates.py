"""Update check: is there a newer release on GitHub? (Only reads the public release list; sends nothing.)"""
from __future__ import annotations

import re

import requests

from . import VERSION

REPO = "psychofreud/dubplatesclient"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=10"
PAGE = f"https://github.com/{REPO}/releases/"


def _ver(tag: str) -> tuple:
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", tag or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def check() -> dict:
    """{current, latest, newer, url, notes, pre}. url = the release page (the user downloads in the browser)."""
    r = requests.get(API, timeout=10, headers={"Accept": "application/vnd.github+json", "User-Agent": f"DubplatesClient/{VERSION}"})
    r.raise_for_status()
    rels = [x for x in r.json() if not x.get("draft") and _ver(x.get("tag_name", "")) > (0, 0, 0)]
    if not rels:
        return {"current": VERSION, "latest": VERSION, "newer": False}
    best = max(rels, key=lambda x: _ver(x["tag_name"]))
    url = best.get("html_url") or PAGE
    if not url.startswith(PAGE):
        url = PAGE
    return {"current": VERSION, "latest": best["tag_name"].lstrip("v"), "newer": _ver(best["tag_name"]) > _ver(VERSION),
            "url": url, "notes": (best.get("body") or "")[:500], "pre": bool(best.get("prerelease"))}
