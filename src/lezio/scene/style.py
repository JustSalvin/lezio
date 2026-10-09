"""House style: colors, fonts, themes and small building blocks.

Frame: x from -7.1 (left) to 7.1 (right), y from -4 (bottom) to 4 (top); keep content inside the safe
area x in [-6.6, 6.6], y in [-3.6, 3.4]. Font sizes: titles 40-56, body 28-36, big symbols 90-160.
"""
import textwrap

from manim import (BOLD, DOWN, NORMAL, Arrow, Circle, DoubleArrow, Line, RoundedRectangle, Text, VGroup,
                   VMobject)

FRAME_WIDTH, FRAME_HEIGHT = 14.222, 8.0
SAFE_LEFT, SAFE_RIGHT, SAFE_BOTTOM, SAFE_TOP = -6.6, 6.6, -3.6, 3.4

BACKGROUND = "#FFFFFF"
BLUE = "#1446A0"
BLUE_LIGHT = "#E3ECFA"
YELLOW = "#F2B705"
YELLOW_LIGHT = "#FFF6D6"
ORANGE = "#E8590C"
ORANGE_LIGHT = "#FDEBDD"
GREEN = "#2E9E44"
GREEN_LIGHT = "#E3F5E7"
RED = "#D32F2F"
RED_LIGHT = "#FDE2E2"
DARK = "#1E1E1E"
GREY = "#6B6B6B"
GREY_LIGHT = "#F2F2F2"
CHALK = "#F4F1E8"                 # chalk colors, for the dark "chalkboard" theme
CHALK_YELLOW = "#FFE07A"
CHALK_BLUE = "#9CC8FF"
CHALK_PINK = "#FF9FB2"
CHALK_GREEN = "#A8E6A1"

FONT = "Avenir Next"
MONO = "Menlo"
HAND = "Chalkboard SE"            # handwriting-like (also available: "Noteworthy", "Marker Felt", "Bradley Hand")

THEMES = {
    "light": {"background": "#FFFFFF", "ink": DARK, "font": FONT},
    "dark": {"background": "#15181E", "ink": "#ECEFF4", "font": FONT},
    "whiteboard": {"background": "#FBFBF8", "ink": "#1F2A36", "font": HAND},
    "chalkboard": {"background": "#2A3B33", "ink": CHALK, "font": HAND},
}
_current = dict(THEMES["light"])


def theme(scene, name="light"):
    """Set the look of the scene: background color, default text color (ink) and font of T().

    name: "light" (white, default) | "dark" | "whiteboard" (white board, handwriting) |
          "chalkboard" (dark green board, chalk colors CHALK, CHALK_YELLOW, CHALK_BLUE, ... and handwriting).
    """
    if name not in THEMES:
        raise ValueError(f"unknown theme '{name}' (themes: {', '.join(THEMES)})")
    _current.clear()
    _current.update(THEMES[name])
    scene.camera.background_color = _current["background"]


def ink():
    """Default text color of the current theme."""
    return _current["ink"]


def T(text, size=36, color=None, bold=False, font=None, **kwargs):
    """Text in the house style (theme font and ink unless given). size = Manim font_size.
    Text does not wrap: use wrap(text, width) for long sentences."""
    return Text(text, font=font or _current["font"], font_size=size, color=color or _current["ink"],
                weight=BOLD if bold else NORMAL, **kwargs)


def wrap(text, width=40):
    """Insert line breaks so that a long sentence fits (width in characters)."""
    return "\n".join(textwrap.wrap(text, width))


def fit(mobject, width=None, height=None):
    """Scale a mobject down (never up) so that it is at most width wide and height tall."""
    if width is not None and mobject.width > width:
        mobject.scale_to_fit_width(width)
    if height is not None and mobject.height > height:
        mobject.scale_to_fit_height(height)
    return mobject


def box(text, w=2.9, h=1.1, size=30, color=BLUE, fill=BLUE_LIGHT, bold=True, font=None):
    """Rounded box with centered text (the text shrinks to fit). Returns VGroup(rectangle, text)."""
    r = RoundedRectangle(width=w, height=h, corner_radius=0.18, stroke_color=color, stroke_width=3,
                         fill_color=fill, fill_opacity=1)
    t = T(text, size, color, bold=bold, font=font, line_spacing=0.8).move_to(r)
    fit(t, w - 0.3, h - 0.2)
    return VGroup(r, t)


def arrow(start, end, color=GREY, double=False, width=5):
    """Straight arrow from start to end (points or mobject.get_right() etc.)."""
    cls = DoubleArrow if double else Arrow
    return cls(start, end, buff=0.1, color=color, stroke_width=width, max_tip_length_to_length_ratio=0.2)


def person(color=BLUE):
    """A simple person icon (head + body)."""
    head = Circle(radius=0.38, fill_color=color, fill_opacity=1, stroke_width=0)
    body = RoundedRectangle(width=1.3, height=1.1, corner_radius=0.5, fill_color=color, fill_opacity=1,
                            stroke_width=0)
    body.next_to(head, DOWN, buff=0.08)
    return VGroup(head, body)


def check(color=GREEN):
    """A check mark."""
    return VMobject().set_points_as_corners([[-0.3, 0, 0], [-0.08, -0.25, 0], [0.35, 0.32, 0]]).set_stroke(color, 10)


def cross(color=RED):
    """A cross mark."""
    return VGroup(Line([-0.28, -0.28, 0], [0.28, 0.28, 0]),
                  Line([-0.28, 0.28, 0], [0.28, -0.28, 0])).set_stroke(color, 10)
