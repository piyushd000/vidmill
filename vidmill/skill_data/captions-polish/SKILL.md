---
name: captions-polish
description: Add, restyle, enlarge or re-time burned-in captions that stay in sync with every cut.
tags: captions, subtitles, accessibility
---

# Captions polish

Use this when the user asks for captions, subtitles, bigger text, a caption style change, or captions that are out of sync after an edit.

## Steps

1. Call `status`. If the job has no `transcript.json`, call `transcribe` first. Pass `language` only when the user says what language is spoken; otherwise let it detect.
2. If the current video changed after the last caption pass (cuts, overlays, an intro), call `captions` again. It remaps the transcript through the cut plan automatically.
3. Call `captions` with:
   - `style: "clean"` for normal footage, `style: "box"` for busy or bright backgrounds.
   - `words_per_line: 4` as a default; `3` for vertical/social edits, `5` for dense information.
   - `fontsize` only when the user asks for a specific size, or when the default looks small on a vertical delivery. Keep it proportional to the video height.
4. Finish with `export`, `preset: "final"` unless the user asked for another preset.

## Rules

- Captions come from the transcript. Do not invent or rewrite words unless the user asks for copy changes; if they do, ask them to confirm the exact text.
- After any later cut or overlay, reburn captions on the new current video.
- Keep logos away from the caption zone: the caption style sits near the lower third.
- If the language is unclear and detection looks wrong, ask the user before transcribing the whole video again.
