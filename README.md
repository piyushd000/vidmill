<div align="center">

# vidmill

**Automatic video editing for the terminal — entirely on your machine.**

From raw footage to a finished, publish-ready video in one command.
No cloud uploads, no subscriptions, and no AI API bill by default.

![CI](https://github.com/piyushd000/vidmill/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

</div>

---

## What it does

vidmill understands the speech in your footage, so it can edit the way
an editor would: remove pauses and still frames, cut dead air and
retakes, caption every word in sync, clean the audio, add music and
B-roll, and export for YouTube, Shorts/Reels or archival delivery.

It works on talking-head recordings, vlogs, presentations and
interviews — locally, with no account and no upload.

| | vidmill | Traditional editors |
|---|---|---|
| Editing decisions | **Understands speech and timing** | You scrub timelines by hand |
| Workflow | **One resumable chain, one command** | Dozens of menus and plugins |
| Your footage | **Never leaves your machine** | Cloud editors require uploads |
| Automation | **Agent-ready via CLI manifest + MCP** | Closed, non-scriptable |

## Features

- **One-command editing** — `vmill auto` goes from raw file to `final.mp4` with zero manual work
- **Every non-AI edit, automatic** — pauses, still frames, retakes, captions, audio cleanup and watermark removal all run by default
- **Zero AI bill by default** — the full edit runs locally; an optional single AI checkpoint costs a few cents at most
- **AI editor on demand** — ask for changes in plain language and the model calls the same tools you do
- **Editable skills** — bundled Markdown recipes the AI loads on demand, overridable per user or project
- **Speech-aware cuts** — pauses, still frames and false starts; video and audio always stay in sync
- **Word-synced captions** — burned in, automatically re-timed after every cut
- **Studio audio** — neural noise removal plus broadcast-standard loudness
- **Watermark removal** — conservative auto-detection in the corners, or an exact pixel region
- **No-copyright music & SFX** — verified commercial-safe catalog; list, download, mix
- **B-roll & overlays** — logos, watermarks, picture-in-picture and full-frame cutaways
- **Semantic vision** — scene cuts, a searchable frame index, zero-shot tags, smart thumbnails and transcript-to-B-roll matching; heuristics are free and a local image-text model is optional
- **HTML intros & outros** — render a HyperFrames composition and drop it onto the timeline
- **Face swap** — optional module driven by a single reference photo
- **Delivery presets** — YouTube H.264, compact HEVC, Shorts 1080×1920, landscape 1920×1080
- **GPU acceleration** — used automatically when the hardware encoder is genuinely available
- **Resumable job model** — every edit is a plain folder; inspect, archive or continue later
- **Agent-ready** — JSON tool manifest and a built-in MCP server
- **Local web UI** — drop a video, every edit ticked, it starts on its own

## Install

Linux or macOS, Python 3.10+:

```bash
git clone https://github.com/piyushd000/vidmill.git
cd vidmill
./install.sh            # core: transcription, editing, export
./install.sh --vision   # optional: local semantic vision (search, tags, B-roll)
./install.sh --extras   # optional: face swap (requires conda)

vmill doctor            # verify the installation
```

The installer provisions the required engines; `vmill doctor` reports
exactly what is ready and what is optional.

## Usage

### Automatic — upload and walk away

```bash
vmill auto myvideo.mp4 --job myedit
```

The free local pass probes the video, transcribes every word, removes
pauses, still frames and likely retakes, removes watermarks, cleans the
audio, burns word-synced captions, and exports `myedit/final.mp4`.
No API key is involved.

```bash
vmill auto myvideo.mp4 --job myedit                 # everything on
vmill auto myvideo.mp4 --job myedit --no-mistakes   # keep retakes
vmill auto myvideo.mp4 --job myedit --no-silence --no-freeze
vmill auto myvideo.mp4 --job myedit --watermark off # keep the watermark
vmill auto myvideo.mp4 --job myedit --watermark 1180:30:90:60
vmill auto --job myedit --ai                        # opt into one AI review
```

Watermark detection is deliberately conservative: it removes a wide,
text-like overlay that stays fixed in a corner, and does nothing when it
is unsure. Pass an explicit `X:Y:W:H` region for a graphic logo or an
unusual spot. `--watermark-mode blur` keeps the background texture
instead of interpolating it.

With `--ai` and an OpenAI-compatible key, vidmill sends **one compact
text digest** — never the video — asking what else should be cut. If no
key is set or the call fails, the free edit is delivered unchanged.

```bash
export VIDMILL_AI_KEY=sk-...                     # or OPENAI_API_KEY
export VIDMILL_AI_BASE=https://api.openai.com/v1 # any compatible API
export VIDMILL_AI_MODEL=gpt-4o-mini
```

### AI editor — change anything, in plain language

`vmill ai` is a separate, optional loop where the model can call **any
vidmill tool**: plan new cuts, remove a watermark, add a logo or B-roll,
re-caption, change the export preset. It receives the job state and tool
results only — never the video.

```bash
vmill ai --job myedit "cut the long pause at 0:42 and add my logo top-right"
vmill ai --job myedit "remove the corner watermark and export for Shorts"
vmill ai --job myedit --dry-run "..."    # show the request, make no call
```

Nothing changes without a tool call, every step is recorded in
`job.json`, and a failed request leaves the job intact.

### Skills — reusable edits the AI can load

vidmill ships with editing skills: short Markdown recipes for common
workflows such as tight cuts, captions, audio cleanup, logos, music,
Shorts delivery, B-roll, watermark removal and intros/outros. The AI
sees each skill's name and description, then loads the full recipe only
when it is relevant — so prompts stay small and the instructions are
easy to change.

```bash
vmill skills list
vmill skills show tight-cut
vmill skills add my-house-style --description "My channel's pacing and caption style." --edit
vmill skills edit tight-cut --from my-tight-cut.md
vmill skills reset tight-cut          # remove the override, restore bundled
vmill skills remove my-house-style
vmill skills check                    # validate every skill file
```

Skills are plain files:

- **user** — `~/.config/vidmill/skills/<name>/SKILL.md` (or `$VIDMILL_SKILLS_DIR`)
- **project** — `.vmill/skills/<name>/SKILL.md` in the directory where you run `vmill`
- **bundled** — ship with vidmill and act as defaults

A project skill overrides a user skill with the same name; a user skill
overrides the bundled one. The studio's AI panel has a **Skills** button
to browse, read, edit, create, reset and attach up to four skills to a
request. `vmill ai --skill tight-cut` preloads a recipe explicitly, and
`--no-skills` hides the library for that run.

The skills library is part of the agent surface too: MCP clients get
`skills` (management) and `skill` (load one recipe), and the CLI entry
appears in `vmill tools --json`.

### HTML intros & outros

Render a HyperFrames HTML composition and place it at the start or end
of the current cut, automatically matched to the job's resolution, frame
rate and audio:

```bash
vmill hyperframes --job myedit --project ./intro --where intro
vmill hyperframes --job myedit --project ./outro --where outro
vmill hyperframes --job myedit --project ./card  --where render
vmill hyperframes --check                        # is the toolchain ready?
```

Node.js 22+ is required; HyperFrames is fetched on demand through
`npx`, so it is not a dependency of the rest of vidmill.

### Step by step

```bash
vmill probe myvideo.mp4 --job myedit      # open the video
vmill transcribe --job myedit             # word-level transcript
vmill plan --job myedit --mistakes        # cut plan
vmill cut --job myedit                    # apply it -> cut.mp4
vmill delogo --job myedit                 # remove a watermark
vmill clean --job myedit                  # denoise + normalize
vmill captions --job myedit               # burned-in captions
vmill export --job myedit --preset shorts # delivery file
vmill status --job myedit                 # inspect artifacts
```

Every step skips work that already exists, so the chain is resumable.
`vmill pipeline myvideo.mp4 --job myedit` runs the whole chain at once.

### Web UI

```bash
vmill serve --open        # http://127.0.0.1:8765
```

Drop a video onto the page and the free local pass starts immediately:
the checklist below the upload area has every non-AI edit ticked by
default — silences, still frames, retakes, captions, audio cleanup and
watermark removal. Untick anything you want to keep, or paste an exact
watermark region, and the next run starts again from the original
source. The log streams live and the result plays in the browser when it
is ready. The optional AI panel lets you ask for further changes in plain
language; it greys out when no API key is configured.

The editor is a three-pane studio: a media bin and project inspector on
the left, the program monitor with a multi-track timeline in the centre,
and the AI editor on the right. The bin shows every output plus its source,
with thumbnails and waveforms generated locally; import extra video, audio
or image assets straight into it. Projects opened by path keep the
original file in place and show it in the bin without copying it.

Jobs live in `~/vmill-jobs` (`--dir` to change). The server is
standard-library only and binds loopback by default.

### Music & sound effects

```bash
vmill music list --mood happy --json    # browse the verified catalog
vmill music get carefree --job myedit   # download into the job
vmill music mix carefree --job myedit   # mix under the voice
```

Every track is commercial-safe (CC0, public domain or CC BY). `mix`
loops, ducks and fades the music and prints the attribution line your
video description needs.

### B-roll, logos & watermarks

```bash
vmill overlay --job myedit --image logo.png --position top-right \
              --scale 0.15 --at 0 --to 10 --fade 0.4
vmill overlay --job myedit --video broll.mp4 --mode pip --at 5 --to 11
vmill overlay --job myedit --video broll.mp4 --mode cutaway --at 5 --to 11
```

Overlays stack as `overlay_1.mp4`, `overlay_2.mp4`, … and become the
current video, so captions and export chain on top. `--spec
overlays.json` applies a list in one run.

To remove an existing watermark rather than add one, use `vmill delogo`
(auto-detects text overlays in the corners, or pass `--region X:Y:W:H`).

### Semantic vision

`vmill vision` gives the editor a sense of what is on screen:

```bash
vmill vision scenes --job myedit            # cut list -> vision/scenes.json
vmill vision index  --job myedit            # searchable frames + tags
vmill vision search --job myedit "hands on a keyboard"
vmill vision tag    --job myedit            # what is in each scene
vmill vision thumbnail --job myedit "product close-up"
vmill vision broll  --job myedit --extract  # match B-roll to the spoken lines
```

- **Scene cuts** come from low-resolution frame signatures, so they are
  fast and free on any machine.
- **The index** samples frames at scene midpoints and describes each one
  with colour, sharpness and nearby transcript words.
- **Search** ranks frames against what you type — or, with the optional
  local image-text model installed, against its understanding of the
  picture.
- **Thumbnails** pick the sharpest, best-lit frame, or the one that best
  matches a description.
- **B-roll matching** proposes cutaways for each spoken line and writes
  `vision/assets/overlays.json`, which `vmill overlay --spec` applies.

The model is downloaded once, stays on your machine and is never used
for the free path — everything above works without it. `vmill vision
check` reports what is ready, and `vmill doctor` shows whether the
optional model is installed.

### Face swap

```bash
vmill face --job myedit --image face.jpg
vmill export --job myedit
```

Requires the optional module from `./install.sh --extras`; see
`vmill face --help` for model and enhancement options.

### Agents

Every capability is a stable CLI tool with declared inputs and outputs:

```bash
vmill tools --json     # machine-readable manifest
vmill mcp              # MCP server over stdio (Claude Desktop, etc.)
```

MCP client configuration:

```json
{
  "mcpServers": {
    "vidmill": { "command": "vmill", "args": ["mcp"] }
  }
}
```

Schemas are generated from the real CLI, so the agent surface cannot
drift from the product.

## The tools

| Command | What it does |
|---|---|
| `vmill auto` | The whole edit in one command — upload and walk away |
| `vmill probe` | Open a video as a job and record its specs |
| `vmill transcribe` | Word-level transcript + subtitle file |
| `vmill plan` | Build the cut plan (pauses, still segments, retakes, agent cuts) |
| `vmill cut` | Apply the plan — cuts stay perfectly in sync |
| `vmill delogo` | Remove a watermark/logo (auto-detected or exact region) |
| `vmill clean` | Denoise and normalize the audio |
| `vmill captions` | Burn word-synced captions |
| `vmill face` | Neural face swap from a reference photo |
| `vmill ai` | Natural-language edits through any tool, via your own API key |
| `vmill skills` | List, read, add, edit, reset and remove AI editing skills |
| `vmill music` | No-copyright music & SFX: list, download, mix |
| `vmill overlay` | Logos, watermarks and B-roll (pip or full-frame cutaway) |
| `vmill vision` | Scene cuts, visual search, tags, thumbnails, B-roll matching |
| `vmill hyperframes` | Render HTML intros/outros and place them on the timeline |
| `vmill export` | Delivery presets: `final`, `hevc`, `shorts`, `yt` |
| `vmill pipeline` | Run the whole chain, resumable |
| `vmill mcp` | MCP server: every tool for AI agents over stdio |
| `vmill serve` | Local web UI: upload, edit, watch, download |
| `vmill status` | Inspect a job's artifacts and history |
| `vmill doctor` | Verify your installation |

## How it works

Every edit is a **job folder**. Each tool reads the current result,
produces the next artifact, and records what it did — which makes the
chain resumable, inspectable and scriptable by humans and agents alike:

```
probe ──► transcript ──► cut plan ──► cut ──► delogo ──► clean ──► captions ──► export
 (specs)   (the words)   (what to     (the    (watermark  (studio   (burned in   (delivery
                          drop)        edit)   removed)    audio)    sync)        file)
```

Job folders are plain files: copy them, diff `job.json`, archive them,
or hand them to an agent.

## Requirements

- Linux or macOS
- Python 3.10+
- Node.js 22+ only for HTML intros/outros (`vmill hyperframes`) — optional
- ~5 GB free disk for optional model downloads (first use only); the
  semantic vision model is about 600 MB and downloads on first index
- A CPU is enough. A GPU accelerates transcription and delivery
  exports when a working hardware encoder is present — both are
  detected automatically, with a CPU fallback.

## Contributing

Contributions are welcome: bug fixes, new tools, documentation and
engine improvements. The full guide lives in
[CONTRIBUTING.md](CONTRIBUTING.md).

### Report a bug

Open an [issue](https://github.com/piyushd000/vidmill/issues/new?template=bug_report.md)
with:

- the command you ran and what happened
- `vmill --version`, your OS, and the output of `vmill doctor`
- the relevant part of the job log or traceback

### Fix a bug and send a commit

```bash
# 1. fork the repository on GitHub, then:
git clone https://github.com/<your-user>/vidmill.git
cd vidmill
git remote add upstream https://github.com/piyushd000/vidmill.git

# 2. work on a branch, never on main
git checkout -b fix/short-description

# 3. make the change, then run the same checks as CI
python -m compileall vidmill
vmill doctor
vmill hyperframes --check
vmill tools --json | python -m json.tool > /dev/null
vmill mcp --check
vmill serve --check

# 4. commit and push
git add -A
git commit -m "fix: one-line summary of the change"
git push origin fix/short-description
```

Then open a pull request against `main`. Keep one logical change per
pull request, describe the problem, the fix and how you verified it,
and make sure CI is green. Write clear commit messages in the
`fix:`, `feat:` or `docs:` style.

### Add a tool

1. Create `vidmill/tools/<name>.py` with `PURPOSE`, `add_args()` and
   `run()` — follow the existing modules.
2. Register it in `vidmill/tools/__init__.py` and describe it in
   `vidmill/registry.py`.
3. Regenerate the agent manifest: `vmill tools --json > tools.json`.
4. Add a row to the tools table above and a short usage section.
5. Verify: `python -m compileall vidmill && vmill mcp --check`.

By contributing you agree that your changes are released under the
project license, AGPL-3.0-or-later.

## FAQ

**Is my footage uploaded anywhere?**
No. vidmill runs entirely on your machine. Nothing is sent to any
service unless you explicitly opt into the AI checkpoint, and even then
only a compact text digest is sent — never the video.

**How aggressive are the automatic cuts?**
Conservative by default: obvious pauses are removed, still segments
are dropped only where nobody is speaking, and likely retakes are
dropped with a confidence margin — `--no-mistakes` keeps them all. The
optional AI review can only add a few reasoned cuts; you always have the
final say.

**Will it remove a watermark it shouldn't?**
It only removes a wide, flat, text-like overlay that stays fixed in a
corner across the whole video. If it is not confident, it does nothing
and tells you. For graphic logos or unusual placements, pass the exact
`--region X:Y:W:H`.

**Can I drive it from scripts or an AI agent?**
Yes — that is the design. Every tool is a stable CLI with declared
inputs and outputs, discoverable via `vmill tools --json`, plus an
MCP server for agent frameworks.

## License

vidmill — automatic video editing for the terminal.
Copyright (C) 2026 vidmill contributors.

This is free software: you can redistribute it and/or modify it under
the terms of the **GNU Affero General Public License v3.0 or later**
([LICENSE](LICENSE)). If you build something on vidmill — including a
hosted service — your version must also be released under the same
terms, so improvements always flow back to everyone. See the
[GNU AGPL FAQ](https://www.gnu.org/licenses/agpl-3.0.en.html#faq) for details.
