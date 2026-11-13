"""Tool: plan — build cut_plan.json (segments to keep / drop).

Sources of cuts, in order:
  1. explicit --cut start:end ranges (from a human or an AI agent)
  2. an external --plan-file (agent-authored plan merged in)
  3. speech/silence: word gaps from transcript.json when available,
     else ffmpeg silencedetect
  4. optional false-start heuristic (repeated phrases) — recorded as
     `suggestions`, applied only with --mistakes
"""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
from pathlib import Path

from .. import job as jobmod
from .. import util

PURPOSE = "build cut_plan.json: what to keep and what to drop"


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--threshold-db", type=float, default=-40.0,
                   help="silence threshold when no transcript exists (default -40)")
    p.add_argument("--pad", type=float, default=0.15, help="seconds kept around each speech block")
    p.add_argument("--min-keep", type=float, default=0.40, help="drop keep-segments shorter than this")
    p.add_argument("--gap", type=float, default=0.35, help="word/silence gap that counts as a pause")
    p.add_argument("--freeze", action="store_true",
                   help="also remove still/no-movement video segments (freezedetect)")
    p.add_argument("--freeze-db", type=float, default=-60.0, help="freezedetect noise level")
    p.add_argument("--freeze-min", type=float, default=0.5, help="min freeze duration to remove")
    p.add_argument("--freeze-quiet-only", action="store_true",
                   help="only drop freezes that are also quiet (never cut speech)")
    p.add_argument("--cut", action="append", default=[], metavar="START:END",
                   help="force-remove a range in seconds (repeatable)")
    p.add_argument("--plan-file", help="merge cuts from an external plan json")
    p.add_argument("--mistakes", action="store_true",
                   help="also apply false-start suggestions detected from the transcript")
    p.add_argument("--no-heuristic", action="store_true", help="disable false-start detection")


def run(args: argparse.Namespace) -> None:
    j = jobmod.Job.load(args.job)
    src = j.current_video()
    info = util.probe_info(src)
    duration = info["duration"]

    silences = detect_silences(j, src, duration, args)
    if args.freeze:
        freezes = ff_freezes(src, args.freeze_db, args.freeze_min, duration)
        if args.freeze_quiet_only and j.has("transcript.json"):
            gaps = set(silences)
            freezes = intersect(freezes, sorted(gaps))
            print(f"freezedetect: keeping {len(freezes)} still-but-quiet segment(s) "
                  f"(speech-bearing freezes preserved)")
        if freezes:
            print(f"freezedetect: {len(freezes)} still segment(s) marked for removal")
        silences = merge(silences + freezes)
    speech = complement(silences, duration)

    keeps = merge([(max(0.0, s - args.pad), min(duration, e + args.pad)) for s, e in speech])

    explicit = [parse_cut(c) for c in args.cut]
    external = []
    if args.plan_file:
        external = load_external_cuts(args.plan_file)

    cuts = [{"from_s": round(a, 3), "to_s": round(b, 3), "reason": why}
            for a, b, why in explicit + external]
    cuts = merge_ranges(cuts)
    for c in cuts:  # remove cuts from keeps
        keeps = subtract(keeps, [(c["from_s"], c["to_s"])])

    suggestions = []
    if not args.no_heuristic and j.has("transcript.json"):
        suggestions = find_false_starts(j, duration, src=src)
    if args.mistakes:
        for s in suggestions:
            cuts = merge_ranges(cuts + [{"from_s": s["from_s"], "to_s": s["to_s"], "reason": s["why"]}])
            keeps = subtract(keeps, [(s["from_s"], s["to_s"])])

    keeps = [(s, e) for s, e in keeps if e - s >= args.min_keep]
    keeps = merge(keeps)
    if not keeps:
        raise util.ToolError("nothing to keep — check thresholds/cuts")

    fps = info.get("fps")
    plan = {
        "video": str(src),
        "duration": round(duration, 3),
        "fps": fps,
        "params": {"threshold_db": args.threshold_db, "pad": args.pad,
                   "min_keep": args.min_keep, "gap": args.gap, "mistakes": args.mistakes},
        "keep_seconds": [[round(s, 3), round(e, 3)] for s, e in keeps],
        "cuts": cuts,
        "suggestions": suggestions,
        "summary": {
            "original_seconds": round(duration, 2),
            "edited_seconds": round(sum(e - s for s, e in keeps), 2),
            "removed_seconds": round(duration - sum(e - s for s, e in keeps), 2),
            "pieces_kept": len(keeps),
        },
    }
    if fps:
        plan["keep_frames"] = [[int(s * fps), int(e * fps)] for s, e in keeps]

    util.atomic_json(j.apath("cut_plan.json"), plan)
    s = plan["summary"]
    j.record("plan", {"pad": args.pad, "explicit_cuts": len(explicit),
                      "mistakes": args.mistakes},
             {"cut_plan.json": {"keep_segments": s["pieces_kept"],
                                "removed_seconds": s["removed_seconds"]}})
    print(f"plan: keep {s['pieces_kept']} segments  "
          f"{util.fmt_ts(s['original_seconds'])} -> {util.fmt_ts(s['edited_seconds'])}  "
          f"(-{s['removed_seconds']}s)")
    if suggestions and not args.mistakes:
        print(f"{len(suggestions)} false-start suggestion(s) found — re-run with --mistakes to apply:")
        for s_ in suggestions[:8]:
            print(f"  {util.fmt_ts(s_['from_s'])}-{util.fmt_ts(s_['to_s'])}  {s_['why']}")


