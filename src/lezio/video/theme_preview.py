# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""A still image showing a theme (./lezio themes --preview NAME). File handed to the manim command;
the theme comes from the LEZIO_THEME environment variable."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from manim import DOWN, LEFT, RIGHT, UP, Create, RoundedRectangle, Scene, VGroup  # noqa: E402

from lezio.scene import style  # noqa: E402

style.apply_theme(os.environ.get("LEZIO_THEME", "light"))

from lezio.scene import (HAND, HIGHLIGHT, MT, MUTED, NEGATIVE, NEGATIVE_SOFT, NEUTRAL_SOFT, POSITIVE,  # noqa: E402
                         POSITIVE_SOFT, PRIMARY, PRIMARY_SOFT, SECONDARY, SECONDARY_SOFT, SMALL_SIZE, T, arrow,
                         box, check, cross, heading)


class ThemePreview(Scene):
    def construct(self):
        self.camera.background_color = style.BACKGROUND
        data = style.load_theme(style.ACTIVE)
        title = heading(f"{data.get('name', style.ACTIVE)}: il sistema binario")
        sub = T(data.get("description", ""), SMALL_SIZE, MUTED).next_to(title, DOWN, aligned_edge=LEFT, buff=0.2)
        body = T("Ogni cifra di un numero binario ha un peso.").next_to(sub, DOWN, aligned_edge=LEFT, buff=0.5)
        formula = MT("1101<sub>2</sub> = 2<sup>3</sup> + 2<sup>2</sup> + 2<sup>0</sup> = 13", color=PRIMARY)
        formula.next_to(body, DOWN, aligned_edge=LEFT, buff=0.4)
        mark = RoundedRectangle(width=formula.width + 0.3, height=formula.height + 0.3, corner_radius=0.08,
                                stroke_color=HIGHLIGHT, stroke_width=5, fill_color=HIGHLIGHT,
                                fill_opacity=0.16).move_to(formula)
        boxes = VGroup(box("CPU"), box("Memoria", color=SECONDARY, fill=SECONDARY_SOFT),
                       box("I/O", color=MUTED, fill=NEUTRAL_SOFT)).arrange(RIGHT, buff=0.9)
        boxes.next_to(formula, DOWN, aligned_edge=LEFT, buff=0.6)
        links = VGroup(arrow(boxes[0].get_right(), boxes[1].get_left(), double=True),
                       arrow(boxes[1].get_right(), boxes[2].get_left(), double=True))
        verdicts = VGroup(VGroup(check(), box("giusto", w=2.2, h=0.8, size=26, color=POSITIVE, fill=POSITIVE_SOFT))
                          .arrange(RIGHT, buff=0.3),
                          VGroup(cross(), box("sbagliato", w=2.2, h=0.8, size=26, color=NEGATIVE, fill=NEGATIVE_SOFT))
                          .arrange(RIGHT, buff=0.3)).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        verdicts.to_edge(RIGHT, buff=0.8).shift(UP * 0.6)
        hand = T("scritto a mano: 13 : 2 = 6 resto 1", font=HAND, color=PRIMARY)
        hand.next_to(boxes, DOWN, aligned_edge=LEFT, buff=0.6)
        swatches = VGroup()
        for name in ("PRIMARY", "SECONDARY", "HIGHLIGHT", "POSITIVE", "NEGATIVE", "MUTED"):
            color = getattr(style, name)
            chip = RoundedRectangle(width=0.5, height=0.5, corner_radius=0.08, stroke_width=0, fill_color=color,
                                    fill_opacity=1)
            swatches.add(VGroup(chip, T(name, 20, MUTED)).arrange(RIGHT, buff=0.15))
        swatches.arrange(RIGHT, buff=0.35).to_edge(DOWN, buff=0.4)
        self.add(title, sub, body, mark, formula, boxes, links, verdicts, hand, swatches)
        self.play(Create(mark), run_time=0.1)
