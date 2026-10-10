# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Entry file handed to the `manim` command (Manim loads scene files outside of any package)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lezio.video.scene_runner import SegmentScene as _SegmentScene  # noqa: E402


class SegmentScene(_SegmentScene):
    pass
