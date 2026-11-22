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
from . import skills as skillsmod
from . import util
from .web_ui import HTML

PURPOSE = "local web UI: upload, automatic edit, AI changes, watch, download"

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}
REGION_RE = re.compile(r"^\d+:\d+:\d+:\d+$")
DEFAULT_OPTS = {"silences": True, "still": True, "mistakes": True,
                "captions": True, "clean": True, "watermark": "auto"}

RUNS: dict[str, dict] = {}
AI_RUNS: dict[str, dict] = {}
VISION_RUNS: dict[str, dict] = {}
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
        "fps": info.get("fps"), "has_audio": info.get("has_audio"),
        "job_dir": str(jdir),
        "ai_model": os.environ.get("VIDMILL_AI_MODEL") or "openai-compatible",
        "artifacts": arts, "video": video, "running": running,
        "ai_running": ai_running, "ai_available": _has_key(),
        "opts": opts, "finished": bool(video) and not running and not ai_running,
        "current": next((a for a in arts if a["name"] == video), None),
        "asset_count": _asset_count(jdir, j),
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


# ------------------------------------------------------------------- skills

def _skills_state() -> dict:
    found, warnings = skillsmod.discover_with_warnings()
    return {
        "skills": [skillsmod.summary(s) for s in found],
        "warnings": warnings,
        "count": len(found),
        "dirs": {k: str(v) for k, v in skillsmod.roots().items()},
    }


def _skill_detail(name: str) -> dict:
    skill = skillsmod.load(name)
    return {"skill": {**skillsmod.summary(skill), "body": skill.body}}


def _skill_create(payload: dict) -> dict:
    skill = skillsmod.upsert(
        str(payload.get("name") or ""),
        str(payload.get("description") or ""),
        str(payload.get("body") or ""),
        payload.get("tags") or (),
        str(payload.get("scope") or "user"),
    )
    return _skill_detail(skill.name)


def _skill_save(name: str, payload: dict) -> dict:
    existing = skillsmod.load(name)
    scope = str(payload.get("scope") or
                ("project" if existing.source == "project" else "user"))
    skill = skillsmod.update(
        name,
        payload.get("description") if "description" in payload else None,
        payload.get("body") if "body" in payload else None,
        payload.get("tags") if "tags" in payload else None,
        scope,
    )
    return _skill_detail(skill.name)


def _skill_reset(name: str, payload: dict) -> dict:
    scope = str(payload.get("scope") or "user")
    scopes = ("user", "project") if scope == "all" else (skillsmod.clean_scope(scope),)
    removed = skillsmod.reset(name, scopes)
    current = skillsmod.find(name)
    return {"removed": [str(p) for p in removed],
            "skill": {**skillsmod.summary(current), "body": current.body}
            if current else None}


def _media_kind(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    if suffix in VIDEO_EXT:
        return "video"
    if suffix in IMAGE_EXT:
        return "image"
    if suffix in AUDIO_EXT:
        return "audio"
    return None


PROBE_CACHE: dict[str, tuple[tuple[int, int], dict]] = {}
PROBE_LOCK = threading.Lock()


def _probe(path: Path) -> dict:
    """Probe once per (size, mtime); media bins and timelines are polled."""
    try:
        st = path.stat()
    except OSError:
        return {}
    key = str(path)
    sig = (st.st_mtime_ns, st.st_size)
    with PROBE_LOCK:
        hit = PROBE_CACHE.get(key)
    if hit and hit[0] == sig:
        return hit[1]
    try:
        info = util.probe_info(path)
    except Exception:
        info = {}
    with PROBE_LOCK:
        PROBE_CACHE[key] = (sig, info)
    return info


def _job_file(jdir: Path, filename: str) -> Path:
    fname = Path(filename).name
    if not fname or fname.startswith(".") or _media_kind(fname) is None:
        raise FileNotFoundError(filename)
    path = (jdir / fname).resolve()
    if path.parent != jdir or not path.exists():
        raise FileNotFoundError(filename)
    return path


def _media_files(jdir: Path) -> list[Path]:
    if not jdir.exists():
        return []
    return sorted((p for p in jdir.iterdir()
                   if p.is_file() and not p.name.startswith(".") and _media_kind(p.name)),
                  key=lambda p: p.name.lower())


def _created_of(path: Path) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(path.stat().st_mtime))


