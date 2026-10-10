"""Structures: cycle, tree, layers, venn, timeline, concept_map (diagrams of how parts are arranged)."""
import json
import math
import textwrap
from typing import Literal

import numpy as np
from manim import (DL, DOWN, DR, LEFT, RIGHT, UL, UP, ArcBetweenPoints, Create, Difference, Dot, Ellipse, FadeIn,
                   FadeOut, GrowFromCenter, Intersection, LaggedStart, Line, Rectangle, RoundedRectangle, Union, VGroup)
from manim.mobject.geometry.tips import ArrowTriangleFilledTip

from .. import style
from ..style import T
from . import template
from .kit import run_phases

DIM = 0.45          # opacity of the parts already discussed


# ------------------------------------------------------------------ shared helpers
def _clean(text):
    return " ".join(str(text).split())


def _center_lines(mob, lines):
    """Center the lines of a multi-line Text (Manim aligns them left). With ligatures disabled every character,
    spaces and line breaks included, is one glyph: lines are matched to glyphs by length."""
    if len(lines) < 2 or len(mob) != len("\n".join(lines)):
        return mob
    x, k = mob.get_center()[0], 0
    for i, line in enumerate(lines):
        c = len(line) + (1 if i < len(lines) - 1 else 0)
        g = VGroup(*mob[k:k + c])
        g.shift(RIGHT * (x - g.get_center()[0]))
        k += c
    return mob


def _label(text, max_width, size, color=None, bold=False, center=True, max_height=None):
    """Text wrapped to max_width (words are never split: a word that is too long shrinks the text), with
    centered lines unless center=False; shrunk to max_height if given."""
    text = _clean(text)
    one = T(text, size, color, bold=bold, disable_ligatures=True)
    if one.width <= max_width or " " not in text:
        return style.fit(one, max_width, max_height)
    longest = max(len(w) for w in text.split())
    n = max(longest, min(len(text) - 1, int(len(text) * max_width / one.width)))
    while True:
        lines = textwrap.wrap(text, n, break_long_words=False)
        mob = T("\n".join(lines), size, color, bold=bold, disable_ligatures=True)
        if mob.width <= max_width or n <= longest:
            break
        n = max(longest, min(n - 1, int(n * max_width / mob.width) + 1))
    if center:
        _center_lines(mob, lines)
    return style.fit(mob, max_width, max_height)


def _node(text, max_width, size, stroke, fill, bold=False, width=None, height=None, text_color=None,
          padx=0.3, pady=0.2):
    """A rounded box around wrapped, centered text. width/height: fixed size (the text shrinks to fit)."""
    label = _label(text, (width or max_width) - 2 * padx, size, text_color or stroke, bold,
                   max_height=height - 0.08 if height else None)
    rect = RoundedRectangle(width=width or label.width + 2 * padx, height=height or label.height + 2 * pady,
                            corner_radius=0.16, stroke_color=stroke, stroke_width=3, fill_color=fill, fill_opacity=1)
    label.move_to(rect)
    node = VGroup(rect, label)
    node.colors = (stroke, fill)
    return node


def _look(node, mode, animate=False):
    """Show a node as "current" (highlighted), "normal" or "past" (dimmed). animate=True returns animations."""
    stroke, fill = node.colors
    width, opacity = 3, 1.0
    if mode == "current":
        stroke, fill, width = style.HIGHLIGHT, style.HIGHLIGHT_SOFT, 6
    elif mode == "past":
        opacity = DIM
    rect, label = node[0], node[1]
    if animate:
        return [rect.animate.set_stroke(stroke, width, opacity=opacity).set_fill(fill, opacity=opacity),
                label.animate.set_opacity(opacity)]
    rect.set_stroke(stroke, width, opacity=opacity).set_fill(fill, opacity=opacity)
    label.set_opacity(opacity)
    return []


def _fade_line(line, opacity):
    return line.animate.set_stroke(opacity=opacity)


def _inside(p, mob, buff):
    return abs(p[0] - mob.get_x()) <= mob.width / 2 + buff and abs(p[1] - mob.get_y()) <= mob.height / 2 + buff


def _border_point(mob, toward, buff=0.06):
    """Point on the bounding box of mob (plus buff) in the direction of `toward`."""
    c = mob.get_center()
    d = np.array(toward) - c
    sx = (mob.width / 2 + buff) / abs(d[0]) if abs(d[0]) > 1e-6 else math.inf
    sy = (mob.height / 2 + buff) / abs(d[1]) if abs(d[1]) > 1e-6 else math.inf
    return c + d * min(sx, sy, 1.0)


def _overlaps(a, b, buff=0.0):
    return (abs(a.get_x() - b.get_x()) < (a.width + b.width) / 2 + buff
            and abs(a.get_y() - b.get_y()) < (a.height + b.height) / 2 + buff)


def _ring(n, rx, ry, start):
    """Angles and points of n positions on an ellipse, clockwise from `start` (radians)."""
    angles = [start - 2 * math.pi * k / n for k in range(n)]
    return angles, [np.array([rx * math.cos(a), ry * math.sin(a), 0.0]) for a in angles]


