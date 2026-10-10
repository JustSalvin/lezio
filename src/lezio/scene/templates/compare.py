"""Comparing and reasoning: compare (side-by-side columns), misconception, analogy, example_nonexample."""
import numpy as np
from manim import (DOWN, LEFT, RIGHT, UP, UR, Circle, Create, FadeIn, GrowFromCenter, LaggedStart, Line, Text,
                   VGroup, Write)

from .. import style
from ..style import T, arrow, box, check, cross
from . import template
from .kit import panel, run_phases, text_box

FAMILIES = (("PRIMARY", "PRIMARY_SOFT"), ("SECONDARY", "SECONDARY_SOFT"), ("MUTED", "NEUTRAL_SOFT"))


@template(category="compare", use_for="two or three things side by side: before/after, A vs B, approaches, "
          "properties of each; the viewer sees them at the same time",
          example={"title": "Analogico o digitale", "args": {"columns": [
              {"title": "Analogico", "items": ["Valori continui", "Sensibile al rumore"], "verdict": "no"},
              {"title": "Digitale", "items": ["Valori discreti", "Robusto al rumore"], "verdict": "ok"}]},
                   "say": ["Il segnale analogico varia con continuità ed è sensibile al rumore.",
                           "Il digitale usa valori discreti e resiste al rumore.", "Per i calcolatori vince il digitale."]})
def compare(ctx, steps, columns: list[dict]):
    """2-3 columns side by side: [{"title", "items": [up to 5 short strings], "verdict": "ok" | "no" | null}].
    Phases: one per column, then the verdicts (if any)."""
    n = len(columns)
    w = (ctx.area.width - (n - 1) * 0.5) / n
    cols, marks = [], []
    for k, c in enumerate(columns):
        stroke, fill = (getattr(style, name) for name in FAMILIES[k % 3])
        head = box(c["title"], w=w, h=1.0, size=32, color=stroke, fill=fill)
        rows = VGroup(*[text_box(s, w - 0.3, style.TEXT_SIZE - 2) for s in c.get("items", [])])
        rows.arrange(DOWN, buff=0.3, aligned_edge=LEFT).next_to(head, DOWN, buff=0.45)
        cols.append(VGroup(head, rows))
        marks.append(c.get("verdict"))
    group = VGroup(*cols).arrange(RIGHT, buff=0.5, aligned_edge=DOWN * 0 + [0, 1, 0])
    ctx.place(group, at="top")
    verdicts = []
    for col, v in zip(cols, marks):
        if v in ("ok", "no"):
            verdicts.append((check() if v == "ok" else cross()).next_to(col, DOWN, buff=0.4))

    def side(col):
        def run(t):
            t.play(FadeIn(col[0]), rt=0.4)
            t.play(LaggedStart(*[FadeIn(r, shift=RIGHT * 0.2) for r in col[1]], lag_ratio=0.4), rt=1.0)
        return run

    phases = [side(c) for c in cols] + ([lambda t: t.play(*[Create(m) for m in verdicts], rt=0.6)] if verdicts else [])
    run_phases(steps, phases)


# ------------------------------------------------------------------ helpers
def _wrapped(text, width, size=None, color=None, bold=False):
    """Wrapped text (like text_box) whose glyphs are one submobject per visible character, so that its
    lines can be found (see _line_glyphs)."""
    probe = text_box(text, width, size, color, bold=bold)
    m = T(probe.original_text, size or style.TEXT_SIZE, color, bold=bold, disable_ligatures=True, line_spacing=0.9)
    return style.fit(m, width)


def _line_glyphs(mob):
    """The glyphs of each line of a text made by _wrapped (the whole text if they cannot be told apart)."""
    text, subs = mob.original_text, mob.submobjects
    if len(subs) == len(text):                       # one submobject per character, spaces included
        visible = [m for m, c in zip(subs, text) if not c.isspace()]
    elif len(subs) == len("".join(text.split())):    # one per visible character
        visible = list(subs)
    else:
        return [mob]
    groups, i = [], 0
    for line in text.split("\n"):
        n = len("".join(line.split()))
        groups.append(VGroup(*visible[i:i + n]))
        i += n
    return [g for g in groups if len(g)]


