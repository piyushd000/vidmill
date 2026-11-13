"""Tool: export — delivery presets -> final.mp4."""

from __future__ import annotations

import argparse

from .. import job as jobmod
from .. import util

PURPOSE = "export the current video with a delivery preset -> final.mp4"

PRESETS = {
    "final": ("h264 youtube-safe", ["-c:v", "libx264", "-crf", "20", "-preset", "medium",
                                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                                    "-movflags", "+faststart"]),
    "hevc": ("smaller files (x265)", ["-c:v", "libx265", "-crf", "24", "-preset", "medium",
                                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                                      "-tag:v", "hvc1", "-movflags", "+faststart"]),
    "shorts": ("1080x1920 vertical", ["-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                                     "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
                                      "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                                      "-movflags", "+faststart"]),
    "yt": ("1920x1080 horizontal", ["-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                                    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1",
                                    "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                                    "-movflags", "+faststart"]),
}


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--preset", choices=sorted(PRESETS), default="final")
    p.add_argument("--in", dest="in_artifact", help="video artifact to export (default: current)")
    p.add_argument("--out-name", default="final.mp4")


def run(args: argparse.Namespace) -> None:
    j = jobmod.Job.load(args.job)
    src = j.apath(args.in_artifact) if args.in_artifact else j.current_video()
    out = j.apath(args.out_name)
    desc, enc = PRESETS[args.preset]
    util.run_ffmpeg(src, enc, out)
    info = util.probe_info(out)
    j.record("export", {"preset": args.preset, "input": str(src)},
             {args.out_name: {"duration": round(info["duration"], 2),
                              "width": info["width"], "height": info["height"],
                              "preset": args.preset}})
    print(f"{args.out_name}  {info['width']}x{info['height']}  "
          f"{util.fmt_ts(info['duration'])}  {util.human_size(info['size_bytes'])}  ({desc})")
