# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Original pages and figures of the study material: page (walkthrough with highlights), figure (a picture
with callouts and zoom)."""
import numpy as np
from manim import (Circle, Create, FadeIn, FadeOut, Group, GrowFromCenter, ImageMobject, Line, Rectangle,
                   ReplacementTransform, RoundedRectangle, Transform, VGroup, linear)

from .. import style
from ..style import T
from . import template
from .kit import run_phases, text_box


@template(category="material", use_for="the original page itself (when it is what is studied, or when the "
          "user asks for the original slides): the page on screen and a highlight on the lines being discussed",
          example={"args": {"ref": "demo.pdf#p1", "marks": [1, [2, 3], None]},
                   "say": ["Ecco la pagina originale.", "Le prime due righe dicono che bastano due simboli.",
                           "Il resto lo vedremo tra poco."]})
def page(ctx, steps, ref: str, marks: list, zoom: bool = False):
    """An original PDF page (ref "file.pdf#p3") as large as possible, with a highlight frame on its text
    lines following the narration: marks has one entry per narration piece, a lines spec (3, [3, 5],
    {"lines": [2, 4]}, "a phrase in a line") or null for no highlight. zoom: a slow zoom while talking
    (picture pages). Use it without a block title to show the page full screen."""
    pg = ctx.material.page(ref)
    if ctx.title is not None:
        ctx.place(pg)
    if len(marks) != steps.left:
        raise ValueError(f"page: {len(marks)} marks for {steps.left} narration pieces (one mark per piece)")
    hl = None
    for k, spec in enumerate(marks):
        t = steps()
        if k == 0:
            t.play(FadeIn(pg), rt=0.4)
        if spec is not None:
            new = pg.mark(spec)
            t.play(Create(new) if hl is None else ReplacementTransform(hl, new), rt=0.5)
            hl = new
        elif hl is not None:
            t.play(FadeOut(hl), rt=0.3)
            hl = None
        if zoom and t.left > 0.2:
            g = Group(pg, hl) if hl is not None else pg
            t.play(g.animate.scale(1 + 0.006 * t.duration), rt=t.left, rate_func=linear)


def _fractions(v, n, where):
    if not isinstance(v, list) or len(v) != n or not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                         and 0 <= x <= 1 for x in v):
        raise ValueError(f"figure: {where} must be {n} numbers from 0 to 1 (fractions of the picture from its "
                         f"top-left corner), got {v!r}")
    return [float(x) for x in v]


def _rect(cx, cy, w, h):
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def _overlap(a, b):
    return max(min(a[2], b[2]) - max(a[0], b[0]), 0) * max(min(a[3], b[3]) - max(a[1], b[1]), 0)


def _label_spot(size, mark, pic, area, taken):
    """Where to put a callout label of size (w, h) for a marker at `mark`: next to it (on the picture, the
    side covering least of it) or in the margin beside the picture at the same height if there is room.
    Returns (center, in_margin)."""
    w, h = size
    mx, my, r = mark[0], mark[1], 0.3 + 0.12
    cands = [((pic[0] - 0.45 - w / 2, my), True), ((pic[2] + 0.45 + w / 2, my), True)]
    first = (-1, 1) if mx < (pic[0] + pic[2]) / 2 else (1, -1)
    for dx, dy in ((first[0], 0), (first[1], 0), (0, -1), (0, 1), (1, -1), (-1, -1), (1, 1), (-1, 1)):
        cands.append(((mx + dx * (r + w / 2), my + dy * (r + h / 2)), False))
    best = None
    for k, ((cx, cy), margin) in enumerate(cands):
        box = _rect(cx, cy, w, h)
        inside = box[0] >= area.left - 0.01 and box[2] <= area.right + 0.01 and box[1] >= area.bottom - 0.01 \
            and box[3] <= area.top + 0.01
        if not inside:
            continue
        clash = sum(_overlap(box, t) for t in taken)
        across = (mx - pic[0] if cx < mx else pic[2] - mx) if margin else 0     # leader line over the picture
        score = 100 * clash + _overlap(box, pic) / (w * h) + 0.06 * np.hypot(cx - mx, cy - my) + 0.5 * across \
            + 0.001 * k
        if best is None or score < best[0]:
            best = (score, (cx, cy), margin)
    if best is None:                                   # nowhere inside: next to the marker, pulled inside the area
        cx = min(max(mx + r + w / 2, area.left + w / 2), area.right - w / 2)
        cy = min(max(my, area.bottom + h / 2), area.top - h / 2)
        return np.array([cx, cy, 0]), False
    return np.array([*best[1], 0]), best[2]


@template(category="material", use_for="an original figure or picture of the material (a diagram, a photo, a chart "
          "the learner will meet again) shown large, with numbered callouts on its parts and an optional zoom",
          example={"title": "Due insiemi disgiunti",
                   "args": {"ref": "figure.png", "zoom": [0.1, 0.17, 0.9, 0.83],
                            "callouts": [{"at": [0.17, 0.3], "text": "Insieme A"},
                                         {"at": [0.83, 0.3], "text": "Insieme B"},
                                         {"at": [0.5, 0.5], "text": "Nessun elemento in comune"}]},
                   "say": ["Questa è la figura del libro.", "Avviciniamoci ai due cerchi.",
                           "A sinistra c'è l'insieme A.", "A destra l'insieme B.",
                           "Tra i due non c'è sovrapposizione: non hanno elementi in comune."]})
def figure(ctx, steps, ref: str, callouts: list[dict] | None = None, zoom: list[float] | None = None):
    """A figure or picture of the material (ref "file.pdf#p3.f1", a picture source, or a whole page) as large
    as possible. callouts (up to 6): [{"at": [x, y], "text": "a few words"}], x and y fractions of the
    picture (0-1 from its top-left corner): one per phase, a numbered marker on that point with its label
    right beside it (placed where it covers least of the picture; the current one highlighted). Point at
    the part itself, not at text printed on it: the marker is a small disc that hides what is under it.
    zoom: [x0, y0, x1, y1] (fractions) a region enlarged before the callouts (it replaces the whole
    picture; the callouts must lie inside it, still given as fractions of the whole picture).
    Phases: the picture, the zoom (if any), one per callout."""
    callouts = callouts or []
    if len(callouts) > 6:
        raise ValueError(f"figure: {len(callouts)} callouts; use at most 6 (split them over two blocks)")
    spots = []
    for k, c in enumerate(callouts):
        if not isinstance(c, dict) or "at" not in c or not str(c.get("text", "")).strip():
            raise ValueError(f"figure: callouts[{k}] must be {{\"at\": [x, y], \"text\": \"...\"}}")
        unknown = [key for key in c if key not in ("at", "text")]
        if unknown:
            raise ValueError(f"figure: callouts[{k}] has unknown keys {unknown} (allowed: at, text)")
        spots.append(_fractions(c["at"], 2, f"callouts[{k}].at"))
    region = None
    if zoom is not None:
        region = _fractions(zoom, 4, "zoom")
        x0, y0, x1, y1 = region
        if x1 - x0 < 0.05 or y1 - y0 < 0.05:
            raise ValueError("figure: zoom must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1 (at least 0.05 apart)")
        for k, (x, y) in enumerate(spots):
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                raise ValueError(f"figure: callouts[{k}] at {[x, y]} is outside the zoom region {region}")
        spots = [((x - x0) / (x1 - x0), (y - y0) / (y1 - y0)) for x, y in spots]

    full = ctx.material.figure(ref)
    img = full
    if region is not None:
        h, w = full.pixel_array.shape[:2]
        x0, y0, x1, y1 = region
        r0, c0 = int(y0 * h), int(x0 * w)
        img = ImageMobject(full.pixel_array[r0:max(int(y1 * h), r0 + 2), c0:max(int(x1 * w), c0 + 2)])
        ctx.place(full, grow=4)
    ctx.place(img, grow=4)
    border = Rectangle(width=img.width, height=img.height, stroke_color=style.MUTED, stroke_width=2).move_to(img)

    def at(fx, fy, pic):
        return np.array([pic.get_left()[0] + fx * pic.width, pic.get_top()[1] - fy * pic.height, 0])

    pic_box = (img.get_left()[0], img.get_bottom()[1], img.get_right()[0], img.get_top()[1])
    markers = []
    for k, (fx, fy) in enumerate(spots):
        disc = Circle(radius=0.3, fill_color=style.PRIMARY, fill_opacity=1, stroke_color=style.BACKGROUND,
                      stroke_width=4).move_to(at(fx, fy, img))
        markers.append(VGroup(disc, T(str(k + 1), style.SMALL_SIZE, style.BACKGROUND, bold=True).move_to(disc)))
    taken = [(m.get_left()[0] - 0.05, m.get_bottom()[1] - 0.05, m.get_right()[0] + 0.05, m.get_top()[1] + 0.05)
             for m in markers]
    labels, leads = [], []
    for k, c in enumerate(callouts):
        text = text_box(c["text"], 4.4, style.TEXT_SIZE - 4, style.TEXT)
        pill = RoundedRectangle(width=text.width + 0.36, height=text.height + 0.28, corner_radius=0.12,
                                stroke_color=style.PRIMARY, stroke_width=3, fill_color=style.BACKGROUND,
                                fill_opacity=0.92)
        label = VGroup(pill, text.move_to(pill))
        center, margin = _label_spot((label.width, label.height), markers[k].get_center(), pic_box, ctx.area, taken)
        label.move_to(center)
        taken.append(_rect(center[0], center[1], label.width + 0.1, label.height + 0.1))
        labels.append(label)
        lead = None
        if margin:
            p = markers[k].get_center()
            end = np.array([label.get_left()[0] if center[0] > p[0] else label.get_right()[0], center[1], 0])
            lead = Line(p + (end - p) / max(np.linalg.norm(end - p), 1e-6) * 0.3, end, color=style.PRIMARY,
                        stroke_width=3)
        leads.append(lead)

    def p_picture(t):
        if region is None:
            t.play(FadeIn(img), Create(border), rt=0.8)
        else:
            t.play(FadeIn(full), rt=0.8)

    def p_zoom(t):
        x0, y0, x1, y1 = region
        a0, a1 = at(x0, y0, full), at(x1, y1, full)
        frame_ = Rectangle(width=a1[0] - a0[0], height=a0[1] - a1[1], stroke_color=style.HIGHLIGHT,
                           stroke_width=5).move_to((a0 + a1) / 2)
        t.play(Create(frame_), rt=0.6)
        t.until(0.25)
        center, width = img.get_center(), img.width
        img.set(width=frame_.width).move_to(frame_)
        ctx.scene.add(img, frame_)
        t.play(img.animate.set(width=width).move_to(center), FadeOut(full), Transform(frame_, border), rt=1.2)
        ctx.scene.remove(frame_)
        ctx.scene.add(border)

    def p_callout(k):
        def run(t):
            anims = [GrowFromCenter(markers[k])] + ([Create(leads[k])] if leads[k] is not None else [])
            anims += [labels[j][0].animate.set_stroke(style.MUTED, 2.5) for j in range(k)]
            t.play(*anims, rt=0.5)
            labels[k][0].set_stroke(style.HIGHLIGHT, 5)
            t.play(FadeIn(labels[k], scale=0.9), rt=0.5)
        return run

    phases = [p_picture] + ([p_zoom] if region is not None else []) + [p_callout(k) for k in range(len(callouts))]
    run_phases(steps, phases)