def _strike(glyphs, color):
    """A line through a line of text, at the height of its lowercase letters."""
    y = float(np.median([c.get_center()[1] for c in glyphs])) if len(glyphs) > 1 else glyphs.get_center()[1]
    return Line([glyphs.get_left()[0] - 0.08, y, 0], [glyphs.get_right()[0] + 0.08, y, 0], color=color,
                stroke_width=6)


_CAP = {}


def _cap_height(size, bold=False):
    """Height of the capital letters of the theme font at a size."""
    key = (style.FONT, bold)
    if key not in _CAP:
        _CAP[key] = T("H", 100, bold=bold).height / 100
    return _CAP[key] * size


def _card(content, width, stroke, fill, min_height=0.95, pad=0.3, size=None, bold=False):
    """A panel of the given width around content (centered), as tall as the content needs. With the size of
    a text content, the text is centered on its capital height, so that the cards of a row line up."""
    bg = panel(width, max(min_height, content.height + 2 * pad), stroke, fill)
    content.move_to(bg)
    lines = _line_glyphs(content) if size and isinstance(content, Text) else []
    if lines and lines[0] is not content:
        first, last = (float(np.median([c.get_bottom()[1] for c in g])) for g in (lines[0], lines[-1]))
        content.shift(UP * (bg.get_center()[1] - (first + _cap_height(size, bold) + last) / 2))
    return VGroup(bg, content)


def _badge(mark, stroke):
    """A ✓ or ✗ in a small disc, to pin on the corner of a card."""
    disc = Circle(radius=0.36, stroke_color=stroke, stroke_width=4, fill_color=style.BACKGROUND, fill_opacity=1)
    return VGroup(disc, mark.scale(0.62).move_to(disc))


def _place_readable(ctx, name, group, size=None, **kwargs):
    """ctx.place, but refuse a layout whose text would be shrunk below a readable size."""
    size = size or style.TEXT_SIZE
    natural = group.width
    ctx.place(group, **kwargs)
    scale = group.width / natural if natural else 1
    if size * scale < 24:
        raise ValueError(f"{name}: too much text for one screen (it would be shrunk to {scale:.0%}): shorten the "
                         "texts to a few words (the voice explains) or split them over two blocks")
    return group


def _pairs(name, pairs, what):
    """Check that pairs is a list of [a, b] texts."""
    if not pairs:
        raise ValueError(f"{name}: give at least one pair")
    for k, p in enumerate(pairs):
        if len(p) != 2 or not all(isinstance(x, str) and x.strip() for x in p):
            raise ValueError(f"{name}: pairs[{k}] must be [{what}] (two non-empty texts)")
    if len(pairs) > 6:
        raise ValueError(f"{name}: at most 6 pairs fit on one screen (got {len(pairs)}): split them over two blocks")


# ------------------------------------------------------------------ misconception
@template(category="compare", use_for="a common wrong idea the material touches: optionally a question to predict, "
          "the wrong idea stated plainly, then crossed out with why it fails, then the right idea",
          example={"title": "Più bit, più valori?",
                   "args": {"question": "Da 4 a 8 bit: quanti valori in più?",
                            "wrong": "Il doppio dei valori",
                            "why": "Ogni bit in più raddoppia i valori: 4 bit in più li raddoppiano 4 volte",
                            "right": "16 volte tanti: da 2⁴ = 16 a 2⁸ = 256"},
                   "say": [{"say": "Una domanda: se passo da quattro a otto bit, quanti valori in più posso scrivere?",
                            "pause": 3},
                           "Viene spontaneo pensare: il doppio, perché i bit sono raddoppiati.",
                           "Ma non funziona così: ogni bit in più raddoppia i valori, e qui i bit in più sono quattro.",
                           "Quindi i valori diventano sedici volte tanti: da sedici a duecentocinquantasei."]})
