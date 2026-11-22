---
name: watermark-removal
description: Remove a fixed watermark or logo with an explicit pixel region or conservative auto-detection.
tags: delogo, watermark, cleanup
---

# Watermark removal

Use this when the user asks to remove a watermark, channel bug, logo or text overlay that is already burned into the video.

## Steps

1. Call `status` and inspect the video dimensions. A region is expressed in source pixels.
2. If the user gives a region, normalize it to `X:Y:W:H` with the top-left corner as the origin.
   - If they give only a corner or a description, do not guess precise pixels; ask for the region or offer conservative auto-detection.
3. Call `delogo` with:
   - `region: "X:Y:W:H"` when the box is known.
   - no region when the user is happy with auto-detection. Auto-detection only removes a confident, static, text-like corner overlay and does nothing when unsure.
   - `mode: "delogo"` for simple backgrounds; `mode: "blur"` when the background texture matters more than seamlessness.
4. Call `status` or inspect the tool output to confirm `delogo.mp4` was produced. If auto-detection found nothing, report that and ask for the region rather than running a blind crop.
5. Do this before captions and export so later steps chain on the cleaned video.
6. Finish with `export`, `preset: "final"` unless the user asked for another preset.

## Rules

- `delogo` treats the current video. If the current video is already captioned, removing a watermark can also affect nearby caption pixels; prefer doing it earlier in the chain.
- Do not crop or zoom the whole frame to hide a watermark unless the user explicitly accepts the reframing.
- A moving watermark cannot be tracked by this tool. If the watermark moves, explain the limitation instead of stacking many regions.
- Keep the region tight: a box much larger than the watermark removes more of the picture than necessary.
