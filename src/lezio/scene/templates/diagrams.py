"""Diagrams and processes: flow, mapping, cards, diagram (general boxes and arrows)."""
from manim import (DOWN, LEFT, RIGHT, UP, FadeIn, GrowArrow, Indicate, LaggedStart, VGroup)

from .. import style
from ..style import T, arrow, box
from . import template
from .kit import focus_anims, run_phases, text_box


def _family(name):
    """(stroke, fill) of a named color family of the active theme."""
    return {"primary": (style.PRIMARY, style.PRIMARY_SOFT), "secondary": (style.SECONDARY, style.SECONDARY_SOFT),
            "highlight": (style.HIGHLIGHT, style.HIGHLIGHT_SOFT), "positive": (style.POSITIVE, style.POSITIVE_SOFT),
            "negative": (style.NEGATIVE, style.NEGATIVE_SOFT), "neutral": (style.MUTED, style.NEUTRAL_SOFT)
            }.get(name, (style.PRIMARY, style.PRIMARY_SOFT))


@template(category="diagram", use_for="a process or sequence of stages, a chain of causes, an evolution: "
          "boxes linked by arrows, one stage per piece",
          example={"title": "Dal problema al programma", "args": {"items": ["Problema", "Algoritmo", "Programma", "Esecuzione"],
                                                                 "below": ["cosa", "come", "codice", "risultato"]},
                   "say": ["Si parte da un problema,", "si trova un algoritmo,", "lo si scrive come programma,",
                           "e infine lo si esegue."]})
def flow(ctx, steps, items: list[str], above: list[str] | None = None, below: list[str] | None = None,
         vertical: bool = False):
    """Boxes linked by arrows, revealed one per phase; the current stage is highlighted, the previous ones
    dimmed a little. above/below: optional small labels (same length as items). vertical: top to bottom.
    Phases: one per item."""
    n = len(items)
    if not 2 <= n <= 7:
        raise ValueError("flow: 2 to 7 items (split a longer process into two blocks)")
    gap = 0.9 if n <= 4 else 0.6
    if vertical:
        w, h = min(6.0, ctx.area.width * 0.55), min(1.3, (ctx.area.height - (n - 1) * 0.5) / n)
        gap = 0.5
    else:
        w, h = min(3.6, (ctx.area.width - (n - 1) * gap) / n), 1.6 if n <= 4 else 1.4
    boxes = [box(s, w=w, h=h) for s in items]
    groups = []
    for i, b in enumerate(boxes):
        g = VGroup(b)
        if above and i < len(above) and above[i]:
            g.add(text_box(above[i], w, style.SMALL_SIZE, style.MUTED, align="center").next_to(b, UP, buff=0.2))
        if below and i < len(below) and below[i]:
            g.add(text_box(below[i], w, style.SMALL_SIZE, style.TEXT, align="center").next_to(b, DOWN, buff=0.2))
        groups.append(g)
    layout = VGroup(*groups).arrange(DOWN if vertical else RIGHT, buff=gap)
    ctx.place(layout)
    arrows = []
    for i in range(n - 1):
        a, b = boxes[i], boxes[i + 1]
        arrows.append(arrow(a.get_bottom(), b.get_top(), style.PRIMARY, width=6) if vertical
                      else arrow(a.get_right(), b.get_left(), style.PRIMARY, width=6))

    def phase(i):
        def run(t):
            anims = [FadeIn(groups[i], shift=(DOWN if vertical else RIGHT) * 0.2)]
            if i > 0:
                anims.insert(0, GrowArrow(arrows[i - 1]))
            t.play(*anims, *focus_anims(groups[:i], -1, 0.55), rt=0.7)
        return run

    run_phases(steps, [phase(i) for i in range(n)])


@template(category="diagram", use_for="correspondences: term -> meaning, cause -> effect, input -> output, "
          "symbol -> code; one pair per piece",
          example={"title": "Unità di misura", "args": {"pairs": [["bit", "una cifra binaria"], ["byte", "otto bit"],
                                                                   ["kilobyte", "mille ventiquattro byte"]],
                                                         "left_title": "Nome", "right_title": "Che cos'è"},
                   "say": ["Il bit è una cifra binaria.", "Un byte sono otto bit.", "Un kilobyte, mille ventiquattro byte."]})