def _fitting_size(items, lines=2, sizes=None, best=False, bold=False):
    """The largest text size (down to SMALL_SIZE) at which every (text, max_width) fits in `lines` lines without
    shrinking a word; best=True returns (size, whether it fits)."""
    sizes = sizes or [style.TEXT_SIZE - 4, style.TEXT_SIZE - 8, style.SMALL_SIZE]
    sizes = sorted({max(s, style.SMALL_SIZE) for s in sizes}, reverse=True)
    measured = []
    for text, w in items:
        text = _clean(text)
        word = max(text.split(), key=len) if text else ""
        measured.append((T(text, 100, bold=bold).width / 100, T(word, 100, bold=bold).width / 100 if word else 0, w))
    for size in sizes:
        if all(word * size <= w and full * size <= (w if lines == 1 else lines * w * 0.9)
               for full, word, w in measured):
            return (size, True) if best else size
    return (sizes[-1], False) if best else sizes[-1]


def _check_count(name, what, items, lo, hi, texts=True):
    """A list of lo..hi entries; texts=True: each a non-empty string."""
    if not isinstance(items, list) or not lo <= len(items) <= hi:
        got = len(items) if isinstance(items, list) else type(items).__name__
        raise ValueError(f"{name}: {what} must have {lo} to {hi} entries (got {got})")
    for i, x in enumerate(items if texts else []):
        if not isinstance(x, str) or not _clean(x):
            raise ValueError(f"{name}: {what}[{i}] must be a non-empty text (got {json.dumps(x, ensure_ascii=False)})")


