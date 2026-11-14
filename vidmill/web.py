"""Tool: serve — local web UI on top of the job model.

  vmill serve                 # http://127.0.0.1:8765
  vmill serve --port 9000 --open
  vmill serve --check         # self-test (used by CI)

No framework, no npm, no extra dependencies: one stdlib HTTP server plus
an embedded single-page UI. The page uploads a video (raw PUT, streamed
to disk), creates a job, runs the automatic edit as a real `vmill auto`
subprocess, streams its log, and plays the finished MP4. Jobs live under
--dir (default ~/vmill-jobs). Binds loopback by default.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import job as jobmod
from . import util

PURPOSE = "local web UI: upload, run the automatic edit, watch, download"

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".MP4", ".MOV", ".MKV"}
VIDEO_ARTIFACTS = ("final.mp4", "swapped.mp4", "captioned.mp4", "cleaned.mp4", "cut.mp4")

RUNS: dict[str, dict] = {}
RUNS_LOCK = threading.Lock()
ROOT: Path = Path.home() / "vmill-jobs"


# ------------------------------------------------------------------ jobs

def _safe_name(name: str) -> str:
    name = (name or "").strip()
    if not NAME_RE.match(name):
        raise ValueError("job name must be letters, digits, dot, dash or underscore (max 64)")
    return name


def _job_dir(name: str) -> Path:
    name = _safe_name(name)
    path = (ROOT / name).resolve()
    if path.parent != ROOT.resolve():
        raise ValueError("job escapes the workspace")
    return path


def _unique_job(name: str) -> str:
    base = _safe_name(name)
    candidate, n = base, 2
    while _job_dir(candidate).exists():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _video_artifacts(j: jobmod.Job) -> list[dict]:
    out = []
    for name, meta in j.data.get("artifacts", {}).items():
        if not name.endswith(".mp4"):
            continue
        p = j.apath(name)
        if not p.exists():
            continue
        m = meta.get("meta") or {}
        out.append({"name": name, "bytes": p.stat().st_size,
                    "duration": m.get("duration"), "created": meta.get("created")})
    return out


def _status(name: str) -> dict:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    j = jobmod.Job.load(jdir)
    info = j.data.get("info", {})
    arts = _video_artifacts(j)
    video = next((n for n in VIDEO_ARTIFACTS if any(a["name"] == n for a in arts)), None)
    if video is None and arts:
        video = max(arts, key=lambda a: a.get("created") or "")["name"]
    with RUNS_LOCK:
        run = RUNS.get(name)
        running = bool(run and run["proc"].poll() is None)
        if run and not running and not run.get("closed"):
            try:
                run["fh"].close()
            except Exception:
                pass
            run["closed"] = True
    return {
        "name": name,
        "source": Path(j.data.get("video", "")).name,
        "created": j.data.get("created"),
        "width": info.get("width"), "height": info.get("height"),
        "duration": info.get("duration"), "size_bytes": info.get("size_bytes"),
        "artifacts": arts, "video": video, "running": running,
        "finished": bool(video == "final.mp4"),
    }


def _list_jobs() -> list[dict]:
    jobs = []
    if ROOT.exists():
        for d in sorted(ROOT.iterdir(), reverse=True):
            if d.is_dir() and (d / "job.json").exists():
                try:
                    s = _status(d.name)
                    jobs.append({k: s[k] for k in
                                 ("name", "created", "duration", "video", "running", "finished")})
                except Exception:
                    continue
    return jobs[:100]


def _log_tail(name: str, limit: int = 40000) -> str:
    f = _job_dir(name) / ".run.log"
    if not f.exists():
        return ""
    data = f.read_bytes()
    return data[-limit:].decode("utf-8", "replace")


def _start_run(name: str, opts: dict) -> None:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    with RUNS_LOCK:
        run = RUNS.get(name)
        if run and run["proc"].poll() is None:
            raise RuntimeError("already running")
        argv = [sys.executable, "-m", "vidmill", "auto", "--job", str(jdir)]
        if opts.get("mistakes"):
            argv.append("--mistakes")
        if not opts.get("ai"):
            argv.append("--no-ai")
        if not opts.get("captions", True):
            argv.append("--no-captions")
        if not opts.get("clean", True):
            argv.append("--no-clean")
        log = jdir / ".run.log"
        fh = open(log, "wb")
        proc = subprocess.Popen(argv, stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)
        RUNS[name] = {"proc": proc, "log": log, "fh": fh, "closed": False}


def _cancel_run(name: str) -> bool:
    with RUNS_LOCK:
        run = RUNS.get(name)
        if not run or run["proc"].poll() is not None:
            return False
        run["proc"].terminate()
        return True


def _create_from_path(name: str, video_path: str) -> str:
    src = Path(os.path.expanduser(video_path))
    if not src.exists() or src.suffix not in VIDEO_EXT:
        raise ValueError("not a video file on this machine")
    name = _unique_job(name or src.stem)
    jdir = _job_dir(name)
    jdir.mkdir(parents=True, exist_ok=True)
    jobmod.Job.create(jdir, src, copy=False)
    return name


def _receive_upload(name: str, filename: str, rfile, length: int) -> str:
    filename = Path(filename or "upload.mp4").name
    if Path(filename).suffix not in VIDEO_EXT:
        raise ValueError(f"unsupported video extension: {Path(filename).suffix or '(none)'}")
    name = _unique_job(name or Path(filename).stem)
    jdir = _job_dir(name)
    jdir.mkdir(parents=True, exist_ok=True)
    dest = jdir / filename
    got = 0
    with open(dest, "wb") as f:
        while got < length:
            chunk = rfile.read(min(1024 * 1024, length - got))
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
    if got != length:
        dest.unlink(missing_ok=True)
        raise ValueError("upload interrupted")
    jobmod.Job.create(jdir, dest, copy=False)
    return name


# -------------------------------------------------------------------- html

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vidmill — automatic video editing</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--line:#262b36;--fg:#e8ebf1;--dim:#8b93a7;--acc:#5b8cff;--ok:#3ecf8e;--warn:#f2b84b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:22px 28px;border-bottom:1px solid var(--line);display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
h1{margin:0;font-size:22px;letter-spacing:.4px}
h2{margin:0 0 14px;font-size:15px;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim)}
.sub{color:var(--dim)}
main{max-width:1000px;margin:0 auto;padding:22px 18px 60px;display:grid;gap:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}
.hidden{display:none}
#drop{border:2px dashed var(--line);border-radius:12px;padding:34px;text-align:center;color:var(--dim);transition:.2s}
#drop.hot{border-color:var(--acc);color:var(--fg);background:#141a2b}
.btn{display:inline-block;padding:9px 16px;border-radius:9px;border:1px solid var(--line);background:#1d222c;color:var(--fg);cursor:pointer;text-decoration:none;font-size:14px}
.btn:hover{border-color:var(--acc)}
.btn.primary{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.btn:disabled{opacity:.45;cursor:not-allowed}
.row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
input[type=text]{flex:1;min-width:220px;padding:9px 12px;border-radius:9px;border:1px solid var(--line);background:#12151b;color:var(--fg)}
.checks{display:flex;gap:18px;flex-wrap:wrap;margin-top:14px;color:var(--dim);font-size:14px}
.checks label{display:flex;gap:7px;align-items:center;cursor:pointer}
.msg{margin-top:12px;color:var(--warn);min-height:20px;font-size:14px}
.jobs{display:grid;gap:10px}
.job{display:flex;justify-content:space-between;gap:12px;padding:12px 14px;border:1px solid var(--line);border-radius:10px;cursor:pointer;align-items:center}
.job:hover{border-color:var(--acc)}
.job .meta{color:var(--dim);font-size:13px}
.pill{font-size:12px;padding:2px 9px;border-radius:99px;border:1px solid var(--line);color:var(--dim)}
.pill.run{color:var(--warn);border-color:var(--warn)}
.pill.done{color:var(--ok);border-color:var(--ok)}
video{width:100%;max-height:70vh;border-radius:10px;background:#000;margin-top:14px}
.log{background:#0b0d11;border:1px solid var(--line);border-radius:10px;padding:14px;max-height:340px;overflow:auto;font:12.5px/1.45 ui-monospace,Menlo,Consolas,monospace;color:#c9d3e6;white-space:pre-wrap;margin-top:14px}
.arts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.arts a{font-size:13px}
.dhead{display:flex;justify-content:space-between;align-items:center;gap:10px}
</style></head>
<body>
<header><h1>vidmill</h1><span class="sub">upload it, walk away, come back to a finished edit</span></header>
<main>
<section class="card" id="newcard">
  <h2>New edit</h2>
  <div id="drop">Drop a video here, or <label class="btn" style="margin-left:6px">browse<input type="file" id="file" accept="video/*" hidden></label>
    <div id="picked" class="meta" style="margin-top:8px;color:var(--dim)"></div></div>
  <div class="row">
    <input type="text" id="path" placeholder="…or an absolute path on this machine">
    <input type="text" id="jobname" placeholder="job name (optional)">
  </div>
  <div class="checks">
    <label><input type="checkbox" id="mistakes"> remove mistakes</label>
    <label><input type="checkbox" id="captions" checked> captions</label>
    <label><input type="checkbox" id="clean" checked> clean audio</label>
    <label><input type="checkbox" id="ai"> AI checkpoint (needs API key)</label>
  </div>
  <div class="row"><button class="btn primary" id="go" disabled>Start edit</button></div>
  <div class="msg" id="msg"></div>
</section>
<section class="card"><h2>Jobs</h2><div class="jobs" id="list"></div></section>
<section class="card hidden" id="detail">
  <div class="dhead"><h2 id="dtitle"></h2><span class="pill" id="dstate"></span></div>
  <div class="row">
    <button class="btn primary" id="run">Run automatic edit</button>
    <button class="btn" id="cancel">Cancel</button>
    <a class="btn" id="dl" download>Download</a>
  </div>
  <video id="player" controls playsinline></video>
  <div class="arts" id="arts"></div>
  <pre class="log" id="log"></pre>
</section>
</main>
<script>
var current=null, fileObj=null, timer=null;
function $(s){return document.querySelector(s)}
function fmt(n){if(n==null)return "?";var m=Math.floor(n/60),s=Math.round(n%60);return m+":"+(s<10?"0":"")+s}
function flag(id){return $("#"+id).checked}
function opts(){return {mistakes:flag("mistakes"),captions:flag("captions"),clean:flag("clean"),ai:flag("ai")}}
function setMsg(t){$("#msg").textContent=t||""}
function picked(f){fileObj=f;var p=$("#picked");p.textContent=f?(f.name+"  "+(f.size/1048576).toFixed(1)+" MB"):"";$("#go").disabled=!(f||$("#path").value.trim())}
$("#file").addEventListener("change",function(e){picked(e.target.files[0]||null)});
$("#path").addEventListener("input",function(){picked(fileObj)});
$("#drop").addEventListener("dragover",function(e){e.preventDefault();$("#drop").classList.add("hot")});
$("#drop").addEventListener("dragleave",function(){$("#drop").classList.remove("hot")});
$("#drop").addEventListener("drop",function(e){e.preventDefault();$("#drop").classList.remove("hot");picked(e.dataTransfer.files[0]||null)});
$("#go").onclick=async function(){
  var o=opts(), name=$("#jobname").value.trim(), path=$("#path").value.trim();
  setMsg("");$("#go").disabled=true;
  try{
    var job;
    if(fileObj && !path){
      setMsg("uploading…");
      var q=new URLSearchParams({filename:fileObj.name}); if(name)q.set("name",name);
      var r=await fetch("/api/upload?"+q,{method:"PUT",body:fileObj});
      var d=await r.json(); if(!r.ok)throw new Error(d.error||"upload failed");
      job=d.name;
    }else{
      var r=await fetch("/api/jobs",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name:name||undefined,path:path})});
      var d=await r.json(); if(!r.ok)throw new Error(d.error||"could not open video");
      job=d.name;
    }
    setMsg("starting edit…");
    var rr=await fetch("/api/jobs/"+encodeURIComponent(job)+"/run",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(o)});
    var dd=await rr.json(); if(!rr.ok)throw new Error(dd.error||"could not start");
    fileObj=null;$("#picked").textContent="";$("#path").value="";$("#jobname").value="";
    openJob(job); refreshJobs();
  }catch(err){setMsg(String(err.message||err));$("#go").disabled=false}
};
async function refreshJobs(){
  try{
    var r=await fetch("/api/jobs"); var jobs=await r.json();
    var el=$("#list"); el.innerHTML="";
    if(!jobs.length){el.innerHTML='<div class="meta" style="color:var(--dim)">no jobs yet — upload a video above</div>';return}
    jobs.forEach(function(j){
      var row=document.createElement("div"); row.className="job";
      var left=document.createElement("div");
      left.innerHTML='<b>'+j.name+'</b><div class="meta">'+fmt(j.duration)+' · '+(j.video||"no output yet")+'</div>';
      var pill=document.createElement("span");
      pill.className="pill "+(j.running?"run":(j.finished?"done":""));
      pill.textContent=j.running?"editing…":(j.finished?"ready":"partial");
      row.appendChild(left);row.appendChild(pill);
      row.onclick=function(){openJob(j.name)};
      el.appendChild(row);
    });
  }catch(e){}
}
function openJob(name){
  current=name; $("#detail").classList.remove("hidden");
  $("#dtitle").textContent=name; $("#detail").scrollIntoView({behavior:"smooth"});
  if(timer)clearInterval(timer); poll(); timer=setInterval(poll,1500);
}
async function poll(){
  if(!current)return;
  try{
    var r=await fetch("/api/jobs/"+encodeURIComponent(current)); if(!r.ok)return;
    var s=await r.json();
    $("#dstate").textContent=s.running?"editing…":(s.finished?"ready":"idle");
    $("#dstate").className="pill "+(s.running?"run":(s.finished?"done":""));
    var log=await fetch("/api/jobs/"+encodeURIComponent(current)+"/log");
    var lt=(await log.json()).text||"";
    var el=$("#log"); var stick=el.scrollTop+el.clientHeight>=el.scrollHeight-40;
    el.textContent=lt; if(stick)el.scrollTop=el.scrollHeight;
    if(s.video){
      var src="/media/"+encodeURIComponent(current)+"/"+encodeURIComponent(s.video)+"?t="+(s.artifacts.find(function(a){return a.name===s.video})||{}).created;
      if($("#player").getAttribute("src")!==src)$("#player").setAttribute("src",src);
      $("#dl").href=src; $("#dl").setAttribute("download",s.video);
    }
    var arts=$("#arts"); arts.innerHTML="";
    s.artifacts.slice().reverse().forEach(function(a){
      var link=document.createElement("a"); link.className="btn";
      link.href="/media/"+encodeURIComponent(current)+"/"+encodeURIComponent(a.name);
      link.textContent=a.name+" ("+(a.bytes/1048576).toFixed(1)+" MB)";
      arts.appendChild(link);
    });
  }catch(e){}
}
$("#run").onclick=async function(){
  var r=await fetch("/api/jobs/"+encodeURIComponent(current)+"/run",{method:"POST",
    headers:{"Content-Type":"application/json"},body:JSON.stringify(opts())});
  if(!r.ok){var d=await r.json();alert(d.error||"could not start")}
  poll();
};
$("#cancel").onclick=async function(){
  await fetch("/api/jobs/"+encodeURIComponent(current)+"/cancel",{method:"POST"});
  poll();
};
refreshJobs(); setInterval(refreshJobs,4000);
</script></body></html>
"""


