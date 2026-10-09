"""Entry file handed to the `manim` command (Manim loads scene files outside of any package)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slidereader.engine import LessonScene as _LessonScene  # noqa: E402


class LessonScene(_LessonScene):
    pass
