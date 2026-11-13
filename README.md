<div align="center">

# vidmill

**The all-in-one AI video editor for the terminal.**

Turn raw footage into a finished, published video in one sitting —
cuts, captions, clean audio, face swap, delivery presets — entirely on
your own machine.

![CI](https://github.com/piyushd000/vidmill/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

</div>

---

## What is vidmill?

vidmill is a complete video editing product built around a simple idea:
**your editor should understand your video, not just play it.**

Give vidmill any footage — a talking-head recording, a vlog, a
presentation — and it will:

1. **Watch and listen** — produce a word-level transcript, find the
   pauses, spot the retakes and self-corrections
2. **Edit** — remove dead air and mistakes, keep every cut perfectly in
   sync, denoise and normalize the audio, burn word-synced captions,
   even swap in a face from a single reference photo
3. **Deliver** — export finished files for YouTube, Shorts/Reels, or
   your storage format of choice

You can drive it yourself from the terminal, or let an AI agent direct
the edit while you stay the editor-in-chief.

**No cloud. No uploads. No subscriptions.** Your footage never leaves
your computer, and vidmill is free software that will stay free.

## Why vidmill?

| | vidmill | Traditional editors |
|---|---|---|
| Editing decisions | **Understands speech and timing** | You scrub timelines by hand |
| Workflow | **One resumable chain, one command** | Dozens of menus and plugins |
| Your footage | **Never uploaded anywhere** | Cloud editors require uploads |
| Automation | **AI-agent ready via a tool manifest** | Closed, non-scriptable |
| Price & freedom | **Free, open source (AGPL)** | Subscriptions and lock-in |

## Features

- **Speech understanding** — word-level transcripts in 90+ languages,
  with exact timing for every word
- **Smart cutting** — automatic pause removal, false-start detection,
  and precise manual/agent-authored cuts; audio and video always stay
  in sync
- **Studio audio** — deep neural noise removal plus broadcast-standard
  loudness normalization in one pass
- **Word-synced captions** — burned into the video with correct
  styling, automatically re-timed after cuts
- **Neural face swap** — replace or restyle the face in your footage
  from a single reference image
- **Delivery presets** — YouTube-safe H.264, compact HEVC, 1080×1920
  Shorts/Reels vertical, 1920×1080 landscape
- **Resumable by design** — every edit is a plain job folder; interrupt
  anything and continue later, inspect or archive every step
- **Agent-ready** — a machine-readable manifest (`vmill tools --json`)
  lets any LLM agent discover and drive every tool

## Install

**Linux / macOS.** Python 3.10+ required; everything else is handled
by the installer.

```bash
git clone https://github.com/piyushd000/vidmill.git
cd vidmill
./install.sh            # core: transcription + editing + export
./install.sh --extras   # optional: neural face-swap module (needs conda)
```

Then confirm your machine is ready:

```bash
vmill doctor
```

## Quickstart — one command

```bash
vmill pipeline myvideo.mp4 --job myedit
```

That runs the full editing chain — understand, plan, cut, export — and
skips any step you've already done. A finished, pause-free, publish-ready
`final.mp4` lands in `myedit/`.

## Quickstart — step by step

```bash
vmill probe myvideo.mp4 --job myedit      # open the video
vmill transcribe --job myedit             # word-level transcript
vmill plan --job myedit --mistakes        # cut plan: pauses + retakes
vmill cut --job myedit                    # apply it -> cut.mp4
vmill clean --job myedit                  # denoise + loudness -> cleaned.mp4
vmill captions --job myedit               # word-synced captions
vmill export --job myedit --preset shorts # 1080x1920 -> final.mp4
vmill status --job myedit                 # inspect every step
```

## Let an AI direct the edit

The judgment calls — which take is wrong, which story to trim — are
what AI is good at. vidmill exposes them cleanly:

```bash
vmill transcribe --job myedit          # agent reads myedit/transcript.json
# agent writes myedit/agent_plan.json:
#   { "cuts": [ { "from_s": 60.98, "to_s": 63.30,
#                 "why": "false start, corrected on the next line" } ] }
vmill plan --job myedit --plan-file myedit/agent_plan.json
vmill cut   --job myedit
```

Any agent (LLM coding assistant, script, automation) can discover the
full toolset with `vmill tools --json` and drive the product end to end.
See [`examples/agent_plan.json`](examples/agent_plan.json).

## Face swap

```bash
vmill face --job myedit --image face.jpg
vmill export --job myedit
```

One reference photo is enough. The module installs with
`./install.sh --extras` (requires conda) and supports face-swap model
and enhancement options via `--extra` — see `vmill face --help`.

## The tools

| Command | What it does |
|---|---|
| `vmill probe` | Open a video as a job and record its specs |
| `vmill transcribe` | Word-level transcript + subtitle file |
| `vmill plan` | Build the cut plan (pauses, retakes, agent cuts) |
| `vmill cut` | Apply the plan — cuts stay perfectly in sync |
| `vmill clean` | Denoise and normalize the audio |
| `vmill captions` | Burn word-synced captions |
| `vmill face` | Neural face swap from a reference photo |
| `vmill export` | Delivery presets: `final`, `hevc`, `shorts`, `yt` |
| `vmill pipeline` | Run the whole chain, resumable |
| `vmill status` | Inspect a job's artifacts and history |
| `vmill doctor` | Verify your installation |

## How it fits together

Every edit is a **job folder**. Tools read the current result, produce
the next one, and record what they did — so the chain is resumable,
inspectable, and scriptable by anyone (human or AI):

```
probe ──► transcript ──► cut plan ──► cut ──► clean ──► captions ──► export
 (specs)   (the words)   (what to     (the    (studio   (burned in   (delivery
                          drop)        edit)   audio)    sync)        file)
```

Job folders are plain files — copy them, diff their `job.json`, archive
them, or hand them to an agent.

## Requirements

- Linux or macOS
- Python 3.10+
- ~5 GB free disk for optional AI models (downloaded on first use)
- A CPU is enough; any GPU accelerates transcription and face swap

## Roadmap

- [ ] Agent-native interface (MCP server over the same tools)
- [ ] Web UI on top of the job model
- [ ] Background music and B-roll tools
- [ ] Automatic GPU detection and acceleration profiles

## FAQ

**Is my footage uploaded anywhere?**
No. vidmill runs entirely on your machine. Nothing is sent to any
service, ever.

**How good are the automatic cuts?**
They are conservative by default: obvious pauses are removed, likely
retakes are suggested (shown with reasons, applied only when you ask).
You always have the final say.

**Can I use it in my workflow/scripts?**
That's the point. Every tool is a stable CLI with JSON output
(`vmill tools --json`), designed to be driven by scripts and AI agents.

## License

vidmill — the all-in-one AI video editor for the terminal.
Copyright (C) 2026 vidmill contributors.

This is free software: you can redistribute it and/or modify it under
the terms of the **GNU Affero General Public License v3.0 or later**
([LICENSE](LICENSE)). If you build something on vidmill — including a
hosted service — your version must also be released under the same
terms, so improvements always flow back to everyone. See the
[GNU AGPL FAQ](https://www.gnu.org/licenses/agpl-3.0.en.html#faq) for details.
