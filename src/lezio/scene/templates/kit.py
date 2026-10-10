"""Helpers for writing templates (also available to the agent's own templates via `from lezio.scene import *`)."""
from manim import (DOWN, LEFT, RIGHT, UP, Indicate, RoundedRectangle, SurroundingRectangle, VGroup)

# Drawing order: Manim draws mobjects in the order they were added, and a mobject being animated on top of
# everything. When something moves over other parts (a value moving into a cell) give it a higher z_index.
# MarkupText (MT) uses ligatures (fi, ffi): its glyphs do not match the characters one to one.

from .. import style


def run_phases(steps, phases):
    """Spread phase functions (each takes a Timer t) over the narration pieces left in `steps`: with as many
    pieces as phases each phase starts with its piece; with fewer pieces phases share them; with more
    pieces the last phases get the extra time."""
    n_steps, n_ph = steps.left, len(phases)
    if n_steps < 1:
        raise RuntimeError("no narration pieces left for this template")
    groups = [[] for _ in range(n_steps)]
    for i, ph in enumerate(phases):
        groups[min(i * n_steps // max(n_ph, 1), n_steps - 1)].append(ph)
    for group in groups:
        t = steps()
        for j, ph in enumerate(group):
            ph(t)
            if j < len(group) - 1:
                t.until((j + 1) / len(group) * 0.92)


def _wrapped(text, chars):
    import textwrap
    return [line for para in text.split("\n")
            for line in (textwrap.wrap(para, chars, break_long_words=False, break_on_hyphens=False) or [""])]


def text_lines(text, max_width, size=None, color=None, bold=False, font=None, align="left", line_spacing=0.25):
    """Text wrapped to at most max_width (scene units) as a VGroup with one Text per line (lines can be
    animated or struck through one by one). align: "left" | "center" | "right". Words are never split: a
    word longer than the width makes the whole text smaller."""
    size = size or style.TEXT_SIZE
    best = None
    lo, hi = 6, max(len(text), 6)
    while lo <= hi:                                  # the widest wrap that fits
        mid = (lo + hi) // 2
        lines = _wrapped(text, mid)
        g = VGroup(*[style.T(x or " ", size, color, bold=bold, font=font) for x in lines])
        if max(m.width for m in g) <= max_width:
            best, lo = g, mid + 1
        else:
            hi = mid - 1
    if best is None:                                 # a single very long word
        best = VGroup(*[style.T(x or " ", size, color, bold=bold, font=font) for x in _wrapped(text, 6)])
        style.fit(best, max_width)
    edge = {"left": LEFT, "right": RIGHT}.get(align)
    best.arrange(DOWN, buff=line_spacing * best[0].height + 0.08, **({"aligned_edge": edge} if edge is not None else {}))
    best.original_text = text
    return best


def text_box(text, max_width, size=None, color=None, bold=False, font=None, align="left", line_spacing=0.9):
    """Text wrapped so that it is at most max_width wide (scene units), in the house style. Left aligned
    it is one Text (wrapped with line breaks); align="center" or "right" gives centered/right-aligned lines
    (a VGroup, see text_lines). Words are never split."""
    if align != "left":
        return text_lines(text, max_width, size, color, bold, font, align)
    size = size or style.TEXT_SIZE
    best = None
    lo, hi = 6, max(len(text), 6)
    while lo <= hi:                                  # the widest wrap that fits
        mid = (lo + hi) // 2
        m = style.T("\n".join(_wrapped(text, mid)), size, color, bold=bold, font=font, line_spacing=line_spacing)
        if m.width <= max_width:
            best, lo = m, mid + 1
        else:
            hi = mid - 1
    if best is None:                                 # a single very long word
        best = style.fit(style.T("\n".join(_wrapped(text, 6)), size, color, bold=bold, font=font), max_width)
    return best


def frame(mob, color=None, buff=0.15, fill_opacity=0.12, stroke_width=4):
    """A highlight frame around a mobject (HIGHLIGHT unless given)."""
    color = color or style.HIGHLIGHT
    return SurroundingRectangle(mob, color=color, buff=buff, corner_radius=0.1, stroke_width=stroke_width,
                                fill_color=color, fill_opacity=fill_opacity)


def panel(width, height, color=None, fill=None, stroke_width=2.5, radius=0.2):
    """A rounded card (NEUTRAL_SOFT fill, MUTED border unless given)."""
    return RoundedRectangle(width=width, height=height, corner_radius=radius, stroke_color=color or style.MUTED,
                            stroke_width=stroke_width, fill_color=fill or style.NEUTRAL_SOFT, fill_opacity=1)


def _remember_opacity(mob):
    for m in mob.family_members_with_points():
        if not hasattr(m, "_lezio_opacity"):
            m._lezio_opacity = (m.get_fill_opacity(), m.get_stroke_opacity())


def dim_to(mob, factor):
    """An animation bringing every part of mob to `factor` times its original opacity (1 = as created).
    Unlike set_opacity it keeps open lines unfilled and soft fills soft."""
    from manim import Transform
    _remember_opacity(mob)
    target = mob.copy()
    for orig, m in zip(mob.family_members_with_points(), target.family_members_with_points()):
        fill, stroke = orig._lezio_opacity
        m.set_fill(opacity=fill * factor)
        m.set_stroke(opacity=stroke * factor)
    return Transform(mob, target)


def focus_anims(items, i, dim=0.35):
    """Animations that show item i at full opacity and dim the others (signaling the current element);
    i = -1 dims them all."""
    return [dim_to(m, 1 if k == i else dim) for k, m in enumerate(items)]


def pulse(mob, color=None):
    return Indicate(mob, color=color or style.HIGHLIGHT, scale_factor=1.08)


def column(mobs, buff=0.3, align=LEFT):
    return VGroup(*mobs).arrange(DOWN, buff=buff, aligned_edge=align)


def row(mobs, buff=0.4, align=UP):
    return VGroup(*mobs).arrange(RIGHT, buff=buff, aligned_edge=align)
