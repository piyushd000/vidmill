"""Tool: overlay — images, logos/watermarks and B-roll onto the video.

  vmill overlay --job myedit --image logo.png --position top-right --scale 0.15
  vmill overlay --job myedit --image bug.png --at 2 --to 6 --fade 0.3
  vmill overlay --job myedit --video broll.mp4 --mode pip --at 5 --to 11
  vmill overlay --job myedit --video broll.mp4 --mode cutaway --at 5 --to 11
  vmill overlay --job myedit --spec overlays.json      # several in one go

Each pass writes overlay_1.mp4, overlay_2.mp4, ... and rebinds the
job's current video, so captions / export / further overlays chain on
top of it. Modes:

  image    picture or logo over the video (position, scale, opacity,
           time window, alpha fade in/out)
  pip      B-roll as picture-in-picture in a time window (main audio
           kept; B-roll loops if shorter than the window)
  cutaway  B-roll replaces the full frame in a time window (main audio
           kept underneath; frame is scaled+cropped to fit)

`--spec` accepts a JSON file: {"overlays": [ {...}, ... ]} with the
same keys as the flags (image/video, mode, position, scale, opacity,
at, to, fade, margin).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import job as jobmod
from .. import util

PURPOSE = "overlay images, logos and B-roll (pip or cutaway) onto the video"

PRESETS = ("top-left", "top-right", "bottom-left", "bottom-right", "center")


# ------------------------------------------------------------------ helpers

def parse_time(v, default=None):
    """Accept seconds (12, '12.5') or clock time ('1:02', '0:01:02')."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return default
    if ":" in s:
        try:
            parts = [float(p) for p in s.split(":")]
        except ValueError:
            raise util.ToolError(f"bad time '{s}'")
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        raise util.ToolError(f"bad time '{s}'")
    try:
        return float(s)
    except ValueError:
        raise util.ToolError(f"bad time '{s}'")


def _resolve(p, j) -> Path:
    path = Path(str(p)).expanduser()
    if path.exists():
        return path.resolve()
    alt = j.path / path
    if alt.exists():
        return alt.resolve()
    raise util.ToolError(f"media not found: {p}")


def _xy(pos: str, W: int, H: int, w: int, h: int, margin: int) -> tuple[str, str]:
    """Position preset or a raw 'X:Y' expression (W,H,w,h available)."""
    if pos == "top-left":
        return f"{margin}", f"{margin}"
    if pos == "top-right":
        return f"W-w-{margin}", f"{margin}"
    if pos == "bottom-left":
        return f"{margin}", f"H-h-{margin}"
    if pos == "bottom-right":
        return f"W-w-{margin}", f"H-h-{margin}"
    if pos == "center":
        return "(W-w)/2", "(H-h)/2"
    if ":" in pos:
        x, _, y = pos.partition(":")
        return x.strip() or "0", y.strip() or "0"
    raise util.ToolError(
        f"unknown position '{pos}' — use one of {', '.join(PRESETS)} or 'X:Y'")


def _fades(at: float, to, fade: float) -> str:
    """Alpha fade in/out on the overlay's own stream (its t == main t)."""
    if fade <= 0:
        return ""
    out = ""
    if at > 0:
        out += f",fade=t=in:st={at:.3f}:d={fade:.3f}:alpha=1"
    if to is not None and to - at > fade:
        out += f",fade=t=out:st={max(at, to - fade):.3f}:d={fade:.3f}:alpha=1"
    return out


def _enable(at: float, to) -> str:
    if at <= 0 and to is None:
        return ""
    end = f"{to:.3f}" if to is not None else "1e7"
    return f":enable='between(t,{at:.3f},{end})'"


# ------------------------------------------------------------- spec runners

