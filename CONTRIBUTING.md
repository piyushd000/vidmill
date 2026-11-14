# Contributing to vidmill

Thanks for taking the time to improve vidmill. This guide covers the
development workflow, how to report and fix bugs, and how to add a new
tool. Everything here mirrors what CI runs, so a green local run means
a green pull request.

## Ways to contribute

- **Bug reports** — reproducible issues with logs are the most valuable
  contributions. Open one with the bug report template.
- **Bug fixes and features** — small, focused pull requests against
  `main`.
- **Documentation** — clearer usage, examples and troubleshooting.
- **Engine and performance work** — faster cuts, better defaults,
  hardware support, new presets.

For anything larger than a bug fix, open an issue first so the design
can be discussed before you invest time.

## Development setup

Requirements: Linux or macOS, Python 3.10+, git, and the engines the
installer provisions.

```bash
git clone https://github.com/piyushd000/vidmill.git
cd vidmill

./install.sh              # provisions engines + installs vidmill (editable)
# or, if the engines are already installed:
pip install -e .
pip install faster-whisper

vmill doctor              # everything core should be OK
```

If you plan to work on the face-swap module, run `./install.sh --extras`.
Node.js 22+ is only needed for `vmill hyperframes`; AI editing (`vmill ai`)
needs an OpenAI-compatible key in the environment. Neither is required
for the core test suite.

## Repository layout

```
vidmill/
  cli.py               argument parsing + built-in commands
  job.py               job folder model (artifacts, history, current video)
  registry.py          the tool manifest (what agents see)
  mcp_server.py        MCP server over stdio
  web.py               local web UI (stdlib only)
  tools/               one module per tool: PURPOSE, add_args(), run()
  assets/music.json    verified no-copyright audio catalog
  tools.json           generated manifest (commit it after registry changes)
  install.sh           installer
  .github/workflows/   CI
```

Each tool is a small module. `run()` reads the current video from the
job, writes a new artifact, and records it with `job.record()`. That is
the whole architecture — keep new tools to the same shape.

## Before you open a pull request

Run exactly what CI runs:

```bash
python -m compileall vidmill
vmill doctor
vmill hyperframes --check
vmill tools --json | python -m json.tool > /dev/null
vmill mcp --check
vmill serve --check
```

If `registry.py` changed, regenerate and commit the manifest:

```bash
vmill tools --json > tools.json
```

If your change touches a tool, also run it end to end on a small clip
you can regenerate, for example:

```bash
ffmpeg -f lavfi -i testsrc=duration=4:size=640x360:rate=30 \
       -f lavfi -i sine=frequency=440:duration=4 \
       -c:v libx264 -c:a aac -shortest /tmp/clip.mp4
vmill auto /tmp/clip.mp4 --job /tmp/clip-job --no-ai
vmill status --job /tmp/clip-job
```

Regenerate the agent manifest whenever `registry.py` changes:

```bash
vmill tools --json > tools.json
```

## Reporting a bug

Open an issue using the
[bug report template](https://github.com/piyushd000/vidmill/issues/new?template=bug_report.md).
A good report includes:

1. What you ran (the full command).
2. What you expected and what happened instead.
3. `vmill --version`, your OS, and the output of `vmill doctor`.
4. The relevant traceback or the tail of the job log
   (`vmill status --job <dir>`).
5. If possible, a minimal clip or exact steps that reproduce it.

Do not paste secrets. Redact API keys and private paths.

## Fixing a bug: the full workflow

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/<your-user>/vidmill.git
cd vidmill
git remote add upstream https://github.com/piyushd000/vidmill.git

# Stay current
git fetch upstream
git checkout -b fix/short-description upstream/main

# ... make the change ...

# Verify (see "Before you open a pull request")
python -m compileall vidmill
vmill mcp --check && vmill serve --check && vmill hyperframes --check

git add -A
git commit -m "fix: what changed and why"
git push origin fix/short-description
```

Open a pull request against `main` with:

- a link to the issue it fixes,
- the root cause in one or two sentences,
- how you verified the fix (commands, before/after),
- screenshots or a short clip for visible changes.

Keep one logical change per pull request. If your branch falls behind,
rebase on `upstream/main` rather than merging. CI must be green before
review.

## Commit messages

Use a short imperative subject line, optionally with a body:

```
fix: keep captions in sync when the plan starts mid-word

The first word could be clipped by the cut boundary because padding was
applied after remapping. Remap first, then pad.
```

Prefixes: `fix:`, `feat:`, `docs:`, `refactor:`, `perf:`, `test:`,
`chore:`.

## Adding a tool

1. Create `vidmill/tools/<name>.py`:

   ```python
   PURPOSE = "one line shown in `vmill tools` and the MCP manifest"

   def add_args(p):
       p.add_argument("--job", required=True)
       # ... tool-specific flags ...

   def run(args):
       j = jobmod.Job.load(args.job)
       src = j.current_video()
       out = j.apath("<artifact>.mp4")
       # ... do the work, then record it:
       j.record("<name>", {"flag": "value"}, {"<artifact>.mp4": {"duration": ...}})
   ```

2. Register it in `vidmill/tools/__init__.py` (`REGISTRY`) and describe
   its inputs/outputs/engine in `vidmill/registry.py` (`TOOLS`).
3. Regenerate the manifest: `vmill tools --json > tools.json`.
4. Add a row to the README tools table and a short usage section.
5. Verify: `python -m compileall vidmill && vmill mcp --check`, then run
   the tool end to end on a small clip.

The MCP server derives its schema from `add_args()`, so agents see the
new tool automatically — no extra wiring.

## Code style

- Python standard library first; avoid new heavy dependencies without
  discussion in an issue.
- Match the surrounding style: type hints where present, `util.ToolError`
  for user-facing failures, `util.run_ffmpeg()` for encodes.
- Keep tools deterministic and resumable: no hidden state outside the
  job folder.
- Prefer clear, user-facing error messages over tracebacks.

## License

vidmill is licensed under AGPL-3.0-or-later. By submitting a pull
request you agree that your contribution is released under the same
license.
