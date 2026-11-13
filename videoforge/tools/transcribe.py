"""Tool: transcribe — word-level transcript via Faster-Whisper.

Runs in the current Python env (faster-whisper is a pip dependency).
"""

from __future__ import annotations

import argparse

from .. import job as jobmod
from .. import util

PURPOSE = "word-level transcript of the current video (faster-whisper)"


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("--model", default="large-v3-turbo",
                   help="tiny|base|small|medium|large-v3|large-v3-turbo (default: large-v3-turbo)")
    p.add_argument("--language", default=None, help="iso code, e.g. en, hi; default: auto-detect")
    p.add_argument("--beam", type=int, default=5)
    p.add_argument("--device", default="auto", help="cpu | cuda | auto")


def run(args: argparse.Namespace) -> None:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise util.ToolError("faster-whisper not installed — pip install faster-whisper") from e

    j = jobmod.Job.load(args.job)
    src = j.current_video()
    print(f"transcribing {src.name} with {args.model} (this can take a few minutes)...")

    # decode via ffmpeg -> 16k mono float32 (avoids PyAV, works with any codec)
    import numpy as np
    raw = j.apath("audio_16k.f32")
    util.run([util.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
              "-i", str(src), "-vn", "-f", "f32le", "-acodec", "pcm_f32le",
              "-ac", "1", "-ar", "16000", str(raw)], quiet=True)
    audio = np.fromfile(raw, dtype=np.float32)
    raw.unlink(missing_ok=True)

    model = WhisperModel(args.model, device=args.device, compute_type="auto")
    segments_iter, info = model.transcribe(
        audio, language=args.language, beam_size=args.beam,
        word_timestamps=True, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        condition_on_previous_text=False,
    )

    segments, words_count = [], 0
    for seg in segments_iter:
        words = [{"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3),
                  "probability": round(w.probability, 3)} for w in (seg.words or [])]
        words_count += len(words)
        segments.append({
            "start": round(seg.start, 3), "end": round(seg.end, 3),
            "text": seg.text.strip(), "words": words,
        })
        if words_count % 200 < len(words):
            print(f"  ... {util.fmt_ts(seg.end)}")

    data = {
        "model": args.model,
        "language": getattr(info, "language", None),
        "duration": getattr(info, "duration", None) or j.data["info"]["duration"],
        "words": words_count,
        "segments": segments,
    }
    util.atomic_json(j.apath("transcript.json"), data)
    write_srt(j.apath("transcript.srt"), segments)

    j.record("transcribe",
             {"model": args.model, "language": data["language"]},
             {"transcript.json": {"language": data["language"], "words": words_count,
                                  "duration": data["duration"]},
              "transcript.srt": {"words": words_count}})
    print(f"language={data['language']}  words={words_count}  segments={len(segments)}")
    print(f"wrote transcript.json + transcript.srt")


def write_srt(path, segments) -> None:
    def ts(t: float) -> str:
        h, rem = divmod(max(0, t), 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    lines = []
    for i, seg in enumerate(segments, 1):
        lines += [str(i), f"{ts(seg['start'])} --> {ts(seg['end'])}", seg["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")
