"""House style: colors, fonts and sizes of the active theme (themes/<name>.toml), and building blocks.

The theme is chosen in config.toml ([video] theme) or, for one lesson, in its plan. Scene code uses the
color NAMES below, never fixed colors, so every lesson follows the active theme.

Frame: x from -7.1 (left) to 7.1 (right), y from -4 (bottom) to 4 (top); keep content inside the safe
area x in [-6.6, 6.6], y in [-3.6, 3.4].
"""
import sys
import textwrap
import tomllib

from manim import (BOLD, DOWN, NORMAL, UL, Arrow, Circle, DoubleArrow, Line, MarkupText, RoundedRectangle, Text,
                   VGroup, VMobject)

from ..config import THEMES as THEMES_DIR
from ..settings import house_theme
FRAME_WIDTH, FRAME_HEIGHT = 14.222, 8.0
SAFE_LEFT, SAFE_RIGHT, SAFE_BOTTOM, SAFE_TOP = -6.6, 6.6, -3.6, 3.4

COLOR_NAMES = {           # theme key -> name in scene code
    "background": "BACKGROUND", "text": "TEXT", "muted": "MUTED",
    "primary": "PRIMARY", "primary_soft": "PRIMARY_SOFT", "secondary": "SECONDARY",
    "secondary_soft": "SECONDARY_SOFT", "highlight": "HIGHLIGHT", "highlight_soft": "HIGHLIGHT_SOFT",
    "positive": "POSITIVE", "positive_soft": "POSITIVE_SOFT", "negative": "NEGATIVE",
    "negative_soft": "NEGATIVE_SOFT", "neutral_soft": "NEUTRAL_SOFT",
}
FONT_NAMES = {"text": "FONT", "title": "TITLE_FONT", "mono": "MONO", "hand": "HAND"}
SIZE_NAMES = {"title": "TITLE_SIZE", "text": "TEXT_SIZE", "small": "SMALL_SIZE"}
# Names used by scenes written before themes existed: they follow the theme too
LEGACY = {"BLUE": "PRIMARY", "BLUE_LIGHT": "PRIMARY_SOFT", "ORANGE": "SECONDARY", "ORANGE_LIGHT": "SECONDARY_SOFT",
          "YELLOW": "HIGHLIGHT", "YELLOW_LIGHT": "HIGHLIGHT_SOFT", "GREEN": "POSITIVE", "GREEN_LIGHT": "POSITIVE_SOFT",
          "RED": "NEGATIVE", "RED_LIGHT": "NEGATIVE_SOFT", "DARK": "TEXT", "GREY": "MUTED", "GREY_LIGHT": "NEUTRAL_SOFT"}


# ------------------------------------------------------------------ themes
def available_themes():
    """{name: description} of the theme files in themes/."""
    out = {}
    for path in sorted(THEMES_DIR.glob("*.toml")):
        try:
            out[path.stem] = tomllib.loads(path.read_text()).get("description", "")
        except tomllib.TOMLDecodeError:
            out[path.stem] = "(invalid file)"
    return out


def load_theme(name):
    """The theme as a dict; missing keys are taken from the light theme."""
    path = THEMES_DIR / f"{name}.toml"
    if not path.exists():
        raise ValueError(f"unknown theme '{name}' (themes: {', '.join(available_themes())})")
    data = tomllib.loads(path.read_text())
    base = tomllib.loads((THEMES_DIR / "light.toml").read_text()) if name != "light" else {}
    for section in ("colors", "fonts", "sizes"):
        data[section] = {**base.get(section, {}), **data.get(section, {})}
    return data


def theme_values(data):
    """Scene-code names -> values for a theme."""
    values = {COLOR_NAMES[k]: v for k, v in data["colors"].items() if k in COLOR_NAMES}
    values.update({FONT_NAMES[k]: v for k, v in data["fonts"].items() if k in FONT_NAMES})
    values.update({SIZE_NAMES[k]: v for k, v in data["sizes"].items() if k in SIZE_NAMES})
    values.update({old: values[new] for old, new in LEGACY.items()})
    return values


