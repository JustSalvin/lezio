# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Public helper library for scene code: `from lezio.scene import *`.

A segment's scene is a file scenes/<segment>.py defining

    def build(scene, steps, material):
        ...

It gives all of Manim plus: the narration sync (Steps/Timer, see sync.py), the house style (colors,
fonts and sizes of the active theme, T, heading, box, ... in style.py), the study material
(material.page/figure, in material.py) and what is needed to write templates (@template, Ctx and the
helpers of templates/kit.py). Keep this API stable: templates and scenes written by the agent depend on it.
"""
from manim import *  # noqa: F401,F403  (all of Manim for scene code)

from .style import (BACKGROUND, FONT, FRAME_HEIGHT, FRAME_WIDTH, HAND, HIGHLIGHT, HIGHLIGHT_SOFT,  # noqa: F401
                    MONO, MT, MUTED, NEGATIVE, NEGATIVE_SOFT, NEUTRAL_SOFT, POSITIVE, POSITIVE_SOFT, PRIMARY,
                    PRIMARY_SOFT, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP, SECONDARY, SECONDARY_SOFT,
                    SMALL_SIZE, TEXT, TEXT_SIZE, TITLE_FONT, TITLE_SIZE, T, arrow, box, check, cross, fit, heading,
                    person, wrap)
from .style import (BLUE, BLUE_LIGHT, DARK, GREEN, GREEN_LIGHT, GREY, GREY_LIGHT, ORANGE,  # noqa: F401  (legacy)
                    ORANGE_LIGHT, RED, RED_LIGHT, YELLOW, YELLOW_LIGHT)
from .templates import Ctx, template  # noqa: F401,E402  (writing templates)
from .templates.kit import (column, dim_to, focus_anims, frame, panel, pulse, row, run_phases,  # noqa: F401,E402
                            text_box, text_lines)
