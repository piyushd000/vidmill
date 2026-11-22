"""Native vision primitives for vidmill.

No cloud calls, no OpenCLIP dependency. Scene cuts are found from
low-resolution RGB signatures decoded with ffmpeg; frames are sampled at
scene midpoints; optional image-text embeddings add semantic search.
Everything here is deterministic and writes plain files into the job.
"""

from __future__ import annotations

import hashlib
import math
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import ToolError, util

VISION_DIR = "vision"
FRAMES_DIR = "vision/frames"
ASSETS_DIR = "vision/assets"
SCENES_FILE = "vision/scenes.json"
INDEX_FILE = "vision/index.json"
EMBEDDINGS_FILE = "vision/embeddings.json"
BROLL_FILE = "vision/broll.json"
THUMB_FILE = "vision/assets/thumbnail.jpg"

SAMPLE_WIDTH = 64
SAMPLE_HEIGHT = 36
DEFAULT_FPS = 4.0
DEFAULT_THRESHOLD = 0.35
DEFAULT_MIN_SCENE = 0.8
DEFAULT_MAX_FRAMES = 120
DEFAULT_INTERVAL = 5.0

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
    "could", "did", "do", "does", "for", "from", "had", "has", "have", "he",
    "her", "here", "him", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "just", "like", "me", "my", "no", "not", "now", "of", "on", "one",
    "or", "our", "out", "really", "she", "so", "some", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "to", "too",
    "up", "us", "very", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your",
}

