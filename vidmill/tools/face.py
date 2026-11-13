"""Tool: face — wrap FaceFusion's headless CLI -> swapped.mp4.

The FaceFusion GUI is fully scriptable with `headless-run`; this tool
connects it to the vidmill chain so the rest of the pipeline feeds it.

Needs: conda env `facefusion` and the repo checkout. Override the repo
location with AVF_FACEFUSION_DIR (default: ~/facefusion).
"""

from __future__ import annotations

import argparse
import os
import shlex

from .. import job as jobmod
from .. import util

PURPOSE = "swap a reference face onto the video (FaceFusion headless)"

ENV = "facefusion"
REPO = os.environ.get("AVF_FACEFUSION_DIR", os.path.expanduser("~/facefusion"))


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--image", required=True, help="reference face image (jpg/png)")
    p.add_argument("--in", dest="in_artifact", help="video artifact (default: current)")
    p.add_argument("--extra", default="", help="extra raw args passed to facefusion, quoted")
    p.add_argument("--out-name", default="swapped.mp4")


def run(args: argparse.Namespace) -> None:
    repo = os.path.expanduser(REPO)
    py = util.env_bin(ENV, "python3") or util.env_bin(ENV, "python")
    if not (py and os.path.isdir(repo)):
        raise util.ToolError(
            f"FaceFusion not ready (env '{ENV}' or repo {repo} missing). "
            f"Install it or set AVF_FACEFUSION_DIR. `vmill doctor` shows details.")

    j = jobmod.Job.load(args.job)
    if not args.image:
        raise util.ToolError("face needs a reference image: vmill face --job <dir> --image face.jpg")
    src = j.apath(args.in_artifact) if args.in_artifact else j.current_video()
    image = os.path.expanduser(args.image)
    if not os.path.exists(image):
        raise util.ToolError(f"face image not found: {image}")
    out = j.apath(args.out_name)

    cmd = [str(py), "facefusion.py", "headless-run",
           "-s", image, "-t", str(src), "-o", str(out)]
    cmd += shlex.split(args.extra or "")

    print("facefusion:", " ".join(cmd[:6]) + " ...")
    util.run_in_env(ENV, cmd, cwd=repo)
    if not out.exists() or out.stat().st_size == 0:
        raise util.ToolError("facefusion produced no output")

    info = util.probe_info(out)
    j.record("face", {"image": image, "extra": args.extra},
             {args.out_name: {"duration": round(info["duration"], 2)}})
    print(f"{args.out_name}  {util.fmt_ts(info['duration'])}")