# ----------------------------------------------------------------- handler

class Handler(BaseHTTPRequestHandler):
    server_version = "vidmill"

    def log_message(self, *a):  # quiet
        pass

    # ---------------------------------------------------------- responses
    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code: int, msg: str) -> None:
        self._json(code, {"error": msg})

    def _body_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------- routes
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            if not parts:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parts == ["api", "jobs"]:
                return self._json(200, _list_jobs())
            if parts[:2] == ["api", "jobs"] and len(parts) >= 3:
                name = parts[2]
                if len(parts) == 3:
                    return self._json(200, _status(name))
                if parts[3] == "log":
                    return self._json(200, {"text": _log_tail(name)})
            if parts[0] == "media" and len(parts) == 3:
                return self._media(parts[1], parts[2])
            self._err(404, "not found")
        except FileNotFoundError:
            self._err(404, "job not found")
        except ValueError as e:
            self._err(400, str(e))
        except Exception as e:  # noqa: BLE001
            self._err(500, f"{type(e).__name__}: {e}")

    def do_POST(self) -> None:
        parts = [p for p in urllib.parse.urlparse(self.path).path.split("/") if p]
        try:
            if parts == ["api", "jobs"]:
                body = self._body_json()
                path = body.get("path")
                if not path:
                    return self._err(400, "video path required")
                name = _create_from_path(body.get("name") or "", path)
                return self._json(200, {"name": name})
            if parts[:2] == ["api", "jobs"] and len(parts) == 4:
                name, action = parts[2], parts[3]
                _job_dir(name)  # validate
                if action == "run":
                    _start_run(name, self._body_json())
                    return self._json(200, {"ok": True})
                if action == "cancel":
                    return self._json(200, {"cancelled": _cancel_run(name)})
            self._err(404, "not found")
        except FileNotFoundError:
            self._err(404, "job not found")
        except ValueError as e:
            self._err(400, str(e))
        except RuntimeError as e:
            self._err(409, str(e))
        except Exception as e:  # noqa: BLE001
            self._err(500, f"{type(e).__name__}: {e}")

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/upload":
            return self._err(404, "not found")
        q = urllib.parse.parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self._err(400, "empty upload")
        try:
            name = _receive_upload((q.get("name") or [""])[0],
                                   (q.get("filename") or [""])[0],
                                   self.rfile, length)
            return self._json(200, {"name": name})
        except ValueError as e:
            return self._err(400, str(e))
        except Exception as e:  # noqa: BLE001
            return self._err(500, f"{type(e).__name__}: {e}")

    # -------------------------------------------------------------- media
    def _media(self, name: str, filename: str) -> None:
        jdir = _job_dir(name)
        fname = Path(filename).name
        path = (jdir / fname).resolve()
        if path.parent != jdir or not path.exists() or path.suffix.lower() != ".mp4":
            return self._err(404, "not found")
        size = path.stat().st_size
        ctype = mimetypes.guess_type(fname)[0] or "video/mp4"
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            try:
                start = int(a) if a else 0
                end = int(b) if b else size - 1
            except ValueError:
                start, end = 0, size - 1
            if start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(256 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)


