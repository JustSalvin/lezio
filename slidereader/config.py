"""Project paths and configuration (config.toml)."""
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
LESSONS = ROOT / "lessons"
PACKAGE = ROOT / "slidereader"

VIDEO_PY = ROOT / ".venv" / "bin" / "python"      # Manim, PyMuPDF, Claude Agent SDK, the program
VOICE_PY = ROOT / ".venv-tts" / "bin" / "python"  # MLX and the TTS engines
FFMPEG = ROOT / ".venv" / "bin" / "ffmpeg"
MANIM = ROOT / ".venv" / "bin" / "manim"

CONFIG = tomllib.loads((ROOT / "config.toml").read_text())

# Environment for the subprocesses (Manim, speech worker): project importable, ffmpeg on PATH
SUBPROCESS_ENV = {**os.environ, "PATH": f"{ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}",
                  "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1"}
