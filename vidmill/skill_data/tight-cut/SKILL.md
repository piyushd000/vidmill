---
name: tight-cut
description: Tighten a talking-head edit by removing pauses, still frames and false starts, then export.
tags: cut, silence, retakes, pacing
---

# Tight cut

Use this when the user asks to tighten, shorten, remove dead air, remove pauses, remove retakes, or make a talking-head edit feel faster.

## Steps

1. Call `status` to confirm the current video and which artifacts already exist.
2. Call `plan` on the current video with:
   - `freeze: true` and `freeze_quiet_only: true` — removes still frames without cutting speech.
   - `mistakes: true` — applies false-start/retake cuts. Use it when the user wants retakes gone; leave it off when they only asked about pauses.
   - `no_silence: false` (the default) unless the user explicitly wants to keep pauses.
   - `pad: 0.2` or `0.25` if speech starts abruptly and the first syllable sounds clipped; otherwise keep the default.
   - `gap: 0.25` to `0.35` for pacing; do not go below `0.2`.
3. Read the plan's removed-seconds summary. If it removes a large share of the video, or the user did not ask for aggressive cuts, raise `pad` or turn `mistakes` off and re-plan.
4. Call `cut` to apply that plan.
5. If the job already had captions, or the user wants captions, call `captions` after `cut` so timings are remapped to the new video.
6. If the user also wants studio audio, call `clean` after the cut.
7. Finish with `export`, `preset: "final"` unless the user asked for another delivery preset.

## Rules

- `cut` applies the existing `cut_plan.json`. Never call `cut` twice expecting new ranges to appear.
- To remove one specific range, call `plan` with `cut: ["START:END"]` (seconds in the current video), then `cut`. Do not mix old explicit cuts with a new request.
- Protect speech: use `freeze_quiet_only`, and never lower `gap` or `pad` just to hit a target duration.
- Do not delete artifacts or reset the job; edits chain on the current video.
