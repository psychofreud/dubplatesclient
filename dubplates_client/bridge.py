"""Local bridge for dubplates.net: the site finds the client (ping), sends "make stems" jobs and follows them.

HTTP on 127.0.0.1:47821 (only this computer). Browsers send an Origin header that a page can not fake: only the
dubplates.net site (and local development of it) may use the bridge. Nothing here reads or sends files.

  GET  /v1/ping            {app, version, gpu}
  POST /v1/separate        {root, path}  -> {req}       (root = the site's music folder name, path = the file in it)
  POST /v1/upload?name=<file name>   body = the audio   -> {req}   (a track that is not in a music folder: dropped
                           into the site, or from the site's library. Saved in <app dir>/From dubplates.net)
  GET  /v1/req/<id>        {state, pct, msg, folder, stems, rel, err}
  GET  /v1/req/<id>/stem/<n>  the audio of stem n (when done): the site loads it into the deck
  GET  /v1/inbox?user=     stem sets the user sent from the client to a deck: [{id, deck, title, stems}] (each once).
                           A signed-in mixer asks every 2 s; so the client knows that the site is open.
  GET  /v1/send/<id>/stem/<n>  the audio of stem n of a sent set
                           state: asking | needRoot | queued | running | done | error | cancelled
"""
from __future__ import annotations

import itertools
import json
import logging
import mimetypes
import threading
from urllib.parse import parse_qs, urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import VERSION

log = logging.getLogger("dubplates")
PORTS = (47821, 47822, 47823)              # the site tries these in order
ORIGINS = {"https://dubplates.net", "https://www.dubplates.net",
           "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8765", "http://127.0.0.1:8765"}
MAX_UPLOAD = 1 << 30                       # 1 GB
_ids = itertools.count(1)


class Requests:
    """Jobs the site asked for. The window may ask the user first (see Api.site_* and LinkAsk.jsx)."""

    def __init__(self, api):
        self.api = api
        self.lock = threading.Lock()
        self.items: dict[int, dict] = {}

    def new(self, root: str, path: str) -> dict:
        info = self.api._link_info(root, path)
        if info.get("action") == "error":
            raise ValueError(info["error"])
        return self._add({"root": info["root"], "path": info["path"], "name": info["name"], "file": info.get("file", ""),
                          "state": "needRoot" if info.get("needRoot") else "asking"})

    def new_file(self, file: Path) -> dict:
        """A track the site sent (upload): it is already on this computer."""
        return self._add({"root": "", "path": "", "name": file.name, "file": str(file), "state": "asking"})

    def _add(self, r: dict) -> dict:
        rid = next(_ids)
        r.update(id=rid, job=None, err="")
        with self.lock:
            self.items[rid] = r
        if r["state"] == "asking" and self.api._cfg["trustSite"]:
            self.accept(rid)
        else:
            self.api._ask_site(rid)                     # the window comes to the front and asks
        return r

    def get(self, rid: int) -> dict | None:
        with self.lock:
            return self.items.get(rid)

    def accept(self, rid: int, file: str | None = None):
        r = self.get(rid)
        if not r:
            raise ValueError("Unknown request")
        if file:
            r["file"] = file
        out = self.api._start_job(r["file"])
        r.update(state="queued", job=out["job"])

    def cancel(self, rid: int):
        r = self.get(rid)
        if r and r["state"] in ("asking", "needRoot"):
            r["state"] = "cancelled"

    def stem_file(self, rid: int, n: int) -> Path | None:
        r = self.get(rid)
        j = r and r["job"] and self.api._job(r["job"])
        if not j or j["state"] != "done" or not 0 <= n < len(j["stems"]):
            return None
        f = (Path(j["folder"]) / j["stems"][n]["file"]).resolve()
        return f if f.is_file() and Path(j["folder"]).resolve() in f.parents else None

    def status(self, rid: int) -> dict | None:
        r = self.get(rid)
        if not r:
            return None
        out = {"state": r["state"], "name": r["name"], "path": r["path"], "err": r["err"]}
        if r["job"]:
            j = self.api._job(r["job"])
            if j:
                out.update(state=j["state"], pct=j["pct"], msg=j["msg"], err=j.get("err", ""), stems=j["stems"], folder=j["folder"])
                # the Stems folder inside the site's music folder: the site loads it from there
                base = self.api._cfg["roots"].get(r["root"])
                if j["folder"] and base:
                    try:
                        out["rel"] = Path(j["folder"]).resolve().relative_to(Path(base).resolve()).as_posix()
                    except ValueError:
                        out["rel"] = ""            # (stems go to a folder outside the music folder: Settings › Output)
        return out


