"""Tool registry — the contract that makes this a *tool-based* AI app.

Every capability is a named tool with declared inputs/outputs and a
stable CLI call. `vf tools --json` emits this manifest so any AI agent
(LLM loop, MCP server, script) can discover and drive the app.
"""

from __future__ import annotations

from . import __version__, APP_NAME

TOOLS = [
    {
        "name": "probe",
        "cmd": "vf probe <video> --job <dir> [--copy]",
        "purpose": "Open a video as a job and record its media info (probe.json).",
        "inputs": {"video": "path", "job": "dir", "--copy": "copy source into job"},
        "outputs": ["job.json", "probe.json"],
        "engine": "ffprobe",
    },
    {
        "name": "transcribe",
        "cmd": "vf transcribe --job <dir> [--model large-v3-turbo] [--language auto]",
        "purpose": "Word-level transcript of the current video (transcript.json + srt).",
        "inputs": {"--model": "tiny|base|small|medium|large-v3|large-v3-turbo", "--language": "iso code or auto"},
        "outputs": ["transcript.json", "transcript.srt"],
        "engine": "faster-whisper",
    },
    {
        "name": "plan",
        "cmd": "vf plan --job <dir> [--threshold-db -40] [--pad 0.15] [--cut 12.3:14.8 ...] [--plan-file x.json]",
        "purpose": "Build cut_plan.json: segments to keep/drop from silence detection + explicit/agent cuts.",
        "inputs": {"--threshold-db": "silence threshold", "--pad": "keep this many seconds around speech",
                   "--cut": "force-remove range sec:sec (repeatable)", "--plan-file": "merge an agent-authored plan"},
        "outputs": ["cut_plan.json"],
        "engine": "ffmpeg silencedetect + transcript heuristics",
    },
    {
        "name": "cut",
        "cmd": "vf cut --job <dir> [--plan-file cut_plan.json]",
        "purpose": "Apply cut_plan.json to the current video -> cut.mp4 (trim+concat, audio kept in sync).",
        "inputs": {"--plan-file": "plan to apply (default: latest in job)"},
        "outputs": ["cut.mp4"],
        "engine": "ffmpeg trim/concat",
    },
    {
        "name": "clean",
        "cmd": "vf clean --job <dir> [--engine auto|dfnet|ffmpeg] [--loudness -16]",
        "purpose": "Denoise + loudness-normalize audio -> cleaned.mp4.",
        "inputs": {"--engine": "dfnet (DeepFilterNet env) or ffmpeg afftdn fallback", "--loudness": "LUFS target"},
        "outputs": ["cleaned.mp4"],
        "engine": "DeepFilterNet / ffmpeg afftdn+loudnorm",
    },
    {
        "name": "captions",
        "cmd": "vf captions --job <dir> [--style clean|box] [--words-per-line 4]",
        "purpose": "Burn word-synced captions from transcript.json -> captioned.mp4.",
        "inputs": {"--words-per-line": "caption line length", "--fontsize": "ass font size"},
        "outputs": ["captions.ass", "captioned.mp4"],
        "engine": "ffmpeg libass",
    },
    {
        "name": "face",
        "cmd": "vf face --job <dir> --image face.jpg [--model inswapper_128] [--extra '...raw facefusion args...']",
        "purpose": "Swap a reference face onto the current video (FaceFusion headless) -> swapped.mp4.",
        "inputs": {"--image": "reference face image", "--extra": "pass-through to facefusion"},
        "outputs": ["swapped.mp4"],
        "engine": "facefusion headless-run (conda env 'facefusion')",
    },
    {
        "name": "export",
        "cmd": "vf export --job <dir> [--preset final|hevc|shorts|yt] [--in <artifact>]",
        "purpose": "Export the current video with a delivery preset -> final.mp4.",
        "inputs": {"--preset": "final (h264/youtube)|hevc|shorts (1080x1920)|yt (1920x1080)"},
        "outputs": ["final.mp4"],
        "engine": "ffmpeg",
    },
    {
        "name": "pipeline",
        "cmd": "vf pipeline <video> --job <dir> --steps probe,transcribe,plan,cut,export",
        "purpose": "Run a chain of tools in order, skipping steps whose artifacts already exist (resumable).",
        "inputs": {"--steps": "comma list of tool names", "--args-plan": "extra args for plan step"},
        "outputs": ["whatever the chain produces"],
        "engine": "videoforge",
    },
    {
        "name": "status",
        "cmd": "vf status --job <dir>",
        "purpose": "Show artifacts, media info and the tool history of a job.",
        "inputs": {},
        "outputs": [],
        "engine": "videoforge",
    },
    {
        "name": "doctor",
        "cmd": "vf doctor",
        "purpose": "Check which engines are installed and usable on this machine.",
        "inputs": {},
        "outputs": [],
        "engine": "videoforge",
    },
]


def manifest() -> dict:
    return {
        "name": APP_NAME,
        "version": __version__,
        "description": ("Open-source AI video editing toolkit: FFmpeg, Faster-Whisper, "
                        "FaceFusion and DeepFilterNet exposed as connected CLI tools "
                        "that any human or AI agent can orchestrate."),
        "job_model": ("Tools read/write artifacts inside one job directory. "
                      "Each tool consumes the job's current video artifact and "
                      "records its output in job.json, so chains are resumable "
                      "and inspectable with `vf status`."),
        "tools": TOOLS,
    }
