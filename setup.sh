#!/usr/bin/env bash
# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
# One-time installation of lezio (macOS on Apple Silicon).
# Creates two virtual environments inside the project and downloads the speech model.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

say() { printf "\n==> %s\n" "$*"; }

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "lezio needs macOS on Apple Silicon (the speech model runs with MLX)." >&2
  exit 1
fi

# Python >= 3.11 (mise is used if available, see mise.toml)
if command -v mise >/dev/null 2>&1; then
  say "Python via mise (mise.toml)"
  mise install
  PY="mise exec -- python"
else
  PY="python3"
fi
$PY -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'

# System libraries needed by Manim
say "System libraries (cairo, pkg-config) via Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required: https://brew.sh" >&2
  exit 1
fi
brew list cairo >/dev/null 2>&1 || brew install cairo
brew list pkgconf >/dev/null 2>&1 || brew install pkgconf

say "Program and video environment (.venv)"
[ -d .venv ] || $PY -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-video.txt
# Manim and the scripts expect an `ffmpeg` executable: use the one bundled with imageio-ffmpeg
ln -sf "$(.venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" .venv/bin/ffmpeg

say "Speech environment (.venv-tts)"
[ -d .venv-tts ] || $PY -m venv .venv-tts
.venv-tts/bin/pip install -q --upgrade pip
.venv-tts/bin/pip install -q -r requirements-tts.txt

say "Speech model of the configured TTS engine (downloaded once, e.g. into ~/.cache/huggingface)"
PYTHONPATH="$PWD/src" .venv-tts/bin/python -m lezio.voice.synthesize download

mkdir -p input output lessons
say "Done. Put your study material in input/ and run ./lezio"