def _source_path(j: jobmod.Job) -> Path | None:
    """The project's original video, if it still exists on disk."""
    src = Path(j.data.get("video", "")).expanduser()
    try:
        if src.is_file() and _media_kind(src.name):
            return src.resolve()
    except OSError:
        pass
    return None


def _external_source(jdir: Path, j: jobmod.Job) -> Path | None:
    """A source imported by path, left outside the job folder on purpose."""
    src = _source_path(j)
    if src is None:
        return None
    try:
        if src.parent == jdir.resolve():
            return None
    except OSError:
        return None
    return src


def _external_asset(name: str, jdir: Path, j: jobmod.Job, src: Path,
                    info: dict) -> dict:
    probed = _probe(src)
    display = j.data.get("source_name") or src.name
    if (jdir / display).exists():
        stem, suffix = Path(display).stem, Path(display).suffix
        display = f"{stem} (source){suffix}"
    st = src.stat()
    quote = urllib.parse.quote
    return {
        "name": display,
        "kind": _media_kind(src.name) or "video",
        "bytes": st.st_size,
        "duration": round(float(probed.get("duration") or info.get("duration") or 0), 3) or None,
        "width": probed.get("width") or info.get("width"),
        "height": probed.get("height") or info.get("height"),
        "fps": probed.get("fps") or info.get("fps"),
        "has_audio": probed.get("has_audio", info.get("has_audio")),
        "created": _created_of(src),
        "source": True,
        "external": True,
        "artifact": False,
        "current": False,
        "thumb": f"/source_thumb/{quote(name, safe='')}?v={st.st_mtime_ns}",
        "url": f"/source/{quote(name, safe='')}?v={st.st_mtime_ns}",
    }


def _asset_count(jdir: Path, j: jobmod.Job) -> int:
    return len(_media_files(jdir)) + (1 if _external_source(jdir, j) else 0)


def _assets(name: str) -> dict:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    j = jobmod.Job.load(jdir)
    info = j.data.get("info", {})
    arts = j.data.get("artifacts", {})
    video = _current_video(j, _video_artifacts(j))
    src = Path(j.data.get("video", "")).expanduser()
    try:
        src_resolved = src.resolve()
    except OSError:
        src_resolved = src
    out = []
    for path in _media_files(jdir):
        kind = _media_kind(path.name) or "file"
        meta = (arts.get(path.name) or {}).get("meta") or {}
        probed = _probe(path) if kind in ("video", "audio") else {}
        dur = meta.get("duration")
        if dur is None:
            dur = probed.get("duration")
        if kind == "image":
            dur = None
        st = path.stat()
        try:
            is_source = path.resolve() == src_resolved
        except OSError:
            is_source = False
        out.append({
            "name": path.name,
            "kind": kind,
            "bytes": st.st_size,
            "duration": round(float(dur), 3) if dur else None,
            "width": meta.get("width") or probed.get("width") or info.get("width"),
            "height": meta.get("height") or probed.get("height") or info.get("height"),
            "fps": probed.get("fps") or info.get("fps"),
            "has_audio": probed.get("has_audio", info.get("has_audio")),
            "created": (arts.get(path.name) or {}).get("created") or _created_of(path),
            "source": is_source,
            "artifact": path.name in arts,
            "current": path.name == video,
            "thumb": f"/thumb/{urllib.parse.quote(name, safe='')}/"
                     f"{urllib.parse.quote(path.name, safe='')}?v={st.st_mtime_ns}",
            "url": f"/media/{urllib.parse.quote(name, safe='')}/"
                   f"{urllib.parse.quote(path.name, safe='')}",
        })

    ext = _external_source(jdir, j)
    if ext is not None:
        out.append(_external_asset(name, jdir, j, ext, info))

    def rank(a: dict) -> tuple:
        if a["current"]:
            return (0, a["name"].lower())
        if a["source"]:
            return (1, a["name"].lower())
        if not a["artifact"]:
            return (2, a["name"].lower())
        return (3, a["name"].lower())

    out.sort(key=rank)
    return {"assets": out, "source": src.name if src.name else None, "video": video}


def _receive_asset(name: str, filename: str, rfile, length: int) -> str:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    original = Path(filename or "asset").name
    kind = _media_kind(original)
    if kind is None:
        raise ValueError("asset must be a video, image or audio file")
    stem = _slug(Path(original).stem)[:48] or "asset"
    suffix = Path(original).suffix.lower()
    candidate, n = f"{stem}{suffix}", 2
    while (jdir / candidate).exists():
        candidate = f"{stem}-{n}{suffix}"
        n += 1
    dest = jdir / candidate
    tmp = dest.with_name(dest.name + ".part")
    got = 0
    with open(tmp, "wb") as f:
        while got < length:
            chunk = rfile.read(min(1024 * 1024, length - got))
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
    if got != length:
        tmp.unlink(missing_ok=True)
        raise ValueError("upload interrupted")
    tmp.replace(dest)
    return candidate


