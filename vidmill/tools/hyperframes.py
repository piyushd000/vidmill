"""Tool: hyperframes — render an HTML composition and use it as an intro/outro.

HyperFrames turns HTML/CSS/JS timelines into video frame by frame. This
tool renders a project with the HyperFrames CLI (`npx hyperframes`) and
places the result at the start or end of the current video, normalized
to the job's resolution/frame rate with matched audio.

  vmill hyperframes --job myedit --project ./intro --where intro
  vmill hyperframes --job myedit --project ./outro --where outro
  vmill hyperframes --job myedit --project ./card --where render

Node.js 22+ is required; HyperFrames itself is fetched by npx on first
use, so vidmill does not add a dependency. `vmill hyperframes --check`
reports whether the toolchain is present.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from .. import job as jobmod
from .. import util

PURPOSE = "render a HyperFrames HTML project and add it as an intro/outro"
QUALITIES = ("draft", "looks", "delivery")


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", help="job directory (not needed with --check)")
    p.add_argument("--project", help="HyperFrames project directory or an .html composition")
    p.add_argument("--clip", help="an already rendered clip to place (skips rendering)")
    p.add_argument("--where", choices=["intro", "outro", "render"], default="intro",
                   help="place at the start, at the end, or just render it")
    p.add_argument("--out", help="artifact name (default intro.mp4/outro.mp4/hyperframes.mp4)")
    p.add_argument("--quality", choices=QUALITIES, default="looks")
    p.add_argument("--timeout", type=int, default=900,
                   help="render timeout in seconds (default 900)")
    p.add_argument("--check", action="store_true", help="report the HyperFrames toolchain")


def _toolchain() -> tuple[str | None, str | None]:
    node = shutil.which("node")
    npx = shutil.which("npx")
    nver = None
    if node:
        p = util.run([node, "--version"], check=False, quiet=True)
        nver = (p.stdout or "").strip() or None
    return nver, npx


def _check() -> None:
    node, npx = _toolchain()
    print(f"node : {node or 'not found'}")
    print(f"npx  : {npx or 'not found'}")
    if node and npx:
        print("hyperframes: available on demand via `npx hyperframes` "
              "(first render downloads it)")
        print("render with: vmill hyperframes --job <dir> --project <dir> --where intro")
    else:
        print("hyperframes: optional — install Node.js 22+ to render HTML intros/outros")


def _render(project: str, quality: str, timeout: int, out: Path) -> None:
    node, npx = _toolchain()
    if not node or not npx:
        raise util.ToolError(
            "HyperFrames needs Node.js 22+ (node/npx not found).\n"
            "Install Node from https://nodejs.org, then retry. "
            "Everything else in vidmill works without it."
        )
    proj = Path(project).expanduser().resolve()
    if not proj.exists():
        raise util.ToolError(f"HyperFrames project not found: {proj}")
    if proj.is_file():
        if proj.suffix.lower() not in (".html", ".htm"):
            raise util.ToolError("--project must be a project directory or an .html file")
        root, comp = proj.parent, proj.name
    else:
        root, comp = proj, None
    if not (root / "index.html").exists() and not comp:
        raise util.ToolError(
            f"{root} has no index.html. Create a project with: "
            f"npx hyperframes init <dir> --skip-skills"
        )

    cmd = [npx, "--yes", "hyperframes", "render", str(root),
           "--quality", quality, "--skill=hyperframes",
           "-o", str(out), "--quiet"]
    if comp and comp != "index.html":
        rel = proj.relative_to(root)
        cmd += ["-c", str(rel)]
    print(f"hyperframes: rendering {proj} ({quality}) — this can take a few minutes...")
    try:
        p = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out.unlink(missing_ok=True)
        raise util.ToolError(f"HyperFrames render timed out after {timeout}s") from e
    if p.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        tail = ((p.stdout or "") + (p.stderr or "")).strip()[-2500:]
        raise util.ToolError(
            "HyperFrames render failed.\n" + tail +
            "\nHint: run `npx hyperframes doctor` in the project for details."
        )


def _normalize(part: str, idx: int, info: dict, W: int, H: int, fps, dur: float) -> list[str]:
    """Filter graph pieces that make one input concat-safe (video + audio)."""
    video = (
        f"[{idx}:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,format=yuv420p,trim=0:{dur:.3f},"
        f"setpts=PTS-STARTPTS[v{part}]"
    )
    if info.get("has_audio"):
        audio = (
            f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[a{part}]"
        )
    else:
        audio = (
            f"anullsrc=channel_layout=stereo:sample_rate=48000,"
            f"atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[a{part}]"
        )
    return [video, audio]


def _place(j, clip: Path, where: str, out: Path) -> dict:
    src = j.current_video()
    main = util.probe_info(src)
    cinfo = util.probe_info(clip)
    W, H = main["width"], main["height"]
    fps = main.get("fps") or 30
    mdur, cdur = main["duration"], cinfo["duration"]
    if not cdur:
        raise util.ToolError("the rendered clip has no duration")

    parts: list[str] = []
    parts += _normalize("0", 0, main, W, H, fps, mdur)
    parts += _normalize("1", 1, cinfo, W, H, fps, cdur)
    order = ("[v1][a1][v0][a0]" if where == "intro" else "[v0][a0][v1][a1]")
    parts.append(f"{order}concat=n=2:v=1:a=1[v][a]")
    fc = ";".join(parts)

    tmp = out
    same = out.resolve() == src.resolve()
    if same:
        tmp = out.with_name(out.stem + ".tmp" + out.suffix)
    cmd = [util.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
           "-i", str(src), "-i", str(clip),
           "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(tmp)]
    try:
        util.run(cmd)
        if same:
            tmp.replace(out)
    except Exception:
        if same:
            tmp.unlink(missing_ok=True)
        raise
    info = util.probe_info(out)
    return {"duration": round(info["duration"], 2), "width": info["width"],
            "height": info["height"], "where": where, "clip_seconds": round(cdur, 2)}


def run(args: argparse.Namespace) -> None:
    if args.check:
        return _check()
    if not args.job:
        raise util.ToolError("--job is required")
    if bool(args.project) == bool(args.clip):
        raise util.ToolError("pass exactly one of --project (render) or --clip (already rendered)")
    if args.where == "render" and args.clip:
        raise util.ToolError("--where render needs --project (there is nothing to render)")
    if args.timeout < 10:
        raise util.ToolError("--timeout must be at least 10 seconds")

    j = jobmod.Job.load(args.job)
    out_name = args.out or ("hyperframes.mp4" if args.where == "render" else f"{args.where}.mp4")
    out_name = Path(out_name).name
    if not out_name.lower().endswith(".mp4"):
        out_name += ".mp4"
    out = j.apath(out_name)
    if out.resolve() == j.apath("job.json").resolve():
        raise util.ToolError("invalid output name")
    src_before = j.current_video()

    if args.clip:
        clip = Path(args.clip).expanduser().resolve()
        if not clip.exists():
            raise util.ToolError(f"clip not found: {clip}")
    else:
        clip = j.apath(".hyperframes_render.mp4")
        _render(args.project, args.quality, args.timeout, clip)

    try:
        if args.where == "render":
            if clip != out:
                shutil.move(str(clip), str(out))
            info = util.probe_info(out)
            j.record("hyperframes", {"project": args.project, "where": "render",
                                     "quality": args.quality},
                     {out_name: {"duration": round(info["duration"], 2)}})
            print(f"{out_name}  {util.fmt_ts(info['duration'])}  "
                  f"{info['width']}x{info['height']}  (rendered)")
            return

        meta = _place(j, clip, args.where, out)
        j.record("hyperframes", {"project": args.project or args.clip,
                                 "where": args.where, "quality": args.quality},
                 {out_name: meta})
        print(f"{out_name}  {util.fmt_ts(meta['duration'])}  "
              f"{meta['width']}x{meta['height']}  ({args.where} clip, "
              f"{meta['clip_seconds']}s added)")
        print(f"current video is now {out_name}")
        print("note: add intros/outros after captions/export; caption timings "
              "do not account for an added intro.")
    finally:
        if clip.name == ".hyperframes_render.mp4" and clip != out:
            clip.unlink(missing_ok=True)