# -------------------------------------------------------------------- cli

def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--dir", default=str(Path.home() / "vmill-jobs"),
                   help="workspace directory for jobs (default ~/vmill-jobs)")
    p.add_argument("--open", action="store_true", help="open the browser")
    p.add_argument("--check", action="store_true", help="self-test the server and exit")


def _make_server(host: str, port: int) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    return httpd


def _check() -> None:
    global ROOT
    import tempfile
    ROOT = Path(tempfile.mkdtemp(prefix="vmill-web-check-"))
    httpd = _make_server("127.0.0.1", 0)
    port = httpd.server_port
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r:
            body = r.read().decode()
            assert r.status == 200 and "<!doctype html" in body.lower(), "bad index"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/jobs", timeout=10) as r:
            jobs = json.load(r)
            assert jobs == [], jobs
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/jobs/..%2Fescape", timeout=5)
            raise AssertionError("path traversal not blocked")
        except urllib.error.HTTPError as e:
            assert e.code in (400, 404), e.code
        print(f"web ui self-test OK: HTTP 200, {len(body)} bytes, api + sandbox checks passed")
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(ROOT, ignore_errors=True)


def run(args: argparse.Namespace) -> None:
    global ROOT
    if args.check:
        return _check()
    ROOT = Path(os.path.expanduser(args.dir)).resolve()
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        httpd = _make_server(args.host, args.port)
    except OSError as e:
        raise util.ToolError(f"cannot bind {args.host}:{args.port} ({e}) — try --port 0 for a free one") from e
    port = httpd.server_port
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '') else args.host}:{port}/"
    print(f"vidmill web ui: {url}")
    print(f"jobs workspace: {ROOT}")
    print("Ctrl+C to stop")
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        print("\nstopped")