def misconception(ctx, steps, wrong: str, right: str, why: str | None = None, question: str | None = None):
    """Refuting a misconception, top to bottom: an optional question (the viewer predicts: put a "pause" on
    its piece); the wrong idea in a neutral card, stated plainly as people believe it; then it is crossed out
    (✗) and `why` it fails appears under it; then the right idea in a green card (✓).
    Keep the texts short (key words: the voice explains).
    Phases: question (if any), wrong idea, crossed out + why, right idea."""
    if not wrong.strip() or not right.strip():
        raise ValueError("misconception: 'wrong' and 'right' must not be empty")
    W = ctx.area.width
    wrong_t = _wrapped(wrong, W - 1.8, style.TEXT_SIZE, style.TEXT)
    right_t = _wrapped(right, W - 1.8, style.TEXT_SIZE, style.TEXT)
    cw = min(W - 0.6, max(wrong_t.width, right_t.width, 3.0) + 1.2)
    bad = _card(wrong_t, cw, style.MUTED, style.NEUTRAL_SOFT, 0.95, 0.25, style.TEXT_SIZE)
    good = _card(right_t, cw, style.POSITIVE, style.POSITIVE_SOFT, 0.95, 0.25, style.TEXT_SIZE)
    for card in (bad, good):
        card[1].align_to(card[0].get_left() + RIGHT * 0.5, LEFT)
    column = [bad]
    why_g = None
    if why:
        why_t = text_box(why, cw - 0.9, style.TEXT_SIZE - 4, style.TEXT)
        bar = Line(UP * why_t.height / 2, DOWN * why_t.height / 2, color=style.NEGATIVE, stroke_width=6)
        why_g = VGroup(bar, why_t.next_to(bar, RIGHT, buff=0.25))
        column.append(why_g)
    column.append(good)
    body = VGroup(*column).arrange(DOWN, buff=0.35, aligned_edge=LEFT)
    if why_g is not None:
        why_g.shift(RIGHT * 0.5)
    parts = [body]
    q = None
    if question:
        mark = T("?", 76, style.SECONDARY, bold=True)
        q = VGroup(mark, text_box(question, W - 1.3, 40, style.TEXT, bold=True)).arrange(RIGHT, buff=0.35)
        parts.insert(0, q)
    _place_readable(ctx, "misconception", VGroup(*parts).arrange(DOWN, buff=0.55), grow=1.25)
    strikes = VGroup(*[_strike(g, style.NEGATIVE) for g in _line_glyphs(wrong_t)])
    x_badge = _badge(cross(), style.NEGATIVE).move_to(bad[0].get_corner(UR) + [-0.1, -0.1, 0])
    v_badge = _badge(check(), style.POSITIVE).move_to(good[0].get_corner(UR) + [-0.1, -0.1, 0])

    def p_question(t):
        t.play(FadeIn(q[0], scale=0.6), FadeIn(q[1], shift=UP * 0.2), rt=0.7)

    def p_wrong(t):
        t.play(FadeIn(bad, shift=UP * 0.2), rt=0.7)

    def p_refute(t):
        t.play(Create(strikes, lag_ratio=0.5), wrong_t.animate.set_opacity(0.6),
               bad[0].animate.set_stroke(style.NEGATIVE, 4).set_fill(style.NEGATIVE_SOFT, 1), rt=0.9)
        t.play(GrowFromCenter(x_badge), rt=0.4)
        if why_g is not None:
            t.until(0.3)
            t.play(Create(why_g[0]), FadeIn(why_g[1], shift=UP * 0.15), rt=0.6)

    def p_right(t):
        t.play(FadeIn(good, shift=UP * 0.2), rt=0.7)
        t.play(GrowFromCenter(v_badge), rt=0.4)

    run_phases(steps, ([p_question] if q is not None else []) + [p_wrong, p_refute, p_right])


# ------------------------------------------------------------------ analogy
@template(category="compare", use_for="an analogy with something the viewer already knows: source and target side "
          "by side, corresponding parts linked row by row, then where the analogy stops working",
          example={"title": "La corrente come l'acqua",
                   "args": {"source": "Circuito idraulico", "target": "Circuito elettrico",
                            "pairs": [["Pompa", "Pila"], ["Acqua che scorre", "Corrente"],
                                      ["Pressione", "Tensione"], ["Tubo stretto", "Resistenza"]],
                            "limit": "Filo tagliato: la corrente non esce, si ferma"},
                   "say": ["Pensiamo a un circuito idraulico accanto a un circuito elettrico.",
                           "La pompa spinge l'acqua: è il ruolo della pila.",
                           "L'acqua che scorre corrisponde alla corrente.",
                           "La differenza di pressione è come la tensione.",
                           "E un tubo stretto frena l'acqua, proprio come una resistenza frena la corrente.",
                           "Attenzione però: se tagli un tubo l'acqua esce, se tagli un filo la corrente si ferma."]})
