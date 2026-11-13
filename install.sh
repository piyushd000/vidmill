#!/usr/bin/env bash
# vidmill installer — core + optional AI engines
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }

say "checking prerequisites"
command -v ffmpeg >/dev/null || { echo "ffmpeg is required: sudo apt install ffmpeg (or brew install ffmpeg)"; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
python3 - <<'EOF' || { echo "python >= 3.10 is required"; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)
EOF

say "installing core (faster-whisper + vmill CLI)"
python3 -m pip install -q faster-whisper
python3 -m pip install -q -e .

if [[ "${1:-}" == "--extras" ]]; then
  say "optional engines"
  if command -v conda >/dev/null; then
    if ! conda env list | grep -q '^dfnet '; then
      say "creating conda env 'dfnet' (DeepFilterNet audio denoise)"
      conda create -y -n dfnet python=3.11
      conda run -n dfnet pip install deepfilternet onnxruntime soundfile
    else
      say "conda env 'dfnet' already exists"
    fi
    if ! conda env list | grep -q '^facefusion '; then
      say "cloning FaceFusion and creating conda env 'facefusion'"
      [ -d "$HOME/facefusion" ] || git clone --depth 1 https://github.com/facefusion/facefusion "$HOME/facefusion"
      conda create -y -n facefusion python=3.11
      conda run -n facefusion pip install -r "$HOME/facefusion/requirements.txt"
    else
      say "conda env 'facefusion' already exists"
    fi
  else
    echo "conda not found — install miniconda first for the extras; skipping."
  fi
fi

say "verifying with vmill doctor"
vmill doctor
say "done — try:  vmill pipeline myvideo.mp4 --job myedit"