# ------------------------------------------------------------ thumbnails

def _render_cached(jdir: Path, folder: str, src: Path, ext: str,
                   args: list, timeout: int = 60) -> Path:
    st = src.stat()
    outdir = jdir / folder
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{src.stem}-{st.st_mtime_ns}{ext}"
    if out.exists() and out.stat().st_size > 0:
        return out
    tmp = out.with_name(out.stem + "-tmp" + out.suffix)
    cmd = [util.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin"]
    cmd += [str(a) for a in args] + [str(tmp)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"preview render failed: {e}") from e
    if proc.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        detail = (proc.stderr or b"")[-300:].decode("utf-8", "replace")
        raise RuntimeError(f"preview render failed: {detail or 'no output'}")
    tmp.replace(out)
    return out


def _thumb_file(jdir: Path, src: Path) -> Path:
    kind = _media_kind(src.name)
    if kind == "image":
        args = ["-i", src, "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4"]
        return _render_cached(jdir, ".thumbs", src, ".jpg", args)
    if kind == "video":
        dur = float(_probe(src).get("duration") or 0)
        ss = min(max(dur * 0.25, 0.0), 1.0) if dur else 0.0
        args = ["-ss", f"{ss:.3f}", "-i", src, "-frames:v", "1",
                "-vf", "scale=360:-2", "-q:v", "4"]
        return _render_cached(jdir, ".thumbs", src, ".jpg", args)
    if kind == "audio":
        args = ["-i", src, "-filter_complex",
                "aformat=channel_layouts=stereo,"
                "showwavespic=s=360x200:colors=#5b8cff:scale=sqrt",
                "-frames:v", "1"]
        return _render_cached(jdir, ".thumbs", src, ".png", args)
    raise FileNotFoundError(src.name)


def _wave_file(jdir: Path, src: Path) -> Path:
    info = _probe(src)
    if not info.get("has_audio"):
        raise ValueError("this file has no audio")
    args = ["-i", src, "-filter_complex",
            "aformat=channel_layouts=stereo,"
            "showwavespic=s=1200x180:colors=#5b8cff:scale=sqrt",
            "-frames:v", "1"]
    return _render_cached(jdir, ".wave", src, ".png", args)


# --------------------------------------------------------------- timeline

def _art_meta(arts: dict, name: str) -> dict:
    return (arts.get(name) or {}).get("meta") or {}


def _clip_len(arts: dict, name: str, total: float) -> float:
    meta = _art_meta(arts, name)
    clip = meta.get("clip_seconds")
    if clip is None:
        duration = meta.get("duration")
        clip = duration if duration and duration < total - 0.05 else 0
    try:
        return max(0.0, min(float(clip or 0), total))
    except (TypeError, ValueError):
        return 0.0


def _timeline(name: str) -> dict:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    j = jobmod.Job.load(jdir)
    info = j.data.get("info", {})
    arts = j.data.get("artifacts", {})
    video = _current_video(j, _video_artifacts(j))
    if not video:
        src = Path(j.data.get("video", ""))
        try:
            if src.exists() and src.resolve().parent == jdir.resolve():
                video = src.name
        except OSError:
            video = None
    cur_meta = _art_meta(arts, video) if video else {}
    cur_info = _probe(j.apath(video)) if video else {}
    ext = _external_source(jdir, j)
    ext_info = _probe(ext) if ext is not None and not video else {}
    duration = (cur_meta.get("duration") or cur_info.get("duration")
                or ext_info.get("duration") or info.get("duration") or 0)
    try:
        duration = round(float(duration), 3)
    except (TypeError, ValueError):
        duration = 0.0
    width = (cur_meta.get("width") or cur_info.get("width")
             or ext_info.get("width") or info.get("width"))
    height = (cur_meta.get("height") or cur_info.get("height")
              or ext_info.get("height") or info.get("height"))
    fps = cur_info.get("fps") or ext_info.get("fps") or info.get("fps")
    has_audio = bool(cur_info.get("has_audio",
                                  ext_info.get("has_audio", info.get("has_audio"))))

    intro_len = _clip_len(arts, "intro.mp4", duration) if video == "final.mp4" else 0.0
    outro_len = _clip_len(arts, "outro.mp4", duration) if video == "final.mp4" else 0.0
    segments: list[dict] = []
    if duration > 0:
        if intro_len or outro_len:
            main_end = max(intro_len, duration - outro_len)
            if intro_len > 0:
                segments.append({"start": 0.0, "end": round(intro_len, 3),
                                 "label": "Intro", "kind": "intro"})
            if main_end > intro_len + 0.02:
                segments.append({"start": round(intro_len, 3),
                                 "end": round(main_end, 3),
                                 "label": "Main edit", "kind": "main"})
            if outro_len > 0:
                segments.append({"start": round(main_end, 3),
                                 "end": duration, "label": "Outro", "kind": "outro"})
        if not segments:
            label = "Source" if not any(a["name"] == video for a in _video_artifacts(j)) else "Edit"
            segments.append({"start": 0.0, "end": duration,
                             "label": label, "kind": "main"})

    captions = None
    if (jdir / "captions.ass").exists():
        cstart, cend = 0.0, duration
        if segments and segments[0]["kind"] == "intro":
            cstart = segments[0]["end"]
        if segments and segments[-1]["kind"] == "outro":
            cend = segments[-1]["start"]
        count = _art_meta(arts, "captions.ass").get("lines")
        if count is None:
            try:
                transcript = util.read_json(jdir / "transcript.json")
                segs = transcript.get("segments")
                count = len(segs) if isinstance(segs, list) else None
            except Exception:
                count = None
        captions = {"start": round(cstart, 3), "end": round(cend, 3),
                    "count": count, "file": "captions.ass"}

    overlays = []
    for fname, meta in arts.items():
        if not (fname.startswith("overlay_") and fname.endswith(".mp4")):
            continue
        m = meta.get("meta") or {}
        if m.get("at") is None or not (jdir / fname).exists():
            continue
        try:
            start = float(m.get("at") or 0)
            end = float(m["to"]) if m.get("to") is not None else duration
        except (TypeError, ValueError):
            continue
        if duration and start >= duration:
            continue
        media = Path(str(m.get("media") or "")).name
        overlays.append({
            "start": round(max(0.0, start), 3),
            "end": round(min(duration or end, max(end, start + 0.05)), 3),
            "kind": m.get("kind") or "overlay",
            "label": media or fname,
            "media": media or None,
            "file": fname,
        })
    overlays.sort(key=lambda o: o["start"])

    cut = None
    try:
        plan = util.read_json(jdir / "cut_plan.json")
        summary = plan.get("summary") or {}
        cut = {
            "removed": summary.get("removed_seconds", plan.get("removed_seconds")),
            "kept": summary.get("edited_seconds"),
            "pieces": summary.get("pieces_kept"),
            "ranges": plan.get("keep_seconds") or [],
        }
    except Exception:
        pass

    source = Path(j.data.get("video", ""))
    try:
        wave_v = (j.apath(video).stat().st_mtime_ns if video
                  else ext.stat().st_mtime_ns if ext is not None else 0)
    except OSError:
        wave_v = round(duration * 1000)
    quote = urllib.parse.quote
    if has_audio and video:
        waveform = f"/waveform/{quote(name, safe='')}/{quote(video, safe='')}?v={wave_v}"
    elif has_audio and ext is not None:
        waveform = f"/source_wave/{quote(name, safe='')}?v={wave_v}"
    else:
        waveform = None
    return {
        "job": name,
        "video": video,
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": has_audio,
        "segments": segments,
        "captions": captions,
        "overlays": overlays,
        "audio": {
            "file": video or (ext.name if ext is not None else None),
            "present": has_audio,
            "waveform": waveform,
        },
        "cut": cut,
        "source": {
            "name": Path(j.data.get("source_name") or source.name).name,
            "duration": info.get("duration"),
        },
    }


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


def _start_ai(name: str, prompt: str, skill_names=None) -> None:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("describe the change you want")
    try:
        selected = skillsmod.resolve_many(skill_names or [])
    except FileNotFoundError as e:
        raise ValueError(str(e)) from e
    if not _has_key():
        raise RuntimeError("AI editing needs VIDMILL_AI_KEY (or OPENAI_API_KEY) "
                           "in the server's environment")
    with RUNS_LOCK:
        if _active(RUNS.get(name)):
            raise RuntimeError("the automatic edit is still running")
        if _active(AI_RUNS.get(name)):
            raise RuntimeError("the AI editor is already working on this job")
        argv = [sys.executable, "-u", "-m", "vidmill", "ai", "--job", str(jdir)]
        for skill in selected:
            argv += ["--skill", skill.name]
        argv += ["--", prompt]
        log = jdir / ".ai.log"
        fh = open(log, "wb")
        proc = subprocess.Popen(argv, stdout=fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True,
                                env=dict(os.environ))
        AI_RUNS[name] = {"proc": proc, "log": log, "fh": fh, "closed": False}


def _cancel(name: str) -> bool:
    cancelled = False
    with RUNS_LOCK:
        for runs in (RUNS, AI_RUNS, VISION_RUNS):
            run = runs.get(name)
            if _active(run):
                _kill(run["proc"])
                cancelled = True
    return cancelled


def _vision_file(jdir: Path, filename: str) -> Path:
    """Serve an indexed frame or thumbnail; nothing else inside vision/."""
    rel = Path(filename)
    if (rel.is_absolute() or ".." in rel.parts or not rel.parts
            or rel.parts[0] != "vision"
            or len(rel.parts) < 3 or rel.parts[1] not in ("frames", "assets")
            or rel.suffix.lower() not in IMAGE_EXT):
        raise FileNotFoundError(filename)
    path = (jdir / rel).resolve()
    if jdir.resolve() not in path.parents or not path.is_file():
        raise FileNotFoundError(filename)
    return path


def _vision_result(name: str) -> dict | None:
    """The last --json object a vision run printed, if any.

    The tool prints one indented JSON object, so the payload we want is
    the brace that starts a line and spans to the end of the log.
    """
    text = _log_tail(name, ".vision.log", limit=200000)
    dec = json.JSONDecoder()
    starts = [i for i, ch in enumerate(text) if ch == "{"
              and (i == 0 or text[i - 1] == "\n")]
    for i in reversed(starts[-8:]):
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            continue
        if isinstance(obj, dict) and text[end:].strip() == "":
            return obj
    return None


def _vision_state(name: str) -> dict:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)

    def read(path: Path) -> dict:
        try:
            return util.read_json(path)
        except Exception:
            return {}

    index = read(jdir / "vision/index.json")
    scenes = read(jdir / "vision/scenes.json")
    broll = read(jdir / "vision/broll.json")
    thumbnail = read(jdir / "vision/thumbnail.json")
    with RUNS_LOCK:
        run = VISION_RUNS.get(name)
        running = _active(run)
        if run and not running:
            _close(run)

    def vurl(p: str | None) -> str | None:
        if not p:
            return None
        return ("/vmedia/" + urllib.parse.quote(name, safe="")
                + "/" + urllib.parse.quote(str(p).replace("\\", "/"), safe=""))

    frames = [{
        "id": f.get("id"), "time": f.get("time"), "scene": f.get("scene"),
        "tags": (f.get("tags") or [])[:6],
        "url": vurl(f.get("file")),
    } for f in index.get("frames", [])]
    scenes_list = [{"index": s.get("index"), "start": s.get("start"),
                    "end": s.get("end"), "duration": s.get("duration")}
                   for s in scenes.get("scenes", [])]
    spec = "vision/assets/overlays.json" if (jdir / "vision/assets/overlays.json").exists() else None
    return {
        "name": name,
        "indexed": bool(index),
        "frames": frames,
        "frame_count": len(frames),
        "scenes": scenes_list,
        "scene_count": len(scenes_list),
        "tags": index.get("tags") or {},
        "backend": index.get("backend"),
        "thumbnail": thumbnail or None,
        "thumb_url": vurl("vision/assets/thumbnail.jpg") if thumbnail else None,
        "broll": {
            "count": len(broll.get("suggestions", [])),
            "suggestions": broll.get("suggestions", [])[:12],
            "spec": spec,
        },
        "has_transcript": (jdir / "transcript.json").exists(),
        "running": running,
        "log": _log_tail(name, ".vision.log"),
        "result": _vision_result(name) if run and not running else None,
    }