# ------------------------------------------------------------------ cycle
def _ring_arrow(a, b, a_angle, b_angle, rx, ry):
    """Curved arrow along the ellipse (clockwise) from node a to node b; None if there is no room."""
    pts = [np.array([rx * math.cos(t), ry * math.sin(t), 0.0]) for t in np.linspace(a_angle, b_angle, 300)]
    free = [i for i, p in enumerate(pts) if not _inside(p, a, 0.12) and not _inside(p, b, 0.12)]
    if len(free) < 2:
        return None
    i0, i1 = free[0], free[-1]
    start, end, mid = pts[i0], pts[i1], pts[(i0 + i1) // 2]
    chord = end - start
    c = float(np.linalg.norm(chord))
    if c < 0.45:
        return None
    sag = abs(chord[0] * (mid - start)[1] - chord[1] * (mid - start)[0]) / c
    arc = ArcBetweenPoints(start, end, angle=-4 * math.atan2(2 * sag, c), color=style.MUTED, stroke_width=5)
    arc.add_tip(tip_shape=ArrowTriangleFilledTip, tip_length=0.24, tip_width=0.24)
    return arc


@template(category="diagram", use_for="a cyclic process that comes back to its start (a natural or biological "
          "cycle, the instruction cycle, an iterative method): the stages around a ring with curved arrows, one "
          "stage per piece",
          example={"title": "Il ciclo dell'istruzione",
                   "args": {"items": ["Prelievo dalla memoria", "Decodifica", "Esecuzione", "Scrittura del risultato"],
                            "center": "CPU"},
                   "say": ["Il processore ripete sempre lo stesso ciclo.",
                           "Preleva dalla memoria la prossima istruzione,",
                           "la decodifica, per capire che cosa deve fare,", "la esegue,",
                           "e scrive il risultato. Poi il ciclo ricomincia."]})
def cycle(ctx, steps, items: list[str], center: str | None = None):
    """The stages of a cycle (2-8 short items) around a ring, clockwise from the top, linked by curved arrows.
    The stage being discussed is highlighted and the earlier ones dimmed; with the last stage the arrow back
    to the first closes the loop, every stage lights up again and the first is highlighted (it starts over).
    center: optional label in the middle (what goes around the cycle, or who runs it).
    Phases: center (if given), then one per stage."""
    n = len(items) if isinstance(items, list) else 0
    _check_count("cycle", "items", items, 2, 8)
    a = ctx.area
    maxw = 4.2 if n <= 4 else 3.4
    size = _fitting_size([(s, maxw - 0.6) for s in items])
    nodes = [_node(s, maxw, size, style.PRIMARY, style.PRIMARY_SOFT) for s in items]
    start = math.pi if n == 2 else (math.pi / 2 - math.pi / n if n == 8 else math.pi / 2)
    for _ in range(20):                   # shrink the stages until they are apart and every arrow has room
        nw, nh = max(m.width for m in nodes), max(m.height for m in nodes)
        ry = a.height / 2 - nh / 2 - 0.05
        rx = a.width / 2 - nw / 2 - 0.05
        if n <= 4:
            rx = min(rx, max(ry * 1.7, nw * 0.9))
        angles, points = _ring(n, rx, ry, start)
        for m, p in zip(nodes, points):
            m.move_to(p)
        arrows = [_ring_arrow(nodes[k], nodes[(k + 1) % n], angles[k], angles[k] - 2 * math.pi / n, rx, ry)
                  for k in range(n)]
        apart = all(not _overlaps(nodes[i], nodes[j], 0.2) for i in range(n) for j in range(i + 1, n))
        if apart and all(x is not None for x in arrows):
            break
        for m in nodes:
            m.scale(0.92)
    parts = nodes + [x for x in arrows if x is not None]
    mid = None
    if center:
        mid = _label(center, min(4.2, max(1.5, 2 * rx - nw - 0.6)), style.TEXT_SIZE, style.PRIMARY, bold=True)
        for _ in range(12):
            if not any(_overlaps(mid, m, 0.2) for m in nodes):
                break
            mid.scale(0.9)
        parts.append(mid)
    ctx.place(VGroup(*parts))
    for m in nodes:
        _look(m, "current")

    def p_center(t):
        t.play(FadeIn(mid, scale=0.9), rt=0.6)

    def stage(k):
        def run(t):
            anims = [FadeIn(nodes[k], scale=0.9)]
            if k > 0:
                anims += _look(nodes[k - 1], "past", animate=True)
                if arrows[k - 1] is not None:
                    anims.insert(0, Create(arrows[k - 1]))
            t.play(*anims, rt=0.8)
            if k == n - 1:
                t.until(0.5)
                if arrows[k] is not None:
                    t.play(Create(arrows[k]), rt=0.5)
                t.play(*[x for j, m in enumerate(nodes) for x in _look(m, "current" if j == 0 else "normal", True)],
                       rt=0.5)
        return run

    run_phases(steps, ([p_center] if mid is not None else []) + [stage(k) for k in range(n)])


# ------------------------------------------------------------------ tree
def _parse_tree(items, path):
    if not isinstance(items, list):
        raise ValueError(f"tree: {path} must be a list of children")
    out = []
    for i, c in enumerate(items):
        where = f"{path}[{i}]"
        if isinstance(c, str) and c.strip():
            out.append({"label": c, "children": []})
        elif (isinstance(c, list) and len(c) in (1, 2) and isinstance(c[0], str) and c[0].strip()
              and (len(c) == 1 or isinstance(c[1], list))):
            out.append({"label": c[0], "children": _parse_tree(c[1], where + "[1]") if len(c) == 2 else []})
        else:
            got = json.dumps(c, ensure_ascii=False)
            raise ValueError(f"tree: {where} must be a label or [label, [children...]] (got {got[:70]})")
    return out


@template(category="diagram", use_for="a hierarchy: a classification or taxonomy, an organization chart, a whole "
          "split into parts and sub-parts, a file system; built level by level, branch by branch or node by node",
          example={"title": "Le memorie del calcolatore",
                   "args": {"root": "Memoria", "children": [["Primaria", ["RAM", "ROM", "Cache"]],
                                                            ["Secondaria", ["Disco magnetico", "SSD"]]]},
                   "say": ["Partiamo dalla memoria di un calcolatore.",
                           "Si divide in due famiglie: la memoria primaria e quella secondaria.",
                           "Nella primaria troviamo RAM, ROM e cache; nella secondaria i dischi magnetici e gli SSD."]})
def tree(ctx, steps, root: str, children: list, reveal: Literal["levels", "branches", "nodes"] = "levels",
         direction: Literal["auto", "down", "right"] = "auto"):
    """A hierarchy drawn as a tree. children: a list whose entries are labels (leaves) or [label, [children...]]
    (nested, any depth up to 4 levels below the root, at most 10 leaves), e.g.
    ["Pesci", ["Mammiferi", ["Primati", "Roditori"]]].
    reveal: "levels" (one level per phase), "branches" (the root, then each child of the root with all its
    descendants), "nodes" (one node per phase, depth-first). The new part is highlighted, the path from the
    root to it stays in full color, the rest is dimmed.
    direction: "down" (root on top), "right" (root on the left, better for many leaves or long labels),
    "auto" (down for up to 6 leaves).
    Phases: one per level / branch (after the root) / node, as chosen by reveal."""
    if not isinstance(root, str) or not _clean(root):
        raise ValueError("tree: root must be a non-empty text")
    top = {"label": root, "children": _parse_tree(children, "children"), "parent": None}
    if not top["children"]:
        raise ValueError("tree: children is empty (give at least one child of the root)")
    order = []

    def walk(nd, depth, leaf0):
        nd["depth"], nd["leaf0"] = depth, leaf0
        order.append(nd)
        count = 0
        for ch in nd["children"]:
            ch["parent"] = nd
            count += walk(ch, depth + 1, leaf0 + count)
        nd["leaves"] = max(count, 1)
        return nd["leaves"]

    n_leaves = walk(top, 0, 0)
    n_levels = max(nd["depth"] for nd in order) + 1
    if n_levels > 5:
        raise ValueError(f"tree: at most 4 levels below the root (got {n_levels - 1})")
    if n_leaves > 10:
        raise ValueError(f"tree: at most 10 leaves (got {n_leaves}): split it into several blocks (e.g. one per "
                         "branch)")
    a = ctx.area
    families = [(style.PRIMARY, style.PRIMARY_SOFT), (style.SECONDARY, style.SECONDARY_SOFT),
                (style.MUTED, style.NEUTRAL_SOFT)]
    padx, pady = 0.2, 0.16
    slot_d, lh = a.width / n_leaves, min(2.0, a.height / n_levels)
    cw, slot_r = a.width / n_levels, a.height / n_leaves

    def limits(way, nd):
        """(max width, max height) of a node in a layout."""
        if way == "down":
            return min(4.0, nd["leaves"] * slot_d - 0.2), lh - 0.55
        return min(4.4, cw - 0.7), nd["leaves"] * slot_r - 0.1

    def text_size(way):
        lines = 2 if way == "down" or slot_r >= 1.25 else 1
        return _fitting_size([(nd["label"], limits(way, nd)[0] - 2 * padx) for nd in order[1:]], lines, best=True)

    if direction == "auto":
        (sd, fd), (sr, fr) = text_size("down"), text_size("right")
        direction = "down" if (fd and (sd >= sr or not fr)) or (not fd and not fr and n_leaves <= 6) else "right"
    slot = slot_d if direction == "down" else slot_r
    lines = 2 if direction == "down" or slot_r >= 1.25 else 1
    if direction == "right":
        pady = 0.1
    for nd in order:
        nd["maxw"], nd["maxh"] = limits(direction, nd)
    sizes = [style.TEXT_SIZE]
    for d in range(1, n_levels):        # a level is never larger than the one above it
        level = [nd for nd in order if nd["depth"] == d]
        sizes.append(min(sizes[-1], _fitting_size([(nd["label"], nd["maxw"] - 2 * padx) for nd in level], lines)))
    for d in range(n_levels):            # a line must fit the height of the level's boxes (same size for all)
        room = min(nd["maxh"] for nd in order if nd["depth"] == d) - 0.08
        while sizes[d] > style.SMALL_SIZE and T("Hpg", sizes[d]).height > room:
            sizes[d] -= 2
        line = T("Hpg", sizes[d]).height
        if line > room:
            sizes[d] *= room / line
    for nd in order:
        nd["size"] = sizes[nd["depth"]]
        lab = _label(nd["label"], nd["maxw"] - 2 * padx, nd["size"], bold=nd is top)
        nd["need"] = (lab.width + 2 * padx, lab.height + 2 * pady)
    for d in range(n_levels):            # the nodes of a level share their size
        level = [nd for nd in order if nd["depth"] == d]
        w = max(1.5, max(nd["need"][0] for nd in level))
        h = min(max(nd["need"][1] for nd in level), min(nd["maxh"] for nd in level))
        for nd in level:
            stroke, fill = families[min(d, 2)]
            nd["mob"] = _node(nd["label"], nd["maxw"], nd["size"], stroke, fill, bold=nd is top,
                              width=min(w, nd["maxw"]), height=h, text_color=style.TEXT if d >= 2 else None,
                              padx=padx, pady=pady)
    for nd in order:
        if direction == "down":
            x = a.left + (nd["leaf0"] + nd["leaves"] / 2) * slot
            y = a.top - (nd["depth"] + 0.5) * lh
        else:
            x = a.left + (nd["depth"] + 0.5) * cw
            y = a.top - (nd["leaf0"] + nd["leaves"] / 2) * slot
        nd["mob"].move_to([x, y, 0])
    for nd in order[1:]:
        p, c = nd["parent"]["mob"], nd["mob"]
        if direction == "down":
            nd["edge"] = Line(p.get_bottom() + DOWN * 0.04, c.get_top() + UP * 0.04, color=style.MUTED, stroke_width=3)
        else:
            nd["edge"] = Line(p.get_right() + RIGHT * 0.04, c.get_left() + LEFT * 0.04, color=style.MUTED,
                              stroke_width=3)
    ctx.place(VGroup(*[nd["mob"] for nd in order], *[nd["edge"] for nd in order[1:]]))

    if reveal == "branches":
        groups = [[top]]
        for ch in top["children"]:
            groups.append([nd for nd in order if _descends(nd, ch)])
    elif reveal == "nodes":
        groups = [[nd] for nd in order]
    else:
        groups = [[nd for nd in order if nd["depth"] == d] for d in range(n_levels)]
    for nd in order:
        _look(nd["mob"], "current")
    shown = []

    def phase(group):
        def run(t):
            keep = {id(x) for nd in group for x in _ancestors(nd)}
            anims = []
            for nd in shown:
                mode = "normal" if id(nd) in keep else "past"
                anims += _look(nd["mob"], mode, animate=True)
                if nd.get("edge") is not None:
                    anims.append(_fade_line(nd["edge"], 1.0 if mode == "normal" else DIM))
            anims += [Create(nd["edge"]) for nd in group if nd.get("edge") is not None]
            anims += [FadeIn(nd["mob"], shift=(DOWN if direction == "down" else RIGHT) * 0.15) for nd in group]
            t.play(*anims, rt=0.8)
            shown.extend(group)
        return run

    run_phases(steps, [phase(g) for g in groups])


def _descends(nd, anc):
    while nd is not None:
        if nd is anc:
            return True
        nd = nd["parent"]
    return False


def _ancestors(nd):
    out, nd = [], nd["parent"]
    while nd is not None:
        out.append(nd)
        nd = nd["parent"]
    return out


# ------------------------------------------------------------------ layers
@template(category="diagram", use_for="stacked layers: levels of abstraction, a layered architecture (hardware -> "
          "operating system -> applications, network protocol stacks), strata; one layer per piece",
          example={"title": "I livelli di un sistema di calcolo",
                   "args": {"items": ["Hardware", "Sistema operativo", "Applicazioni", "Utente"],
                            "notes": ["CPU, memoria, periferiche", "gestisce le risorse",
                                      "browser, editor, giochi", "chi usa il computer"]},
                   "say": ["Alla base c'è l'hardware: processore, memoria e periferiche.",
                           "Sopra lavora il sistema operativo, che gestisce le risorse.",
                           "Sul sistema operativo girano le applicazioni.",
                           "E in cima ci siamo noi, gli utenti."]})
def layers(ctx, steps, items: list[str], notes: list[str] | None = None, bottom_up: bool = True):
    """Layers stacked on each other (2-8), revealed one per phase; the layer being discussed is highlighted,
    the others dimmed. bottom_up=true: items[0] is the bottom layer and the stack grows upwards; false: items[0]
    is the top layer and the stack grows downwards. notes: optional short note beside each layer (one per item,
    "" for none). Phases: one per layer, in the order of items."""
    n = len(items) if isinstance(items, list) else 0
    _check_count("layers", "items", items, 2, 8)
    if notes is not None and len(notes) != n:
        raise ValueError(f"layers: notes must have one entry per item ({n}; use \"\" for none), got {len(notes)}")
    notes = [_clean(x) for x in notes] if notes else [""] * n
    a = ctx.area
    has_notes = any(notes)
    gap = 0.14
    h = min(1.15, (a.height - (n - 1) * gap) / n)
    bw = min(9.5, a.width * (0.55 if has_notes else 0.78))
    sizes = [x for x in (style.TEXT_SIZE, style.TEXT_SIZE - 4, style.TEXT_SIZE - 8) if x > style.SMALL_SIZE]
    size = next((x for x in sizes if T("Hpg", x, bold=True).height <= h - 0.24), style.SMALL_SIZE)
    size = min(size, _fitting_size([(s, bw - 0.6) for s in items], 1 if h < 1.0 else 2, [size] + sizes, bold=True))
    bands = [_node(s, bw, size, style.PRIMARY, style.PRIMARY_SOFT, bold=True, width=bw, height=h) for s in items]
    visual = list(reversed(bands)) if bottom_up else bands
    stack = VGroup(*visual).arrange(DOWN, buff=gap)
    nw = a.width - bw - 0.45
    note_mobs = []
    for band, note in zip(bands, notes):
        if note:
            m = _label(note, nw, max(style.SMALL_SIZE, style.TEXT_SIZE - 6), style.MUTED, center=False,
                       max_height=h + gap)
            m.next_to(band, RIGHT, buff=0.45)
        else:
            m = None
        note_mobs.append(m)
    ctx.place(VGroup(stack, *[m for m in note_mobs if m is not None]))
    for b in bands:
        _look(b, "current")
    drop = DOWN if bottom_up else UP

    def phase(k):
        def run(t):
            anims = [FadeIn(bands[k], shift=drop * 0.3)]
            if note_mobs[k] is not None:
                anims.append(FadeIn(note_mobs[k], shift=LEFT * 0.2))
            if k > 0:
                anims += _look(bands[k - 1], "past", animate=True)
                if note_mobs[k - 1] is not None:
                    anims.append(note_mobs[k - 1].animate.set_opacity(DIM + 0.1))
            t.play(*anims, rt=0.7)
        return run

    run_phases(steps, [phase(k) for k in range(n)])


# ------------------------------------------------------------------ venn
VENN_FAMILIES = (("PRIMARY", "PRIMARY_SOFT"), ("SECONDARY", "SECONDARY_SOFT"), ("MUTED", "NEUTRAL_SOFT"))


def _venn_margin(cands, w, h, members, centers, r, sx, k):
    """For each candidate center, the smallest distance (in circle units) between a w x h box there and the
    border of the region `members` (negative: the box leaves the region)."""
    ox, oy = np.linspace(-w / 2, w / 2, 6), np.linspace(-h / 2, h / 2, 4)
    offs = np.array([(x, y) for x in ox for y in oy])
    pts = cands[:, None, :] + offs[None, :, :]
    margin = np.full(len(cands), np.inf)
    for i in range(k):
        d = np.hypot((pts[..., 0] - centers[i][0]) / sx, pts[..., 1] - centers[i][1])
        m = (r - d) if i in members else (d - r)
        margin = np.minimum(margin, m.min(axis=1))
    return margin


def _place_elements(elements, members, centers, r, sx, k, sizes, max_w, box):
    """A block with the elements of a region, as large as possible (down to SMALL_SIZE), placed where it fits
    best inside the region; None if it does not fit."""
    xs = np.linspace(box[0], box[1], 90)
    ys = np.linspace(box[2], box[3], 70)
    cands = np.array([(x, y) for x in xs for y in ys])
    for size in sizes:
        for cols in (1, 2):
            if cols == 2 and len(elements) < 3:
                continue
            mobs = [_label(e, max_w / cols, size, style.TEXT) for e in elements]
            block = VGroup(*mobs)
            if cols == 1:
                block.arrange(DOWN, buff=0.12)
            else:
                block.arrange_in_grid(cols=2, buff=(0.35, 0.12))
            margin = _venn_margin(cands, block.width + 0.1, block.height + 0.1, members, centers, r, sx, k)
            best = int(np.argmax(margin))
            if margin[best] > 0.04:
                return block.move_to([cands[best][0], cands[best][1], 0])
    return None


@template(category="diagram", use_for="sets and what they share: two or three overlapping circles with their "
          "elements, to classify examples, compare categories, show an intersection",
          example={"title": "Mammiferi e animali acquatici",
                   "args": {"sets": ["Mammiferi", "Animali acquatici"],
                            "regions": {"Mammiferi": ["cane", "gatto"], "Animali acquatici": ["squalo", "polpo"],
                                        "Mammiferi&Animali acquatici": ["balena", "delfino"]}},
                   "say": ["Prendiamo l'insieme dei mammiferi,", "e quello degli animali che vivono in acqua.",
                           "Cane e gatto sono mammiferi, ma non vivono in acqua.",
                           "Squalo e polpo vivono in acqua, ma non sono mammiferi.",
                           "Balena e delfino stanno in entrambi: sono mammiferi acquatici."]})
def venn(ctx, steps, sets: list[str], regions: dict | None = None):
    """A Venn diagram of 2 or 3 sets (names in `sets`), then the elements of its regions.
    regions: {region: [elements]}, where a region is the set names joined by "&": "A" = only in A, "A&B" = in A
    and B but not in the others, "A&B&C" = in all three; keep each region to a few short elements. Regions
    appear in the order given, each highlighted as its elements are written (an empty list only highlights it).
    Phases: one per set, then one per region."""
    k = len(sets) if isinstance(sets, list) else 0
    _check_count("venn", "sets", sets, 2, 3)
    names = [_clean(s) for s in sets]
    keys = [s.casefold() for s in names]
    if not all(names) or len(set(keys)) != k or any("&" in s for s in names):
        raise ValueError("venn: set names must be distinct, not empty, without '&'")
    parsed, seen = [], set()
    for key, elems in (regions or {}).items():
        members = set()
        for part in str(key).split("&"):
            p = _clean(part).casefold()
            if p not in keys:
                raise ValueError(f"venn: region '{key}': '{_clean(part)}' is not a set ({', '.join(names)}); a region "
                                 f"is set names joined by &, e.g. '{names[0]}&{names[1]}'")
            members.add(keys.index(p))
        if frozenset(members) in seen:
            raise ValueError(f"venn: region '{key}' is given twice")
        seen.add(frozenset(members))
        if isinstance(elems, str):
            elems = [elems]
        if not isinstance(elems, list) or not all(isinstance(e, (str, int, float)) for e in elems):
            raise ValueError(f"venn: region '{key}' must be a list of short strings")
        if len(elems) > 6:
            raise ValueError(f"venn: region '{key}' has {len(elems)} elements: at most 6 (better 2-3)")
        parsed.append((key, members, [_clean(e) for e in elems]))

    a = ctx.area
    fams = [(getattr(style, s), getattr(style, f)) for s, f in VENN_FAMILIES[:k]]
    if k == 2:
        heads = [_label(nm, 4.4, style.TEXT_SIZE, fams[i][0], bold=True) for i, nm in enumerate(names)]
        lh = max(m.height for m in heads)
        r = (a.height - lh - 0.3) / 2
        sx = min(1.55, (a.width / 2 - 0.1) / (1.55 * r))
        unit = [(-0.55, 0.0), (0.55, 0.0)]
    else:
        heads = [_label(nm, 2.7, style.TEXT_SIZE, fams[i][0], bold=True) for i, nm in enumerate(names)]
        r = (a.height - 0.15) / 2.87
        side = max(heads[0].width, heads[1].width)
        sx = max(1.0, min(1.5, (a.width / 2 - side - 0.3) / (1.37 * r)))
        unit = [(-0.5, 0.29), (0.5, 0.29), (0.0, -0.58)]
    centers = [(ux * r * sx, uy * r) for ux, uy in unit]
    shapes = []
    for (cx, cy), (stroke, _) in zip(centers, fams):
        e = Ellipse(width=2 * r * sx, height=2 * r).move_to([cx, cy, 0])
        e.set_stroke(stroke, 4).set_fill(stroke, 0.1)
        shapes.append(e)
    if k == 2:
        for i, hd in enumerate(heads):
            hd.next_to(shapes[i], UP, buff=0.15).set_x(centers[i][0] + (-0.25 if i == 0 else 0.25) * r * sx)
    else:
        for i, (ang, corner) in enumerate(((150, DR), (30, DL), (-28, UL))):     # the corner of the label on the
            p = np.array([centers[i][0] + r * sx * math.cos(math.radians(ang)),   # ellipse: the label lies outside
                          centers[i][1] + r * math.sin(math.radians(ang)), 0])
            heads[i].move_to(p - heads[i].get_corner(corner) + heads[i].get_center()
                             + 0.1 * np.array([-corner[0], -corner[1], 0]))

    sizes = [style.TEXT_SIZE, style.TEXT_SIZE - 4, style.TEXT_SIZE - 8] if k == 2 else [style.SMALL_SIZE + 4]
    sizes = sorted({max(s, style.SMALL_SIZE) for s in sizes + [style.SMALL_SIZE]}, reverse=True)
    box = (-a.width / 2, a.width / 2, min(c[1] for c in centers) - r, max(c[1] for c in centers) + r)
    region_mobs = []
    for key, members, elems in parsed:
        hl = _region_shape(shapes, members).set_fill(style.HIGHLIGHT_SOFT, 0.85).set_stroke(style.HIGHLIGHT, 5)
        block = None
        if elems:
            block = _place_elements(elems, members, centers, r, sx, k, sizes, 3.4 if k == 2 else 2.4, box)
            if block is None:
                raise ValueError(f"venn: the elements of region '{key}' do not fit: use fewer or shorter elements"
                                 + (" (with 3 sets an overlap holds one or two words of about 8 letters)"
                                    if k == 3 and len(members) > 1 else ""))
        region_mobs.append((hl, block))
    ctx.place(VGroup(*shapes, *heads, *[x for pair in region_mobs for x in pair if x is not None]), grow=1.0)

    def set_phase(i):
        def run(t):
            t.play(Create(shapes[i]), FadeIn(heads[i], shift=DOWN * 0.15), rt=0.9)
        return run

    current = {"hl": None}

    def region_phase(j):
        def run(t):
            hl, block = region_mobs[j]
            anims = [FadeIn(hl)]
            if current["hl"] is not None:
                anims.append(FadeOut(current["hl"]))
            for _, b in region_mobs[:j]:
                if b is not None:
                    anims.append(b.animate.set_opacity(0.6))
            t.play(*anims, rt=0.6)
            current["hl"] = hl
            if block is not None:
                t.play(LaggedStart(*[FadeIn(m, scale=0.9) for m in block], lag_ratio=0.3), rt=0.8)
        return run

    run_phases(steps, [set_phase(i) for i in range(k)] + [region_phase(j) for j in range(len(region_mobs))])


def _region_shape(shapes, members):
    """The area that is inside the sets `members` and outside the others."""
    inside = [shapes[i].copy() for i in sorted(members)]
    shape = inside[0] if len(inside) == 1 else Intersection(*inside)
    others = [shapes[i].copy() for i in range(len(shapes)) if i not in members]
    if others:
        shape = Difference(shape, others[0] if len(others) == 1 else Union(*others))
    return shape


# ------------------------------------------------------------------ timeline
@template(category="diagram", use_for="events in time order: a history, the stages of a development, a "
          "chronology; one event per piece along a time axis",
          example={"title": "Breve storia del calcolo automatico",
                   "args": {"events": [["1642", "Pascal: la Pascalina"], ["1837", "Babbage: la macchina analitica"],
                                       ["1936", "Turing: la macchina astratta"],
                                       ["1946", "ENIAC, il primo elettronico"], ["1971", "Il primo microprocessore"]]},
                   "say": ["Nel milleseicentoquarantadue Pascal costruisce una calcolatrice meccanica.",
                           "Due secoli dopo Babbage progetta la macchina analitica.",
                           "Nel millenovecentotrentasei Turing descrive la sua macchina astratta.",
                           "Dieci anni dopo arriva l'ENIAC, il primo calcolatore elettronico.",
                           "E nel millenovecentosettantuno nasce il primo microprocessore."]})
def timeline(ctx, steps, events: list[list[str]]):
    """Events along a horizontal time axis (evenly spaced, in the given order): events[i] = [when, what]
    (what may be omitted), 2-10 events; when short ("1946", "III sec. a.C."), what a few words. The event
    being discussed is highlighted, the earlier ones dimmed; with 5 or more events the descriptions alternate
    above and below the axis. Phases: one per event."""
    n = len(events) if isinstance(events, list) else 0
    _check_count("timeline", "events", events, 2, 10, texts=False)
    for i, ev in enumerate(events):
        if not 1 <= len(ev) <= 2 or not _clean(ev[0]):
            raise ValueError(f"timeline: events[{i}] must be [when, what] (got {json.dumps(ev, ensure_ascii=False)})")
    a = ctx.area
    w = a.width
    slot = w / n
    alt = n >= 5
    xs = [-w / 2 + slot * (k + 0.5) for k in range(n)]
    tw = min(2 * slot - 0.35, 4.2) if alt else slot - 0.35
    dsize = _fitting_size([(ev[1], tw) for ev in events if len(ev) > 1 and _clean(ev[1])] or [("x", tw)], 3,
                          [style.TEXT_SIZE - 2, style.TEXT_SIZE - 6, style.SMALL_SIZE])
    dates = [_label(ev[0], tw, style.TEXT_SIZE if n <= 6 else style.TEXT_SIZE - 4, style.PRIMARY, bold=True)
             for ev in events]
    date_h = max(m.height for m in dates)
    gap = 0.28
    if alt:
        avail = a.height / 2 - (gap + date_h + 0.3) - 0.05
    else:
        avail = a.height - (gap + date_h) - 0.4
    descs = [_label(ev[1], tw, dsize, style.TEXT, max_height=avail) if len(ev) > 1 and _clean(ev[1]) else None
             for ev in events]
    axis = style.arrow([-w / 2, 0, 0], [w / 2, 0, 0], style.MUTED, width=4)
    dots = [Dot([x, 0, 0], radius=0.12, color=style.PRIMARY) for x in xs]
    stems = [None] * n

    def clamp(m, x):
        m.set_x(min(max(x, -w / 2 + m.width / 2), w / 2 - m.width / 2))

    for k in range(n):
        up = 1 if (not alt or k % 2 == 1) else -1        # side of the date
        dates[k].move_to([0, up * (gap + dates[k].height / 2), 0])
        clamp(dates[k], xs[k])
        d = descs[k]
        if d is None:
            continue
        if alt:
            edge = -up * (gap + date_h + 0.3)
            d.move_to([0, edge - up * d.height / 2, 0])
            stems[k] = Line([xs[k], -up * 0.14, 0], [xs[k], edge + up * 0.08, 0], color=style.MUTED, stroke_width=2)
        else:
            d.move_to([0, -(0.4 + d.height / 2), 0])
        clamp(d, xs[k])
    parts = [axis, *dots, *dates, *[m for m in descs + stems if m is not None]]
    ctx.place(VGroup(*parts))
    for dot in dots:
        dot.set_color(style.HIGHLIGHT).scale(1.6)

    def phase(k):
        def run(t):
            if k == 0:
                t.play(Create(axis), rt=0.6)
            anims = [GrowFromCenter(dots[k]), FadeIn(dates[k], shift=DOWN * 0.1)]
            if stems[k] is not None:
                anims.append(Create(stems[k]))
            if descs[k] is not None:
                anims.append(FadeIn(descs[k], shift=(UP if descs[k].get_y() > axis.get_y() else DOWN) * 0.15))
            if k > 0:
                j = k - 1
                anims += [dots[j].animate.set_color(style.PRIMARY).scale(1 / 1.6), dates[j].animate.set_opacity(DIM)]
                if descs[j] is not None:
                    anims.append(descs[j].animate.set_opacity(DIM))
                if stems[j] is not None:
                    anims.append(_fade_line(stems[j], DIM))
            t.play(*anims, rt=0.7)
        return run

    run_phases(steps, [phase(k) for k in range(n)])


# ------------------------------------------------------------------ concept map
def _link_label(text, spoke, boxes, others):
    """A link label for a spoke: on the line (masking it with the background) where the line is steep enough to
    stay visible around it, else just above the line; placed where it covers no box and no other spoke.
    None if text is empty."""
    text = _clean(text)
    if not text:
        return None
    start, end = spoke.get_start(), spoke.get_end()
    d = end - start
    flat = abs(d[1]) < 0.3 * abs(d[0])
    own = [start + d * f for f in np.linspace(0, 1, 41)]
    samples = [o.get_start() + (o.get_end() - o.get_start()) * f for o in others for f in np.linspace(0, 1, 25)]
    best = None
    for mode in (("above", "on") if flat else ("on", "above")):
        for width in (3.2, 2.5, 1.9):
            lab = _label(text, width, max(style.SMALL_SIZE, style.TEXT_SIZE - 8), style.MUTED)
            for f in (0.5, 0.58, 0.42, 0.66, 0.34):
                p = start + d * f
                lab.move_to(p + (UP * (lab.height / 2 + 0.1) if mode == "above" else 0))
                clear = min((max(abs(lab.get_x() - m.get_x()) - (lab.width + m.width) / 2,
                                 abs(lab.get_y() - m.get_y()) - (lab.height + m.height) / 2) for m in boxes),
                            default=1.0)
                if any(_inside(q, lab, 0.06) for q in samples):
                    clear = min(clear, -0.5)
                covered = sum(_inside(q, lab, 0.08) for q in own) / len(own)
                score = clear - (max(0.0, covered - 0.6) if mode == "on" else 2 * covered)
                if best is None or score > best[0]:
                    best = (score, lab.copy(), mode)
                if score > 0.08:
                    break
            if best[0] > 0.08:
                break
        if best[0] > 0.08:
            break
    _, lab, mode = best
    bg = Rectangle(width=lab.width + 0.16, height=lab.height + 0.1, stroke_width=0, fill_color=style.BACKGROUND,
                   fill_opacity=1 if mode == "on" else 0).move_to(lab)
    return VGroup(bg, lab)


@template(category="diagram", use_for="a central concept and the ideas connected to it (its parts, properties, "
          "causes, examples), each linked by a labelled line; one connection per piece",
          example={"title": "La cellula",
                   "args": {"center": "Cellula", "nodes": ["Membrana cellulare", "Nucleo", "Citoplasma", "Mitocondri"],
                            "links": ["è delimitata dalla", "custodisce il DNA nel", "è piena di",
                                      "ricava energia dai"]},
                   "say": ["Al centro mettiamo la cellula.", "È delimitata dalla membrana cellulare,",
                           "custodisce il DNA nel nucleo,", "è piena di citoplasma,",
                           "e ricava energia dai mitocondri."]})
def concept_map(ctx, steps, center: str, nodes: list[str], links: list[str] | None = None):
    """A central concept in the middle and 2-8 related concepts in two columns on its right and left (clockwise
    from the top right), each joined to the center by a line. links: optional labels of the lines, one per node,
    read from the center to the node ("" for none), a few words each.
    The connection being discussed is highlighted, the earlier ones dimmed.
    Phases: the center, then one per node."""
    n = len(nodes) if isinstance(nodes, list) else 0
    _check_count("concept_map", "nodes", nodes, 2, 8)
    if not _clean(center):
        raise ValueError("concept_map: center must be a non-empty text")
    if links is not None and len(links) != n:
        raise ValueError(f"concept_map: links must have one entry per node ({n}; use \"\" for none), got {len(links)}")
    a = ctx.area
    hub = _node(center, 3.2, style.TEXT_SIZE, style.PRIMARY, style.PRIMARY_SOFT, bold=True, padx=0.35, pady=0.24)
    n_right = (n + 1) // 2
    n_left = n - n_right
    maxw = min(3.6, (a.width - hub.width) / 2 - 1.7)
    size = _fitting_size([(s, maxw - 0.5) for s in nodes])
    labs = [_label(s, maxw - 0.5, size) for s in nodes]
    w = max(1.6, max(m.width for m in labs) + 0.5)
    h = min(max(m.height for m in labs) + 0.36, a.height / n_right - 0.3)
    sats = [_node(s, w, size, style.SECONDARY, style.SECONDARY_SOFT, width=w, height=h, padx=0.25, pady=0.18)
            for s in nodes]
    x = a.width / 2 - w / 2

    def column_y(j, m):                     # a column spans the whole height: steep spokes leave room for labels
        return 0.0 if m == 1 else (a.height - h) / 2 - j * (a.height - h) / (m - 1)

    for j in range(n_right):               # clockwise: the right column top to bottom, then the left bottom to top
        sats[j].move_to([x, column_y(j, n_right), 0])
    for j in range(n_left):
        sats[n_right + j].move_to([-x, -column_y(j, n_left), 0])
    spokes = [Line(_border_point(hub, m.get_center()), _border_point(m, hub.get_center()), color=style.MUTED,
                   stroke_width=3) for m in sats]
    labels = []
    for k, sp in enumerate(spokes):
        lab = None
        if links:
            lab = _link_label(links[k], sp, [hub, *sats, *[x for x in labels if x is not None]],
                              [o for o in spokes if o is not sp])
        labels.append(lab)
    ctx.place(VGroup(hub, *sats, *spokes, *[x for x in labels if x is not None]))
    for m in sats:
        _look(m, "current")

    def p_center(t):
        t.play(FadeIn(hub, scale=0.9), rt=0.6)

    def link(k):
        def run(t):
            anims = [Create(spokes[k])]
            if labels[k] is not None:
                anims.append(FadeIn(labels[k]))
            if k > 0:
                anims += _look(sats[k - 1], "past", animate=True) + [_fade_line(spokes[k - 1], DIM)]
                if labels[k - 1] is not None:
                    anims.append(labels[k - 1][1].animate.set_opacity(DIM))
            t.play(*anims, rt=0.6)
            t.play(FadeIn(sats[k], scale=0.9), rt=0.5)
        return run

    run_phases(steps, [p_center] + [link(k) for k in range(n)])