def mapping(ctx, steps, pairs: list[list[str]], left_title: str | None = None, right_title: str | None = None):
    """Rows "left -> right" revealed one per phase (pairs: [[left, right], ...], up to 6).
    Phases: one per pair."""
    n = len(pairs)
    if not 1 <= n <= 6:
        raise ValueError("mapping: 1 to 6 pairs (split longer lists into two blocks)")
    lw, rw = ctx.area.width * 0.36, ctx.area.width * 0.44
    h = min(1.25, (ctx.area.height - 1.0) / n - 0.3)
    rows, heads = [], VGroup()
    for left, right in pairs:
        a = box(left, w=lw, h=h)
        c = box(right, w=rw, h=h, color=style.SECONDARY, fill=style.SECONDARY_SOFT, bold=False)
        c.next_to(a, RIGHT, buff=ctx.area.width - lw - rw - 0.3)
        rows.append(VGroup(a, c))
    table = VGroup(*rows).arrange(DOWN, buff=0.3)
    for text, color, col in ((left_title, style.PRIMARY, 0), (right_title, style.SECONDARY, 1)):
        if text:
            heads.add(T(text, style.SMALL_SIZE + 2, color, bold=True).next_to(rows[0][col], UP, buff=0.3))
    whole = VGroup(heads, table) if len(heads) else table
    ctx.place(whole)
    arrows = [arrow(r[0].get_right(), r[1].get_left()) for r in rows]

    def phase(i):
        def run(t):
            if i == 0 and len(heads):
                t.play(FadeIn(heads), rt=0.4)
            t.play(FadeIn(rows[i][0], shift=RIGHT * 0.2), rt=0.5)
            t.until(0.3)
            t.play(GrowArrow(arrows[i]), FadeIn(rows[i][1], shift=LEFT * 0.2), rt=0.6)
        return run

    run_phases(steps, [phase(i) for i in range(n)])


@template(category="diagram", use_for="a set of possibilities and then a choice among them (options, cases, "
          "candidates)",
          example={"args": {"cards": ["0 simboli", "1 simbolo", "2 simboli", "10 simboli"], "pick": 2,
                            "prompt": "Quanti simboli servono?"},
                   "say": ["Proviamo con diverse possibilità.", "La scelta giusta è due simboli."]})
def cards(ctx, steps, cards: list[str], pick: int, prompt: str | None = None):
    """Cards for the options (2-8), then the one at index `pick` (0-based) is selected and the others dimmed.
    Phases: show all, select."""
    if not 2 <= len(cards) <= 8:
        raise ValueError("cards: 2 to 8 cards")
    cols = min(4, len(cards))
    w = min(3.4, (ctx.area.width - (cols - 1) * 0.4) / cols)
    grid = VGroup(*[box(c, w=w, h=1.5, color=style.MUTED, fill=style.NEUTRAL_SOFT, bold=False) for c in cards])
    grid.arrange_in_grid(cols=cols, buff=0.4)
    parts = [grid]
    head = text_box(prompt, ctx.area.width - 1, 44, style.PRIMARY, bold=True, align="center") if prompt else None
    if head is not None:
        parts.insert(0, head)
    ctx.place(VGroup(*parts).arrange(DOWN, buff=0.6))

    def show(t):
        if head is not None:
            t.play(FadeIn(head), rt=0.5)
        t.play(LaggedStart(*[FadeIn(c, shift=UP * 0.3) for c in grid], lag_ratio=0.15), rt=1.4)

    def select(t):
        chosen = grid[pick]
        t.play(*[c.animate.set_opacity(0.35) for c in grid if c is not chosen], rt=0.6)
        t.play(chosen[0].animate.set_stroke(style.HIGHLIGHT, 6).set_fill(style.HIGHLIGHT_SOFT, 1),
               chosen[1].animate.set_color(style.TEXT), rt=0.5)
        t.play(chosen.animate.scale(1.12), rt=0.4)

    run_phases(steps, [show, select])


