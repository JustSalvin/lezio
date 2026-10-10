# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Access to the study material from scene code: the `material` argument of build(scene, steps, material).

    pg = material.page("slides.pdf#p3")          # the page as a picture, fitted to the frame
    t.play(FadeIn(pg), rt=0.5)
    hl = pg.mark([2, 4])                        # highlight frame around text lines L2-L4 of that page
    t.play(Create(hl), rt=0.5)
    fig = material.figure("slides.pdf#p3.f1", height=4)   # a figure (or picture source) alone
"""
import numpy as np
from manim import ImageMobject, RoundedRectangle

from ..material import Material, line_box
from . import style
from .style import FRAME_HEIGHT, FRAME_WIDTH


def _size(mob, width, height):
    if width is None and height is None:                 # fit the whole frame
        if mob.width / mob.height >= FRAME_WIDTH / FRAME_HEIGHT:
            mob.width = FRAME_WIDTH
        else:
            mob.height = FRAME_HEIGHT
    elif width is not None and height is not None:      # fit inside width x height
        mob.width = width
        if mob.height > height:
            mob.height = height
    elif width is not None:
        mob.width = width
    else:
        mob.height = height
    return mob


class Page(ImageMobject):
    """A PDF page shown as a picture. Knows where its text lines are, wherever it is moved or scaled."""

    def __init__(self, path, item, **kwargs):
        super().__init__(str(path), **kwargs)
        self.item = item
        self.page_width, self.page_height = item["size"]

    def point(self, x, y):
        """Scene point of a position on the page given in PDF points (x from the left, y from the top)."""
        left, top = self.get_left()[0], self.get_top()[1]
        return np.array([left + x / self.page_width * self.width, top - y / self.page_height * self.height, 0])

    def region(self, lines):
        """(center, width, height) in the scene of some text lines (spec as in mark)."""
        x0, y0, x1, y1 = line_box(self.item, lines)
        a, b = self.point(x0, y0), self.point(x1, y1)
        return (a + b) / 2, b[0] - a[0], a[1] - b[1]

    def mark(self, lines, color=None, pad=0.07, fill_opacity=0.16, stroke_width=5):
        """A highlight frame around text lines of this page, placed where the page is now.

        Color: HIGHLIGHT unless given.
        lines: 3 | [3, 5] (L-numbers, a range) | {"lines": [2, 4, 6]} (exactly these) | "phrase in a line"
               | ["start phrase", "end phrase"]. L-numbers are those shown by the read tool.
        """
        center, w, h = self.region(lines)
        color = color or style.HIGHLIGHT
        r = RoundedRectangle(width=w + 2 * pad, height=h + 2 * pad, corner_radius=0.08, stroke_color=color,
                             stroke_width=stroke_width, fill_color=color, fill_opacity=fill_opacity)
        return r.move_to(center)


class SceneMaterial:
    """The material of the lesson, for scene code."""

    def __init__(self, lesson):
        self._m = Material(lesson)

    def page(self, ref, width=None, height=None):
        """A PDF page as a Page picture (default: as large as the frame allows, centered)."""
        item = self._m.item(ref)
        if "text_lines" not in item:
            raise ValueError(f"'{ref}' is not a PDF page (use figure() for pictures)")
        return _size(Page(self._m.path(item["image"]), item), width, height)

    def figure(self, ref, width=None, height=None):
        """A picture: a figure (slides.pdf#p3.f1, notes.docx#s2.f1), a picture source or a whole page.
        Default size: as large as the frame allows."""
        fig = self._m.figure(ref)
        return _size(ImageMobject(str(self._m.path(fig["image"]))), width, height)

    def text(self, ref):
        """The text of a page or section (as the read tool shows it)."""
        return self._m.read(ref)

    def lines(self, ref):
        """The text lines of a PDF page, in order (line L1 is lines(ref)[0])."""
        return [line["text"] for line in self._m.item(ref).get("text_lines", [])]