def serve(api) -> int | None:
    import secrets
    reqs = api._site = Requests(api)
    media_token = secrets.token_urlsafe(18)          # (only the client's window knows it)

    class H(BaseHTTPRequestHandler):
        server_version = "DubplatesClient"

        def log_message(self, *a):
            pass

        def _origin(self) -> str | None:
            o = self.headers.get("Origin")
            return o if o in ORIGINS else None

        def _send(self, code: int, body: dict | None = None):
            o = self._origin()
            data = json.dumps(body or {}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if o:
                self.send_header("Access-Control-Allow-Origin", o)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(data)

        def _file(self, f: Path, origin: str | None = None):
            """The file, or the part that a Range header asks for (the <audio> player jumps with it)."""
            size = f.stat().st_size
            a, b = 0, size - 1
            rng = self.headers.get("Range", "")
            part = rng.startswith("bytes=") and "," not in rng
            if part:
                x, _, y = rng[6:].partition("-")
                try:
                    if x:
                        a, b = int(x), (min(int(y), size - 1) if y else size - 1)
                    else:
                        a = max(0, size - int(y))
                except ValueError:
                    part, a, b = False, 0, size - 1
                if part and (a > b or a >= size):
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
            self.send_response(206 if part else 200)
            self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(b - a + 1))
            self.send_header("Accept-Ranges", "bytes")
            if part:
                self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", origin or self._origin())
            self.send_header("Vary", "Origin")
            self.end_headers()
            left = b - a + 1
            try:
                with open(f, "rb") as fh:
                    fh.seek(a)
                    while left > 0 and (chunk := fh.read(min(left, 1 << 20))):
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except OSError:
                pass                                     # (the player stopped this request: normal when it jumps)

        def do_OPTIONS(self):                            # CORS preflight (+ Chrome's local network access)
            if not self._origin():
                self.send_response(403)
                self.end_headers()
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self._origin())
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
            self.end_headers()

        def do_GET(self):
            u = urlsplit(self.path)
            if u.path == f"/media/{media_token}":             # the client's own window: play stem files (Library)
                f = Path((parse_qs(u.query).get("f") or [""])[0])
                if not f.is_file() or not api._lib.allowed(f):
                    self.send_response(404)
                    self.end_headers()
                    return
                return self._file(f, "*")
            if not self._origin():
                return self._send(403, {"error": "Only dubplates.net"})
            if self.path == "/v1/ping":
                d = getattr(api, "_device", None) or {}
                return self._send(200, {"app": "dubplates-client", "version": VERSION, "gpu": d.get("name", "")})
            if u.path == "/v1/inbox":
                return self._send(200, {"items": api._inbox((parse_qs(u.query).get("user") or [""])[0])})
            m = self.path.split("/")
            if len(m) == 6 and m[1:3] == ["v1", "send"] and m[4] == "stem":
                try:
                    f = api._send_file(int(m[3]), int(m[5]))
                except ValueError:
                    f = None
                return self._file(f) if f else self._send(404, {"error": "No such stem"})
            if len(m) == 6 and m[1:3] == ["v1", "req"] and m[4] == "stem":
                try:
                    f = reqs.stem_file(int(m[3]), int(m[5]))
                except ValueError:
                    f = None
                if not f:
                    return self._send(404, {"error": "No such stem"})
                return self._file(f)
            if self.path.startswith("/v1/req/"):
                try:
                    st = reqs.status(int(self.path.rsplit("/", 1)[1]))
                except ValueError:
                    st = None
                return self._send(200, st) if st else self._send(404, {"error": "Unknown request"})
            self._send(404, {"error": "Not found"})

        def _save_upload(self, name: str) -> Path:
            from .config import app_dir
            from .engine import safe_name
            from .jobs import AUDIO
            name = safe_name(Path(name.replace("\\", "/")).name)[:150]
            if Path(name).suffix.lower() not in AUDIO:
                raise ValueError("Send an audio file (WAV, FLAC, MP3, M4A, OGG, AIFF)")
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= MAX_UPLOAD:
                raise ValueError("The file is empty or bigger than 1 GB")
            d = app_dir() / "From dubplates.net"
            d.mkdir(exist_ok=True)
            f, k = d / name, 2
            while f.exists():
                f, k = d / f"{Path(name).stem} ({k}){Path(name).suffix}", k + 1
            tmp = f.with_name(f.name + ".part")
            left = n
            with open(tmp, "wb") as fh:
                while left > 0:
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    fh.write(chunk)
                    left -= len(chunk)
            if left:
                tmp.unlink(missing_ok=True)
                raise ValueError("The upload stopped")
            tmp.replace(f)
            return f

        def do_POST(self):
            if not self._origin():
                return self._send(403, {"error": "Only dubplates.net"})
            u = urlsplit(self.path)
            if u.path == "/v1/upload":
                try:
                    f = self._save_upload((parse_qs(u.query).get("name") or [""])[0])
                    r = reqs.new_file(f)
                    return self._send(200, {"req": r["id"], "state": r["state"]})
                except Exception as e:  # noqa: BLE001
                    return self._send(400, {"error": str(e)})
            if self.path != "/v1/separate":
                return self._send(404, {"error": "Not found"})
            try:
                n = min(int(self.headers.get("Content-Length") or 0), 10000)
                body = json.loads(self.rfile.read(n) or b"{}")
                r = reqs.new(str(body.get("root", "")), str(body.get("path", "")))
                self._send(200, {"req": r["id"], "state": r["state"]})
            except Exception as e:  # noqa: BLE001
                self._send(400, {"error": str(e)})

    for port in PORTS:
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), H)
        except OSError:
            continue
        threading.Thread(target=srv.serve_forever, daemon=True, name="bridge").start()
        api._media = f"http://127.0.0.1:{port}/media/{media_token}?f="
        log.info("bridge on 127.0.0.1:%s", port)
        return port
    log.warning("bridge: no free port")
    return None
