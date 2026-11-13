"""Tool registry: tool name -> module. Each module defines PURPOSE, add_args(), run()."""

from . import apply_cuts, audio_clean, captions, export, face, pipeline, plan_cuts, probe, transcribe

REGISTRY = {
    "probe": probe,
    "transcribe": transcribe,
    "plan": plan_cuts,
    "cut": apply_cuts,
    "clean": audio_clean,
    "captions": captions,
    "face": face,
    "export": export,
    "pipeline": pipeline,
}
