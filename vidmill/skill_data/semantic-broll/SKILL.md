---
name: semantic-broll
description: Match B-roll cutaways to what is being said by indexing the footage and using transcript-to-visual matching.
tags: vision, b-roll, cutaway, transcript
---

# Semantic B-roll

Use this when the user asks to add B-roll that matches the narration, or wants
suggestions for what to show while each line is spoken.

## Steps

1. Call `status`. If the job has no `transcript.json`, call `transcribe` first —
   the matching is driven by the spoken lines.
2. Call `broll` with `extract: true` (and `library` only when the user points at
   a folder of extra images/video). The tool indexes the current video, scores
   every transcript line against indexed scenes and any imported assets, and
   writes:
   - `vision/broll.json` — one suggestion per line: time window, candidate,
     score, and a ready `overlay` command.
   - `vision/assets/overlays.json` — the extracted B-roll clips as a spec.
3. Read the suggestions. Reject any window that covers a face, a caption or a
   key on-screen graphic, and any suggestion whose score is clearly weak. You
   can drop entries from the spec before applying it.
4. Apply with `overlay` and `spec: "vision/assets/overlays.json"`. It creates
   `overlay_N.mp4` files and makes the last one current.
5. If captions exist or are wanted, call `captions` after the overlays, then
   `export`, `preset: "final"`.

## Rules

- Never call `overlay` once per suggestion; apply the written spec once.
- B-roll windows come from the transcript, so they already avoid cutting into
  the wrong sentence. Do not widen them beyond about 6 seconds.
- With no vision model installed the matching uses tags, filenames and the
  transcript; say so plainly if the suggestions look weak instead of inventing
  a better match.
- Semantic matching needs the optional vision extra. If `check` reports it is
  missing, still finish the free-path edit and mention the upgrade.
- Cutaways keep the main audio; never remove speech to make room for B-roll.
- After the overlays, the current video is the overlaid one: run captions and
  export on top of it, and do not re-run `broll` on the new artifact unless the
  user asks for another pass.
