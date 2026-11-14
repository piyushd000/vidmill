"""Tool: serve — local web UI on top of the job model.

  vmill serve                 # http://127.0.0.1:8765
  vmill serve --port 9000 --open
  vmill serve --check         # self-test (used by CI)

No framework, no npm, no extra dependencies: one stdlib HTTP server plus
an embedded single-page UI. Upload a video and the free local pass starts
automatically with every non-AI edit ticked — pauses, still frames,
retakes, captions, audio cleanup and watermark removal. An optional AI
panel lets a model call any vidmill tool to customize the result.

Jobs live under --dir (default ~/vmill-jobs). Binds loopback by default.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import signal
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

PURPOSE = "local web UI: upload, automatic edit, AI changes, watch, download"

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
REGION_RE = re.compile(r"^\d+:\d+:\d+:\d+$")
DEFAULT_OPTS = {"silences": True, "still": True, "mistakes": True,
                "captions": True, "clean": True, "watermark": "auto"}

RUNS: dict[str, dict] = {}
AI_RUNS: dict[str, dict] = {}
OPTS: dict[str, dict] = {}
RUNS_LOCK = threading.Lock()
ROOT: Path = Path.home() / "vmill-jobs"


# ------------------------------------------------------------------ helpers

def _slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", (text or "").strip()).strip("-._")
    return (text or "job")[:64]


def _safe_name(name: str) -> str:
    if not NAME_RE.match(name or ""):
        raise ValueError("job name must be letters, digits, dot, dash or underscore (max 64)")
    return name


def _job_dir(name: str) -> Path:
    name = _safe_name(name)
    path = (ROOT / name).resolve()
    if path.parent != ROOT.resolve():
        raise ValueError("job escapes the workspace")
    return path


def _unique_job(name: str) -> str:
    base = _safe_name(_slug(name))
    candidate, n = base, 2
    while _job_dir(candidate).exists():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _has_key() -> bool:
    return bool(os.environ.get("VIDMILL_AI_KEY") or os.environ.get("OPENAI_API_KEY"))


def _norm_opts(raw: dict | None) -> dict:
    raw = raw or {}
    wm = str(raw.get("watermark") or "auto").strip()
    if wm.lower() not in ("auto", "off") and not REGION_RE.match(wm):
        raise ValueError("watermark must be auto, off, or X:Y:W:H")
    return {
        "silences": bool(raw.get("silences", True)),
        "still": bool(raw.get("still", True)),
        "mistakes": bool(raw.get("mistakes", True)),
        "captions": bool(raw.get("captions", True)),
        "clean": bool(raw.get("clean", True)),
        "watermark": "off" if wm.lower() == "off" else (wm.lower() if wm.lower() == "auto" else wm),
    }


def _active(run: dict | None) -> bool:
    return bool(run and run["proc"].poll() is None)


def _close(run: dict) -> None:
    if run.get("closed"):
        return
    try:
        run["fh"].close()
    except Exception:
        pass
    run["closed"] = True


def _kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


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


def _current_video(j: jobmod.Job, arts: list[dict]) -> str | None:
    try:
        cur = j.current_video()
    except Exception:
        cur = None
    if cur and cur.exists() and cur.resolve().parent == j.path.resolve():
        if any(a["name"] == cur.name for a in arts):
            return cur.name
    if arts:
        return max(arts, key=lambda a: a.get("created") or "")["name"]
    return None


def _status(name: str) -> dict:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    j = jobmod.Job.load(jdir)
    info = j.data.get("info", {})
    arts = _video_artifacts(j)
    video = _current_video(j, arts)
    with RUNS_LOCK:
        run, airun = RUNS.get(name), AI_RUNS.get(name)
        running, ai_running = _active(run), _active(airun)
        for r, active in ((run, running), (airun, ai_running)):
            if r and not active:
                _close(r)
        opts = dict(OPTS.get(name) or DEFAULT_OPTS)
    return {
        "name": name,
        "source": j.data.get("source_name") or Path(j.data.get("video", "")).name,
        "created": j.data.get("created"),
        "width": info.get("width"), "height": info.get("height"),
        "duration": info.get("duration"), "size_bytes": info.get("size_bytes"),
        "artifacts": arts, "video": video, "running": running,
        "ai_running": ai_running, "ai_available": _has_key(),
        "opts": opts, "finished": bool(video) and not running and not ai_running,
    }


def _list_jobs() -> list[dict]:
    jobs = []
    if ROOT.exists():
        for d in sorted(ROOT.iterdir(), reverse=True):
            if d.is_dir() and (d / "job.json").exists():
                try:
                    s = _status(d.name)
                    jobs.append({k: s[k] for k in
                                 ("name", "created", "duration", "video", "running",
                                  "ai_running", "finished")})
                except Exception:
                    continue
    return jobs[:100]


def _log_tail(name: str, filename: str = ".run.log", limit: int = 60000) -> str:
    f = _job_dir(name) / filename
    if not f.exists():
        return ""
    data = f.read_bytes()
    return data[-limit:].decode("utf-8", "replace")


def _ai_text(name: str) -> str:
    return _log_tail(name, ".ai.log")


def _start_run(name: str, raw_opts: dict) -> None:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    opts = _norm_opts(raw_opts)
    with RUNS_LOCK:
        if _active(RUNS.get(name)):
            raise RuntimeError("an automatic edit is already running")
        if _active(AI_RUNS.get(name)):
            raise RuntimeError("the AI editor is busy with this job")
        if raw_opts.get("restart"):
            j = jobmod.Job.load(jdir)
            src = Path(j.data.get("video", ""))
            if not src.exists():
                raise ValueError("the original source video is gone")
            jobmod.Job.create(jdir, src)  # reset artifacts, keep the source
            for stale in (".run.log", ".ai.log"):
                (jdir / stale).unlink(missing_ok=True)
        OPTS[name] = opts
        argv = [sys.executable, "-u", "-m", "vidmill", "auto", "--job", str(jdir), "--no-ai"]
        if not opts["silences"]:
            argv.append("--no-silence")
        if not opts["still"]:
            argv.append("--no-freeze")
        argv.append("--mistakes" if opts["mistakes"] else "--no-mistakes")
        if not opts["captions"]:
            argv.append("--no-captions")
        if not opts["clean"]:
            argv.append("--no-clean")
        argv += ["--watermark", opts["watermark"]]
        log = jdir / ".run.log"
        fh = open(log, "wb")
        proc = subprocess.Popen(argv, stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        RUNS[name] = {"proc": proc, "log": log, "fh": fh, "closed": False}


def _start_ai(name: str, prompt: str) -> None:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("describe the change you want")
    if not _has_key():
        raise RuntimeError("AI editing needs VIDMILL_AI_KEY (or OPENAI_API_KEY) "
                           "in the server's environment")
    with RUNS_LOCK:
        if _active(RUNS.get(name)):
            raise RuntimeError("the automatic edit is still running")
        if _active(AI_RUNS.get(name)):
            raise RuntimeError("the AI editor is already working on this job")
        argv = [sys.executable, "-u", "-m", "vidmill", "ai", "--job", str(jdir), "--", prompt]
        log = jdir / ".ai.log"
        fh = open(log, "wb")
        proc = subprocess.Popen(argv, stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True,
                                env=dict(os.environ))
        AI_RUNS[name] = {"proc": proc, "log": log, "fh": fh, "closed": False}


def _cancel(name: str) -> bool:
    cancelled = False
    with RUNS_LOCK:
        for runs in (RUNS, AI_RUNS):
            run = runs.get(name)
            if _active(run):
                _kill(run["proc"])
                cancelled = True
    return cancelled


def _create_from_path(name: str, video_path: str) -> str:
    src = Path(os.path.expanduser(video_path))
    if not src.exists() or src.suffix.lower() not in VIDEO_EXT:
        raise ValueError("not a video file on this machine")
    name = _unique_job(name or src.stem)
    jdir = _job_dir(name)
    jdir.mkdir(parents=True, exist_ok=True)
    jobmod.Job.create(jdir, src, copy=False)
    return name


def _receive_upload(name: str, filename: str, rfile, length: int) -> str:
    filename = Path(filename or "upload.mp4").name
    suffix = Path(filename).suffix.lower()
    if suffix not in VIDEO_EXT:
        raise ValueError(f"unsupported video extension: {suffix or '(none)'}")
    name = _unique_job(name or Path(filename).stem)
    jdir = _job_dir(name)
    jdir.mkdir(parents=True, exist_ok=True)
    dest = jdir / ("source" + suffix)
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
    job = jobmod.Job.create(jdir, dest, copy=False)
    job.data["source_name"] = filename
    job.save()
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
h2.sect{margin-top:26px}
.sub{color:var(--dim)}
main{max-width:1020px;margin:0 auto;padding:22px 18px 60px;display:grid;gap:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}
.hidden{display:none}
#drop{border:2px dashed var(--line);border-radius:12px;padding:30px;text-align:center;color:var(--dim);transition:.2s}
#drop.hot{border-color:var(--acc);color:var(--fg);background:#141a2b}
.btn{display:inline-block;padding:9px 16px;border-radius:9px;border:1px solid var(--line);background:#1d222c;color:var(--fg);cursor:pointer;text-decoration:none;font-size:14px}
.btn:hover{border-color:var(--acc)}
.btn.primary{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.btn:disabled{opacity:.45;cursor:not-allowed}
.row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
input[type=text]{flex:1;min-width:220px;padding:9px 12px;border-radius:9px;border:1px solid var(--line);background:#12151b;color:var(--fg)}
.checklist{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px 18px;margin-top:16px;color:var(--fg);font-size:14px}
.checklist label{display:flex;gap:8px;align-items:center;cursor:pointer;color:var(--dim)}
.checklist input[type=checkbox]{accent-color:var(--acc)}
.wmrow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.wmrow input[type=text]{min-width:170px;flex:0 1 200px;padding:5px 9px;font-size:13px}
.note{color:var(--dim);font-size:13px;margin-top:12px;line-height:1.45}
.msg{margin-top:12px;color:var(--warn);min-height:20px;font-size:14px}
.jobs{display:grid;gap:10px}
.job{display:flex;justify-content:space-between;gap:12px;padding:12px 14px;border:1px solid var(--line);border-radius:10px;cursor:pointer;align-items:center}
.job:hover{border-color:var(--acc)}
.job .meta{color:var(--dim);font-size:13px}
.pill{font-size:12px;padding:2px 9px;border-radius:99px;border:1px solid var(--line);color:var(--dim)}
.pill.run{color:var(--warn);border-color:var(--warn)}
.pill.done{color:var(--ok);border-color:var(--ok)}
video{width:100%;max-height:70vh;border-radius:10px;background:#000;margin-top:14px}
.log{background:#0b0d11;border:1px solid var(--line);border-radius:10px;padding:14px;max-height:340px;overflow:auto;font:12.5px/1.45 ui-monospace,Menlo,Consolas,monospace;color:#c9d3e6;white-space:pre-wrap;margin-top:8px}
.arts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.arts a{font-size:13px}
.dhead{display:flex;justify-content:space-between;align-items:center;gap:10px}
</style></head>
<body>
<header><h1>vidmill</h1><span class="sub">drop a video — get a finished edit, free and entirely on your machine</span></header>
<main>
<section class="card" id="newcard">
  <h2>New edit</h2>
  <div id="drop">Drop a video here, or <label class="btn" style="margin-left:6px">browse<input type="file" id="file" accept="video/*" hidden></label>
    <div id="picked" class="meta" style="margin-top:8px;color:var(--dim)"></div></div>
  <div class="row">
    <input type="text" id="path" placeholder="…or an absolute path on this machine">
    <input type="text" id="jobname" placeholder="job name (optional)">
  </div>
  <div class="checklist">
    <label><input type="checkbox" id="n_silences" checked> Remove silences</label>
    <label><input type="checkbox" id="n_still" checked> Remove still frames</label>
    <label><input type="checkbox" id="n_mistakes" checked> Remove retakes</label>
    <label><input type="checkbox" id="n_captions" checked> Burn captions</label>
    <label><input type="checkbox" id="n_clean" checked> Clean audio</label>
    <div class="wmrow"><label><input type="checkbox" id="n_watermark" checked> Remove watermark</label>
      <input type="text" id="n_wmregion" placeholder="auto-detect or X:Y:W:H"></div>
  </div>
  <div class="note">These all run in the free local pass — no AI, no API key, no upload. The edit starts as soon as the video is in.</div>
  <div class="row"><button class="btn primary" id="go" disabled>Upload &amp; edit</button></div>
  <div class="msg" id="msg"></div>
</section>
<section class="card"><h2>Jobs</h2><div class="jobs" id="list"></div></section>
<section class="card hidden" id="detail">
  <div class="dhead"><h2 id="dtitle"></h2><span class="pill" id="dstate"></span></div>
  <video id="player" controls playsinline></video>
  <div class="row">
    <button class="btn primary" id="run">Apply &amp; re-run from source</button>
    <button class="btn" id="cancel">Cancel</button>
    <a class="btn" id="dl" download>Download</a>
  </div>
  <div class="checklist">
    <label><input type="checkbox" id="d_silences" checked> Remove silences</label>
    <label><input type="checkbox" id="d_still" checked> Remove still frames</label>
    <label><input type="checkbox" id="d_mistakes" checked> Remove retakes</label>
    <label><input type="checkbox" id="d_captions" checked> Burn captions</label>
    <label><input type="checkbox" id="d_clean" checked> Clean audio</label>
    <div class="wmrow"><label><input type="checkbox" id="d_watermark" checked> Remove watermark</label>
      <input type="text" id="d_wmregion" placeholder="auto-detect or X:Y:W:H"></div>
  </div>
  <div class="note">Re-running resets this job's artifacts and starts again from the original source.</div>
  <div class="arts" id="arts"></div>
  <h2 class="sect">Log</h2><pre class="log" id="log"></pre>
  <h2 class="sect">Ask AI to change this edit</h2>
  <div class="row">
    <input type="text" id="aiprompt" placeholder="e.g. cut the pause at 0:42 and add my logo top-right">
    <button class="btn" id="ai">Ask AI</button>
  </div>
  <div class="note" id="aihint">Optional. The AI can call any vidmill tool; only text and tool results leave the machine.</div>
  <pre class="log" id="ailog"></pre>
</section>
</main>
<script>
var current=null,fileObj=null,timer=null,aiTimer=null,optsLoaded=false;

function $(s){return document.querySelector(s)}
function fmt(n){if(n==null)return "?";var m=Math.floor(n/60),s=Math.round(n%60);return m+":"+(s<10?"0":"")+s}
function enc(s){return encodeURIComponent(s)}
function setMsg(t){$("#msg").textContent=t||""}
function picked(f){fileObj=f;var p=$("#picked");p.textContent=f?(f.name+"  "+(f.size/1048576).toFixed(1)+" MB"):"";$("#go").disabled=!(f||$("#path").value.trim())}

function readOpts(prefix){
  var on=$("#"+prefix+"watermark").checked;
  var region=$("#"+prefix+"wmregion").value.trim();
  return {
    silences:$("#"+prefix+"silences").checked,
    still:$("#"+prefix+"still").checked,
    mistakes:$("#"+prefix+"mistakes").checked,
    captions:$("#"+prefix+"captions").checked,
    clean:$("#"+prefix+"clean").checked,
    watermark:on?(region||"auto"):"off"
  };
}
function writeOpts(prefix,o){
  o=o||{};
  $("#"+prefix+"silences").checked=o.silences!==false;
  $("#"+prefix+"still").checked=o.still!==false;
  $("#"+prefix+"mistakes").checked=o.mistakes!==false;
  $("#"+prefix+"captions").checked=o.captions!==false;
  $("#"+prefix+"clean").checked=o.clean!==false;
  var wm=o.watermark||"auto";
  $("#"+prefix+"watermark").checked=wm!=="off";
  $("#"+prefix+"wmregion").value=(wm!=="auto"&&wm!=="off")?wm:"";
}

$("#file").addEventListener("change",function(e){picked(e.target.files[0]||null)});
$("#path").addEventListener("input",function(){picked(fileObj)});
$("#drop").addEventListener("dragover",function(e){e.preventDefault();$("#drop").classList.add("hot")});
$("#drop").addEventListener("dragleave",function(){$("#drop").classList.remove("hot")});
$("#drop").addEventListener("drop",function(e){e.preventDefault();$("#drop").classList.remove("hot");picked(e.dataTransfer.files[0]||null)});

$("#go").onclick=async function(){
  var o=readOpts("n_"),name=$("#jobname").value.trim(),path=$("#path").value.trim();
  setMsg("");$("#go").disabled=true;
  try{
    var job;
    if(fileObj&&!path){
      setMsg("uploading…");
      var q=new URLSearchParams({filename:fileObj.name});if(name)q.set("name",name);
      var r=await fetch("/api/upload?"+q,{method:"PUT",body:fileObj});
      var d=await r.json();if(!r.ok)throw new Error(d.error||"upload failed");
      job=d.name;
    }else{
      if(!path)throw new Error("choose a video or paste a path on this machine");
      var r=await fetch("/api/jobs",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name:name||undefined,path:path})});
      var d=await r.json();if(!r.ok)throw new Error(d.error||"could not open video");
      job=d.name;
    }
    setMsg("starting the free local edit…");
    var rr=await fetch("/api/jobs/"+enc(job)+"/run",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify(o)});
    var dd=await rr.json();if(!rr.ok)throw new Error(dd.error||"could not start the edit");
    fileObj=null;$("#picked").textContent="";$("#path").value="";$("#jobname").value="";
    $("#go").disabled=true;
    openJob(job);refreshJobs();
  }catch(err){setMsg(String(err.message||err));$("#go").disabled=false}
};

async function refreshJobs(){
  try{
    var r=await fetch("/api/jobs");var jobs=await r.json();
    var el=$("#list");el.innerHTML="";
    if(!jobs.length){el.innerHTML='<div class="meta" style="color:var(--dim)">no jobs yet — pick a video above and it starts automatically</div>';return}
    jobs.forEach(function(j){
      var row=document.createElement("div");row.className="job";
      var left=document.createElement("div");
      var b=document.createElement("b");b.textContent=j.name;left.appendChild(b);
      var m=document.createElement("div");m.className="meta";
      m.textContent=fmt(j.duration)+" · "+(j.video||"no output yet");
      left.appendChild(m);
      var pill=document.createElement("span");
      pill.className="pill "+(j.running||j.ai_running?"run":(j.finished?"done":""));
      pill.textContent=j.running?"editing…":(j.ai_running?"AI editing…":(j.finished?"ready":"partial"));
      row.appendChild(left);row.appendChild(pill);
      row.onclick=function(){openJob(j.name)};
      el.appendChild(row);
    });
  }catch(e){}
}

function openJob(name){
  current=name;optsLoaded=false;$("#detail").classList.remove("hidden");
  $("#dtitle").textContent=name;$("#ailog").textContent="";
  $("#detail").scrollIntoView({behavior:"smooth"});
  if(timer)clearInterval(timer);if(aiTimer)clearTimeout(aiTimer);
  poll();timer=setInterval(poll,1500);
}

async function poll(){
  if(!current)return;
  try{
    var r=await fetch("/api/jobs/"+enc(current));if(!r.ok)return;
    var s=await r.json();
    var state=s.running?"editing…":(s.ai_running?"AI editing…":(s.finished?"ready":"idle"));
    $("#dstate").textContent=state;
    $("#dstate").className="pill "+((s.running||s.ai_running)?"run":(s.finished?"done":""));
    $("#run").disabled=s.running||s.ai_running;
    $("#cancel").disabled=!(s.running||s.ai_running);
    $("#ai").disabled=s.running||s.ai_running||!s.ai_available;
    $("#aihint").textContent=s.ai_available
      ?"Optional. The AI can call any vidmill tool; only text and tool results leave the machine."
      :"Set VIDMILL_AI_KEY (or OPENAI_API_KEY) in the server environment to enable AI edits.";
    if(!optsLoaded){writeOpts("d_",s.opts);optsLoaded=true}
    var log=await fetch("/api/jobs/"+enc(current)+"/log");
    var lt=(await log.json()).text||"";
    var el=$("#log");var stick=el.scrollTop+el.clientHeight>=el.scrollHeight-40;
    el.textContent=lt;if(stick)el.scrollTop=el.scrollHeight;
    if(s.video){
      var meta=(s.artifacts.find(function(a){return a.name===s.video})||{}).created||"";
      var src="/media/"+enc(current)+"/"+enc(s.video)+"?t="+enc(meta);
      if($("#player").getAttribute("src")!==src)$("#player").setAttribute("src",src);
      $("#dl").href=src;$("#dl").setAttribute("download",s.video);
    }
    var arts=$("#arts");arts.innerHTML="";
    s.artifacts.slice().reverse().forEach(function(a){
      var link=document.createElement("a");link.className="btn";
      link.href="/media/"+enc(current)+"/"+enc(a.name);
      link.textContent=a.name+" ("+(a.bytes/1048576).toFixed(1)+" MB)";
      arts.appendChild(link);
    });
    if(s.ai_running&&!aiTimer)pollAI();
  }catch(e){}
}

async function pollAI(){
  if(!current)return;
  try{
    var r=await fetch("/api/jobs/"+enc(current)+"/ai");var s=await r.json();
    var el=$("#ailog");var stick=el.scrollTop+el.clientHeight>=el.scrollHeight-40;
    el.textContent=s.text||"";if(stick)el.scrollTop=el.scrollHeight;
    if(s.running){aiTimer=setTimeout(pollAI,1500);return}
    aiTimer=null;poll();
  }catch(e){aiTimer=null}
}

$("#run").onclick=async function(){
  if(!current)return;
  if(!confirm("Reset this job's artifacts and run the free edit again from the original source?"))return;
  var r=await fetch("/api/jobs/"+enc(current)+"/run",{method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(Object.assign(readOpts("d_"),{restart:true}))});
  if(!r.ok){var d=await r.json();alert(d.error||"could not start")}
  optsLoaded=false;$("#log").textContent="";poll();
};

$("#cancel").onclick=async function(){
  if(!current)return;
  await fetch("/api/jobs/"+enc(current)+"/cancel",{method:"POST"});poll();
};

$("#ai").onclick=askAI;
$("#aiprompt").addEventListener("keydown",function(e){if(e.key==="Enter")askAI()});
async function askAI(){
  if(!current)return;
  var p=$("#aiprompt").value.trim();if(!p)return;
  $("#ai").disabled=true;$("#ailog").textContent="starting the AI editor…";
  try{
    var r=await fetch("/api/jobs/"+enc(current)+"/ai",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({prompt:p})});
    var d=await r.json();if(!r.ok)throw new Error(d.error||"could not start the AI");
    $("#aiprompt").value="";pollAI();poll();
  }catch(e){$("#ailog").textContent=String(e.message||e);$("#ai").disabled=false}
}

refreshJobs();setInterval(refreshJobs,4000);
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
                if parts[3] == "ai":
                    with RUNS_LOCK:
                        running = _active(AI_RUNS.get(name))
                        if AI_RUNS.get(name) and not running:
                            _close(AI_RUNS[name])
                    return self._json(200, {"running": running, "text": _ai_text(name)})
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
                if action == "ai":
                    _start_ai(name, (self._body_json() or {}).get("prompt", ""))
                    return self._json(200, {"ok": True})
                if action == "cancel":
                    return self._json(200, {"cancelled": _cancel(name)})
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
            assert "Remove watermark" in body and "Ask AI" in body, "ui sections missing"
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