def _edge_points(a, b):
    """Attach an arrow to the facing sides of two boxes."""
    ca, cb = a.get_center(), b.get_center()
    dx, dy = cb[0] - ca[0], cb[1] - ca[1]
    if abs(dx) * a.height >= abs(dy) * a.width:
        return (a.get_right(), b.get_left()) if dx > 0 else (a.get_left(), b.get_right())
    return (a.get_top(), b.get_bottom()) if dy > 0 else (a.get_bottom(), b.get_top())


@template(category="diagram", use_for="any structure of boxes and arrows (architectures, data flows, actors and "
          "relations) built piece by piece; when no more specific template fits",
          example={"title": "Architettura di von Neumann",
                   "args": {"nodes": [{"id": "cpu", "text": "CPU", "at": [0, 1.2]},
                                      {"id": "mem", "text": "Memoria", "at": [-3.5, -1.2], "color": "secondary"},
                                      {"id": "io", "text": "Ingresso e uscita", "at": [3.5, -1.2], "color": "neutral"}],
                            "edges": [{"from": "cpu", "to": "mem", "double": True, "label": "dati"},
                                      {"from": "cpu", "to": "io", "double": True}],
                            "reveal": [["cpu"], ["mem", "cpu>mem"], ["io", "cpu>io"], ["!cpu"]]},
                   "say": ["Al centro c'è il processore.", "Dialoga con la memoria,", "e con i dispositivi di ingresso e uscita.",
                           "Tutto passa dal processore."]})
def diagram(ctx, steps, nodes: list[dict], edges: list[dict] | None = None, reveal: list[list[str]] | None = None):
    """General boxes-and-arrows diagram, revealed piece by piece.
    nodes: [{"id", "text", "at": [x, y], "w": 2.8, "h": 1.1, "color": "primary|secondary|highlight|positive|
    negative|neutral"}] (x from -6 to 6, y from -3 to 3; the whole diagram is fitted to the free area).
    edges: [{"from", "to", "double": false, "label": null, "color": "neutral"}]; an edge's id is "from>to".
    reveal: one list per phase of node/edge ids to show; "!id" makes a visible element pulse.
    Default: everything in one phase."""
    edges = edges or []
    objs = {}
    for nd in nodes:
        col, fill = _family(nd.get("color", "primary"))
        objs[nd["id"]] = box(nd["text"], w=nd.get("w", 2.8), h=nd.get("h", 1.1), size=nd.get("size", 28),
                             color=col, fill=fill).move_to([nd["at"][0], nd["at"][1], 0])
    for e in edges:
        a, b = objs[e["from"]], objs[e["to"]]
        start, end = _edge_points(a, b)
        ar = arrow(start, end, _family(e.get("color", "neutral"))[0], double=e.get("double", False))
        g = VGroup(ar)
        if e.get("label"):
            g.add(T(e["label"], style.SMALL_SIZE, style.MUTED).next_to(
                ar, UP if abs(end[1] - start[1]) < 0.5 else RIGHT, buff=0.12))
        objs[f'{e["from"]}>{e["to"]}'] = g
    ctx.place(VGroup(*objs.values()))
    reveal = reveal or [[*[n["id"] for n in nodes], *[f'{e["from"]}>{e["to"]}' for e in edges]]]

    def phase(i):
        def run(t):
            anims = []
            for key in reveal[i]:
                if key.startswith("!"):
                    anims.append(Indicate(objs[key[1:]], color=style.HIGHLIGHT, scale_factor=1.1))
                elif ">" in key:
                    anims.append(GrowArrow(objs[key][0]))
                    anims += [FadeIn(m) for m in objs[key][1:]]
                else:
                    anims.append(FadeIn(objs[key], shift=UP * 0.15))
            if anims:
                t.play(*anims, rt=0.8)
        return run

    run_phases(steps, [phase(i) for i in range(len(reveal))])
