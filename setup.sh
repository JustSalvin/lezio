#!/usr/bin/env bash
# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
# One-time setup of the project: two virtual environments inside the project folder, their Python packages
# and the speech model of the configured voice. It installs nothing on the system: what the system needs
# (Python, cairo, ...) is listed in README.md, "Requirements".
#   Another Python than python3:  PYTHON=/path/to/python ./setup.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

say() { printf "\n==> %s\n" "$*"; }
fail() { printf "\n%s\nSee README.md, \"Requirements\".\n" "$*" >&2; exit 1; }

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || fail "Python not found ($PY)."
"$PY" -c 'import sys; assert (3, 13) <= sys.version_info[:2] <= (3, 14)' 2>/dev/null \
  || fail "lezio needs Python 3.13 or 3.14 (found: $("$PY" --version 2>&1))."

say "Program and video environment (.venv)"
[ -x .venv/bin/pip ] || "$PY" -m venv --clear .venv || fail "Could not create .venv (Python's venv module is needed)."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-video.txt \
  || fail "Installing the packages of .venv failed (on macOS and Linux Manim's pycairo is built against cairo)."
# Manim and the scripts expect an `ffmpeg` executable: use the one bundled with imageio-ffmpeg
ln -sf "$(.venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" .venv/bin/ffmpeg

say "Speech environment (.venv-tts)"
[ -x .venv-tts/bin/pip ] || "$PY" -m venv --clear .venv-tts || fail "Could not create .venv-tts (Python's venv module is needed)."
.venv-tts/bin/pip install -q --upgrade pip
.venv-tts/bin/pip install -q -r requirements-tts.txt || fail "Installing the packages of .venv-tts failed."

say "Speech model of the configured TTS engine (downloaded once, e.g. into ~/.cache/huggingface)"
PYTHONPATH="$PWD/src" .venv-tts/bin/python -m lezio.voice.synthesize download

mkdir -p input output lessons
say "Done. Put your study material in input/ and run ./lezio"
