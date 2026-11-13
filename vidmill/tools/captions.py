"""Tool: captions — burn word-synced captions from the transcript.

The transcript was timed on the original video; if a cut plan was applied,
timestamps are remapped through keep_seconds so captions stay in sync
(this is how artifacts connect).
"""

from __future__ import annotations

import argparse

from .. import job as jobmod
from .. import util

PURPOSE = "burn word-synced captions -> captioned.mp4"


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--in", dest="in_artifact", help="video to caption (default: current)")
    p.add_argument("--style", choices=["clean", "box"], default="clean")
    p.add_argument("--words-per-line", type=int, default=4)
    p.add_argument("--fontsize", type=int, help="default: height/26")


def run(args: argparse.Namespace) -> None:
    j = jobmod.Job.load(args.job)
    src = j.apath(args.in_artifact) if args.in_artifact else j.current_video()
    if not j.has("transcript.json"):
        raise util.ToolError("no transcript.json — run `vmill transcribe` first")

    words = []
    for seg in util.read_json(j.apath("transcript.json")).get("segments", []):
        words.extend(w for w in seg.get("words", []) if w["word"])
    if not words:
        raise util.ToolError("transcript has no words")

    plan = util.read_json(j.apath("cut_plan.json")) if j.has("cut_plan.json") else None
    words = [dict(w, start=remap(w["start"], plan), end=remap(w["end"], plan)) for w in words]

    info = util.probe_info(src)
    fontsize = args.fontsize or max(18, int((info["height"] or 720) / 26))
    ass = build_ass(words, args.words_per_line, fontsize, args.style,
                    info.get("width") or 1920, info.get("height") or 1080)
    ass_path = j.apath("captions.ass")
    ass_path.write_text(ass, encoding="utf-8")

    out = j.apath("captioned.mp4")
    util.run_ffmpeg(src, ["-vmill", f"ass={ass_path.name}",
                          "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                          "-c:a", "copy"], out, cwd=j.path)
    out_info = util.probe_info(out)
    j.record("captions", {"style": args.style, "words": len(words)},
             {"captions.ass": {"lines": len(words) // max(1, args.words_per_line) + 1},
              "captioned.mp4": {"duration": round(out_info["duration"], 2)}})
    print(f"captioned.mp4  {util.fmt_ts(out_info['duration'])}  style={args.style}")


def remap(t: float, plan: dict | None) -> float:
    """Original-video time -> edited-video time, via the cut plan."""
    if not plan or not plan.get("keep_seconds"):
        return t
    acc = 0.0
    for s, e in plan["keep_seconds"]:
        if t < s:  # fell into a removed gap before this segment
            return round(acc, 3)
        if t <= e:
            return round(acc + (t - s), 3)
        acc += e - s
    return round(acc, 3)


def build_ass(words, wpl: int, fontsize: int, style: str, w: int, h: int) -> str:
    groups = []
    for i in range(0, len(words), wpl):
        chunk = words[i:i + wpl]
        text = " ".join(c["word"] for c in chunk)
        groups.append((chunk[0]["start"], chunk[-1]["end"], text))
    # avoid overlapping captions
    fixed = []
    for s, e, text in groups:
        if fixed and s < fixed[-1][1]:
            e = max(e, fixed[-1][1] + 0.01)
            s = fixed[-1][1] + 0.01 if s <= fixed[-1][1] else s
        fixed.append((s, max(e, s + 0.3), text))

    border = "3" if style == "box" else "1"
    outline = "0" if style == "box" else "3"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,{fontsize},&H00FFFFFF,&H00FFFFFF,&H00101010,&H7F101010,-1,0,0,0,100,100,0,0,{border},{outline},2,2,60,60,{int(h * 0.09)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [f"Dialogue: 0,{ass_ts(s)},{ass_ts(e)},Cap,,0,0,0,,{text}" for s, e, text in fixed]
    return head + "\n".join(lines) + "\n"


def ass_ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"
