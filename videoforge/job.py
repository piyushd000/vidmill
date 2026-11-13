"""Job directory: where tool outputs connect.

Layout:
    job/
      job.json          state + tool history (the chain)
      source*           original video (if copied in)
      probe.json        media info
      transcript.json   word-level transcript
      transcript.srt
      cut_plan.json     segments to keep / drop + reasons
      cut.mp4           after applying the plan
      cleaned.mp4       after audio cleanup
      captions.ass
      captioned.mp4
      final.mp4         export preset output
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import APP_NAME, ToolError, util

JOB_FILE = "job.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Job:
    def __init__(self, path: Path, data: dict):
        self.path = Path(path)
        self.data = data

    # ------------------------------------------------------------- lifecycle

    @classmethod
    def create(cls, job_dir: Path, video: Path, copy: bool = False) -> "Job":
        video = Path(video).expanduser().resolve()
        if not video.exists():
            raise ToolError(f"video not found: {video}")
        job_dir = Path(job_dir).expanduser().resolve()
        job_dir.mkdir(parents=True, exist_ok=True)
        src = video
        if copy:
            dest = job_dir / video.name
            if not dest.exists():
                shutil_copy(video, dest)
            src = dest
        info = util.probe_info(src)
        util.atomic_json(job_dir / "probe.json", info)
        data = {
            "app": APP_NAME,
            "created": now(),
            "video": str(src),
            "info": info,
            "artifacts": {"probe.json": {"created": now(), "meta": {"duration": info["duration"]}}},
            "history": [{"tool": "new", "ts": now(), "ok": True}],
        }
        util.atomic_json(job_dir / JOB_FILE, data)
        return cls(job_dir, data)

    @classmethod
    def load(cls, job_dir: Path) -> "Job":
        job_dir = Path(job_dir).expanduser().resolve()
        f = job_dir / JOB_FILE
        if not f.exists():
            raise ToolError(f"no job at {job_dir} — run `vf new <video> --job {job_dir}` first")
        return cls(job_dir, util.read_json(f))

    def save(self) -> None:
        util.atomic_json(self.path / JOB_FILE, self.data)

    # -------------------------------------------------------------- artifacts

    def has(self, name: str) -> bool:
        p = self.path / name
        return name in self.data.get("artifacts", {}) and p.exists()

    def apath(self, name: str) -> Path:
        return self.path / name

    def require(self, *names: str) -> None:
        missing = [n for n in names if not self.has(n)]
        if missing:
            raise ToolError(
                f"job is missing artifacts: {', '.join(missing)}. "
                f"Run the tool that creates them (see `vf tools`)."
            )

    def latest(self, name: str) -> dict:
        return self.data.get("artifacts", {}).get(name, {})

    def record(self, tool: str, args: dict, artifacts: dict | None = None) -> None:
        """Mark artifacts as produced by a tool. args may contain absolute paths — sanitize."""
        clean = {k: (str(v) if isinstance(v, Path) else v) for k, v in args.items()}
        self.data.setdefault("history", []).append({"tool": tool, "ts": now(), "args": clean, "ok": True})
        arts = self.data.setdefault("artifacts", {})
        for name, meta in (artifacts or {}).items():
            arts[name] = {"created": now(), "meta": meta}
        self.data["updated"] = now()
        self.save()

    def current_video(self) -> Path:
        """Most recent video artifact = the tool chain's current result."""
        order = ["final.mp4", "swapped.mp4", "captioned.mp4", "cleaned.mp4", "cut.mp4"]
        for name in order:
            if self.has(name):
                return self.apath(name)
        src = self.data.get("video")
        if src and Path(src).exists():
            return Path(src)
        raise ToolError("job has no video yet (is the source file still there?)")

    def print_status(self) -> None:
        i = self.data.get("info", {})
        print(f"job     : {self.path}")
        print(f"source  : {self.data.get('video')}")
        print(f"media   : {i.get('width')}x{i.get('height')} @ {i.get('fps')}fps  "
              f"{util.fmt_ts(i.get('duration', 0))}  audio={i.get('has_audio')}")
        if not self.data.get("artifacts"):
            print("artifacts: (none yet)")
            return
        print("artifacts:")
        for name, meta in sorted(self.data["artifacts"].items(), key=lambda kv: kv[1].get("created", "")):
            extra = ""
            m = meta.get("meta") or {}
            if m.get("duration") is not None:
                extra += f"  {util.fmt_ts(m['duration'])}"
            if m.get("words"):
                extra += f"  {m['words']} words"
            if m.get("keep_segments"):
                extra += f"  {m['keep_segments']} keep segments"
            if m.get("removed_seconds"):
                extra += f"  -{m['removed_seconds']:.1f}s"
            print(f"  [{meta.get('created', '?')[:19]}] {name:<18}{extra}")
        print("history:")
        for h in self.data.get("history", []):
            print(f"  {h.get('ts', '?')[11:19]}  {h.get('tool')}")


def shutil_copy(src: Path, dst: Path) -> Path:
    import shutil
    return shutil.copy(src, dst)
