"""Optional ready-made layouts. Use them when they fit; write your own scene code when they do not.

Every layout is called as `name(scene, steps, ...)`: it shows its content over the narration pieces it is
given and returns a Group of what it put on screen (fade it out when you move on). Give it the pieces it
must use with steps.take(n) - e.g. bullets(scene, steps.take(4), title, items) uses the next 4 pieces, one
phase per piece; with fewer pieces than phases the phases are spaced out inside them. Given `steps`
itself, a layout uses all the remaining pieces. All visible texts come from the arguments.
"""
import functools

from manim import (DOWN, LEFT, RIGHT, UL, UP, WHITE, Brace, Circle, Create, FadeIn, FadeOut, GrowArrow,
                   GrowFromCenter, Group, Indicate, LaggedStart, Line, RoundedRectangle, Square, VGroup,
                   Write)

from .style import (BLUE, BLUE_LIGHT, DARK, GREEN, GREEN_LIGHT, GREY, GREY_LIGHT, MONO, ORANGE, ORANGE_LIGHT,
                    RED, RED_LIGHT, YELLOW, YELLOW_LIGHT, T, arrow, box, check, cross, wrap)

COLORS = {
    "blue": (BLUE, BLUE_LIGHT), "orange": (ORANGE, ORANGE_LIGHT), "green": (GREEN, GREEN_LIGHT),
    "yellow": ("#B58900", YELLOW_LIGHT), "grey": (GREY, GREY_LIGHT), "red": (RED, RED_LIGHT),
}


def layout(fn):
    """Make a layout return a Group of the mobjects it added to the scene."""
    @functools.wraps(fn)
    def run(scene, steps, *args, **kwargs):
        before = {id(m) for m in scene.mobjects}
        fn(scene, steps, *args, **kwargs)
        return Group(*[m for m in scene.mobjects if id(m) not in before])
    return run