# ------------------------------------------------------------- timeline remap

def remap(t: float, plan: dict | None) -> float:
    """Original-video time -> edited-video time, via a cut plan's keep_seconds."""
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


def words_for_video(j, src) -> list[dict]:
    """Transcript words, remapped if the transcript was timed on a different
    video than `src` (e.g. planning a cut.mp4 with a transcript from the source)."""
    words = flatten_words(j)
    if not words:
        return words
    tr = j.latest("transcript.json")
    tr_video = (tr.get("meta") or {}).get("video")
    if not tr_video:
        try:
            tr_video = util.read_json(j.apath("transcript.json")).get("video")
        except Exception:
            tr_video = None
    if tr_video and Path(tr_video).resolve() != Path(src).resolve() and j.has("cut_plan.json"):
        prev = util.read_json(j.apath("cut_plan.json"))
        if prev.get("keep_seconds"):
            words = [dict(w, start=remap(w["start"], prev), end=remap(w["end"], prev)) for w in words]
    return words


# ---------------------------------------------------------------- detection

def detect_silences(j, src, duration, args) -> list[tuple[float, float]]:
    """Prefer transcript word gaps; fall back to ffmpeg silencedetect."""
    if j.has("transcript.json"):
        words = words_for_video(j, src)
        if words:
            gaps = []
            t = 0.0
            for i in range(len(words)):
                nxt = words[i]
                if nxt["start"] - t >= args.gap:
                    gaps.append((t, nxt["start"]))
                t = nxt["end"]
            if duration - t >= args.gap:
                gaps.append((t, duration))
            return gaps
    return ff_silences(src, args.threshold_db, args.gap, duration)


def ff_silences(src, threshold_db: float, min_gap: float, duration: float) -> list:
    p = util.run([util.FFMPEG, "-hide_banner", "-nostdin", "-i", str(src),
                  "-af", f"silencedetect=noise={threshold_db}dB:d={min_gap}",
                  "-f", "null", "-"], check=False, quiet=True)
    out = []
    starts = []
    for line in (p.stderr or "").splitlines():
        line = line.strip()
        if line.startswith("silence_start:"):
            starts.append(float(line.split(":", 1)[1]))
        elif line.startswith("silence_end:"):
            end = float(line.split(":", 1)[1].split("|")[0])
            if starts:
                out.append((starts.pop(), end))
    return merge(out)


