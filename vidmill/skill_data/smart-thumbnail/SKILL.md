---
name: smart-thumbnail
description: Pick a strong video thumbnail from the footage by scoring frames or matching a written brief.
tags: vision, thumbnail, youtube, poster
---

# Smart thumbnail

Use this when the user asks for a thumbnail, a poster frame or a cover image
for the edit.

## Steps

1. Call `status` to see the job and its current video.
2. Call `thumbnail` with:
   - `query` — a short brief of what the cover should show, for example
     "product close-up" or "two people laughing". Omit it to just take the
     sharpest, best-lit frame.
   - `at` — only when the user names an exact moment; it overrides the search.
   - `width` — default 1280 is fine for most platforms.
   The tool writes `vision/assets/thumbnail.jpg` and `vision/thumbnail.json`
   with the chosen frame, time and scores.
3. Report the chosen time and why: the visual score, or how well it matched the
   brief.
4. If the user dislikes the result, offer one retry with a different brief, or
   ask for an exact `at` time — do not loop over many briefs unprompted.
5. Export the video as usual; the thumbnail is a separate image file.

## Rules

- The thumbnail is exported as a still image, not burned into the video. Never
  overlay it back onto the timeline.
- Semantic briefs need the optional vision extra; without it the pick uses
  sharpness, exposure and tags. Say which method was used.
- Do not invent a timestamp that was never indexed; use `at` only when the user
  asked for that moment, and let the tool snap to the nearest indexed frame.
- Thumbnails usually need large text on top; that is a design task outside this
  tool. Deliver the clean frame unless the user asks for text.
- If the video has no indexed frames yet, the tool builds a light index first;
  expect that to take a few seconds on a long video.