def analogy(ctx, steps, source: str, target: str, pairs: list[list[str]], limit: str | None = None):
    """An analogy: the familiar source (left) and the target being taught (right) side by side; pairs
    [[source part, target part], ...] (up to 6) appear as aligned rows linked by a double arrow, the current
    link highlighted; `limit` (optional) says where the analogy stops working (✗ card at the bottom).
    Keep each part to a few words (the voice explains).
    Phases: the two sides, one per pair, the limit."""
    _pairs("analogy", pairs, "source part, target part")
    W = ctx.area.width
    link_w = 1.3
    cw = (W - link_w) / 2

    def head(text, color):
        label = text_box(text, cw - 0.2, 40, color, bold=True)
        rule = Line(LEFT * cw / 2, RIGHT * cw / 2, color=color, stroke_width=5)
        return VGroup(label, rule).arrange(DOWN, buff=0.18)

    hs, ht = head(source, style.SECONDARY), head(target, style.PRIMARY)
    ht.next_to(hs, RIGHT, buff=link_w).align_to(hs, DOWN)
    heads = VGroup(hs, ht)
    rows = []
    for s, t_ in pairs:
        ls = text_box(s, cw - 0.6, style.TEXT_SIZE, style.TEXT)
        rt_ = text_box(t_, cw - 0.6, style.TEXT_SIZE, style.TEXT)
        h = max(ls.height, rt_.height) + 0.3
        lc = _card(ls, cw, style.SECONDARY, style.SECONDARY_SOFT, max(h, 0.8), 0.15, style.TEXT_SIZE)
        rc = _card(rt_, cw, style.PRIMARY, style.PRIMARY_SOFT, max(h, 0.8), 0.15, style.TEXT_SIZE)
        rc.next_to(lc, RIGHT, buff=link_w)
        rows.append(VGroup(lc, rc))
    table = VGroup(*rows).arrange(DOWN, buff=0.2)
    parts = [heads, table]
    lim = None
    if limit:
        lim_t = text_box(limit, W - 2.0, style.TEXT_SIZE, style.TEXT)
        lim_c = VGroup(cross().scale(0.6), lim_t).arrange(RIGHT, buff=0.35)
        lim = _card(lim_c, min(W, lim_c.width + 0.8), style.NEGATIVE, style.NEGATIVE_SOFT, 0.8, 0.18)
        parts.append(lim)
    whole = VGroup(*parts).arrange(DOWN, buff=0.3)
    if lim is not None:
        lim.shift(DOWN * 0.1)
    _place_readable(ctx, "analogy", whole, grow=1.25)
    links = [arrow(r[0].get_right(), r[1].get_left(), style.HIGHLIGHT, double=True) for r in rows]

    def p_heads(t):
        t.play(FadeIn(hs, shift=DOWN * 0.15), rt=0.6)
        t.play(FadeIn(ht, shift=DOWN * 0.15), rt=0.6)

    def p_pair(i):
        def run(t):
            older = [rows[k] for k in range(i)]
            t.play(FadeIn(rows[i][0], shift=RIGHT * 0.2), *[r.animate.set_opacity(0.6) for r in older],
                   *[links[k].animate.set_color(style.MUTED) for k in range(i)], rt=0.6)
            t.until(0.3)
            t.play(GrowFromCenter(links[i]), FadeIn(rows[i][1], shift=LEFT * 0.2), rt=0.7)
        return run

    def p_limit(t):
        t.play(*[r.animate.set_opacity(0.6) for r in rows], links[-1].animate.set_color(style.MUTED),
               FadeIn(lim, shift=UP * 0.2), rt=0.8)

    run_phases(steps, [p_heads] + [p_pair(i) for i in range(len(rows))] + ([p_limit] if lim is not None else []))


