#!/usr/bin/env python3
"""Local server for the rain viewers: static files plus a small job API.

    python serve.py [--port 8000]

Open http://localhost:8000/pulse.html. Works as a drop-in for `python -m http.server`;
the extra endpoints let pulse.html build other year ranges from PRISM and process
your own uploaded rasters with rain_engine.py.

    POST /api/prism?start=Y&end=Y            build a PRISM range  -> {job}
    POST /api/upload?job=<id|new>&name=F     body = raw file bytes -> {job}
    POST /api/process                        JSON options          -> {ok}
    GET  /api/job?id=<id>                    {state, pct, msg, dataset?}

Binds to 127.0.0.1 only: uploads go to your own disk, nothing leaves the machine
(except the PRISM download, which is fetched from prism.oregonstate.edu / nacse.org).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import threading
import traceback
import uuid
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import rain_engine as eng

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
MAX_UPLOAD = 2 * 1024**3                      # per file
MAX_FILES = 200
HIDDEN = ("/uploads", "/prism_annual", "/__pycache__")
JOB_ID = re.compile(r"^[0-9a-f]{10}$")

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def job_update(jid: str, **kw) -> None:
    with LOCK:
        JOBS[jid].update(kw)


def run_job(jid: str, fn) -> None:
    def progress(p: float, m: str) -> None:
        job_update(jid, pct=round(p, 3), msg=m)

    def work() -> None:
        try:
            meta = fn(progress)
            job_update(jid, state="done", pct=1.0, msg="Done", dataset=meta["id"])
        except eng.EngineError as e:
            job_update(jid, state="error", msg=str(e))
        except Exception as e:                # unexpected: keep the trace server-side
            traceback.print_exc()
            job_update(jid, state="error", msg=f"Unexpected error: {type(e).__name__}: {e}")

    job_update(jid, state="running")
    threading.Thread(target=work, daemon=True).start()


def clean_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name or "file").name)[:120]
    return name or "file"


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")     # dev server: never serve stale pages
        super().end_headers()

    # --- helpers ---------------------------------------------------------
    def send_json(self, obj: dict, status: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def fail(self, msg: str, status: int = 400) -> None:
        self.send_json({"error": msg}, status)

    def body_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise ValueError("Request too large")
        return json.loads(self.rfile.read(n) or b"{}")

    # --- routing ---------------------------------------------------------
    def do_GET(self) -> None:
        u = urlparse(self.path)
        if u.path.startswith(HIDDEN) or u.path.endswith(".py"):
            return self.send_error(HTTPStatus.NOT_FOUND)
        if u.path == "/api/job":
            jid = (parse_qs(u.query).get("id") or [""])[0]
            with LOCK:
                job = JOBS.get(jid)
                return self.send_json(dict(job) if job else {"error": "Unknown job"}, 200 if job else 404)
        super().do_GET()

    def do_POST(self) -> None:
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/prism":
                return self.api_prism(q)
            if u.path == "/api/upload":
                return self.api_upload(q)
            if u.path == "/api/process":
                return self.api_process()
        except (ValueError, KeyError) as e:
            return self.fail(str(e))
        self.send_error(HTTPStatus.NOT_FOUND)

    # --- endpoints -------------------------------------------------------
    def api_prism(self, q: dict) -> None:
        start, end = int(q["start"]), int(q["end"])
        meta_path = eng.DATA / f"prism-{start}-{end}" / "meta.json"
        jid = uuid.uuid4().hex[:10]
        with LOCK:
            JOBS[jid] = {"state": "queued", "pct": 0.0, "msg": "Queued"}
        if meta_path.exists():                 # already built
            job_update(jid, state="done", pct=1.0, msg="Done", dataset=f"prism-{start}-{end}")
        else:
            run_job(jid, lambda progress: eng.build_prism(start, end, progress))
        self.send_json({"job": jid})

    def api_upload(self, q: dict) -> None:
        jid = q.get("job", "new")
        if jid == "new":
            jid = uuid.uuid4().hex[:10]
            with LOCK:
                JOBS[jid] = {"state": "uploading", "pct": 0.0, "msg": "Uploading", "files": 0}
        elif not JOB_ID.match(jid) or jid not in JOBS:
            return self.fail("Unknown upload job")
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_UPLOAD:
            return self.fail(f"File must be 1 byte to {MAX_UPLOAD // 1024**3} GB")
        if JOBS[jid].get("files", 0) >= MAX_FILES:
            return self.fail(f"At most {MAX_FILES} files per dataset")
        d = UPLOADS / jid
        d.mkdir(parents=True, exist_ok=True)
        dest = d / clean_name(q.get("name", "file"))
        left = n
        with open(dest, "wb") as fh:
            while left:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    return self.fail("Upload was cut short")
                fh.write(chunk)
                left -= len(chunk)
        with LOCK:
            JOBS[jid]["files"] = JOBS[jid].get("files", 0) + 1
        self.send_json({"job": jid})

    def api_process(self) -> None:
        o = self.body_json()
        jid = str(o.get("job", ""))
        if not JOB_ID.match(jid) or jid not in JOBS:
            return self.fail("Unknown upload job")
        d = UPLOADS / jid
        files = sorted(p for p in d.iterdir() if p.is_file()) if d.is_dir() else []
        if not files:
            return self.fail("No files were uploaded")
        label = str(o.get("label") or "My dataset")[:80]
        opts = dict(label=label, unit=str(o.get("unit") or "")[:16], palette=str(o.get("palette") or "viridis"),
                    scale=str(o.get("scale") or "linear"), anomaly=str(o.get("anomaly") or "diff"),
                    clip_outliers=bool(o.get("clip")), credit=str(o.get("credit") or "")[:200])
        start_label = int(o.get("start_label") or 1)
        out_dir = eng.DATA / f"{eng.slug(label)}-{jid[:4]}"

        def fn(progress):
            progress(0.02, "Checking files")
            try:
                rasters = eng.resolve_inputs(files, d)
                sources = eng.label_sources(rasters, start_label)
                return eng.build_dataset(sources, out_dir, progress=progress, **opts)
            finally:                          # the packed dataset is all we keep; drop the raw upload
                shutil.rmtree(d, ignore_errors=True)

        job_update(jid, state="queued", pct=0.0, msg="Queued")
        run_job(jid, fn)
        self.send_json({"ok": True, "job": jid})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    UPLOADS.mkdir(exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(ROOT)))
    print(f"Serving {ROOT} at http://localhost:{args.port}/  (pulse.html, index.html)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        shutil.rmtree(UPLOADS, ignore_errors=True)


if __name__ == "__main__":
    main()
