"""Tool registry: tool name -> module. Each module defines PURPOSE, add_args(), run()."""

from . import apply_cuts, audio_clean, auto, captions, export, face, music, overlay, pipeline, plan_cuts, probe, transcribe

REGISTRY = {
    "probe": probe,
    "transcribe": transcribe,
    "plan": plan_cuts,
    "cut": apply_cuts,
    "clean": audio_clean,
    "captions": captions,
    "face": face,
    "music": music,
    "overlay": overlay,
    "auto": auto,
    "export": export,
    "pipeline": pipeline,
}