def apply_theme(name):
    """Make `name` the active theme: rebinds the names in every lezio.scene module (call it before the scene
    code is executed). Returns the theme name."""
    values = theme_values(load_theme(name))
    for module_name, module in list(sys.modules.items()):
        if module_name == "lezio.scene" or module_name.startswith("lezio.scene."):
            for key, value in values.items():
                if key in vars(module):
                    setattr(module, key, value)
    globals().update(values)
    global ACTIVE
    ACTIVE = name
    return name


ACTIVE = house_theme()
globals().update(theme_values(load_theme(ACTIVE)))


# ------------------------------------------------------------------ text
def T(text, size=None, color=None, bold=False, font=None, **kwargs):
    """Text in the house style: theme font, TEXT color and TEXT_SIZE unless given (size = Manim font_size).
    Text does not wrap: use wrap(text, width) for long sentences."""
    return Text(text, font=font or FONT, font_size=size or TEXT_SIZE, color=color or TEXT,
                weight=BOLD if bold else NORMAL, **kwargs)


def MT(markup, size=None, color=None, bold=False, font=None, **kwargs):
    """Text with Pango markup in the house style: formulas and mixed formatting, in any font.
    Exponents and indices: MT("2<sup>k-1</sup> + log<sub>2</sub> n"); also <b>, <i>, <span color="...">.
    Write "<" as "&lt;" and "&" as "&amp;"."""
    return MarkupText(markup, font=font or FONT, font_size=size or TEXT_SIZE, color=color or TEXT,
                      weight=BOLD if bold else NORMAL, **kwargs)


def heading(text, size=None, color=None):
    """The title of a screen, in the same place and look in every scene (top left, TITLE_FONT, PRIMARY)."""
    h = T(text, size or TITLE_SIZE, color or PRIMARY, bold=True, font=TITLE_FONT).to_corner(UL, buff=0.6)
    if h.width > SAFE_RIGHT - SAFE_LEFT:
        h.scale_to_fit_width(SAFE_RIGHT - SAFE_LEFT).to_corner(UL, buff=0.6)
    return h


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


# ------------------------------------------------------------------ building blocks
def box(text, w=2.9, h=1.1, size=30, color=None, fill=None, bold=True, font=None):
    """Rounded box with centered text (the text shrinks to fit); PRIMARY on PRIMARY_SOFT unless given.
    Returns VGroup(rectangle, text)."""
    color, fill = color or PRIMARY, fill or PRIMARY_SOFT
    r = RoundedRectangle(width=w, height=h, corner_radius=0.18, stroke_color=color, stroke_width=3,
                         fill_color=fill, fill_opacity=1)
    t = T(text, size, color, bold=bold, font=font, line_spacing=0.8).move_to(r)
    fit(t, w - 0.3, h - 0.2)
    return VGroup(r, t)


def arrow(start, end, color=None, double=False, width=5):
    """Straight arrow from start to end (points or mobject.get_right() etc.), MUTED unless given."""
    cls = DoubleArrow if double else Arrow
    return cls(start, end, buff=0.1, color=color or MUTED, stroke_width=width, max_tip_length_to_length_ratio=0.2)


def person(color=None):
    """A simple person icon (head + body)."""
    color = color or PRIMARY
    head = Circle(radius=0.38, fill_color=color, fill_opacity=1, stroke_width=0)
    body = RoundedRectangle(width=1.3, height=1.1, corner_radius=0.5, fill_color=color, fill_opacity=1,
                            stroke_width=0)
    body.next_to(head, DOWN, buff=0.08)
    return VGroup(head, body)


def check(color=None):
    """A check mark (POSITIVE)."""
    return VMobject().set_points_as_corners([[-0.3, 0, 0], [-0.08, -0.25, 0], [0.35, 0.32, 0]]).set_stroke(
        color or POSITIVE, 10)


def cross(color=None):
    """A cross mark (NEGATIVE)."""
    return VGroup(Line([-0.28, -0.28, 0], [0.28, 0.28, 0]),
                  Line([-0.28, 0.28, 0], [0.28, -0.28, 0])).set_stroke(color or NEGATIVE, 10)
