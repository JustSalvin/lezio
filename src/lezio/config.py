"""Project paths and configuration (config.toml)."""
import os
import tomllib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent          # src/lezio
SRC = PACKAGE.parent                                # src (on PYTHONPATH)
ROOT = SRC.parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
LESSONS = ROOT / "lessons"
CONFIG_FILE = ROOT / "config.toml"

VIDEO_PY = ROOT / ".venv" / "bin" / "python"      # Manim, PyMuPDF, Claude Agent SDK, the program
VOICE_PY = ROOT / ".venv-tts" / "bin" / "python"  # MLX and the TTS engines
FFMPEG = ROOT / ".venv" / "bin" / "ffmpeg"
MANIM = ROOT / ".venv" / "bin" / "manim"

CONFIG = tomllib.loads(CONFIG_FILE.read_text())

# Environment for the subprocesses (Manim, speech worker): package importable, ffmpeg on PATH
SUBPROCESS_ENV = {**os.environ, "PATH": f"{ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}",
                  "PYTHONPATH": str(SRC), "PYTHONUNBUFFERED": "1"}
