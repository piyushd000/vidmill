"""Tool: clean — denoise + loudness-normalize audio -> cleaned.mp4.

Engines:
  dfnet  — DeepFilterNet (conda env 'dfnet', `deepFilter` CLI) if available
  ffmpeg — afftdn + loudnorm fallback (always available with ffmpeg)
"""

from __future__ import annotations

import argparse

from .. import job as jobmod
from .. import util

PURPOSE = "denoise + normalize audio -> cleaned.mp4"


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--engine", choices=["auto", "dfnet", "ffmpeg"], default="auto")
    p.add_argument("--loudness", type=float, default=-16.0, help="target LUFS (default -16)")
    p.add_argument("--in", dest="in_artifact", help="video artifact to clean (default: current)")


def run(args: argparse.Namespace) -> None:
    j = jobmod.Job.load(args.job)
    src = j.apath(args.in_artifact) if args.in_artifact else j.current_video()
    if not util.probe_info(src)["has_audio"]:
        raise util.ToolError(f"{src.name} has no audio to clean")

    engine = args.engine
    if engine == "auto":
        engine = "dfnet" if util.env_bin("dfnet", "deepFilter") else "ffmpeg"

    out = j.apath("cleaned.mp4")
    used = engine
    if engine == "dfnet":
        try:
            run_dfnet(j, src, out, args.loudness)
        except util.ToolError as e:
            print(f"deepFilter failed ({e}); falling back to ffmpeg afftdn")
            used, engine = "ffmpeg (fallback)", "ffmpeg"
    if engine == "ffmpeg":
        run_ffmpeg_denoise(src, out, args.loudness)

    info = util.probe_info(out)
    j.record("clean", {"engine": used, "loudness": args.loudness},
             {"cleaned.mp4": {"duration": round(info["duration"], 2), "engine": used}})
    print(f"cleaned.mp4  {util.fmt_ts(info['duration'])}  engine={used}")


def run_dfnet(j, src, out, loudness: float) -> None:
    """DeepFilterNet does the denoise; ffmpeg then muxes + loudnorm."""
    wav_in = j.apath("clean_raw.wav")
    util.run_ffmpeg(src, ["-vn", "-acodec", "pcm_s16le", "-ar", "48000"], wav_in)
    outdir = j.path / "dfnet_out"
    util.run_in_env("dfnet", ["deepFilter", str(wav_in), "-o", str(outdir)])
    cleaned = outdir / (wav_in.stem + "_DeepFilterNet48k.wav")
    if not cleaned.exists():
        candidates = list(outdir.glob("*.wav"))
        if not candidates:
            raise util.ToolError("deepFilter produced no output")
        cleaned = candidates[0]
    util.run_ffmpeg(
        cleaned, ["-i", str(src), "-map", "1:v", "-map", "0:a",
                  "-c:v", "copy",
                  "-af", f"loudnorm=I={loudness}:TP=-1.5:LRA=11",
                  "-c:a", "aac", "-b:a", "192k", "-shortest"],
        out)
    wav_in.unlink(missing_ok=True)


def run_ffmpeg_denoise(src, out, loudness: float) -> None:
    util.run_ffmpeg(
        src,
        ["-af", f"afftdn=nr=12:nf=-25,loudnorm=I={loudness}:TP=-1.5:LRA=11",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"],
        out)
