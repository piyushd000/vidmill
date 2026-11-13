"""
vidmill (vmill) — one open-source CLI that turns AI video engines
(FFmpeg, Faster-Whisper, FaceFusion, DeepFilterNet) into connected,
agent-friendly tools.

Every tool reads and writes artifacts inside a *job directory*:
transcripts, cut plans, clips, finals. Tools connect through those
artifacts, so any human — or any AI agent — can run the chain
step by step or all at once with `vmill pipeline`.
"""

__version__ = "0.1.0"

APP_NAME = "vidmill"


class ToolError(Exception):
    """A tool failed. CLI prints it cleanly; agents can catch it."""


__all__ = ["__version__", "APP_NAME", "ToolError"]
