"""Local bridge for dubplates.net: the site finds the client (ping), sends "make stems" jobs and follows them.

HTTP on 127.0.0.1:47821 (only this computer). Browsers send an Origin header that a page can not fake: only the
dubplates.net site (and local development of it) may use the bridge. Nothing here reads or sends files.

  GET  /v1/ping            {app, version, gpu}
  POST /v1/separate        {root, path}  -> {req}       (root = the site's music folder name, path = the file in it)
  GET  /v1/req/<id>        {state, pct, msg, folder, stems, rel, err}
                           state: asking | needRoot | queued | running | done | error | cancelled
"""
from __future__ import annotations

import itertools
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import VERSION

log = logging.getLogger("dubplates")
PORTS = (47821, 47822, 47823)              # the site tries these in order
ORIGINS = {"https://dubplates.net", "https://www.dubplates.net",
           "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8765", "http://127.0.0.1:8765"}
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
        rid = next(_ids)
        r = {"id": rid, "root": info["root"], "path": info["path"], "name": info["name"], "file": info.get("file", ""),
             "state": "needRoot" if info.get("needRoot") else "asking", "job": None, "err": ""}
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
    reqs = api._site = Requests(api)

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
            if not self._origin():
                return self._send(403, {"error": "Only dubplates.net"})
            if self.path == "/v1/ping":
                d = getattr(api, "_device", None) or {}
                return self._send(200, {"app": "dubplates-client", "version": VERSION, "gpu": d.get("name", "")})
            if self.path.startswith("/v1/req/"):
                try:
                    st = reqs.status(int(self.path.rsplit("/", 1)[1]))
                except ValueError:
                    st = None
                return self._send(200, st) if st else self._send(404, {"error": "Unknown request"})
            self._send(404, {"error": "Not found"})

        def do_POST(self):
            if not self._origin():
                return self._send(403, {"error": "Only dubplates.net"})
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
        log.info("bridge on 127.0.0.1:%s", port)
        return port
    log.warning("bridge: no free port")
    return None
