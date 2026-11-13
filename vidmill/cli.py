"""vmill — command line interface for vidmill."""

from __future__ import annotations

import argparse
import json
import shutil
import sys

from . import APP_NAME, ToolError, __version__
from . import job as jobmod
from . import util
from .registry import TOOLS, manifest
from .tools import REGISTRY


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="vmill",
        description=("vidmill — open-source AI video editing toolkit. "
                     "FFmpeg, Faster-Whisper, FaceFusion and DeepFilterNet exposed "
                     "as connected tools driven from one job directory."),
    )
    ap.add_argument("--version", action="version", version=f"vmill {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, mod in REGISTRY.items():
        sp = sub.add_parser(name, help=mod.PURPOSE)
        mod.add_args(sp)
        sp.set_defaults(func=mod.run)

    tp = sub.add_parser("tools", help="list registered tools (--json for the AI manifest)")
    tp.add_argument("--json", action="store_true")
    tp.set_defaults(func=tools_cmd)

    sp2 = sub.add_parser("status", help="show a job's artifacts and tool history")
    sp2.add_argument("--job", required=True)
    sp2.set_defaults(func=status_cmd)

    dp = sub.add_parser("doctor", help="check which engines are installed and usable")
    dp.set_defaults(func=doctor_cmd)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except ToolError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


# ------------------------------------------------------------------ builtins

def tools_cmd(a) -> None:
    m = manifest()
    if a.json:
        print(json.dumps(m, indent=1))
        return
    print(f"{m['name']} v{m['version']} — {len(m['tools'])} tools\n")
    for t in m["tools"]:
        print(f"  {t['name']:<11} {t['cmd']}")
        print(f"  {'':<11} {t['purpose']}\n")


def status_cmd(a) -> None:
    jobmod.Job.load(a.job).print_status()


def doctor_cmd(a) -> None:
    rows: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, note: str = "") -> None:
        rows.append((label, ok, note))

    ffmpeg = shutil.which(util.FFMPEG)
    if ffmpeg:
        v = util.run([util.FFMPEG, "-version"], check=False, quiet=True).stdout.splitlines()[0]
        has_ass = " ass " in util.run([util.FFMPEG, "-hide_banner", "-filters"], check=False, quiet=True).stdout
        check("ffmpeg", True, v.split()[2] + ("" if has_ass else "  [WARNING: no libass — captions unavailable]"))
        check("ffprobe", bool(shutil.which(util.FFPROBE)))
    else:
        check("ffmpeg", False, "install: https://ffmpeg.org")

    try:
        import faster_whisper
        check("faster-whisper", True, faster_whisper.__version__)
    except ImportError:
        check("faster-whisper", False, "pip install faster-whisper")

    df = util.env_bin("dfnet", "deepFilter")
    check("DeepFilterNet (env dfnet)", bool(df), str(df) if df else "conda env 'dfnet' with deepFilter — optional, falls back to ffmpeg afftdn")

    from .tools import face as face_mod
    py = util.env_bin(face_mod.ENV, "python3") or util.env_bin(face_mod.ENV, "python")
    import os
    repo = os.path.expanduser(face_mod.REPO)
    ok = bool(py and os.path.isdir(repo))
    check("FaceFusion (env facefusion)", ok,
          f"{repo}" if ok else "conda env 'facefusion' + repo (set AVF_FACEFUSION_DIR) — optional")

    check("gh CLI", bool(shutil.which("gh")), "for publishing to GitHub (optional)")

    width = max(len(r[0]) for r in rows)
    all_core = True
    for label, ok_, note in rows:
        print(f"  {'OK ' if ok_ else '-- '} {label:<{width}}  {note}")
        if not ok_ and label in ("ffmpeg", "ffprobe", "faster-whisper"):
            all_core = False
    print()
    print("core tools ready" if all_core else "core tools missing — see notes above")
    sys.exit(0 if all_core else 2)
