---
name: brand-logo
description: Place a logo, bug or picture overlay at a corner with a controlled size, opacity and fade.
tags: overlay, logo, branding
---

# Brand logo

Use this when the user asks to add their logo, a brand bug, a watermark or a picture overlay.

## Steps

1. Call `status` and check the media bin. The image should already be in the job or be an absolute path. If it is missing, ask the user to import it rather than inventing a path.
2. Call `overlay` with:
   - `image` — the logo or picture.
   - `position: "top-right"` by default. Choose another corner only when the user asks, or when the top-right is occupied by an existing graphic.
   - `scale: 0.15` as a default; `0.10` to `0.15` for a small persistent bug, `0.2` to `0.3` for a short branded card.
   - `opacity: 0.9` for a subtle bug, `1.0` when the brand must be fully legible.
   - `at` / `to` only for a timed appearance, otherwise the logo stays for the whole video.
   - `fade: 0.3` when the logo appears or disappears mid-video.
3. If the logo would cover captions or a face, move it to another corner or reduce `scale`.
4. Finish with `export`, `preset: "final"` unless the user asked for another preset.

## Rules

- This skill adds an overlay. To remove an existing watermark, use the `watermark-removal` skill with `delogo` instead.
- Positions are presets or `X:Y`; `scale` is a fraction of video width, not a percentage.
- Overlays stack as `overlay_1.mp4`, `overlay_2.mp4`, … and become the current video, so captions and export must come after all overlays.
- Keep the safe margin in mind: the default margin is about 4% of the width, which is safe for most platforms.