def _image_pass(j, src: Path, spec: dict, info: dict, out: Path) -> None:
    W, H = info["width"], info["height"]
    dur = info["duration"]
    at = parse_time(spec.get("at"), 0.0) or 0.0
    to = parse_time(spec.get("to"), None)
    if to is not None and to > dur:
        to = dur
    fade = float(spec.get("fade", 0) or 0)
    opacity = min(1.0, max(0.05, float(spec.get("opacity", 1) or 1)))
    margin = int(spec.get("margin") or max(8, round(0.04 * W)))
    scale = float(spec.get("scale", 0.15) or 0.15)
    tw = max(16, int(W * scale))

    image = _resolve(spec["image"], j)
    x, y = _xy(spec.get("position", "top-right"), W, H, tw, 0, margin)
    start_pad = f",tpad=start_duration={at:.3f}:start_mode=add:color=black@0" if at > 0 else ""
    fc = (
        f"[1:v]format=rgba,scale={tw}:-2,colorchannelmixer=aa={opacity:.2f}"
        f"{start_pad}{_fades(at, to, fade)}[ov];"
        f"[0:v][ov]overlay=x={x}:y={y}{_enable(at, to)}:shortest=1[vout]"
    )
    args = ["-loop", "1", "-t", f"{dur + 0.5:.3f}", "-i", str(image),
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "0:a?",
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "copy",
            "-movflags", "+faststart"]
    util.run_ffmpeg(src, args, out)
    return {"kind": "image", "media": image.name, "position": spec.get("position"),
            "scale": scale, "opacity": opacity, "at": at, "to": to, "fade": fade}


def _pip_pass(j, src: Path, spec: dict, info: dict, out: Path) -> None:
    W, H = info["width"], info["height"]
    dur = info["duration"]
    at = parse_time(spec.get("at"), 0.0) or 0.0
    to = parse_time(spec.get("to"), None)
    if to is None:
        to = dur
    to = min(to, dur)
    if to - at < 0.2:
        raise util.ToolError(f"pip window too short ({to - at:.2f}s)")
    fade = float(spec.get("fade", 0) or 0)
    margin = int(spec.get("margin") or max(8, round(0.04 * W)))
    scale = float(spec.get("scale", 0.3) or 0.3)
    tw = max(16, int(W * scale))

    broll = _resolve(spec["video"], j)
    x, y = _xy(spec.get("position", "bottom-right"), W, H, tw, 0, margin)
    start_pad = f",tpad=start_duration={at:.3f}:start_mode=add:color=black@0" if at > 0 else ""
    fc = (
        f"[1:v]format=rgba,scale={tw}:-2{start_pad}{_fades(at, to, fade)}[ov];"
        f"[0:v][ov]overlay=x={x}:y={y}{_enable(at, to)}:shortest=1[vout]"
    )
    args = ["-stream_loop", "-1", "-t", f"{dur + 0.5:.3f}", "-i", str(broll),
            "-filter_complex", fc,
            "-map", "[vout]", "-map", "0:a?",
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "copy",
            "-movflags", "+faststart"]
    util.run_ffmpeg(src, args, out)
    return {"kind": "pip", "media": broll.name, "position": spec.get("position"),
            "scale": scale, "at": at, "to": to, "fade": fade}


def _cutaway_pass(j, src: Path, spec: dict, info: dict, out: Path) -> None:
    W, H = info["width"] or 1920, info["height"] or 1080
    fps = info.get("fps") or 30
    dur = info["duration"]
    at = parse_time(spec.get("at"), 0.0) or 0.0
    broll = _resolve(spec["video"], j)
    binfo = util.probe_info(broll)
    to = parse_time(spec.get("to"), min(dur, at + binfo["duration"]))
    to = min(to, dur)
    if to - at < 0.2:
        raise util.ToolError(f"cutaway window too short ({to - at:.2f}s)")
    win = to - at
    pre, tail = at > 0.05, dur - to > 0.05

    norm = f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p"
    broll_piece = (f"[1:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,"
                   f"crop={W}:{H},setsar=1,format=yuv420p,"
                   f"trim=start=0:end={win:.3f},setpts=PTS-STARTPTS[c1]")
    if not pre and not tail:
        fc = f"[1:v]{norm},trim=start=0:end={win:.3f},setpts=PTS-STARTPTS[vout]"
        vmap = "[vout]"
    else:
        parts = [f"[0:v]{norm}[m]"]
        pieces = []
        if pre and tail:
            parts.append("[m]split=2[mp][mt]")
            parts.append(f"[mp]trim=start=0:end={at:.3f},setpts=PTS-STARTPTS[c0]")
            parts.append(f"[mt]trim=start={to:.3f},setpts=PTS-STARTPTS[c2]")
            pieces.append("[c0]")
        elif pre:
            parts.append("[m]split=2[mp][mb]")
            parts.append(f"[mp]trim=start=0:end={at:.3f},setpts=PTS-STARTPTS[c0]")
            pieces.append("[c0]")
        elif tail:
            parts.append("[m]split=2[mb][mt]")
            parts.append(f"[mt]trim=start={to:.3f},setpts=PTS-STARTPTS[c2]")
        parts.append(broll_piece)
        pieces.append("[c1]")
        if tail:
            pieces.append("[c2]")
        parts.append("".join(pieces) + f"concat=n={len(pieces)}:v=1:a=0[vout]")
        fc = ";".join(parts)
        vmap = "[vout]"

    args = ["-stream_loop", "-1", "-t", f"{win + 0.5:.3f}", "-i", str(broll),
            "-filter_complex", fc,
            "-map", vmap, "-map", "0:a?",
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-c:a", "copy",
            "-movflags", "+faststart"]
    util.run_ffmpeg(src, args, out)
    return {"kind": "cutaway", "media": broll.name, "at": at, "to": to,
            "broll_duration": binfo["duration"]}