def _start_vision(name: str, body: dict) -> None:
    jdir = _job_dir(name)
    if not (jdir / "job.json").exists():
        raise FileNotFoundError(name)
    body = body or {}
    action = str(body.get("action") or "").strip().lower()
    if action not in ("scenes", "index", "search", "thumbnail", "broll"):
        raise ValueError("vision action must be scenes, index, search, thumbnail or broll")
    argv = [sys.executable, "-u", "-m", "vidmill", "vision", action,
            "--job", str(jdir), "--json"]
    if action == "index":
        argv += ["--max-frames", str(max(10, min(int(body.get("max_frames") or 120), 400)))]
        argv += ["--semantic", str(body.get("semantic") or "off")]
        if body.get("force"):
            argv.append("--force")
    elif action == "scenes":
        if body.get("force"):
            argv.append("--force")
    elif action == "search":
        q = str(body.get("query") or "").strip()
        if not q:
            raise ValueError("type what to search for")
        argv += [q, "--top", str(max(1, min(int(body.get("top") or 12), 50))),
                 "--semantic", str(body.get("semantic") or "auto")]
    elif action == "thumbnail":
        q = str(body.get("query") or "").strip()
        if q:
            argv.append(q)
        if body.get("at") is not None:
            argv += ["--at", str(body.get("at"))]
        argv += ["--semantic", str(body.get("semantic") or "auto")]
    elif action == "broll":
        argv += ["--extract", "--max", str(max(1, min(int(body.get("max") or 12), 40))),
                 "--semantic", str(body.get("semantic") or "auto")]
        if body.get("library"):
            argv += ["--library", str(body.get("library"))]
    with RUNS_LOCK:
        if _active(RUNS.get(name)):
            raise RuntimeError("the automatic edit is still running")
        if _active(AI_RUNS.get(name)):
            raise RuntimeError("the AI editor is busy with this job")
        if _active(VISION_RUNS.get(name)):
            raise RuntimeError("a vision run is already active")
        log = jdir / ".vision.log"
        fh = open(log, "wb")
        try:
            proc = subprocess.Popen(argv, stdout=fh, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        except Exception:
            fh.close()
            raise
        VISION_RUNS[name] = {"proc": proc, "log": log, "fh": fh, "closed": False}


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
            if parts == ["api", "skills"]:
                return self._json(200, _skills_state())
            if parts[:2] == ["api", "skills"] and len(parts) == 3:
                return self._json(200, _skill_detail(urllib.parse.unquote(parts[2])))
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
                if len(parts) == 4 and parts[3] == "assets":
                    return self._json(200, _assets(name))
                if len(parts) == 4 and parts[3] == "vision":
                    return self._json(200, _vision_state(name))
                if len(parts) == 4 and parts[3] == "timeline":
                    return self._json(200, _timeline(name))
            if parts[0] == "media" and len(parts) == 3:
                return self._media(parts[1], parts[2])
            if parts[0] == "vmedia" and len(parts) == 3:
                return self._vmedia(parts[1], urllib.parse.unquote(parts[2]))
            if parts[0] == "thumb" and len(parts) == 3:
                return self._thumb(parts[1], parts[2])
            if parts[0] == "waveform" and len(parts) == 3:
                return self._waveform(parts[1], parts[2])
            if parts[0] in ("source", "source_thumb", "source_wave") and len(parts) == 2:
                return self._source(parts[1], parts[0])
            self._err(404, "not found")
        except FileNotFoundError as e:
            self._err(404, str(e) or "not found")
        except ValueError as e:
            self._err(400, str(e))
        except Exception as e:  # noqa: BLE001
            self._err(500, f"{type(e).__name__}: {e}")

    def do_POST(self) -> None:
        parts = [p for p in urllib.parse.urlparse(self.path).path.split("/") if p]
        try:
            if parts == ["api", "skills"]:
                return self._json(200, _skill_create(self._body_json()))
            if parts[:2] == ["api", "skills"] and len(parts) == 4 and parts[3] == "reset":
                return self._json(200, _skill_reset(
                    urllib.parse.unquote(parts[2]), self._body_json()))
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
                if action == "vision":
                    _start_vision(name, self._body_json())
                    return self._json(200, {"ok": True})
                if action == "ai":
                    body = self._body_json() or {}
                    _start_ai(name, body.get("prompt", ""), body.get("skills") or [])
                    return self._json(200, {"ok": True})
                if action == "cancel":
                    return self._json(200, {"cancelled": _cancel(name)})
            self._err(404, "not found")
        except FileNotFoundError as e:
            self._err(404, str(e) or "not found")
        except ValueError as e:
            self._err(400, str(e))
        except RuntimeError as e:
            self._err(409, str(e))
        except Exception as e:  # noqa: BLE001
            self._err(500, f"{type(e).__name__}: {e}")

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        q = urllib.parse.parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            if parts[:2] == ["api", "skills"] and len(parts) == 3:
                return self._json(200, _skill_save(
                    urllib.parse.unquote(parts[2]), self._body_json()))
            if parsed.path == "/api/upload":
                if length <= 0:
                    return self._err(400, "empty upload")
                name = _receive_upload((q.get("name") or [""])[0],
                                       (q.get("filename") or [""])[0],
                                       self.rfile, length)
                return self._json(200, {"name": name})
            if parts[:2] == ["api", "jobs"] and len(parts) == 4 and parts[3] == "assets":
                if length <= 0:
                    return self._err(400, "empty upload")
                name = parts[2]
                _job_dir(name)  # validate
                asset = _receive_asset(name, (q.get("filename") or [""])[0],
                                       self.rfile, length)
                return self._json(200, {"name": asset})
            self._err(404, "not found")
        except FileNotFoundError as e:
            self._err(404, str(e) or "not found")
        except ValueError as e:
            self._err(400, str(e))
        except Exception as e:  # noqa: BLE001
            self._err(500, f"{type(e).__name__}: {e}")

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        q = urllib.parse.parse_qs(parsed.query)
        try:
            if parts[:2] == ["api", "skills"] and len(parts) == 3:
                name = urllib.parse.unquote(parts[2])
                scope = (q.get("scope") or ["user"])[0]
                path = skillsmod.remove(name, scope)
                return self._json(200, {"removed": str(path),
                                        "skills": [skillsmod.summary(s)
                                                   for s in skillsmod.discover()]})
            self._err(404, "not found")
        except FileNotFoundError as e:
            self._err(404, str(e) or "not found")
        except ValueError as e:
            self._err(400, str(e))
        except Exception as e:  # noqa: BLE001
            self._err(500, f"{type(e).__name__}: {e}")

    # -------------------------------------------------------------- media
    def _send_file(self, path: Path, ranged: bool = True) -> None:
        size = path.stat().st_size
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if ranged and rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            try:
                start = int(a) if a else 0
                end = int(b) if b else size - 1
            except ValueError:
                start, end = 0, size - 1
            if start >= size or end < start:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            end = min(end, size - 1)
            code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes" if ranged else "none")
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

    def _media(self, name: str, filename: str) -> None:
        jdir = _job_dir(name)
        try:
            path = _job_file(jdir, filename)
        except FileNotFoundError:
            return self._err(404, "not found")
        self._send_file(path)

    def _vmedia(self, name: str, filename: str) -> None:
        jdir = _job_dir(name)
        try:
            path = _vision_file(jdir, filename)
        except FileNotFoundError:
            return self._err(404, "not found")
        self._send_file(path, ranged=False)

    def _thumb(self, name: str, filename: str) -> None:
        jdir = _job_dir(name)
        try:
            src = _job_file(jdir, filename)
            out = _thumb_file(jdir, src)
        except FileNotFoundError:
            return self._err(404, "not found")
        except Exception as e:  # noqa: BLE001
            return self._err(404, f"no preview: {e}")
        self._send_file(out, ranged=False)

    def _waveform(self, name: str, filename: str) -> None:
        jdir = _job_dir(name)
        try:
            src = _job_file(jdir, filename)
            out = _wave_file(jdir, src)
        except FileNotFoundError:
            return self._err(404, "not found")
        except ValueError as e:
            return self._err(404, str(e))
        except Exception as e:  # noqa: BLE001
            return self._err(404, f"no waveform: {e}")
        self._send_file(out, ranged=False)

    def _source(self, name: str, mode: str) -> None:
        """Serve the original video when a project was opened by path.

        Only the exact file recorded in job.json is exposed, and only while it
        still lives outside the job folder.
        """
        jdir = _job_dir(name)
        if not (jdir / "job.json").exists():
            return self._err(404, "job not found")
        src = _external_source(jdir, jobmod.Job.load(jdir))
        if src is None:
            return self._err(404, "no external source")
        if mode == "source":
            return self._send_file(src)
        try:
            out = _thumb_file(jdir, src) if mode == "source_thumb" else _wave_file(jdir, src)
        except ValueError as e:
            return self._err(404, str(e))
        except Exception as e:  # noqa: BLE001
            return self._err(404, f"no preview: {e}")
        self._send_file(out, ranged=False)


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
    old_skills = os.environ.get("VIDMILL_SKILLS_DIR")
    os.environ["VIDMILL_SKILLS_DIR"] = str(ROOT / "skills")
    httpd = _make_server("127.0.0.1", 0)
    port = httpd.server_port
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    def api(path: str, method: str = "GET", payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            base + path, data=data, method=method,
            headers={"Content-Type": "application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)

    try:
        with urllib.request.urlopen(base + "/", timeout=10) as r:
            body = r.read().decode()
            assert r.status == 200 and "<!doctype html" in body.lower(), "bad index"
            assert "Remove watermark" in body and "Ask AI" in body, "ui sections missing"
            for part in ("Media bin", "Timeline", "AI editor", "assetGrid", "tlInner",
                         "modalSkills", "skillList", "btnSkills", "visionList",
                         "btnVisionIndex", "visionQuery"):
                assert part in body, f"studio ui missing {part}"
        with urllib.request.urlopen(base + "/api/jobs", timeout=10) as r:
            jobs = json.load(r)
            assert jobs == [], jobs
        skills = api("/api/skills")
        assert skills["count"] >= 9, skills
        assert any(s["name"] == "tight-cut" for s in skills["skills"]), skills
        made = api("/api/skills", "POST", {
            "name": "self-test-skill",
            "description": "Temporary skill used by the web self-test.",
            "body": "# Self test\n\nDo not use this skill.",
            "tags": ["test"],
            "scope": "user",
        })
        assert made["skill"]["source"] == "user", made
        detail = api("/api/skills/self-test-skill")
        assert "Self test" in detail["skill"]["body"], detail
        api("/api/skills/self-test-skill", "PUT", {
            "description": "Edited temporary skill.",
            "body": "# Self test\n\nEdited body.",
        })
        reset = api("/api/skills/self-test-skill/reset", "POST", {"scope": "user"})
        assert reset["removed"] and reset["skill"] is None, reset
        try:
            api("/api/skills/self-test-skill")
            raise AssertionError("removed skill still exists")
        except urllib.error.HTTPError as e:
            assert e.code == 404, e.code
        api("/api/skills", "POST", {
            "name": "self-test-skill", "description": "Temporary skill.",
            "body": "# Temporary\n\nDelete me.", "scope": "user"})
        deleted = api("/api/skills/self-test-skill?scope=user", "DELETE")
        assert deleted["removed"], deleted
        try:
            urllib.request.urlopen(base + "/api/jobs/..%2Fescape", timeout=5)
            raise AssertionError("path traversal not blocked")
        except urllib.error.HTTPError as e:
            assert e.code in (400, 404), e.code

        # vision api: scene detection on a generated fixture, end to end
        fixture = ROOT / "selftest-fixture.mp4"
        util.run([util.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
                  "-f", "lavfi", "-i", "color=c=0xFF0000:s=256x144:d=2:r=24",
                  "-f", "lavfi", "-i", "color=c=0x0000FF:s=256x144:d=2:r=24",
                  "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]",
                  "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                  "-nostdin", str(fixture)], check=True, quiet=True)
        made = api("/api/jobs", "POST", {"path": str(fixture), "name": "selftest-vision"})
        vname = made["name"]
        api("/api/jobs/" + urllib.parse.quote(vname) + "/vision", "POST", {"action": "scenes"})
        st = {}
        deadline = time.time() + 90
        while True:
            st = api("/api/jobs/" + urllib.parse.quote(vname) + "/vision")
            if not st.get("running"):
                break
            if time.time() > deadline:
                raise AssertionError("vision self-test timed out")
            time.sleep(0.4)
        assert st.get("scene_count", 0) >= 2, st
        assert st.get("scenes"), st
        assert not st.get("indexed"), st
        try:
            urllib.request.urlopen(base + "/vmedia/" + urllib.parse.quote(vname) +
                                   "/vision/frames/nope.jpg", timeout=5)
            raise AssertionError("missing vision media still served")
        except urllib.error.HTTPError as e:
            assert e.code == 404, e.code

        print(f"web ui self-test OK: HTTP 200, {len(body)} bytes, "
              f"api + skills + sandbox + vision checks passed")
    finally:
        httpd.shutdown()
        httpd.server_close()
        if old_skills is None:
            os.environ.pop("VIDMILL_SKILLS_DIR", None)
        else:
            os.environ["VIDMILL_SKILLS_DIR"] = old_skills
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