# Labels chosen for editing decisions, not benchmark classes.
DEFAULT_LABELS = [
    "talking head", "person", "two people", "crowd", "hands", "close-up face",
    "computer screen", "phone screen", "text or graphic", "product", "food",
    "nature", "city", "indoor", "outdoor", "wide shot", "interview",
    "presentation", "logo", "animation", "dark scene", "bright scene",
    "vehicle", "animal", "sports", "music performance", "chart or graph",
    "map", "document", "white background", "home interior", "office",
    "street", "sky", "water", "screen recording",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _np():
    try:
        import numpy as np
        return np
    except ImportError as e:
        raise ToolError("numpy is required for vision scene detection — pip install numpy") from e


def _pil():
    try:
        from PIL import Image, ImageFilter, ImageStat
        return Image, ImageFilter, ImageStat
    except ImportError as e:
        raise ToolError("Pillow is required for frame analysis — pip install pillow") from e


# --------------------------------------------------------------- scene cuts

def _signature(frame: bytes, w: int, h: int) -> tuple:
    np = _np()
    a = np.frombuffer(frame, dtype=np.uint8).reshape(h, w, 3).astype(np.float32)
    hist = []
    for c in range(3):
        counts = np.bincount((a[:, :, c] // 16).astype(np.int32).ravel(), minlength=16)
        hist.append(counts.astype(np.float32) / max(1.0, float(counts.sum())))
    bh, bw = h // 4, w // 4
    blocks = a[:bh * 4, :bw * 4].reshape(4, bh, 4, bw, 3).mean(axis=(1, 3))
    return hist, blocks


def detect_scenes(video: Path, fps: float = DEFAULT_FPS,
                  threshold: float = DEFAULT_THRESHOLD,
                  min_scene: float = DEFAULT_MIN_SCENE,
                  width: int = SAMPLE_WIDTH) -> dict:
    """Detect hard cuts from RGB histograms plus coarse spatial change.

    Sampling at 4 fps keeps this fast even for long files. Cuts are
    reported at the first sampled frame after the change, so the time is
    accurate to about 1/fps. `min_scene` suppresses rapid-fire flicker and
    merges cuts that are too close to be useful edit points.
    """
    np = _np()
    video = Path(video).expanduser().resolve()
    if not video.exists():
        raise ToolError(f"video not found: {video}")
    info = util.probe_info(video)
    if not info.get("has_video"):
        raise ToolError(f"no video stream in {video}")
    fps = max(0.5, min(float(fps or DEFAULT_FPS), 12.0))
    threshold = max(0.05, min(float(threshold), 0.95))
    min_scene = max(0.2, float(min_scene))
    width = max(32, min(int(width), 160))
    height = max(18, int(round(width * 9 / 16 / 2)) * 2)
    duration = float(info.get("duration") or 0)

    cmd = [util.FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin",
           "-i", str(video), "-an", "-sn",
           "-vf", f"fps={fps},scale={width}:{height}:flags=area,format=rgb24",
           "-f", "rawvideo", "-"]
    frame_bytes = width * height * 3
    stderr = tempfile.TemporaryFile()
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr)
    except FileNotFoundError as e:
        raise ToolError("ffmpeg not found — install ffmpeg first") from e

    prev = None
    times: list[float] = []
    scores: list[float] = []
    n = 0
    try:
        while True:
            buf = proc.stdout.read(frame_bytes) if proc.stdout else b""
            if not buf or len(buf) < frame_bytes:
                break
            hist, blocks = _signature(buf, width, height)
            if prev is not None:
                ph, pb = prev
                histd = 1.0 - float(np.minimum(ph, hist).sum(axis=1).mean())
                blockd = float(np.abs(blocks - pb).mean())
                score = 0.65 * histd + 0.35 * min(1.0, blockd / 80.0)
                times.append(n / fps)
                scores.append(round(score, 5))
            prev = (hist, blocks)
            n += 1
    finally:
        try:
            if proc.stdout:
                proc.stdout.close()
        except Exception:
            pass
        rc = proc.wait()
        stderr.seek(0)
        err = stderr.read().decode("utf-8", "replace").strip()
        stderr.close()
    if rc != 0:
        raise ToolError(f"ffmpeg could not decode {video.name}: {err[-1200:]}")
    if n == 0:
        raise ToolError(f"no frames decoded from {video.name}")

    if duration <= 0:
        duration = n / fps
    # Only cuts that leave a usable scene on both sides.
    candidates = [(t, s) for t, s in zip(times, scores)
                  if s >= threshold and t >= min_scene and duration - t >= 0.15]
    cuts: list[dict] = []
    for t, s in candidates:
        if cuts and t - cuts[-1]["time"] < min_scene:
            if s > cuts[-1]["score"]:
                cuts[-1] = {"time": round(t, 3), "score": s}
            continue
        cuts.append({"time": round(t, 3), "score": s})

    bounds = [0.0] + [c["time"] for c in cuts] + [round(duration, 3)]
    scenes = []
    for i in range(len(bounds) - 1):
        start, end = bounds[i], bounds[i + 1]
        if end - start <= 0.01:
            continue
        scenes.append({
            "index": len(scenes),
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
        })
    return {
        "version": 1,
        "created": now(),
        "video": {
            "path": str(video), "duration": round(duration, 3),
            "width": info.get("width"), "height": info.get("height"),
            "fps": info.get("fps"), "size_bytes": info.get("size_bytes"),
            "mtime": round(video.stat().st_mtime, 3),
        },
        "method": "rgb-histogram+block-change",
        "sample_fps": fps,
        "sample_size": [width, height],
        "threshold": threshold,
        "min_scene": min_scene,
        "cuts": cuts,
        "scenes": scenes,
    }


def fingerprint(video: Path) -> dict:
    p = Path(video).expanduser().resolve()
    info = util.probe_info(p)
    return {
        "path": str(p),
        "size_bytes": info.get("size_bytes"),
        "mtime": round(p.stat().st_mtime, 3),
        "duration": round(float(info.get("duration") or 0), 3),
    }


def same_video(data: dict, video: Path) -> bool:
    v = data.get("video") or {}
    try:
        fp = fingerprint(video)
    except Exception:
        return False
    return (v.get("path") == fp["path"]
            and int(v.get("size_bytes") or -1) == int(fp["size_bytes"] or -2)
            and abs(float(v.get("mtime") or 0) - float(fp["mtime"] or -1)) < 0.01)


def frame_times(duration: float, scenes: list[dict],
                max_frames: int = DEFAULT_MAX_FRAMES,
                interval: float = DEFAULT_INTERVAL) -> list[float]:
    """One or more useful frames per scene, capped and evenly spread."""
    duration = max(0.0, float(duration))
    max_frames = max(1, int(max_frames))
    interval = max(0.5, float(interval))
    if duration <= 0:
        return []
    times: list[float] = []
    if scenes:
        for s in scenes:
            start, end = float(s["start"]), float(s["end"])
            length = max(0.001, end - start)
            count = max(1, int(round(length / interval))) if length > interval * 1.4 else 1
            for j in range(count):
                times.append(start + (j + 0.5) * length / count)
    else:
        count = max(1, int(math.ceil(duration / interval)))
        for j in range(count):
            times.append((j + 0.5) * duration / count)
    times = [t for t in times if 0.01 < t < duration - 0.01] or [min(duration / 2, 0.5)]
    if len(times) > max_frames:
        idx = [round(i * (len(times) - 1) / (max_frames - 1)) for i in range(max_frames)] \
            if max_frames > 1 else [len(times) // 2]
        times = [times[i] for i in sorted(set(idx))]
    return [round(t, 3) for t in times]


def extract_frame(video: Path, time: float, out: Path, width: int = 640) -> Path:
    """Extract one accurate-enough frame, never upscaling the source."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    width = max(64, int(width))
    vf = f"scale='min({width},iw)':-2:flags=lanczos"
    args = [util.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
            "-ss", f"{max(0.0, float(time)):.3f}", "-i", str(video),
            "-map", "0:v:0", "-frames:v", "1", "-vf", vf, "-q:v", "3",
            "-nostdin", str(out)]
    p = util.run(args, check=False, quiet=True)
    if p.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        # Some containers dislike input seeking; retry with output seeking.
        args = [util.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
                "-i", str(video), "-ss", f"{max(0.0, float(time)):.3f}",
                "-map", "0:v:0", "-frames:v", "1", "-vf", vf, "-q:v", "3",
                "-nostdin", str(out)]
        p = util.run(args, check=False, quiet=True)
    if p.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        tail = ((p.stderr or "") + (p.stdout or ""))[-800:]
        raise ToolError(f"could not extract frame at {time:.2f}s from {video.name}: {tail}")
    return out


# ------------------------------------------------------------- frame stats

def analyze_image(path: Path) -> dict:
    """Cheap visual facts that are useful for editing and always free."""
    np = _np()
    Image, _, _ = _pil()
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            small = im.resize((80, 45), Image.Resampling.BILINEAR)
            a = np.asarray(small, dtype=np.float32)
    except Exception as e:
        raise ToolError(f"could not analyse {path}: {e}") from e
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    sat = np.where(mx > 1, (mx - mn) / np.maximum(mx, 1), 0)
    gy = np.abs(np.diff(luma, axis=0)).mean() if luma.shape[0] > 1 else 0
    gx = np.abs(np.diff(luma, axis=1)).mean() if luma.shape[1] > 1 else 0
    brightness = float(luma.mean())
    contrast = float(luma.std())
    saturation = float(sat.mean())
    warmth = float(r.mean() - b.mean())
    sharpness = float(min(1.0, (gx + gy) / 24.0))
    colorfulness = float(min(1.0, (np.abs(r - g).mean() + np.abs(g - b).mean() +
                                    np.abs(r - b).mean()) / 120.0))
    tags: list[str] = []
    if brightness < 55:
        tags.append("dark")
    elif brightness > 205:
        tags.append("bright")
    else:
        tags.append("normal exposure")
    if saturation < 0.10:
        tags.append("monochrome")
    elif saturation > 0.45:
        tags.append("saturated")
    if warmth > 18:
        tags.append("warm")
    elif warmth < -18:
        tags.append("cool")
    if g.mean() - max(r.mean(), b.mean()) > 12:
        tags.append("green")
    if b.mean() - max(r.mean(), g.mean()) > 12:
        tags.append("blue")
    if r.mean() - max(g.mean(), b.mean()) > 18:
        tags.append("red")
    if contrast > 62:
        tags.append("high contrast")
    if sharpness > 0.38:
        tags.append("sharp")
    elif sharpness < 0.10:
        tags.append("soft focus")
    h, w = a.shape[:2]
    orientation = "landscape" if w > h * 1.08 else ("portrait" if h > w * 1.08 else "square")
    return {
        "brightness": round(brightness, 1),
        "contrast": round(contrast, 1),
        "saturation": round(saturation, 3),
        "warmth": round(warmth, 1),
        "sharpness": round(sharpness, 3),
        "colorfulness": round(colorfulness, 3),
        "mean_rgb": [round(float(x), 1) for x in (r.mean(), g.mean(), b.mean())],
        "orientation": orientation,
        "tags": tags,
    }


# ------------------------------------------------------------------- text

def keywords(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", (text or "").lower())
    out: list[str] = []
    for w in words:
        w = w.strip("'-")
        if len(w) < 3 or w in STOPWORDS:
            continue
        if w.endswith("'s"):
            w = w[:-2]
        if len(w) > 5 and w.endswith("ing"):
            w = w[:-3]
        elif len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        if w and w not in out:
            out.append(w)
        if len(out) >= limit:
            break
    return out


def load_transcript(job_path: Path) -> dict:
    p = Path(job_path) / "transcript.json"
    if not p.exists():
        return {}
    try:
        return util.read_json(p)
    except Exception:
        return {}


def transcript_context(job_path: Path, start: float, end: float,
                       pad: float = 1.2, transcript: dict | None = None) -> str:
    data = transcript if transcript is not None else load_transcript(job_path)
    if not data:
        return ""
    lo, hi = max(0.0, start - pad), end + pad
    words: list[str] = []
    for seg in data.get("segments", []):
        for w in seg.get("words") or []:
            t = float(w.get("start", 0) or 0)
            if lo <= t <= hi and w.get("word"):
                words.append(str(w["word"]).strip())
    if not words:
        for seg in data.get("segments", []):
            a = float(seg.get("start", 0) or 0)
            b = float(seg.get("end", a) or a)
            if b >= lo and a <= hi:
                words.append(str(seg.get("text") or "").strip())
    text = " ".join(w for w in words if w).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:280]


# ------------------------------------------------------------------ index

def load_index(job_path: Path) -> dict:
    p = Path(job_path) / INDEX_FILE
    if not p.exists():
        return {}
    try:
        return util.read_json(p)
    except Exception as e:
        raise ToolError(f"vision index is unreadable: {e}") from e


def load_embeddings(job_path: Path) -> dict:
    p = Path(job_path) / EMBEDDINGS_FILE
    if not p.exists():
        return {}
    try:
        return util.read_json(p)
    except Exception:
        return {}


def index_frames(job_path: Path, data: dict) -> dict[str, dict]:
    return {f["id"]: f for f in data.get("frames", []) if f.get("id")}


def tag_summary(frames: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in frames:
        for tag in f.get("tags") or []:
            out.setdefault(str(tag), []).append(f["id"])
    return dict(sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0])))


def lexical_score(query: str, doc: str) -> float:
    q = set(keywords(query, 20))
    if not q:
        return 0.0
    d = set(keywords(doc, 80))
    if not d:
        return 0.0
    hit = len(q & d) / len(q)
    # Reward exact phrase matches; useful for "red car" vs unrelated words.
    phrase = 1.0 if query.strip().lower() in (doc or "").lower() and len(query.strip()) > 2 else 0.0
    return round(min(1.0, 0.85 * hit + 0.15 * phrase), 4)


def cosine_scores(query_vector, vectors: list[list[float]]) -> list[float]:
    np = _np()
    if not vectors:
        return []
    q = np.asarray(query_vector, dtype=np.float32).reshape(-1)
    m = np.asarray(vectors, dtype=np.float32)
    n = np.linalg.norm(m, axis=1) * max(1e-9, float(np.linalg.norm(q)))
    return [round(float(x), 5) for x in (m @ q) / n]


def quality_score(stats: dict, time: float, duration: float) -> float:
    if not stats:
        return 0.0
    sharp = float(stats.get("sharpness") or 0)
    contrast = min(1.0, float(stats.get("contrast") or 0) / 64.0)
    bright = max(0.0, 1.0 - abs(float(stats.get("brightness") or 0) - 145.0) / 145.0)
    sat = min(1.0, float(stats.get("saturation") or 0) / 0.5)
    edge = 1.0 if 0.25 <= time <= max(0.3, duration - 0.25) else 0.55
    return round((0.42 * sharp + 0.22 * contrast + 0.22 * bright + 0.14 * sat) * edge, 4)


# ----------------------------------------------------------- B-roll library

def _artifact_names(job) -> set[str]:
    return set((job.data.get("artifacts") or {}).keys())


def media_files(job, library: Path | None = None, limit: int = 300) -> list[Path]:
    """Images/videos available for B-roll, excluding the edit itself."""
    current = set()
    try:
        current.add(job.current_video().resolve())
    except Exception:
        pass
    src = Path(job.data.get("video", "")).expanduser()
    try:
        if src.exists():
            current.add(src.resolve())
    except OSError:
        pass
    skip = _artifact_names(job) | {"job.json", "probe.json", "transcript.json",
                                   "transcript.srt", "cut_plan.json", "captions.ass"}
    found: list[Path] = []
    roots = [Path(library).expanduser().resolve()] if library else [job.path]
    for root in roots:
        if not root.exists():
            continue
        it = root.rglob("*") if library else root.iterdir()
        for p in it:
            if len(found) >= limit:
                break
            try:
                if not p.is_file() or p.name.startswith("."):
                    continue
                if "vision" in p.parts or p.name in skip:
                    continue
                if p.suffix.lower() not in IMAGE_EXT | VIDEO_EXT:
                    continue
                if p.resolve() in current:
                    continue
                found.append(p.resolve())
            except OSError:
                continue
    return sorted(found, key=lambda p: (p.suffix.lower() not in VIDEO_EXT, str(p).lower()))


def _hash(text: str, n: int = 8) -> str:
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:n]


def library_candidates(job, library: Path | None = None) -> list[dict]:
    """Preview frames for external images/videos, without semantic work."""
    out: list[dict] = []
    preview_dir = job.path / ASSETS_DIR / "library"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for p in media_files(job, library):
        try:
            info = util.probe_info(p)
        except Exception:
            continue
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", p.stem)[:36] or "media"
        key = _hash(str(p))
        if p.suffix.lower() in IMAGE_EXT:
            preview = preview_dir / f"{stem}-{key}.jpg"
            try:
                if not preview.exists():
                    extract_frame(p, 0, preview, 480)
            except Exception:
                continue
            stats = analyze_image(preview)
            out.append({
                "id": f"img-{key}",
                "kind": "image",
                "path": str(p),
                "time": None,
                "preview": str(preview),
                "label": p.stem.replace("_", " ").replace("-", " "),
                "tags": keywords(p.stem) + stats.get("tags", [])[:3],
                "stats": stats,
                "duration": None,
            })
        else:
            dur = float(info.get("duration") or 0)
            if dur <= 0.2:
                continue
            for j, frac in enumerate((0.12, 0.5, 0.88)):
                t = max(0.05, min(dur - 0.05, dur * frac))
                preview = preview_dir / f"{stem}-{key}-{j}.jpg"
                try:
                    if not preview.exists():
                        extract_frame(p, t, preview, 480)
                except Exception:
                    continue
                stats = analyze_image(preview)
                out.append({
                    "id": f"vid-{key}-{j}",
                    "kind": "video",
                    "path": str(p),
                    "time": round(t, 3),
                    "preview": str(preview),
                    "label": p.stem.replace("_", " ").replace("-", " "),
                    "tags": keywords(p.stem) + stats.get("tags", [])[:3],
                    "stats": stats,
                    "duration": round(dur, 3),
                })
    return out


def scene_candidates(index: dict, job_path: Path | None = None) -> list[dict]:
    """Indexed frames, with the scene range they came from."""
    scenes = {int(s["index"]): s for s in index.get("scenes", [])}
    root = Path(job_path) if job_path else Path(index.get("video", {}).get("path", "")).parent
    out = []
    for f in index.get("frames", []):
        s = scenes.get(int(f.get("scene", -1)), {})
        out.append({
            "id": "frame-" + f["id"],
            "kind": "scene",
            "path": index.get("video", {}).get("path"),
            "time": f.get("time"),
            "preview": str((root / f["file"]).resolve()),
            "label": f"scene {int(f.get('scene', 0)) + 1}",
            "tags": f.get("tags", []),
            "stats": f.get("stats") or {},
            "dialogue": f.get("dialogue") or "",
            "start": s.get("start"),
            "end": s.get("end"),
            "duration": index.get("video", {}).get("duration"),
        })
    return out


def candidate_text(c: dict) -> str:
    bits = [c.get("label") or "", Path(c.get("path") or "").stem, c.get("dialogue") or ""]
    bits += list(c.get("tags") or [])
    return " ".join(str(b) for b in bits if b)


def extract_clip(video: Path, start: float, seconds: float, out: Path,
                 width: int | None = None, height: int | None = None,
                 fps: float = 30.0) -> Path:
    """Cut a silent B-roll clip; the main audio stays underneath."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seconds = max(0.3, float(seconds))
    vf = "setsar=1,format=yuv420p"
    if width and height:
        vf = (f"scale={int(width)}:{int(height)}:force_original_aspect_ratio=increase,"
              f"crop={int(width)}:{int(height)},{vf}")
    args = [util.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
            "-ss", f"{max(0.0, float(start)):.3f}", "-i", str(video),
            "-t", f"{seconds:.3f}", "-an", "-sn", "-vf", vf,
            "-r", str(max(1.0, float(fps))), "-c:v", "libx264", "-crf", "20",
            "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-nostdin", str(out)]
    util.run(args, check=True, quiet=True)
    if not out.exists() or out.stat().st_size == 0:
        raise ToolError(f"could not extract B-roll clip from {video.name}")
    return out


def image_clip(image: Path, seconds: float, out: Path, width: int, height: int,
               fps: float = 30.0) -> Path:
    """Turn a still into a silent clip that fits the main frame."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (f"scale={int(width)}:{int(height)}:force_original_aspect_ratio=increase,"
          f"crop={int(width)}:{int(height)},setsar=1,format=yuv420p")
    args = [util.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
            "-loop", "1", "-t", f"{max(0.3, float(seconds)):.3f}", "-i", str(image),
            "-vf", vf, "-r", str(max(1.0, float(fps))), "-an",
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-nostdin", str(out)]
    util.run(args, check=True, quiet=True)
    return out


# ------------------------------------------------------------------ output

def rel(job_path: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(job_path).resolve()))
    except Exception:
        return str(path)
