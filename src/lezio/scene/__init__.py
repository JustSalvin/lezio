"""Public helper library for scene code: `from lezio.scene import *`.

A segment's scene is a file scenes/<segment>.py defining

    def build(scene, steps, material):
        ...

It gives all of Manim plus: the narration sync (Steps/Timer, see sync.py), the house style (colors,
fonts, themes, T, box, arrow, ... in style.py), the study material (material.page/figure, in
material.py) and optional layouts (layouts.py). Keep this API stable: scene files written by the agent
depend on it.
"""
from manim import *  # noqa: F401,F403  (all of Manim for scene code)

from .layouts import (bullets, cards, compare, diagram, encode, flow, mapping, number_base,  # noqa: F401
                      page_walkthrough, statement, title_card, translate)
from .style import (BACKGROUND, BLUE, BLUE_LIGHT, CHALK, CHALK_BLUE, CHALK_GREEN, CHALK_PINK,  # noqa: F401
                    CHALK_YELLOW, DARK, FONT, FRAME_HEIGHT, FRAME_WIDTH, GREEN, GREEN_LIGHT, GREY, GREY_LIGHT,
                    HAND, MONO, ORANGE, ORANGE_LIGHT, RED, RED_LIGHT, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT,
                    SAFE_TOP, YELLOW, YELLOW_LIGHT, T, arrow, box, check, cross, fit, ink, person, theme, wrap)
