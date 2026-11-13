"""Tool: pipeline — run a chain of tools over one job (resumable).

Example:
    vmill pipeline clip.mp4 --job myedit --steps probe,transcribe,plan,cut,clean,export
    vmill pipeline clip.mp4 --job myedit --opt transcribe:model=small --opt plan:cut=12.5:14.2

Each step is skipped when its artifact already exists in the job, so an
interrupted run (or an AI agent inspecting between steps) can continue.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import job as jobmod
from .. import util

PURPOSE = "run a chain of tools in order (resumable)"


def _registry():
    from . import REGISTRY  # lazy: avoids circular import at module load
    return REGISTRY

# step name -> artifact that marks it done
STEP_ARTIFACT = {
    "probe": "probe.json",
    "transcribe": "transcript.json",
    "plan": "cut_plan.json",
    "cut": "cut.mp4",
    "clean": "cleaned.mp4",
    "captions": "captioned.mp4",
    "face": "swapped.mp4",
    "export": "final.mp4",
}
DEFAULT_STEPS = ["probe", "transcribe", "plan", "cut", "export"]


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("video", nargs="?", help="video to open (ignored if --job exists)")
    p.add_argument("--job", required=True)
    p.add_argument("--steps", default=",".join(DEFAULT_STEPS),
                   help=f"comma list of {', '.join(STEP_ARTIFACT)} (default: {','.join(DEFAULT_STEPS)})")
    p.add_argument("--opt", action="append", default=[], metavar="STEP:KEY=VALUE",
                   help="extra arg for a step, e.g. transcribe:model=small or plan:cut=12.3:14.8")
    p.add_argument("--force", action="store_true", help="redo steps even if artifacts exist")


def run(args: argparse.Namespace) -> None:
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    for s in steps:
        if s not in STEP_ARTIFACT:
            raise util.ToolError(f"unknown step '{s}' — choose from {', '.join(STEP_ARTIFACT)}")

    jdir = args.job
    try:
        j = jobmod.Job.load(jdir)
        if args.video:
            cur = Path(j.data.get("video", "")).resolve()
            new = Path(args.video).expanduser().resolve()
            if new != cur:
                if args.force or not j.has("probe.json"):
                    j = jobmod.Job.create(jdir, new, copy=False)
                    print(f"[rebind] job now tracks {new}")
                else:
                    raise util.ToolError(
                        f"job {jdir} already tracks {cur} — pass --force to rebind it to {new}")
    except util.ToolError:
        if not args.video:
            raise util.ToolError(f"no job at {jdir} and no video given")
        j = jobmod.Job.create(jdir, args.video, copy=False)

    opts: dict[str, list[str]] = {}
    for o in args.opt:
        try:
            step, kv = o.split(":", 1)
            key, val = kv.split("=", 1)
        except ValueError as e:
            raise util.ToolError(f"--opt expects STEP:KEY=VALUE, got '{o}'") from e
        opts.setdefault(step, []).extend(["--" + key.replace("_", "-"), val])

    for step in steps:
        artifact = STEP_ARTIFACT[step]
        if j.has(artifact) and not args.force:
            print(f"[skip] {step:<10} ({artifact} exists — use --force to redo)")
            continue
        print(f"[run ] {step}")
        if step == "probe":
            argv = [args.video or j.data.get("video", ""), "--job", args.job]
        else:
            argv = ["--job", args.job]
        ns = step_args(step, argv)
        ns = apply_opts(ns, step, opts.get(step, []))
        _registry()[step].run(ns)
        j = jobmod.Job.load(jdir)  # tools save their own job state — pick it up
    print("pipeline done — see `vmill status --job " + str(j.path) + "`")


def step_args(step: str, argv: list[str]) -> argparse.Namespace:
    """Build a tool's namespace through its own add_args (single source of truth)."""
    p = argparse.ArgumentParser(prog=f"vmill {step}")
    _registry()[step].add_args(p)
    return p.parse_args([str(a) for a in argv if a is not None])


def apply_opts(ns: argparse.Namespace, step: str, extra: list[str]) -> argparse.Namespace:
    """Apply --opt STEP:KEY=VALUE extras to an already-built namespace."""
    if not extra:
        return ns
    p = argparse.ArgumentParser(prog=f"vmill {step}")
    _registry()[step].add_args(p)
    argv: list = []
    if step == "probe":
        argv.append(getattr(ns, "video", "") or "")
    argv += ["--job", ns.job] + extra
    parsed = p.parse_args(argv)
    for k, v in vars(parsed).items():
        if k == "video" and not v and hasattr(ns, "video") and ns.video:
            continue
        setattr(ns, k, v)
    return ns
