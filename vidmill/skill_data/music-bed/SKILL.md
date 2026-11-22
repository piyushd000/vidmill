---
name: music-bed
description: Choose a commercial-safe track and mix a low music bed under the spoken audio.
tags: music, audio, atmosphere
---

# Music bed

Use this when the user asks for background music, a music bed, or a mood under the voice.

## Steps

1. Call `music list` with a `mood` that matches the request (`calm`, `happy`, `tense`, `ambient`) and `type: "music"`. Only choose from the returned catalog.
2. Prefer instrumental, low-motion tracks under speech. Avoid tracks with prominent vocals or sudden drops unless the user specifically wants that energy.
3. Call `music mix` with the chosen track `id`, the `job`, and:
   - `volume: 0.12` as a default; `0.08` to `0.10` for dense speech, up to `0.18` for an energetic montage.
4. Report the track title and the attribution line printed by the tool. The credit belongs in the video description when the license requires it.
5. Finish with `export`, `preset: "final"` unless the user asked for another preset.

## Rules

- The tool loops the track, ducks it under the voice and fades the ending. Do not add a second music pass on top.
- If the user already mixed music and asks for a different track, export from the pre-music artifact if one exists; otherwise state that the current mix is already baked in and ask before stacking.
- Music must never mask speech. When in doubt, lower `volume` and keep the voice dominant.
- `music get` only downloads a track. Use `music mix` when the goal is a finished edit.
- Do not use sound effects as a full-length bed; filter with `type: "sfx"` only when the user asks for a specific accent.
