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

1. **Understand** — produce a word-level transcript, find the pauses,
   the frozen still frames, and the retakes
2. **Edit** — remove dead air and mistakes, keep every cut perfectly in
   sync, denoise and normalize the audio, burn word-synced captions,
   add no-copyright music, even swap in a face from a single photo
3. **Deliver** — export finished files for YouTube, Shorts/Reels, or
   your storage format of choice

One command does all of it automatically (`vmill auto`). You can also
drive each step yourself from the terminal, or let an AI agent direct
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

- **One-command editing** — `vmill auto` takes a raw video from upload
  to publish-ready with no manual work and no AI API bill
- **Speech understanding** — word-level transcripts in 90+ languages,
  with exact timing for every word
- **Smart cutting** — automatic pause removal, still-frame ("no
  movement") removal, false-start detection, and precise
  manual/agent-authored cuts; audio and video always stay in sync
- **Studio audio** — deep neural noise removal plus broadcast-standard
  loudness normalization in one pass
- **Word-synced captions** — burned into the video with correct
  styling, automatically re-timed after cuts
- **Neural face swap** — replace or restyle the face in your footage
  from a single reference image
- **B-roll & overlays** — logos, watermarks and picture-in-picture or
  full-frame B-roll, positioned and timed from the command line
- **No-copyright music & SFX** — a built-in, verified, commercial-safe
  catalog: list, download, and mix without leaving the terminal
- **Delivery presets** — YouTube-safe H.264, compact HEVC, 1080×1920
  Shorts/Reels vertical, 1920×1080 landscape
- **Resumable by design** — every edit is a plain job folder; interrupt
  anything and continue later, inspect or archive every step
- **Agent-ready** — a machine-readable manifest (`vmill tools --json`)
  and a built-in MCP server (`vmill mcp`) let any LLM agent discover
  and drive every tool

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
vmill auto myvideo.mp4 --job myedit
```

That's the whole workflow: upload (or point at) a video, walk away, and
come back to a finished edit — pauses and still frames removed,
subtitles generated and burned in, audio cleaned, and a publish-ready
`final.mp4` exported. No manual work, no AI API bill.

Prefer to stay in control? Run the chain yourself:

```bash
vmill pipeline myvideo.mp4 --job myedit
```

Every step is skipped if its result already exists, so the chain is
resumable.

## Fully automatic — upload and walk away

`vmill auto` runs the entire edit with zero manual work:

```bash
vmill auto myvideo.mp4 --job myedit            # fully free, no AI call
vmill auto myvideo.mp4 --job myedit --mistakes # also drop likely retakes
vmill auto --job myedit --ai                   # opt into ONE AI review
```

What happens on the free pass:

1. **Understand** the video (probe) and transcribe every word locally
2. **Plan** the cuts: long pauses, frozen "no movement" segments
   (still frames while nobody talks), and optionally likely retakes
3. **Cut**, **clean** the audio, **caption** word-synced, **export**

Then the optional AI checkpoint. By default this costs nothing — if no
API key is set, the free edit is simply delivered. With
`--ai` and an OpenAI-compatible key, vidmill makes **one compact text
call** (a transcript digest of a few thousand characters — the video
itself is never uploaded) asking: *what else should be cut?* Suggested
cuts are applied automatically and the video is re-exported.

```bash
export VIDMILL_AI_KEY=sk-...                        # or OPENAI_API_KEY
export VIDMILL_AI_BASE=https://api.openai.com/v1    # any compatible API
export VIDMILL_AI_MODEL=gpt-4o-mini
vmill auto myvideo.mp4 --job myedit --ai
```

If the call fails or returns nonsense, the free local edit is kept and
delivered — the checkpoint can only improve the video, never break it.

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

## Agent-native: built-in MCP server

vidmill speaks the Model Context Protocol out of the box — no plugins,
no wrapper scripts:

```bash
vmill mcp          # JSON-RPC on stdio, pure protocol
vmill mcp --check  # self-test: initialize + list all tools
```

Point any MCP client at it, e.g. Claude Desktop:

```json
{
  "mcpServers": {
    "vidmill": { "command": "vmill", "args": ["mcp"] }
  }
}
```

The agent then sees every tool — `auto`, `transcribe`, `plan`, `overlay`,
`music`, `export`, … — with schemas generated from the real CLI, so they
can never drift. Tool output is returned as text; failures come back as
errors without killing the server.

## Face swap

```bash
vmill face --job myedit --image face.jpg
vmill export --job myedit
```

One reference photo is enough. The module installs with
`./install.sh --extras` (requires conda) and supports face-swap model
and enhancement options via `--extra` — see `vmill face --help`.

## Music & sounds

A curated catalog of no-copyright music and sound effects ships with
vidmill — every track is commercial-safe (CC0, public domain, or CC BY)
and every download link is verified:

```bash
vmill music list --mood happy --json    # browse the catalog
vmill music get carefree --job myedit   # download into the job
vmill music mix carefree --job myedit   # mix it under the voice
```

`mix` loops the track to cover the video, lowers it under speech,
fades it out at the end, and prints the attribution line (CC BY tracks
need a credit in your video description; CC0 and public-domain tracks
need nothing). An agent can list the catalog, pick a mood, download and
mix — three commands, no third-party service.

## B-roll, logos & watermarks

```bash
# logo / watermark: top-right, 15% width, fade in and out
vmill overlay --job myedit --image logo.png --position top-right \
              --scale 0.15 --at 0 --to 10 --fade 0.4

# B-roll as picture-in-picture in a time window
vmill overlay --job myedit --video broll.mp4 --mode pip --at 5 --to 11

# B-roll replaces the full frame (main audio stays underneath)
vmill overlay --job myedit --video broll.mp4 --mode cutaway --at 5 --to 11
```

Positions are `top-left`, `top-right`, `bottom-left`, `bottom-right`,
`center`, or a raw `X:Y` expression. Every pass writes `overlay_1.mp4`,
`overlay_2.mp4`, … and becomes the current video, so overlays stack and
captions/export chain on top. `--spec overlays.json` applies a whole
list in one run:

```json
{"overlays": [
  {"image": "logo.png", "position": "top-right", "scale": 0.15, "at": 0},
  {"video": "broll.mp4", "mode": "cutaway", "at": 5, "to": 9}
]}
```

## The tools

| Command | What it does |
|---|---|
| `vmill auto` | The whole edit in one command — upload and walk away |
| `vmill probe` | Open a video as a job and record its specs |
| `vmill transcribe` | Word-level transcript + subtitle file |
| `vmill plan` | Build the cut plan (pauses, still segments, retakes, agent cuts) |
| `vmill cut` | Apply the plan — cuts stay perfectly in sync |
| `vmill clean` | Denoise and normalize the audio |
| `vmill captions` | Burn word-synced captions |
| `vmill face` | Neural face swap from a reference photo |
| `vmill music` | Curated no-copyright music & SFX: list, download, mix |
| `vmill overlay` | Logos, watermarks and B-roll (pip or full-frame cutaway) |
| `vmill export` | Delivery presets: `final`, `hevc`, `shorts`, `yt` |
| `vmill pipeline` | Run the whole chain, resumable |
| `vmill mcp` | MCP server: every tool for AI agents over stdio |
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

- [x] Fully automatic edit mode (`vmill auto`) with an optional single AI checkpoint
- [x] Built-in no-copyright music & sound effects catalog (`vmill music`)
- [x] B-roll and image overlay tools (`vmill overlay`)
- [x] Agent-native interface (MCP server over the same tools)
- [ ] Web UI on top of the job model
- [ ] Automatic GPU detection and acceleration profiles

## FAQ

**Is my footage uploaded anywhere?**
No. vidmill runs entirely on your machine. Nothing is sent to any
service, ever.

**How good are the automatic cuts?**
They are conservative by default: obvious pauses are removed, still
"no movement" segments are dropped only where nobody is speaking,
likely retakes are suggested (shown with reasons, applied only when you
ask). The AI checkpoint (if you opt in) suggests at most a few more
cuts, with reasons, and can never remove meaningful content. You always
have the final say.

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