def run_phases(steps, phases):
    """Distribute phase callables (each takes a Timer) over the narration pieces left in `steps`."""
    n_steps, n_ph = steps.left, len(phases)
    if n_steps < 1:
        raise RuntimeError("no narration pieces left for this layout")
    groups = [[] for _ in range(n_steps)]
    for i, ph in enumerate(phases):
        groups[min(i * n_steps // n_ph, n_steps - 1)].append(ph)
    for group in groups:
        t = steps()
        for j, ph in enumerate(group):
            ph(t)
            if j < len(group) - 1:
                t.until((j + 1) / len(group) * 0.92)


def _title(text):
    return T(text, 38, BLUE, bold=True).to_edge(UP, buff=0.6)


# ---------------------------------------------------------------- flow
@layout
def flow(scene, steps, items, title=None, above=None, below=None):
    """Chain of boxes linked by arrows, revealed left to right (a process, an evolution, a recap).

    items: 2-6 short strings.  above / below: optional lists (same length) of small labels.
    Phases: one per item.
    """
    n = len(items)
    w = min(3.0, (13.2 - (n - 1) * 0.5) / n)
    boxes = VGroup(*[box(s, w=w, size=26) for s in items]).arrange(RIGHT, buff=0.5)
    arrows = [arrow(boxes[i].get_right(), boxes[i + 1].get_left(), BLUE) for i in range(n - 1)]
    groups = []
    for i, b in enumerate(boxes):
        g = VGroup(b)
        if above and above[i]:
            g.add(T(above[i], 26, GREY).next_to(b, UP, buff=0.2))
        if below and below[i]:
            g.add(T(below[i], 28, DARK).next_to(b, DOWN, buff=0.25))
        groups.append(g)
    head = _title(title) if title else None

    def phase(i):
        def run(t):
            anims = [FadeIn(groups[i], shift=UP * 0.2)]
            if i == 0 and head:
                anims.append(FadeIn(head))
            if i > 0:
                anims.insert(0, GrowArrow(arrows[i - 1]))
            t.play(*anims, rt=0.7)
        return run

    run_phases(steps, [phase(i) for i in range(n)])


# ---------------------------------------------------------------- mapping
@layout
def mapping(scene, steps, pairs, left_title=None, right_title=None):
    """Rows "left -> right" revealed one by one (definition -> property, cause -> effect).

    pairs: 1-5 [left, right] string pairs.  Phases: one per pair.
    """
    n = len(pairs)
    gap = min(1.7, 6.0 / max(n, 1))
    top = (n - 1) * gap / 2 - 0.3
    heads = VGroup()
    for text, color, x in ((left_title, BLUE, -3.3), (right_title, ORANGE, 3.6)):
        if text:
            head = T(text, 34, color, bold=True)
            if head.width > 6.2:
                head.scale_to_fit_width(6.2)
            heads.add(head.move_to(RIGHT * x + UP * 3.0))

    def phase(i):
        def run(t):
            y = top - i * gap
            a = box(pairs[i][0], w=5.2, h=1.1, size=30).move_to(LEFT * 3.3 + UP * y)
            c = box(pairs[i][1], w=4.2, h=1.1, size=32, color=ORANGE, fill=ORANGE_LIGHT).move_to(RIGHT * 3.6 + UP * y)
            if i == 0 and len(heads):
                t.play(FadeIn(heads), rt=0.5)
            t.play(FadeIn(a, shift=RIGHT * 0.2), rt=0.6)
            t.until(0.3)
            t.play(GrowArrow(arrow(a.get_right(), c.get_left())), FadeIn(c, shift=LEFT * 0.2), rt=0.8)
        return run

    run_phases(steps, [phase(i) for i in range(n)])


# ---------------------------------------------------------------- cards
@layout
def cards(scene, steps, cards, pick, prompt=None):
    """A set of possible options (cards), then one gets selected (a choice among possibilities).

    cards: 2-8 short strings.  pick: index (0-based) or text of the chosen card.
    prompt: optional question shown on top.  Phases: show all, select one.
    """
    pick = cards.index(pick) if isinstance(pick, str) else pick
    cols = min(4, len(cards))
    rows = (len(cards) + cols - 1) // cols
    grid = VGroup(*[box(c, w=3.1, h=1.1, size=28, color=GREY, fill=WHITE, bold=False) for c in cards])
    grid.arrange_in_grid(rows=rows, cols=cols, buff=0.35).move_to(DOWN * 0.7)
    head = None
    if prompt:
        head = box(prompt, w=max(4.4, len(prompt) * 0.27), h=1.0, size=38).to_edge(UP, buff=0.6)

    def show(t):
        if head:
            t.play(FadeIn(head), rt=0.6)
        t.play(LaggedStart(*[FadeIn(c, shift=UP * 0.3) for c in grid], lag_ratio=0.15), rt=1.8)

    def select(t):
        chosen = grid[pick]
        t.play(*[c.animate.set_opacity(0.35) for c in grid if c is not chosen], rt=0.7)
        t.play(chosen[0].animate.set_stroke(YELLOW, 6).set_fill(YELLOW_LIGHT, 1),
               chosen[1].animate.set_color(DARK), rt=0.5)
        t.play(chosen.animate.scale(1.15), rt=0.4)

    run_phases(steps, [show, select])


# ---------------------------------------------------------------- encode
def _code_mobject(code):
    """Morse-like codes made of '.' and '-' are drawn as dots and dashes; anything else as monospaced text."""
    if set(code) <= set(".-·—– "):
        g = VGroup()
        for c in code.replace(" ", ""):
            if c in "-—–":
                g.add(RoundedRectangle(width=0.75, height=0.24, corner_radius=0.1, fill_color=DARK,
                                       fill_opacity=1, stroke_width=0))
            else:
                g.add(Circle(radius=0.13, fill_color=DARK, fill_opacity=1, stroke_width=0))
        return g.arrange(RIGHT, buff=0.22)
    return T(code, 64, DARK, bold=True, font=MONO)


@layout
def encode(scene, steps, items, encode_label, decode_label=None):
    """Symbols -> codes (and optionally codes -> symbols again): encoding and decoding.

    items: 1-4 [symbol, code] pairs. Codes made only of "." and "-" are drawn as Morse dots and dashes,
    e.g. [["B", "-..."], ["A", ".-"]]; any other code is shown as text, e.g. [["A", "01000001"]].
    encode_label / decode_label: captions above the two arrows. Phases: encode, decode.
    """
    n = len(items)
    ys = [((n - 1) / 2 - i) * min(2.4, 6.0 / n) for i in range(n)]
    syms = [T(s, 90, BLUE, bold=True).move_to(LEFT * 5 + UP * y) for (s, _), y in zip(items, ys)]
    codes = [_code_mobject(c).move_to(UP * y) for (_, c), y in zip(items, ys)]
    top = max(ys) + 1.4

    def enc(t):
        t.play(*[FadeIn(s) for s in syms], FadeIn(T(encode_label, 30, BLUE).move_to(LEFT * 2.75 + UP * top)), rt=0.7)
        for s, c in zip(syms, codes):
            t.play(GrowArrow(arrow(s.get_right(), c.get_left(), BLUE)),
                   LaggedStart(*[GrowFromCenter(x) for x in c], lag_ratio=0.25), rt=1.0)

    def dec(t):
        t.play(FadeIn(T(decode_label, 30, ORANGE).move_to(RIGHT * 2.75 + UP * top)), rt=0.5)
        for (s, _), c, y in zip(items, codes, ys):
            d = T(s, 90, ORANGE, bold=True).move_to(RIGHT * 5 + UP * y)
            t.play(GrowArrow(arrow(c.get_right(), d.get_left(), ORANGE)), FadeIn(d), rt=0.8)

    run_phases(steps, [enc, dec] if decode_label else [enc])


# ---------------------------------------------------------------- translate
@layout
def translate(scene, steps, source, via, result, source_note=None, source_brace=None, result_brace=None):
    """Source -> translator box -> result (compiling, converting, any transformation).

    source / result: strings (shown monospaced).  via: label of the middle box.
    source_note: small text under the source.  source_brace / result_brace: labels on braces.
    Phases: source, transformation, braces.
    """
    src = T(source, 72, BLUE, font=MONO).move_to(UP * 2.3)
    if src.width > 12:
        src.scale_to_fit_width(12)
    note = T(source_note, 34, GREY).next_to(src, DOWN, buff=0.25) if source_note else None
    mid = box(via, w=3.8).move_to(DOWN * 0.1)
    res = T(result, 46, DARK, font=MONO).move_to(DOWN * 2.4)
    if res.width > 12.5:
        res.scale_to_fit_width(12.5)

    def p_source(t):
        t.play(Write(src), rt=1.0)
        if note:
            t.play(FadeIn(note), rt=0.5)

    def p_translate(t):
        t.play(GrowArrow(arrow((note or src).get_bottom(), mid.get_top())), FadeIn(mid), rt=0.7)
        t.play(GrowArrow(arrow(mid.get_bottom(), res.get_top())), rt=0.4)
        t.play(Write(res), rt=2.0)

    def p_braces(t):
        if result_brace:
            b = Brace(res, DOWN, color=ORANGE)
            t.play(GrowFromCenter(b), FadeIn(T(result_brace, 34, ORANGE, bold=True).next_to(b, DOWN, buff=0.15)), rt=0.8)
        if source_brace:
            b = Brace(src, UP, color=BLUE)
            t.play(GrowFromCenter(b), FadeIn(T(source_brace, 30, BLUE, bold=True).next_to(b, UP, buff=0.12)), rt=0.8)

    phases = [p_source, p_translate] + ([p_braces] if source_brace or result_brace else [])
    run_phases(steps, phases)


# ---------------------------------------------------------------- number_base
@layout
def number_base(scene, steps, number, base=2, caption=None, claim=None):
    """A decimal number and its representation in another base, with positional weights and sum.

    number: non-negative int.  base: 2..16.  caption: small label on top (e.g. "Anteprima").
    claim: final sentence shown at the bottom. Phases: decimal, digits+weights+sum, claim.
    """
    digits, x = [], number
    while True:
        digits.append("0123456789ABCDEF"[x % base])
        x //= base
        if x == 0:
            break
    digits = digits[::-1]
    weights = [base ** k for k in range(len(digits) - 1, -1, -1)]
    head = T(caption, 30, GREY).to_edge(UP, buff=0.5) if caption else None
    dec = T(str(number), 150, BLUE, bold=True).move_to(LEFT * 3.8)
    lab_d = T("base 10", 32, GREY).next_to(dec, DOWN, buff=0.3)
    ds = VGroup(*[T(d, 120, ORANGE, bold=True) for d in digits]).arrange(RIGHT, buff=0.4).move_to(RIGHT * 3.3)
    if ds.width > 6:
        ds.scale_to_fit_width(6)
    link = arrow(dec.get_right() + RIGHT * 0.2, ds.get_left() + LEFT * 0.2, GREY, double=True)
    lab_b = T(f"base {base}", 32, GREY).next_to(ds, DOWN, buff=0.3)
    ws = VGroup(*[T(str(w), 36, GREY).next_to(d, UP, buff=0.3) for w, d in zip(weights, ds)])
    nonzero = [(int(d, 16), w) for d, w in zip(digits, weights) if d != "0"]
    terms = " + ".join(str(w) if v == 1 else f"{v}×{w}" for v, w in nonzero)
    total = T(f"{terms} = {number}", 46, DARK).next_to(lab_b, DOWN, buff=0.5)

    def p_dec(t):
        t.play(*([FadeIn(head)] if head else []), Write(dec), rt=1.2)
        t.play(FadeIn(lab_d), rt=0.5)

    def p_digits(t):
        t.play(GrowFromCenter(link), rt=0.6)
        t.play(LaggedStart(*[Write(d) for d in ds], lag_ratio=0.3), rt=1.4)
        t.play(FadeIn(lab_b), rt=0.4)
        t.until(0.3)
        t.play(LaggedStart(*[FadeIn(w, shift=DOWN * 0.2) for w in ws], lag_ratio=0.3), rt=1.4)
        t.until(0.62)
        t.play(*[Indicate(d, color=GREEN, scale_factor=1.25) for d, g in zip(ds, digits) if g != "0"], rt=1.0)
        t.play(Write(total), rt=1.2)

    def p_claim(t):
        t.play(Indicate(link, color=BLUE, scale_factor=1.15), rt=0.8)
        t.play(FadeIn(T(claim, 38, BLUE, bold=True).to_edge(DOWN, buff=0.6), shift=UP * 0.2), rt=0.6)

    run_phases(steps, [p_dec, p_digits] + ([p_claim] if claim else []))


# ---------------------------------------------------------------- statement
@layout
def statement(scene, steps, lines, title=None):
    """Big centered sentences appearing one per phase (key definitions, take-home messages).

    lines: 1-4 strings (long ones are wrapped).  title: optional heading.
    """
    n = len(lines)
    mobs = VGroup(*[T(wrap(s, 38), 44, DARK, bold=(i == 0)) for i, s in enumerate(lines)])
    mobs.arrange(DOWN, buff=0.6).move_to(DOWN * 0.3)
    if mobs.height > 6:
        mobs.scale_to_fit_height(6)
    head = _title(title) if title else None

    def phase(i):
        def run(t):
            anims = [FadeIn(mobs[i], shift=UP * 0.2)]
            if i == 0 and head:
                anims.append(FadeIn(head))
            t.play(*anims, rt=0.8)
        return run

    run_phases(steps, [phase(i) for i in range(n)])


# ---------------------------------------------------------------- bullets / title (animated mode)
@layout
def bullets(scene, steps, title, items, focus=None):
    """A slide-like title with bullet points revealed one per phase.

    items: 1-6 strings (long ones are wrapped).  focus: optional index of the item to emphasize at the end.
    Phases: one per item.
    """
    head = T(title, 44, BLUE, bold=True).to_corner(UL, buff=0.7)
    if head.width > 12.5:
        head.scale_to_fit_width(12.5)
    rows = VGroup()
    for s in items:
        dot = Square(0.16, fill_color=BLUE, fill_opacity=1, stroke_width=0)
        txt = T(wrap(s, 52), 32, DARK)
        rows.add(VGroup(dot, txt).arrange(RIGHT, buff=0.3, aligned_edge=UP))
    rows.arrange(DOWN, buff=0.38, aligned_edge=LEFT).next_to(head, DOWN, buff=0.6).align_to(head, LEFT)
    if rows.height > 5.6:
        rows.scale_to_fit_height(5.6).next_to(head, DOWN, buff=0.5).align_to(head, LEFT)

    def phase(i):
        def run(t):
            anims = [FadeIn(rows[i], shift=RIGHT * 0.2)]
            if i == 0:
                anims.append(FadeIn(head))
            t.play(*anims, rt=0.7)
            if focus is not None and i == len(items) - 1:
                t.until(0.6)
                t.play(rows[focus][1].animate.set_color(ORANGE), rt=0.5)
        return run

    run_phases(steps, [phase(i) for i in range(len(items))])


@layout
def title_card(scene, steps, title, subtitle=None):
    """Full-screen title (lesson opening, section change). Phases: title, subtitle."""
    head = T(wrap(title, 30), 64, BLUE, bold=True).move_to(UP * 0.4)
    line = Line(LEFT * 3, RIGHT * 3, color=YELLOW, stroke_width=6).next_to(head, DOWN, buff=0.35)
    sub = T(wrap(subtitle, 45), 36, GREY).next_to(line, DOWN, buff=0.35) if subtitle else None

    def p_title(t):
        t.play(Write(head), rt=1.0)
        t.play(Create(line), rt=0.5)

    def p_sub(t):
        t.play(FadeIn(sub, shift=UP * 0.2), rt=0.6)

    run_phases(steps, [p_title] + ([p_sub] if sub else []))


# ---------------------------------------------------------------- compare
@layout
def compare(scene, steps, left_title, left_items, right_title, right_items, left_verdict=None, right_verdict=None):
    """Two columns side by side (before/after, A vs B, good vs bad).

    *_items: up to 5 short strings each.  *_verdict: optional "ok" / "no" mark under each column.
    Phases: left column, right column, verdicts.
    """
    def column(title, items, color, fill, x):
        head = box(title, w=5.6, h=1.0, size=32, color=color, fill=fill).move_to(RIGHT * x + UP * 2.5)
        rows = VGroup(*[T(wrap(s, 30), 30, DARK) for s in items]).arrange(DOWN, buff=0.35, aligned_edge=LEFT)
        rows.next_to(head, DOWN, buff=0.5)
        return head, rows

    lh, lr = column(left_title, left_items, BLUE, BLUE_LIGHT, -3.4)
    rh, rr = column(right_title, right_items, ORANGE, ORANGE_LIGHT, 3.4)

    def side(head, rows):
        def run(t):
            t.play(FadeIn(head), rt=0.5)
            t.play(LaggedStart(*[FadeIn(r, shift=RIGHT * 0.2) for r in rows], lag_ratio=0.4), rt=1.2)
        return run

    def verdicts(t):
        marks = []
        for v, rows in ((left_verdict, lr), (right_verdict, rr)):
            if v:
                m = (check() if v == "ok" else cross()).next_to(rows, DOWN, buff=0.5)
                marks.append(Create(m))
        t.play(*marks, rt=0.6)

    phases = [side(lh, lr), side(rh, rr)] + ([verdicts] if left_verdict or right_verdict else [])
    run_phases(steps, phases)


# ---------------------------------------------------------------- diagram
@layout
def diagram(scene, steps, nodes, edges=(), reveal=None, title=None):
    """General boxes-and-arrows diagram, revealed piece by piece (architectures, data flows, actors).

    nodes: list of {"id", "text", "at": [x, y], "w": 2.8, "h": 1.1, "color": "blue|orange|green|yellow|grey|red"}
           (text may contain "\\n").
    edges: list of {"from": id, "to": id, "double": False, "label": None, "color": "grey"}; edge id is "from>to".
    reveal: list (one entry per phase) of lists of node/edge ids to show; prefix an id with "!" to make an
            already visible element pulse. Default: everything in one phase.
    """
    objs = {}
    for nd in nodes:
        col, fill = COLORS[nd.get("color", "blue")]
        objs[nd["id"]] = box(nd["text"], w=nd.get("w", 2.8), h=nd.get("h", 1.1), size=nd.get("size", 28),
                             color=col, fill=fill).move_to([nd["at"][0], nd["at"][1], 0])
    for e in edges:
        a, b = objs[e["from"]], objs[e["to"]]
        col = COLORS[e.get("color", "grey")][0]
        start, end = _edge_points(a, b)
        ar = arrow(start, end, col, double=e.get("double", False))
        g = VGroup(ar)
        if e.get("label"):
            g.add(T(e["label"], 26, GREY).next_to(ar, UP if abs(end[1] - start[1]) < 0.5 else RIGHT, buff=0.12))
        objs[f'{e["from"]}>{e["to"]}'] = g
    head = _title(title) if title else None
    reveal = reveal or [[*[n["id"] for n in nodes], *[f'{e["from"]}>{e["to"]}' for e in edges]]]

    def phase(i):
        def run(t):
            anims = [FadeIn(head)] if (head and i == 0) else []
            for key in reveal[i]:
                if key.startswith("!"):
                    anims.append(Indicate(objs[key[1:]], color=YELLOW, scale_factor=1.1))
                elif ">" in key:
                    anims.append(GrowArrow(objs[key][0]))
                    anims += [FadeIn(m) for m in objs[key][1:]]
                else:
                    anims.append(FadeIn(objs[key], shift=UP * 0.15))
            t.play(*anims, rt=0.8)
        return run

    run_phases(steps, [phase(i) for i in range(len(reveal))])


def _edge_points(a, b):
    """Attach an arrow to the facing sides of two boxes."""
    ca, cb = a.get_center(), b.get_center()
    dx, dy = cb[0] - ca[0], cb[1] - ca[1]
    if abs(dx) * a.height >= abs(dy) * a.width:
        return (a.get_right(), b.get_left()) if dx > 0 else (a.get_left(), b.get_right())
    return (a.get_top(), b.get_bottom()) if dy > 0 else (a.get_bottom(), b.get_top())


# ---------------------------------------------------------------- original pages
@layout
def page_walkthrough(scene, steps, material, ref, marks, zoom=False):
    """An original PDF page on screen, with a highlight frame following the narration.

    ref: a page ref ("slides.pdf#p3").  marks: one entry per narration piece used - a lines spec
    (3, [3, 5], {"lines": [2, 4]}, "phrase") or None for no highlight during that piece.
    zoom: slow zoom on the page while talking (picture pages, section dividers).
    """
    from manim import ReplacementTransform, linear
    page = material.page(ref)
    if len(marks) != steps.left:
        raise ValueError(f"page_walkthrough: {len(marks)} marks for {steps.left} narration pieces")
    frame = None
    for k, spec in enumerate(marks):
        t = steps()
        if k == 0:
            t.play(FadeIn(page), rt=0.4)
        if spec is not None:
            new = page.mark(spec)
            t.play(Create(new) if frame is None else ReplacementTransform(frame, new), rt=0.5)
            frame = new
        elif frame is not None:
            t.play(FadeOut(frame), rt=0.3)
            frame = None
        if zoom and t.left > 0.2:
            group = Group(page, frame) if frame is not None else page
            t.play(group.animate.scale(1 + 0.006 * t.duration), rt=t.left, rate_func=linear)


LAYOUTS = {f.__name__: f for f in (title_card, bullets, statement, flow, mapping, compare, cards, diagram, encode,
                                   translate, number_base, page_walkthrough)}
