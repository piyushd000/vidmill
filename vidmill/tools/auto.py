"""Tool: auto — upload-and-walk-away editing, with an optional AI checkpoint.

Everything before the checkpoint is free and local: transcription,
pause removal, no-movement removal, mistake heuristics, denoising,
captions, export. The paid LLM (any OpenAI-compatible API) gets ONE
compact text call — no video upload — to suggest extra cuts. Without
an API key the free result is still delivered.

  vmill auto myvideo.mp4 --job myedit
  vmill auto myvideo.mp4 --job myedit --ai            # opt into 1 LLM call
  VIDMILL_AI_BASE=https://api.openai.com/v1 VIDMILL_AI_KEY=sk-... \
      VIDMILL_AI_MODEL=gpt-4o-mini vmill auto --job myedit --ai
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

from .. import job as jobmod
from .. import util

PURPOSE = "fully automatic edit: free local pass, optional single AI checkpoint"

BASE = os.environ.get("VIDMILL_AI_BASE", "https://api.openai.com/v1")
KEY = os.environ.get("VIDMILL_AI_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("VIDMILL_AI_MODEL", "gpt-4o-mini")
BRIEF_CHARS = 6000

SYSTEM = (
    "You are a meticulous video editor. You receive a word-level transcript "
    "digest of a talking-head video that has ALREADY been auto-edited "
    "(pauses, still segments and obvious retakes removed). Suggest only cuts "
    "that materially improve the video: redundant repeats, dead tangents, "
    "false starts the heuristics missed. Never remove meaningful content. "
    "Reply with ONLY strict JSON: {\"cuts\":[{\"from_s\":number,\"to_s\":number,"
    "\"why\":\"short reason\"}], \"notes\":\"one sentence\"}. Times are seconds "
    "in the CURRENT (already cut) video."
)


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("video", nargs="?", help="video to edit (opens/creates the job)")
    p.add_argument("--job", required=True)
    p.add_argument("--mistakes", action="store_true", help="also drop heuristic retake cuts")
    p.add_argument("--no-ai", action="store_true", help="skip the AI checkpoint entirely")
    p.add_argument("--no-captions", action="store_true")
    p.add_argument("--no-clean", action="store_true")
    p.add_argument("--export-preset", default="final")
    p.add_argument("--dry-run", action="store_true", help="show the AI brief, do not call")


def run(args: argparse.Namespace) -> None:
    from . import pipeline as pipeline_mod

    steps = ["probe", "transcribe", "plan", "cut", "clean", "captions", "export"]
    if args.no_clean:
        steps.remove("clean")
    if args.no_captions:
        steps.remove("captions")

    ns = pipeline_mod.step_args("pipeline", ["--job", args.job])
    ns.job = args.job
    if args.video:
        ns.video = args.video
    ns.steps = ",".join(steps)
    ns.force = False
    ns.opt = ["plan:@freeze", "plan:@freeze-quiet-only"]
    if args.mistakes:
        ns.opt.append("plan:@mistakes")
    pipeline_mod.run(ns)

    j = jobmod.Job.load(args.job)
    brief = build_brief(j)

    if args.dry_run:
        print("\n--- AI brief (dry run, no call made) ---\n" + brief)
        return

    if args.no_ai:
        print("\nAI checkpoint skipped (--no-ai). Free local edit complete.")
        _finish(j)
        return

    if not KEY:
        print("\nAI checkpoint skipped: no API key configured.")
        print("To let an AI review the edit (one small text call, ~1-3k tokens):")
        print("  export VIDMILL_AI_KEY=sk-...        # or OPENAI_API_KEY")
        print("  export VIDMILL_AI_BASE=https://api.openai.com/v1   # any OpenAI-compatible API")
        print("  export VIDMILL_AI_MODEL=gpt-4o-mini")
        _finish(j)
        return

    cuts = ai_checkpoint(brief)
    if cuts is None:
        _finish(j)
        return
    if not cuts:
        print("\nAI review: no further cuts needed.")
        _finish(j)
        return
    _apply_ai_cuts(j, cuts)


# ----------------------------------------------------------------- AI layer

def build_brief(j) -> str:
    """Digest of the CURRENT (already cut) video, in current-video time."""
    from .plan_cuts import words_for_video
    cur = j.current_video()
    info = util.probe_info(cur)
    words = words_for_video(j, cur)
    plan = util.read_json(j.apath("cut_plan.json")) if j.has("cut_plan.json") else {}
    lines = [
        f"video: {info['duration']:.0f}s after auto-edit (was "
        f"{plan.get('summary', {}).get('original_seconds', '?')}s, "
        f"{plan.get('summary', {}).get('removed_seconds', 0)}s removed: "
        f"{plan.get('summary', {}).get('pieces_kept', '?')} segments kept)",
        "transcript of the current video (start-end: text):",
    ]
    used, chunk, chunk_start, chunk_end = 0, [], None, None
    for w in words:
        if chunk and w["start"] - chunk_end > 0.8:
            lines, used = _flush(lines, chunk, chunk_start, chunk_end, used)
            chunk, chunk_start, chunk_end = [], None, None
        if chunk_start is None:
            chunk_start = w["start"]
        chunk.append(w["word"])
        chunk_end = w["end"]
        if len(chunk) >= 14:
            lines, used = _flush(lines, chunk, chunk_start, chunk_end, used)
            chunk, chunk_start, chunk_end = [], None, None
        if used > BRIEF_CHARS:
            lines.append("... (transcript truncated)")
            break
    if chunk:
        lines, used = _flush(lines, chunk, chunk_start, chunk_end, used)
    return "\n".join(lines)


def _flush(lines: list, chunk: list, start, end, used: int) -> tuple[list, int]:
    line = f"{start:.0f}-{end:.0f}: {' '.join(chunk)}"
    lines.append(line)
    return lines, used + len(line)


def ai_checkpoint(brief: str) -> list[dict]:
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": brief}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        f"{BASE.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
    )
    print(f"AI checkpoint: one call to {MODEL} ({len(brief)} chars)...")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = json.load(r)
    except Exception as e:  # never fail the edit because of the API
        print(f"AI checkpoint failed ({e}) — keeping the free local edit.")
        return None
    try:
        text = body["choices"][0]["message"]["content"]
        data = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        print("AI checkpoint returned an unexpected response — ignored.")
        return None
    cuts = [c for c in data.get("cuts", []) if c.get("to_s", 0) > c.get("from_s", 1)]
    if data.get("notes"):
        print(f"AI notes: {data['notes']}")
    return cuts


def _apply_ai_cuts(j, cuts: list[dict]) -> None:
    util.atomic_json(j.apath("ai_plan.json"),
                     {"cuts": [{"from_s": c["from_s"], "to_s": c["to_s"], "why": c.get("why", "ai")}
                               for c in cuts]})
    from . import pipeline as pipeline_mod
    # re-plan on the current video, merging AI cuts, then redo the chain
    for step, extra in [
        ("plan", ["--freeze", "--freeze-quiet-only", "--plan-file", str(j.apath("ai_plan.json"))]),
        ("cut", []),
        ("clean", []),
        ("captions", []),
        ("export", []),
    ]:
        ns = pipeline_mod.step_args(step, ["--job", str(j.path)] + extra)
        pipeline_mod._registry()[step].run(ns)  # noqa: SLF001 - deliberate reuse
        j = jobmod.Job.load(j.path)
    _finish(j)
    print("\nAI-suggested cuts applied. Final: " + str(j.apath("final.mp4")))


def _finish(j) -> None:
    if j.has("final.mp4"):
        info = util.probe_info(j.apath("final.mp4"))
        print(f"\ndone — {j.apath('final.mp4')}: {info['width']}x{info['height']} "
              f"{util.fmt_ts(info['duration'])}  {util.human_size(info['size_bytes'])}")
    print("attribution reminder: if you added music via `vmill music mix`, keep its credit line.")
