"""Tool: delogo — remove a watermark, logo or channel bug from the video.

Two ways to pick the region:

  vmill delogo --job myedit --region 1180:30:90:60
  vmill delogo --job myedit                  # conservative auto-detect

Auto-detection looks for a *text-like, temporally static* overlay inside
the four corners: several similarly sized, horizontally aligned edge
components that never change while the rest of the frame moves. That is
what watermarks look like, and deliberately not what walls, window
frames or signs look like. When it is not confident it does nothing and
says so — pass an explicit region for graphic logos or unusual spots.

Two fill modes: `delogo` (interpolates from the surrounding pixels,
seamless on simple backgrounds) and `blur` (keeps the texture, blurs it).
The result is delogo.mp4 and becomes the job's current video.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess

from .. import job as jobmod
from .. import util

PURPOSE = "remove a watermark/logo region (auto-detected or --region)"
REGION_RE = re.compile(r"^\s*(\d+)\s*[:,]\s*(\d+)\s*[:,]\s*(\d+)\s*[:,]\s*(\d+)\s*$")
SAMPLE_WIDTH = 480
SAMPLES = 9


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--region", metavar="X:Y:W:H",
                   help="watermark box in pixels (default: conservative auto-detect)")
    p.add_argument("--mode", choices=["delogo", "blur"], default="delogo",
                   help="delogo interpolates from the edges; blur keeps the texture")
    p.add_argument("--sample-width", type=int, default=SAMPLE_WIDTH,
                   help=argparse.SUPPRESS)
    p.add_argument("--samples", type=int, default=SAMPLES, help=argparse.SUPPRESS)


def parse_region(text: str) -> tuple[int, int, int, int]:
    m = REGION_RE.match(text or "")
    if not m:
        raise util.ToolError("--region expects X:Y:W:H in pixels, e.g. 1180:30:90:60")
    x, y, w, h = (int(v) for v in m.groups())
    if w <= 0 or h <= 0:
        raise util.ToolError("--region width and height must be positive")
    return x, y, w, h


# ------------------------------------------------------------------ detection

def _sample_frames(src, width: int, count: int) -> tuple[list[bytes], int, int]:
    """Grayscale frames at `width`, evenly spread over the video."""
    info = util.probe_info(src)
    dur = info["duration"]
    if dur <= 1.0 or not info["width"]:
        return [], 0, 0
    frames = []
    for i in range(max(3, count)):
        t = dur * (0.04 + 0.92 * i / max(1, count - 1))
        p = subprocess.run(
            [util.FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", str(src),
             "-frames:v", "1", "-vf", f"scale={width}:-2",
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True,
        )
        if p.returncode == 0 and p.stdout:
            frames.append(p.stdout)
    if not frames:
        return [], 0, 0
    h = len(frames[0]) // width
    return frames, width, h


def _components(mask: list[bool], w: int, h: int) -> list[dict]:
    """Connected components of a boolean mask (4-connectivity)."""
    seen = [False] * len(mask)
    out = []
    for i, on in enumerate(mask):
        if not on or seen[i]:
            continue
        stack, pts = [i], []
        seen[i] = True
        while stack:
            j = stack.pop()
            pts.append(j)
            y, x = divmod(j, w)
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w:
                    k = ny * w + nx
                    if mask[k] and not seen[k]:
                        seen[k] = True
                        stack.append(k)
        xs = [p % w for p in pts]
        ys = [p // w for p in pts]
        out.append({"size": len(pts), "x": min(xs), "y": min(ys),
                    "w": max(xs) - min(xs) + 1, "h": max(ys) - min(ys) + 1})
    return out


def _corner_line(frames: list[bytes], fw: int, fh: int,
                 x0: int, y0: int, cw: int, ch: int) -> dict | None:
    """Find a text line inside one corner patch; return a source-space-ish box."""
    n = len(frames)
    mean, std = [], []
    for yy in range(ch):
        for xx in range(cw):
            vals = [frames[k][(y0 + yy) * fw + x0 + xx] for k in range(n)]
            mu = sum(vals) / n
            mean.append(mu)
            std.append(math.sqrt(sum((v - mu) ** 2 for v in vals) / n))

    static = sum(1 for s in std if s < 7.0) / len(std)
    if static < 0.75:
        return None

    mask = []
    for yy in range(ch):
        for xx in range(cw):
            i = yy * cw + xx
            if xx < 1 or yy < 1 or xx >= cw - 1 or yy >= ch - 1:
                mask.append(False)
                continue
            grad = abs(mean[i] - mean[i - 1]) + abs(mean[i] - mean[i - cw])
            mask.append(grad >= 30.0 and std[i] < 9.0)

    comps = [c for c in _components(mask, cw, ch) if c["size"] >= 10]
    hmin, hmax = max(4, int(fh * 0.015)), max(8, int(fh * 0.07))
    # glyph candidates: small, roughly as tall as wide, not long straight lines
    letters = [c for c in comps if hmin <= c["h"] <= hmax
               and c["w"] <= c["h"] * 4.5 and c["w"] >= 2 and c["size"] >= 12]
    if len(letters) < 3:
        return None
    letters.sort(key=lambda c: c["x"])

    # group by baseline, then keep horizontal runs with small gaps
    groups: list[dict] = []
    for c in letters:
        cy = c["y"] + c["h"] / 2
        for g in groups:
            if abs(cy - g["cy"]) <= max(c["h"], g["h"]) * 0.7:
                g["items"].append(c)
                g["cy"] = (g["cy"] * (len(g["items"]) - 1) + cy) / len(g["items"])
                g["h"] = max(g["h"], c["h"])
                break
        else:
            groups.append({"items": [c], "cy": cy, "h": c["h"]})

    best = None
    for g in groups:
        items = sorted(g["items"], key=lambda c: c["x"])
        run = [items[0]]
        runs = []
        for a, b in zip(items, items[1:]):
            gap = b["x"] - (a["x"] + a["w"])
            if gap <= max(a["h"], b["h"]) * 2.5:
                run.append(b)
            else:
                runs.append(run)
                run = [b]
        runs.append(run)
        for r in runs:
            if len(r) < 3:
                continue
            bx0 = min(c["x"] for c in r)
            bx1 = max(c["x"] + c["w"] for c in r)
            by0 = min(c["y"] for c in r)
            by1 = max(c["y"] + c["h"] for c in r)
            cand = {"x": x0 + bx0, "y": y0 + by0,
                    "w": bx1 - bx0, "h": by1 - by0,
                    "glyphs": len(r), "height": g["h"]}
            if best is None or cand["glyphs"] > best["glyphs"]:
                best = cand
    return best


def detect_watermark(src, width: int = SAMPLE_WIDTH,
                     samples: int = SAMPLES) -> dict | None:
    """Conservative text-watermark detection in the four corners.

    Returns a box in source pixels (already padded) or None when unsure.
    """
    frames, fw, fh = _sample_frames(src, width, samples)
    if not frames or fw < 80 or fh < 80:
        return None
    info = util.probe_info(src)
    sw, sh = info["width"], info["height"]
    cw, ch = int(fw * 0.30), int(fh * 0.20)
    m = max(2, int(fw * 0.015))
    corners = {
        "top-left": (m, m),
        "top-right": (fw - cw - m, m),
        "bottom-left": (m, fh - ch - m),
        "bottom-right": (fw - cw - m, fh - ch - m),
    }
    candidates = []
    for name, (x0, y0) in corners.items():
        box = _corner_line(frames, fw, fh, x0, y0, cw, ch)
        if box:
            box["corner"] = name
            candidates.append(box)
    if not candidates:
        return None

    best = max(candidates, key=lambda b: b["glyphs"])
    sx, sy = sw / fw, sh / fh
    x = int(best["x"] * sx)
    y = int(best["y"] * sy)
    w = max(4, int(best["w"] * sx))
    h = max(4, int(best["h"] * sy))
    pad = max(4, int(best["height"] * sy * 0.45))
    x, y, w, h = x - pad, y - pad, w + 2 * pad, h + 2 * pad
    x = max(1, min(x, sw - 2))
    y = max(1, min(y, sh - 2))
    w = min(w, sw - x - 1)
    h = min(h, sh - y - 1)
    if w < 8 or h < 6:
        return None
    # A text watermark is wide and flat; tall/scattered edges are scenery.
    if w / h < 1.6 or h > sh * 0.10 or w > sw * 0.45:
        return None
    best.update({"x": x, "y": y, "w": w, "h": h,
                 "confidence": "high" if best["glyphs"] >= 3 else "medium"})
    return best


# ---------------------------------------------------------------------- apply

def _apply(src, out, region: tuple[int, int, int, int], mode: str) -> None:
    x, y, w, h = region
    if mode == "blur":
        radius = max(2, min(12, min(w, h) // 6))
        fc = (f"[0:v]split[base][reg];[reg]crop={w}:{h}:{x}:{y},"
              f"boxblur={radius}:2[blur];[base][blur]overlay={x}:{y}[vout]")
        args = ["-filter_complex", fc, "-map", "[vout]", "-map", "0:a?",
                "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart"]
    else:
        args = ["-vf", f"delogo=x={x}:y={y}:w={w}:h={h}",
                "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart"]
    util.run_ffmpeg(src, args, out)


def run(args: argparse.Namespace) -> None:
    j = jobmod.Job.load(args.job)
    src = j.current_video()
    info = util.probe_info(src)
    W, H = info["width"], info["height"]

    if args.region:
        region = parse_region(args.region)
        detected = False
        note = "explicit region"
    else:
        found = detect_watermark(src, args.sample_width, args.samples)
        if not found:
            print("delogo: no watermark detected in the corners.")
            print("       pass --region X:Y:W:H for a graphic logo or an unusual spot.")
            return
        region = (found["x"], found["y"], found["w"], found["h"])
        detected = True
        note = f"auto ({found['corner']}, {found['glyphs']} glyphs)"

    x, y, w, h = region
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > W or y + h > H:
        raise util.ToolError(f"region {x}:{y}:{w}:{h} is outside the {W}x{H} frame")

    out = j.apath("delogo.mp4")
    _apply(src, out, region, args.mode)
    meta = util.probe_info(out)
    j.record("delogo", {"region": f"{x}:{y}:{w}:{h}", "mode": args.mode,
                        "detected": detected},
             {"delogo.mp4": {"duration": round(meta["duration"], 2),
                             "region": f"{x}:{y}:{w}:{h}", "mode": args.mode}})
    print(f"delogo.mp4  {util.fmt_ts(meta['duration'])}  "
          f"{w}x{h} at {x},{y}  ({args.mode}, {note})")
    print("current video is now delogo.mp4")
