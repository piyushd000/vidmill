"""Tool registry: tool name -> module. Each module defines PURPOSE, add_args(), run()."""

from . import (apply_cuts, audio_clean, auto, captions, delogo, export, face, music,
               overlay, pipeline, plan_cuts, probe, transcribe, vision)
from .. import ai_agent
from . import hyperframes

REGISTRY = {
    "probe": probe,
    "transcribe": transcribe,
    "plan": plan_cuts,
    "cut": apply_cuts,
    "delogo": delogo,
    "clean": audio_clean,
    "captions": captions,
    "face": face,
    "music": music,
    "overlay": overlay,
    "vision": vision,
    "hyperframes": hyperframes,
    "auto": auto,
    "ai": ai_agent,
    "export": export,
    "pipeline": pipeline,
}