# ----------------------------------------------------------------- plumbing

def _next_name(j) -> str:
    n = 1
    arts = j.data.get("artifacts", {})
    while (j.apath(f"overlay_{n}.mp4")).exists() or f"overlay_{n}.mp4" in arts:
        n += 1
    return f"overlay_{n}.mp4"


def _specs(args, j) -> list[dict]:
    if args.spec:
        path = _resolve(args.spec, j)
        data = util.read_json(path)
        specs = data.get("overlays", data if isinstance(data, list) else [])
        if not specs:
            raise util.ToolError(f"{path.name} has no overlays")
        return specs
    spec: dict = {}
    if args.image:
        spec["image"] = args.image
    if args.video:
        spec["video"] = args.video
        spec["mode"] = args.mode
    if not spec:
        raise util.ToolError(
            "overlay needs --image, --video or --spec (see `vmill overlay --help`)")
    for key, val in [("position", args.position), ("scale", args.scale),
                     ("opacity", args.opacity), ("at", args.at), ("to", args.to),
                     ("fade", args.fade), ("margin", args.margin)]:
        if val is not None:
            spec[key] = val
    return [spec]


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--image", help="image/logo/watermark to overlay")
    p.add_argument("--video", help="B-roll video (pip or cutaway)")
    p.add_argument("--mode", choices=["pip", "cutaway"], default="pip",
                   help="B-roll style: picture-in-picture or full-frame cutaway")
    p.add_argument("--position", help=f"{'/'.join(PRESETS)} or X:Y (image/pip)")
    p.add_argument("--scale", type=float, help="overlay width as fraction of video width")
    p.add_argument("--opacity", type=float, help="image opacity 0.05..1")
    p.add_argument("--at", help="start time (s or M:SS)")
    p.add_argument("--to", help="end time (s or M:SS)")
    p.add_argument("--fade", type=float, help="alpha fade in/out seconds (image/pip)")
    p.add_argument("--margin", type=int, help="edge margin in pixels (default 4%% of width)")
    p.add_argument("--spec", help="json file with a list of overlay specs")
    p.add_argument("--in", dest="in_artifact", help="video to overlay onto (default: current)")


def run(args: argparse.Namespace) -> None:
    j = jobmod.Job.load(args.job)
    src = j.apath(args.in_artifact) if args.in_artifact else j.current_video()
    if not src.exists():
        raise util.ToolError(f"input not found: {src}")
    info = util.probe_info(src)
    specs = _specs(args, j)

    for i, spec in enumerate(specs):
        kind = "image" if spec.get("image") else \
            ("cutaway" if spec.get("mode") == "cutaway" else "pip")
        runner = {"image": _image_pass, "pip": _pip_pass, "cutaway": _cutaway_pass}[kind]
        name = _next_name(j)
        out = j.apath(name)
        meta = runner(j, src, spec, info, out)
        out_info = util.probe_info(out)
        j.record("overlay", {"kind": kind, "spec": spec},
                 {name: {"duration": round(out_info["duration"], 2),
                         "width": out_info["width"], "height": out_info["height"],
                         **meta}})
        print(f"{name}  {util.fmt_ts(out_info['duration'])}  "
              f"{kind}  ({meta.get('media')})")
        src, info = out, out_info  # chain multiple specs onto each other

    if len(specs) > 1:
        print(f"applied {len(specs)} overlays -> {name}")
    else:
        print(f"current video is now {name}")
