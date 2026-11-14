"""Tool: export — delivery presets -> final.mp4.

Hardware acceleration: `--hwaccel auto` (the default) uses the GPU
encoder when one is genuinely available (NVENC, VideoToolbox, Quick
Sync) and silently falls back to software otherwise. Intermediate
edits stay on libx264 for maximum compatibility; only the delivery
encode is accelerated.
"""

from __future__ import annotations

import argparse

from .. import job as jobmod
from .. import util

PURPOSE = "export the current video with a delivery preset -> final.mp4"

# codec: h264|hevc, crf: quality target, vf: optional scale/pad chain
PRESETS = {
    "final": {"desc": "h264 youtube-safe", "codec": "h264", "crf": 20,
              "audio": ["-c:a", "aac", "-b:a", "192k"], "vf": None},
    "hevc": {"desc": "smaller files (x265)", "codec": "hevc", "crf": 24,
             "audio": ["-c:a", "aac", "-b:a", "160k", "-tag:v", "hvc1"], "vf": None},
    "shorts": {"desc": "1080x1920 vertical", "codec": "h264", "crf": 20,
               "audio": ["-c:a", "aac", "-b:a", "192k"],
               "vf": "scale=1080:1920:force_original_aspect_ratio=decrease,"
                     "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"},
    "yt": {"desc": "1920x1080 horizontal", "codec": "h264", "crf": 20,
           "audio": ["-c:a", "aac", "-b:a", "192k"],
           "vf": "scale=1920:1080:force_original_aspect_ratio=decrease,"
                 "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"},
}

BACKENDS = ("auto", "off", "nvenc", "qsv", "vaapi", "videotoolbox")
VAAPI_DEVICE = "/dev/dri/renderD128"


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--preset", choices=sorted(PRESETS), default="final")
    p.add_argument("--in", dest="in_artifact", help="video artifact to export (default: current)")
    p.add_argument("--out-name", default="final.mp4")
    p.add_argument("--hwaccel", choices=BACKENDS, default="auto",
                   help="GPU encode: auto (default, falls back to CPU), off, or force a backend")


def encoder_args(backend: str | None, codec: str, crf: int, vf: str | None) -> list[str]:
    """ffmpeg output args for one preset on the given backend."""
    args: list[str] = []
    if backend == "vaapi":
        chain = f"{vf}," if vf else ""
        args += ["-vaapi_device", VAAPI_DEVICE,
                 "-vf", chain + "format=nv12,hwupload",
                 "-c:v", "h264_vaapi" if codec == "h264" else "hevc_vaapi",
                 "-qp", str(crf)]
        return args
    if vf:
        args += ["-vf", vf]
    if backend == "nvenc":
        args += ["-c:v", "h264_nvenc" if codec == "h264" else "hevc_nvenc",
                 "-preset", "p5", "-rc", "vbr", "-cq", str(crf), "-b:v", "0",
                 "-pix_fmt", "yuv420p"]
    elif backend == "qsv":
        args += ["-c:v", "h264_qsv" if codec == "h264" else "hevc_qsv",
                 "-global_quality", str(crf), "-preset", "medium",
                 "-pix_fmt", "nv12"]
    elif backend == "videotoolbox":
        args += ["-c:v", "h264_videotoolbox" if codec == "h264" else "hevc_videotoolbox",
                 "-q:v", "65", "-pix_fmt", "yuv420p"]
    else:  # software
        args += ["-c:v", "libx264" if codec == "h264" else "libx265",
                 "-crf", str(crf), "-preset", "medium", "-pix_fmt", "yuv420p"]
    return args


def _backend(args) -> tuple[str | None, str]:
    """Resolve --hwaccel to (backend, human note)."""
    if args.hwaccel == "off":
        return None, "CPU (software encode)"
    if args.hwaccel == "auto":
        det = util.gpu_backend()
        if det:
            return det[0], f"{det[0]} — {det[1]}"
        return None, "CPU (no usable GPU detected)"
    if args.hwaccel == "vaapi" and not __import__("os").path.exists(VAAPI_DEVICE):
        raise util.ToolError(f"vaapi needs {VAAPI_DEVICE} — not present on this machine")
    return args.hwaccel, f"{args.hwaccel} (forced)"


def run(args: argparse.Namespace) -> None:
    j = jobmod.Job.load(args.job)
    src = j.apath(args.in_artifact) if args.in_artifact else j.current_video()
    out = j.apath(args.out_name)
    preset = PRESETS[args.preset]
    backend, note = _backend(args)
    enc = encoder_args(backend, preset["codec"], preset["crf"], preset["vf"])
    enc += preset["audio"] + ["-movflags", "+faststart"]
    if out.resolve() == src.resolve():
        print(f"note: current video is already {out.name}; re-encoding it "
              f"(pass --in <artifact> to export from an earlier step)")
        tmp = out.with_name(out.stem + ".tmp" + out.suffix)
        try:
            util.run_ffmpeg(src, enc, tmp)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        tmp.replace(out)
    else:
        util.run_ffmpeg(src, enc, out)
    info = util.probe_info(out)
    j.record("export", {"preset": args.preset, "input": str(src), "hwaccel": args.hwaccel},
             {args.out_name: {"duration": round(info["duration"], 2),
                              "width": info["width"], "height": info["height"],
                              "preset": args.preset, "encoder": note}})
    print(f"{args.out_name}  {info['width']}x{info['height']}  "
          f"{util.fmt_ts(info['duration'])}  {util.human_size(info['size_bytes'])}  "
          f"({preset['desc']}, encoder={note})")
