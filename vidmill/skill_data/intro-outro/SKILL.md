---
name: intro-outro
description: Add a rendered HTML intro or outro to the current cut, after captions are final.
tags: hyperframes, intro, outro, branding
---

# Intro and outro

Use this when the user asks for a branded intro, an end card, a title sequence, or a rendered HTML clip at the start or end.

## Steps

1. Call `hyperframes` with `check: true` first. If the toolchain is not ready, report what is missing instead of trying to render.
2. If the user already has a rendered clip, call `hyperframes` with `clip` and `where: "intro"` or `where: "outro"`.
3. Otherwise call `hyperframes` with:
   - `project` — the composition directory or `.html` file.
   - `where: "intro"` or `where: "outro"`.
   - `quality: "delivery"` for the final render, or `"draft"` while iterating.
4. The tool matches the current video's resolution, frame rate and audio, then makes the combined file current.
5. Call `export` with `preset: "final"` unless the user asked for another preset.

## Rules

- Add intros and outros after captions are final. Caption timings do not account for an added intro, so adding one first shifts every caption.
- If the video is already exported and the user only wants the intro, re-export after placing it so `final.mp4` includes the new section.
- Do not render an intro and an outro in one call. Place one, then the other.
- Keep the composition's own duration reasonable; this tool places the rendered clip, it does not trim it.
- If Node is unavailable, the rest of the edit still works — report the limitation and continue with the non-HTML steps.
