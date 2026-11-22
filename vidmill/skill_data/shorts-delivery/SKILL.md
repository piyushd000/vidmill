---
name: shorts-delivery
description: Deliver a vertical Shorts, Reels or TikTok file with readable captions and the right preset.
tags: export, shorts, vertical, social
---

# Shorts delivery

Use this when the user asks for Shorts, Reels, TikTok, a vertical video, or a 1080x1920 delivery.

## Steps

1. Call `status` and note the source aspect ratio. The `shorts` preset fits the whole frame into 1080x1920 and pads the sides; it does not crop or auto-reframe. If the user expects a full-frame crop from landscape footage, explain that limitation before exporting.
2. If the video needs captions, use `captions` first with `words_per_line: 3` and a larger `fontsize` suited to a phone screen. Reburn them after any cut or overlay.
3. Call `export` with `preset: "shorts"` and `out_name: "final.mp4"` unless the user asks for a different name.
4. For a 1920x1080 landscape master, use `preset: "yt"`. For a smaller file, use `preset: "hevc"` only when the user cares about size and compatibility is acceptable.
5. Confirm the final dimensions from the export output in your summary.

## Rules

- The preset is delivery, not editing. Make cuts, overlays and captions before the final export.
- Do not upscale a low-resolution source just to fill the vertical frame; the padded result is usually cleaner.
- Keep text inside the middle safe area; platform UI covers the outer edges.
- Do not export twice unless the current video changed after the first export.
