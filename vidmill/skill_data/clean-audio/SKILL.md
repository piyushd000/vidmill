---
name: clean-audio
description: Denoise and loudness-normalize speech for clear, consistent delivery audio.
tags: audio, noise, loudness
---

# Clean audio

Use this when the user asks to remove background noise, fix uneven or quiet audio, or normalize loudness.

## Steps

1. Call `status` and confirm the current video has an audio track. If it does not, tell the user instead of running an audio tool.
2. Call `clean` with:
   - `engine: "auto"` — uses the best available denoiser and falls back safely.
   - `loudness: -16` for normal spoken video. Use `-14` for social platforms and `-18` when the user wants a quieter, more cinematic mix.
3. If the current video changed after the last clean pass (for example a new cut or overlay), call `clean` again on the new current video.
4. Finish with `export`, `preset: "final"` unless the user asked for another preset.

## Rules

- `clean` keeps video and audio in sync; it does not change the edit length.
- Do not stack repeated clean passes on the same artifact just to make it louder. One pass at the requested loudness is enough.
- If music is already mixed in, clean the voice before adding the music bed; otherwise denoising can pump the music.
- Tell the user what changed in one short line: noise reduction plus the LUFS target.
