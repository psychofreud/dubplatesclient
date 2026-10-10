"""Makes a signed plugin package for dubplates.net (run it on the admin's PC; see PLUGINS.md).

  python plugin_pack.py keygen
      Makes the signing key (once): %USERPROFILE%\\.dubplates\\plugin-signing.key (keep it secret, keep a backup).
      Prints the public key: it goes into the client (plugins.TRUST_KEYS).

  python plugin_pack.py pack <plugin folder> [--out <folder>]
      1. Fills in "size" and "sha256" of each model in plugin.json from the files in the folder (the model files
         must be there, with the same names as "file"; each model needs a "url").
      2. Makes <id>-<version>.zip: the plugin without its models, .deps, __pycache__, .venv and audio files.
      3. Signs the zip: <id>-<version>.zip.sig.
      Upload both files on dubplates.net (Settings › Admin › Client plugins).

Needs the package `cryptography` (pip install cryptography).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

KEY = Path(os.environ.get("DUBPLATES_SIGNING_KEY") or Path.home() / ".dubplates" / "plugin-signing.key")
SKIP_DIRS = {".deps", "__pycache__", ".venv", ".git", "venv"}
SKIP_EXT = {".wav", ".flac", ".mp3", ".aif", ".aiff", ".m4a", ".ogg", ".part", ".pyc", ".png", ".log"}


def keygen():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if KEY.exists():
        sys.exit(f"There is a key already: {KEY}\n(Delete it only if you are sure: clients trust the old one.)")
    k = Ed25519PrivateKey.generate()
    KEY.parent.mkdir(parents=True, exist_ok=True)
    KEY.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    print(f"Key saved: {KEY}\nKeep it secret. Make a backup (a USB stick, a password manager).\n")
    print("Public key (send this to put in the client):")
    print(_pub(k))


def _pub(k) -> str:
    from cryptography.hazmat.primitives import serialization
    raw = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def _sha(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        while b := fh.read(1 << 22):
            h.update(b)
    return h.hexdigest()


def pack(folder: Path, out: Path | None):
    from cryptography.hazmat.primitives import serialization
    if not KEY.exists():
        sys.exit("No signing key. Run:  python plugin_pack.py keygen")
    k = serialization.load_pem_private_key(KEY.read_bytes(), password=None)
    mf = folder / "plugin.json"
    m = json.loads(mf.read_text(encoding="utf-8"))
    pid, ver = m.get("id") or folder.name, m.get("version")
    if not ver:
        sys.exit('plugin.json needs a "version" (for example "1.0"). Use a new version for each upload.')
    models = m.get("models") or []
    skip = set()
    for x in models:
        if not str(x.get("url", "")).startswith("https://"):
            sys.exit(f'Model {x.get("file")}: add its download link ("url": "https://...") to plugin.json')
        f = folder / x["file"]
        if f.is_file():
            print(f"  checking {x['file']} ({f.stat().st_size >> 20} MB)...")
            x["size"], x["sha256"] = f.stat().st_size, _sha(f)
        elif not x.get("sha256"):
            sys.exit(f"Model {x['file']}: the file is not in the folder and plugin.json has no sha256 for it")
        skip.add(Path(x["file"]).as_posix())
    m["files"] = [f for f in m.get("files") or [] if Path(f).as_posix() not in skip]
    mf.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out = out or folder.parent / "plugin-packages"
    out.mkdir(parents=True, exist_ok=True)
    z = out / f"{pid}-{ver}.zip"
    n = 0
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(folder.rglob("*")):
            rel = f.relative_to(folder)
            if f.is_dir() or any(p in SKIP_DIRS for p in rel.parts) or f.suffix.lower() in SKIP_EXT or rel.as_posix() in skip:
                continue
            zf.write(f, rel.as_posix())
            n += 1
    sig = base64.b64encode(k.sign(z.read_bytes())).decode()
    (out / (z.name + ".sig")).write_text(sig + "\n", encoding="ascii")
    print(f"\n{n} files -> {z} ({z.stat().st_size >> 10} kB)\nsignature -> {z}.sig\nPublic key of this signature: {_pub(k)}")
    print("Upload both files on dubplates.net: Settings > Admin > Client plugins.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Signed plugin packages for the Dubplates.net Client")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("keygen")
    p = sp.add_parser("pack")
    p.add_argument("folder")
    p.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "keygen":
        keygen()
    else:
        pack(Path(a.folder).resolve(), Path(a.out).resolve() if a.out else None)
