"""Tool: cut — apply cut_plan.json to the current video (ffmpeg trim+concat)."""

from __future__ import annotations

import argparse

from .. import job as jobmod
from .. import util

PURPOSE = "apply the cut plan -> cut.mp4"


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--plan-file", help="plan to apply (default: cut_plan.json in the job)")
    p.add_argument("--in", dest="in_artifact", help="video artifact to cut (default: current)")
    p.add_argument("--crf", type=int, default=20)


def run(args: argparse.Namespace) -> None:
    j = jobmod.Job.load(args.job)
    src = j.apath(args.in_artifact) if args.in_artifact else j.current_video()
    if not src.exists():
        raise util.ToolError(f"input not found: {src}")

    plan_path = j.apath("cut_plan.json") if not args.plan_file else args.plan_file
    if not plan_path.exists():
        raise util.ToolError("no cut_plan.json — run `vf plan` first (or pass --plan-file)")
    plan = util.read_json(plan_path)
    keeps = plan.get("keep_seconds") or []
    if not keeps:
        raise util.ToolError("plan has no keep_seconds")

    has_audio = bool(util.probe_info(src)["has_audio"])
    fc, vmap, amap = build_filter(keeps, has_audio)
    encode = ["-filter_complex", fc, "-map", vmap,
              "-c:v", "libx264", "-crf", str(args.crf), "-preset", "veryfast",
              "-pix_fmt", "yuv420p"]
    if amap:
        encode += ["-map", amap, "-c:a", "aac", "-b:a", "192k"]
    encode += ["-movflags", "+faststart"]

    out = j.apath("cut.mp4")
    util.run_ffmpeg(src, encode, out)
    out_info = util.probe_info(out)

    kept = sum(e - s for s, e in keeps)
    j.record("cut", {"plan": str(plan_path), "segments": len(keeps)},
             {"cut.mp4": {"duration": round(out_info["duration"], 2),
                          "planned_seconds": round(kept, 2),
                          "width": out_info["width"], "height": out_info["height"]}})
    print(f"cut.mp4  {util.fmt_ts(out_info['duration'])}  "
          f"({out_info['width']}x{out_info['height']})  from {len(keeps)} segments")


def build_filter(keeps, has_audio: bool) -> tuple[str, str, str | None]:
    """trim/concat each keep segment; video and audio stay in sync."""
    v, a = [], []
    for i, (s, e) in enumerate(keeps):
        v.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
        if has_audio:
            a.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
    n = len(keeps)
    if n == 1:
        return ";".join(v + a), "[v0]", "[a0]" if has_audio else None
    parts = v + a
    parts.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]")
    amap = None
    if has_audio:
        parts.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[aout]")
        amap = "[aout]"
    return ";".join(parts), "[vout]", amap
