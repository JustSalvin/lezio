"""Entry file handed to the `manim` command (Manim loads scene files outside of any package)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lezio.video.scene_runner import SegmentScene as _SegmentScene  # noqa: E402


class SegmentScene(_SegmentScene):
    pass
