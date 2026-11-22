---
name: b-roll-cutaway
description: Insert B-roll as a picture-in-picture or full-frame cutaway while keeping the main audio.
tags: overlay, b-roll, cutaway, pip
---

# B-roll cutaway

Use this when the user asks to add B-roll, cut away to other footage, or show a picture-in-picture reference.

## Steps

1. Call `status` and check the media bin for the B-roll clip. If it is missing, ask the user to import it; do not invent a filename.
2. Call `overlay` with:
   - `video` — the B-roll asset.
   - `mode: "cutaway"` for a full-frame replacement that keeps the main audio, or `mode: "pip"` for a smaller inset.
   - `at` and `to` — seconds in the current video. Keep cutaways roughly 2–6 seconds and align them with the spoken reference.
   - `scale` and `position` only for `pip`; use `bottom-right` or `top-right` and a scale around `0.25` to `0.35`.
3. If captions should appear over the B-roll, call `captions` after the overlay.
4. Finish with `export`, `preset: "final"` unless the user asked for another preset.

## Rules

- Cutaways replace the frame but not the voice. Never cut the main audio just to insert B-roll.
- B-roll loops when it is shorter than the requested window; keep windows short enough that the loop is not obvious.
- Do not cover faces, captions or key on-screen text with a PIP.
- Times are relative to the current video, not the original source. If the video was just cut, use the new timeline.
- Overlays stack and become the current video; do all overlays before the final captions and export.
