"""Toolkit for full-screen explanation animations (templates and lesson-specific ones).

An animation is a function `def name(scene, steps, **args)`.
`steps` is a Steps object: calling `t = steps()` starts the next narration step (plays its audio)
and returns a Timer `t` holding that step's duration. Spend it with:
    t.play(anim1, anim2, rt=0.8)   # play animations, rt = run time in seconds
    t.until(0.5)                   # wait until 50% of the step's audio has elapsed
Leftover time is waited automatically. Call steps() once per narration step, in order.
"""
from manim import *  # noqa: F401,F403  (re-exported for animation files)
from manim import BOLD, NORMAL, Text

# ---------------------------------------------------------------- style
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
DARK = "#1E1E1E"
GREY = "#6B6B6B"
FONT = "Avenir Next"
MONO = "Menlo"


def T(text, size=36, color=DARK, bold=False, font=FONT, **kw):
    """Text in the house style. size is a Manim font_size (36 = body, 48+ = headings)."""
    return Text(text, font=font, font_size=size, color=color, weight=BOLD if bold else NORMAL, **kw)


# ---------------------------------------------------------------- timing
class Timer:
    def __init__(self, scene, duration):
        self.scene, self.duration, self.left = scene, duration, duration

    def play(self, *anims, rt=1.0, **kw):
        self.scene.play(*anims, run_time=rt, **kw)
        self.left -= rt

    def wait(self, seconds):
        seconds = min(seconds, self.left)
        if seconds > 0.02:
            self.scene.wait(seconds)
            self.left -= seconds

    def until(self, fraction):
        """Wait until `fraction` (0..1) of this step's duration has elapsed."""
        self.wait(self.duration * fraction - (self.duration - self.left))

    def finish(self):
        self.wait(self.left)


class Steps:
    def __init__(self, scene, pieces, gap):
        """pieces: list of (wav_path, duration, pause_after)."""
        self.scene, self.pieces, self.gap = scene, pieces, gap
        self.i, self.current, self.pause = 0, None, 0

    def __len__(self):
        return len(self.pieces)

    def _close(self):
        if self.current is not None:
            self.current.finish()
            self.scene.wait(self.gap + self.pause)
            self.current = None

    def __call__(self):
        self._close()
        if self.i >= len(self.pieces):
            raise RuntimeError("animation asked for more steps than the script provides")
        wav, duration, pause = self.pieces[self.i]
        if wav:
            self.scene.add_sound(wav)
        self.current, self.pause = Timer(self.scene, duration), pause
        self.i += 1
        return self.current

    def finish(self):
        while self.i < len(self.pieces):
            self()
        self._close()


# ---------------------------------------------------------------- building blocks
def box(text, w=2.9, h=1.1, size=30, color=BLUE, fill=BLUE_LIGHT, bold=True):
    """Rounded box with centered text (text shrinks to fit)."""
    r = RoundedRectangle(width=w, height=h, corner_radius=0.18, stroke_color=color, stroke_width=3,
                         fill_color=fill, fill_opacity=1)
    t = T(text, size, color, bold=bold, line_spacing=0.8).move_to(r)
    if t.width > w - 0.3:
        t.scale_to_fit_width(w - 0.3)
    if t.height > h - 0.2:
        t.scale_to_fit_height(h - 0.2)
    return VGroup(r, t)


def arrow(start, end, color=GREY, double=False, width=5):
    cls = DoubleArrow if double else Arrow
    return cls(start, end, buff=0.1, color=color, stroke_width=width, max_tip_length_to_length_ratio=0.2)


def person(color):
    head = Circle(radius=0.38, fill_color=color, fill_opacity=1, stroke_width=0)
    body = RoundedRectangle(width=1.3, height=1.1, corner_radius=0.5, fill_color=color, fill_opacity=1,
                            stroke_width=0)
    body.next_to(head, DOWN, buff=0.08)
    return VGroup(head, body)


def check(color=GREEN):
    return VMobject().set_points_as_corners([[-0.3, 0, 0], [-0.08, -0.25, 0], [0.35, 0.32, 0]]).set_stroke(color, 10)


def cross(color=RED):
    return VGroup(Line([-0.28, -0.28, 0], [0.28, 0.28, 0]),
                  Line([-0.28, 0.28, 0], [0.28, -0.28, 0])).set_stroke(color, 10)


def wrap(text, width=40):
    """Insert line breaks so that long sentences fit (Manim Text does not wrap)."""
    import textwrap
    return "\n".join(textwrap.wrap(text, width))