# ------------------------------------------------------------------ examples and non-examples
@template(category="compare", use_for="a concept taught by contrast: examples paired with non-examples that differ "
          "only in the critical feature, then the feature stated",
          example={"args": {"concept": "Numero primo",
                            "pairs": [["7   divisori: 1, 7", "9   divisori: 1, 3, 9"],
                                      ["13   divisori: 1, 13", "15   divisori: 1, 3, 5, 15"],
                                      ["2   divisori: 1, 2", "1   divisori: 1"]],
                            "feature": "Esattamente due divisori: 1 e sé stesso"},
                   "say": ["Che cosa rende primo un numero? Confrontiamo esempi e controesempi.",
                           "Sette è primo: si divide solo per uno e per sette. Nove no: si divide anche per tre.",
                           "Tredici è primo, quindici no: lo dividono anche tre e cinque.",
                           "Due è primo, anche se è pari. Uno invece non lo è: ha un solo divisore.",
                           "Ecco la caratteristica decisiva: esattamente due divisori, uno e il numero stesso."]})
def example_nonexample(ctx, steps, concept: str, pairs: list[list[str]], feature: str | None = None):
    """A concept with pairs [[example, non-example], ...] (up to 6) side by side under ✓ and ✗, one pair per
    phase (the example, then the non-example); each pair should differ only in the critical feature, which
    `feature` (optional) states at the end in a highlighted card. Keep each text to a few words.
    Phases: the concept, one per pair, the feature."""
    _pairs("example_nonexample", pairs, "example, non-example")
    W = ctx.area.width
    gap = 0.6
    cw = (W - gap) / 2
    title = text_box(concept, W - 1, 48, style.PRIMARY, bold=True)
    rows = []
    for ex, non in pairs:
        a = text_box(ex, cw - 0.6, style.TEXT_SIZE, style.TEXT)
        b = text_box(non, cw - 0.6, style.TEXT_SIZE, style.TEXT)
        h = max(a.height, b.height) + 0.3
        ca = _card(a, cw, style.POSITIVE, style.POSITIVE_SOFT, max(h, 0.8), 0.15, style.TEXT_SIZE)
        cb = _card(b, cw, style.NEGATIVE, style.NEGATIVE_SOFT, max(h, 0.8), 0.15, style.TEXT_SIZE)
        cb.next_to(ca, RIGHT, buff=gap)
        rows.append(VGroup(ca, cb))
    table = VGroup(*rows).arrange(DOWN, buff=0.22)
    marks = VGroup(check().scale(0.8).next_to(rows[0][0], UP, buff=0.3),
                   cross().scale(0.8).next_to(rows[0][1], UP, buff=0.3))
    top = VGroup(title, VGroup(marks, table)).arrange(DOWN, buff=0.35)
    parts = [top]
    feat = None
    if feature:
        ft = text_box(feature, W - 1.2, style.TEXT_SIZE, style.TEXT, bold=True)
        feat = _card(ft, min(W, ft.width + 1.0), style.HIGHLIGHT, style.HIGHLIGHT_SOFT, 0.95, 0.3, style.TEXT_SIZE,
                     bold=True)
        feat[0].set_stroke(width=5)
        parts.append(feat)
    _place_readable(ctx, "example_nonexample", VGroup(*parts).arrange(DOWN, buff=0.45), grow=1.25)

    def p_concept(t):
        t.play(Write(title), rt=0.8)
        t.play(Create(marks[0]), Create(marks[1]), rt=0.5)

    def p_pair(i):
        def run(t):
            t.play(FadeIn(rows[i][0], shift=RIGHT * 0.2), *[rows[k].animate.set_opacity(0.55) for k in range(i)],
                   rt=0.6)
            t.until(0.4)
            t.play(FadeIn(rows[i][1], shift=LEFT * 0.2), rt=0.6)
        return run

    def p_feature(t):
        t.play(*[r.animate.set_opacity(1) for r in rows], FadeIn(feat, scale=0.95), rt=0.8)

    run_phases(steps, [p_concept] + [p_pair(i) for i in range(len(rows))] + ([p_feature] if feat is not None else []))