def ff_freezes(src, noise_db: float, min_dur: float, duration: float) -> list:
    """No-movement (frozen picture) segments via ffmpeg freezedetect."""
    p = util.run([util.FFMPEG, "-hide_banner", "-nostdin", "-i", str(src),
                  "-vf", f"freezedetect=n={noise_db}dB:d={min_dur}",
                  "-f", "null", "-"], check=False, quiet=True)
    out = []
    pending = None
    for line in (p.stderr or "").splitlines():
        line = line.strip()
        if "freeze_start:" in line:
            pending = float(line.rsplit(":", 1)[1])
        elif "freeze_duration:" in line and pending is not None:
            d = float(line.rsplit(":", 1)[1])
            out.append((pending, min(duration, pending + d)))
            pending = None
        elif "freeze_end:" in line and pending is not None:
            out.append((pending, float(line.rsplit(":", 1)[1])))
            pending = None
    if pending is not None:  # video ends while frozen
        out.append((pending, duration))
    return merge(out)


def flatten_words(j) -> list[dict]:
    words = []
    for seg in util.read_json(j.apath("transcript.json")).get("segments", []):
        for w in seg.get("words", []):
            if w["word"] and w["start"] is not None:
                words.append(w)
    words.sort(key=lambda w: w["start"])
    return words


def find_false_starts(j, duration: float, src=None) -> list[dict]:
    """Repeated phrases spoken back-to-back (retakes / self-corrections)."""
    words = words_for_video(j, src) if src else flatten_words(j)
    out, i, n = [], 0, len(words)
    while i < n:
        matched = False
        # k >= 2: real retakes repeat phrases; single-word repeats ("no, no") are natural stutters
        for k in range(2, 7):
            if i + 2 * k > n:
                break
            a = " ".join(w["word"] for w in words[i:i + k]).lower().strip(".,!?")
            b = " ".join(w["word"] for w in words[i + k:i + 2 * k]).lower().strip(".,!?")
            gap = words[i + k]["start"] - words[i + k - 1]["end"]
            if a and b and SequenceMatcher(None, a, b).ratio() >= 0.85 and -0.15 <= gap <= 1.5:
                out.append({
                    "from_s": round(max(0.0, words[i + k]["start"] - 0.05), 3),
                    "to_s": round(min(duration, words[i + 2 * k - 1]["end"] + 0.05), 3),
                    "why": f"possible false start: '{a}' then '{b}'",
                    "text": b,
                })
                i += 2 * k
                matched = True
                break
        if not matched:
            i += 1
    return out


def intersect(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Ranges present in both sorted lists."""
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if lo < hi:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def load_external_cuts(path) -> list[tuple[float, float, str]]:
    data = util.read_json(path)
    cuts = []
    for c in data.get("cuts", []):
        cuts.append((float(c["from_s"]), float(c["to_s"]), c.get("why", "agent cut")))
    for m in data.get("mistake_cuts", []):
        cuts.append((float(m["from_s"]), float(m["to_s"]), m.get("why", "mistake")))
    return cuts


# ------------------------------------------------------------- range algebra

def parse_cut(s: str) -> tuple[float, float, str]:
    try:
        a, b = s.split(":", 1)
        a, b = float(a), float(b)
    except ValueError as e:
        raise util.ToolError(f"--cut expects START:END seconds, got '{s}'") from e
    if b <= a:
        raise util.ToolError(f"--cut end must be > start, got '{s}'")
    return (a, b, "explicit cut")


def merge(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    ranges = sorted((a, b) for a, b in ranges if b > a)
    out = []
    for a, b in ranges:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def merge_ranges(cuts: list[dict]) -> list[dict]:
    cuts = sorted(cuts, key=lambda c: c["from_s"])
    out = []
    for c in cuts:
        if out and c["from_s"] <= out[-1]["to_s"]:
            out[-1]["to_s"] = max(out[-1]["to_s"], c["to_s"])
        else:
            out.append(dict(c))
    return out


def complement(silences: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    keeps, t = [], 0.0
    for a, b in merge(silences):
        if a > t:
            keeps.append((t, a))
        t = max(t, b)
    if t < duration:
        keeps.append((t, duration))
    return keeps


def subtract(keeps: list[tuple[float, float]], cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for s, e in keeps:
        cur = [(s, e)]
        for a, b in cuts:
            nxt = []
            for cs, ce in cur:
                if b <= cs or a >= ce:
                    nxt.append((cs, ce))
                    continue
                if a > cs:
                    nxt.append((cs, a))
                if b < ce:
                    nxt.append((b, ce))
            cur = nxt
        out.extend(cur)
    return out
