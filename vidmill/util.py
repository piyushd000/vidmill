"""Subprocess / filesystem helpers shared by every tool."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import ToolError

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
CONDA = shutil.which("conda") or "conda"


def run(cmd: list, check: bool = True, quiet: bool = False,
        cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command, capturing output. Raises ToolError on failure."""
    cmd = [str(c) for c in cmd]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    except FileNotFoundError as e:
        raise ToolError(f"executable not found: {cmd[0]}") from e
    if check and p.returncode != 0:
        tail = (p.stderr or p.stdout or "")[-2000:]
        raise ToolError(f"command failed ({p.returncode}): {' '.join(cmd)}\n{tail}")
    if not quiet and (p.stdout or p.stderr):
        (p.stdout or "") and print(p.stdout, end="")
        (p.stderr or "") and print(p.stderr, end="", file=__import__("sys").stderr)
    return p


def run_ffmpeg(input_path: Path, args: list, output_path: Path,
               quiet: bool = True, extra_input_args: list | None = None,
               cwd: Path | None = None) -> Path:
    """ffmpeg -y -i input <args> output, with sane global defaults."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
    if quiet:
        cmd += ["-nostdin"]
    cmd += (extra_input_args or []) + ["-i", str(input_path)] + [str(a) for a in args] + ["-nostdin", str(output_path)]
    run(cmd, cwd=cwd)
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ToolError(f"ffmpeg produced nothing: {output_path}")
    return output_path


def ffprobe(path: Path) -> dict:
    p = run([FFPROBE, "-v", "error", "-show_format", "-show_streams",
             "-of", "json", str(path)], quiet=True)
    return json.loads(p.stdout or "{}")


# ------------------------------------------------------------------- gpu

def _can_encode(backend: str) -> bool:
    """True only if a tiny real encode succeeds on this backend."""
    enc = {"nvenc": "h264_nvenc", "qsv": "h264_qsv",
           "videotoolbox": "h264_videotoolbox"}[backend]
    pix = "nv12" if backend == "qsv" else "yuv420p"
    p = run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.2",
             "-frames:v", "2", "-c:v", enc, "-pix_fmt", pix, "-f", "null", "-"],
            check=False, quiet=True)
    return p.returncode == 0


def gpu_backend() -> tuple[str, str] | None:
    """Detect a *usable* hardware encoder backend: (backend, gpu name) or None.

    Candidates must pass a real one-frame encode: a device node or an
    encoder listing alone proves nothing (VMs expose /dev/dri without a
    working driver, containers ship NVENC without a GPU).
    """
    import os
    import platform
    import shutil

    p = run([FFMPEG, "-hide_banner", "-encoders"], check=False, quiet=True)
    encoders = (p.stdout or "") + (p.stderr or "")

    if shutil.which("nvidia-smi") and "h264_nvenc" in encoders:
        q = run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                check=False, quiet=True)
        name = (q.stdout or "").strip().splitlines()
        if q.returncode == 0 and name and _can_encode("nvenc"):
            return "nvenc", name[0].strip()

    if platform.system() == "Darwin" and "h264_videotoolbox" in encoders:
        if _can_encode("videotoolbox"):
            return "videotoolbox", "Apple GPU (VideoToolbox)"

    if os.path.exists("/dev/dri/renderD128") and "h264_qsv" in encoders:
        if _can_encode("qsv"):
            return "qsv", "Intel GPU (Quick Sync)"

    return None


def probe_info(path: Path) -> dict:
    """Compact, tool-friendly media summary."""
    data = ffprobe(path)
    fmt = data.get("format", {})
    info = {
        "path": str(Path(path).resolve()),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "duration": float(fmt.get("duration", 0) or 0),
        "width": None, "height": None, "fps": None,
        "has_audio": False, "has_video": False,
        "audio_rate": None, "audio_channels": None, "codec": None,
    }
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not info["has_video"]:
            info["has_video"] = True
            info["width"] = s.get("width")
            info["height"] = s.get("height")
            avg, _, _ = (s.get("avg_frame_rate") or "0/0").partition("/")
            num, den = float(avg or 0), float(s.get("avg_frame_rate", "").split("/")[1] if "/" in (s.get("avg_frame_rate") or "") else 1)
            if num and den:
                info["fps"] = round(num / den, 4)
            info["codec"] = s.get("codec_name")
        elif s.get("codec_type") == "audio" and not info["has_audio"]:
            info["has_audio"] = True
            info["audio_rate"] = s.get("sample_rate")
            info["audio_channels"] = s.get("channels")
    return info


# ---------------------------------------------------------------- conda envs

def conda_env_path(env_name: str) -> Path | None:
    """Resolve a conda env dir, e.g. env 'dfnet' -> ~/miniconda3/envs/dfnet."""
    if not shutil.which(CONDA):
        return None
    try:
        p = subprocess.run([CONDA, "env", "list"], capture_output=True, text=True)
        for line in p.stdout.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] == env_name and not line.strip().endswith("*"):
                return Path(parts[-1])
            if parts[0] == env_name and line.strip().endswith("*"):
                return Path(parts[-1])
    except Exception:
        return None
    return None


def env_bin(env_name: str, binary: str) -> Path | None:
    """Path to <binary> inside conda env <env_name>, or None."""
    env = conda_env_path(env_name)
    if not env:
        return None
    b = env / "bin" / binary
    return b if b.exists() else None


def run_in_env(env_name: str, cmd: list, cwd: Path | None = None,
               quiet: bool = True) -> subprocess.CompletedProcess:
    """Run a command with a conda env's bin dir first on PATH."""
    env = conda_env_path(env_name)
    if not env:
        raise ToolError(f"conda env '{env_name}' not found")
    e = {**os.environ, "PATH": f"{env}/bin:{os.environ.get('PATH', '')}",
         "CONDA_PREFIX": str(env)}
    cmd = [str(c) for c in cmd]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=e)
    except FileNotFoundError as ex:
        raise ToolError(f"executable not found in env '{env_name}': {cmd[0]}") from ex
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "")[-2000:]
        raise ToolError(f"command failed ({p.returncode}): {' '.join(cmd)}\n{tail}")
    return p


# ------------------------------------------------------------------ files

def atomic_json(path: Path, data: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def read_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def fmt_ts(seconds: float) -> str:
    s = max(0.0, float(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}"


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
