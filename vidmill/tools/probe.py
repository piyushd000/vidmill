"""Tool: probe — open a video as a job (uses ffprobe)."""

from __future__ import annotations

import argparse

from .. import job as jobmod
from .. import util

PURPOSE = "open a video as a job and record its media info"


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("video", nargs="?", help="video file to open")
    p.add_argument("--job", required=True, help="job directory")
    p.add_argument("--copy", action="store_true", help="copy source into the job dir")


def run(args: argparse.Namespace) -> None:
    if not args.video:
        raise util.ToolError("probe needs a video: vmill new <video> --job <dir>")
    j = jobmod.Job.create(args.job, args.video, copy=args.copy)
    i = j.data["info"]
    print(f"job created : {j.path}")
    print(f"source      : {i['path']}")
    print(f"media       : {i['width']}x{i['height']} @ {i['fps']}fps  "
          f"{util.fmt_ts(i['duration'])}  audio={i['has_audio']}  {util.human_size(i['size_bytes'])}")
