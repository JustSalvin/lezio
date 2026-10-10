# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Computing: encode (symbols -> codes), translate (source -> transformation -> result), array (cells and an
algorithm on them, step by step), code (a listing explained line by line)."""
import textwrap

from manim import (DOWN, LEFT, PI, RIGHT, UP, Arrow, Brace, Circle, Create, FadeIn, FadeOut, GrowArrow,
                   GrowFromCenter, LaggedStart, Line, MarkupText, Rectangle, RoundedRectangle, Transform, VGroup,
                   Write)

from .. import style
from ..style import T, arrow, box
from . import template
from .kit import run_phases, text_box, dim_to


def _code_mobject(code):
    """Morse-like codes made of '.' and '-' are drawn as dots and dashes; anything else as monospaced text."""
    if set(code) <= set(".-·—– "):
        g = VGroup()
        for c in code.replace(" ", ""):
            if c in "-—–":
                g.add(RoundedRectangle(width=0.75, height=0.24, corner_radius=0.1, fill_color=style.TEXT,
                                       fill_opacity=1, stroke_width=0))
            else:
                g.add(Circle(radius=0.13, fill_color=style.TEXT, fill_opacity=1, stroke_width=0))
        return g.arrange(RIGHT, buff=0.22)
    return T(code, 60, style.TEXT, bold=True, font=style.MONO)


@template(category="cs", use_for="encoding and decoding: symbols turned into codes (binary, ASCII, Morse) and back",
          example={"args": {"items": [["A", "01000001"], ["B", "01000010"]], "encode_label": "codifica",
                            "decode_label": "decodifica"},
                   "say": ["Ogni carattere diventa una sequenza di bit.", "E dalla sequenza si torna al carattere."]})
def encode(ctx, steps, items: list[list[str]], encode_label: str, decode_label: str | None = None):
    """Symbols -> codes, and optionally codes -> symbols again. items: 1-4 [symbol, code] pairs; codes made
    only of "." and "-" are drawn as Morse dots and dashes. Phases: encode, decode."""
    n = len(items)
    rows = []
    for s, c in items:
        sym = T(s, 84, style.PRIMARY, bold=True)
        code = _code_mobject(c)
        back = T(s, 84, style.SECONDARY, bold=True)
        rows.append(VGroup(sym, code, back))
    gap = 3.3
    for r in rows:
        r[1].move_to(r[0].get_center() + RIGHT * gap + RIGHT * r[1].width / 2)
        r[2].move_to(r[1].get_right() + RIGHT * gap)
    table = VGroup(*rows).arrange(DOWN, buff=0.7, aligned_edge=LEFT)
    labels = VGroup(T(encode_label, 30, style.PRIMARY), T(decode_label or "", 30, style.SECONDARY))
    ctx.place(VGroup(table, labels))
    labels[0].next_to(table, UP, buff=0.4).set_x((rows[0][0].get_x() + rows[0][1].get_left()[0]) / 2)
    labels[1].next_to(table, UP, buff=0.4).set_x((rows[0][1].get_right()[0] + rows[0][2].get_x()) / 2)

    def enc(t):
        t.play(*[FadeIn(r[0]) for r in rows], FadeIn(labels[0]), rt=0.6)
        for r in rows:
            t.play(GrowArrow(arrow(r[0].get_right(), r[1].get_left(), style.PRIMARY)),
                   LaggedStart(*[GrowFromCenter(x) for x in r[1]], lag_ratio=0.15), rt=0.9)

    def dec(t):
        t.play(FadeIn(labels[1]), rt=0.4)
        for r in rows:
            t.play(GrowArrow(arrow(r[1].get_right(), r[2].get_left(), style.SECONDARY)), FadeIn(r[2]), rt=0.7)

    run_phases(steps, [enc, dec] if decode_label else [enc])


@template(category="cs", use_for="a transformation: source -> translator/process -> result (compiling, "
          "converting, encrypting, any input-process-output)",
          example={"args": {"source": "a = b + c", "via": "compilatore", "result": "ADD R1, R2, R3",
                            "result_brace": "linguaggio macchina"},
                   "say": ["Partiamo da un'istruzione ad alto livello.", "Il compilatore la traduce,",
                           "in un'istruzione in linguaggio macchina."]})
def translate(ctx, steps, source: str, via: str, result: str, source_note: str | None = None,
              source_brace: str | None = None, result_brace: str | None = None):
    """Source (monospaced) -> a box for the process -> result (monospaced), top to bottom; optional note
    under the source and labelled braces. Phases: source, transformation, braces."""
    src = T(source, 64, style.PRIMARY, font=style.MONO)
    note = T(source_note, 30, style.MUTED) if source_note else None
    mid = box(via, w=3.8)
    res = T(result, 44, style.TEXT, font=style.MONO)
    parts = [src] + ([note] if note else []) + [mid, res]
    ctx.place(VGroup(*parts).arrange(DOWN, buff=0.7))

    def p_source(t):
        t.play(Write(src), rt=0.9)
        if note:
            t.play(FadeIn(note), rt=0.4)

    def p_translate(t):
        t.play(GrowArrow(arrow((note or src).get_bottom(), mid.get_top())), FadeIn(mid), rt=0.6)
        t.play(GrowArrow(arrow(mid.get_bottom(), res.get_top())), rt=0.4)
        t.play(Write(res), rt=1.4)

    def p_braces(t):
        anims = []
        if result_brace:
            b = Brace(res, DOWN, color=style.SECONDARY)
            anims += [GrowFromCenter(b), FadeIn(T(result_brace, 30, style.SECONDARY, bold=True).next_to(b, DOWN, buff=0.1))]
        if source_brace:
            b = Brace(src, UP, color=style.PRIMARY)
            anims += [GrowFromCenter(b), FadeIn(T(source_brace, 28, style.PRIMARY, bold=True).next_to(b, UP, buff=0.1))]
        t.play(*anims, rt=0.7)

    run_phases(steps, [p_source, p_translate] + ([p_braces] if source_brace or result_brace else []))


# ------------------------------------------------------------------ array
_STATE_KEYS = ("highlight", "pointers", "set", "swap", "done", "dim", "note")


def _check_states(states, n):
    """Validate the states of an array; returns them with integer indexes."""
    def index(v, where):
        if isinstance(v, str) and v.strip().lstrip("-").isdigit():
            v = int(v)
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < n:
            raise ValueError(f"array: {where}: {v!r} is not a cell index (0 to {n - 1})")
        return v

    def indexes(v, where):
        if not isinstance(v, list):
            raise ValueError(f"array: {where} must be a list of cell indexes")
        return [index(x, where) for x in v]

    out = []
    for j, s in enumerate(states):
        w = f"states[{j}]"
        if not isinstance(s, dict):
            raise ValueError(f"array: {w} must be an object like {{\"highlight\": [2], \"note\": \"...\"}}")
        unknown = [k for k in s if k not in _STATE_KEYS]
        if unknown:
            raise ValueError(f"array: {w} has unknown keys {unknown} (allowed: {', '.join(_STATE_KEYS)})")
        c = {"highlight": indexes(s.get("highlight", []), f"{w}.highlight"),
             "done": indexes(s.get("done", []), f"{w}.done"), "dim": indexes(s.get("dim", []), f"{w}.dim"),
             "note": s.get("note"), "pointers": {}, "set": {}, "swap": None}
        if c["note"] is not None and not isinstance(c["note"], str):
            raise ValueError(f"array: {w}.note must be a text")
        ptrs = s.get("pointers", {})
        if not isinstance(ptrs, dict):
            raise ValueError(f"array: {w}.pointers must be an object {{\"name\": index or null}}")
        for name, v in ptrs.items():
            c["pointers"][str(name)] = None if v is None else index(v, f"{w}.pointers.{name}")
        sets = s.get("set", {})
        if not isinstance(sets, dict):
            raise ValueError(f"array: {w}.set must be an object {{\"index\": \"new value\"}}")
        for k, v in sets.items():
            c["set"][index(k, f"{w}.set")] = str(v)
        if s.get("swap") is not None:
            sw = indexes(s["swap"], f"{w}.swap")
            if len(sw) != 2 or sw[0] == sw[1]:
                raise ValueError(f"array: {w}.swap must be two different indexes [a, b]")
            c["swap"] = sw
        out.append(c)
    return out


@template(category="cs", use_for="an array, a memory, a row of bits or registers, and an algorithm on it step by "
          "step (searching, sorting, two pointers): highlights, named pointers, swaps and new values per piece",
          example={"title": "Ordinamento per selezione",
                   "args": {"cells": ["29", "10", "14", "37", "13"], "label": "A",
                            "states": [{"pointers": {"i": 0, "min": 0}, "highlight": [0],
                                        "note": "Cerco il minimo da i in poi"},
                                       {"pointers": {"min": 1}, "highlight": [1], "note": "10 < 29: nuovo minimo"},
                                       {"swap": [0, 1], "done": [0], "pointers": {"min": None},
                                        "note": "Scambio: 10 va al primo posto"},
                                       {"pointers": {"i": 1, "min": 4}, "highlight": [4],
                                        "note": "Il minimo del resto è 13"},
                                       {"swap": [1, 4], "done": [1], "pointers": {"min": None},
                                        "note": "Scambio: 13 va al secondo posto"}]},
                   "say": ["Ecco un array di cinque numeri da ordinare con l'ordinamento per selezione.",
                           "Partiamo dalla prima posizione e cerchiamo il valore più piccolo da lì in avanti.",
                           "Dieci è più piccolo di ventinove: diventa il nuovo minimo.",
                           "Nessun altro è più piccolo, quindi scambiamo il dieci con il primo elemento.",
                           "Ripartiamo dalla seconda posizione: il minimo del resto è tredici.",
                           "Lo scambiamo con il ventinove, e anche il secondo posto è sistemato."]})
def array(ctx, steps, cells: list[str], states: list[dict] | None = None, label: str | None = None,
          indexes: list[str] | None = None):
    """A row of cells (an array, memory, bits, registers; up to 20, best up to 12) with index labels under
    them (indexes: custom labels such as addresses, [] for none; default 0, 1, 2, ...) and an optional
    name on the left. Each state (one per phase) changes the picture:
      "highlight": [2, 3]        cells in focus in this state (cleared at the next state)
      "pointers": {"i": 0, "j": 4}  named arrows above cells; they stay until moved; null removes one
      "swap": [1, 4]             the two values change places (animated)
      "set": {"3": "x"}          new values for some cells
      "done": [0]                cells marked as settled (green; they stay)
      "dim": [5, 6]              cells set aside (grayed; they stay), e.g. the half discarded by a search
      "note": "short text"       a line under the array for this state
    Phases: the array, then one per state."""
    n = len(cells)
    if not 1 <= n <= 20:
        raise ValueError(f"array: {n} cells; use 1 to 20 (split a longer memory or show a part of it)")
    states = _check_states(states or [], n)
    if indexes is None:
        indexes = [str(k) for k in range(n)]
    elif indexes and len(indexes) != n:
        raise ValueError(f"array: {len(indexes)} index labels for {n} cells (give one per cell, or [] for none)")
    W = ctx.area.width
    size = style.TEXT_SIZE

    def value(text):                                       # values stay above the cells they move over
        return T(str(text), size, style.TEXT, bold=True, font=style.MONO).set_z_index(1)

    all_values = [str(c) for c in cells] + [v for s in states for v in s["set"].values()]
    widest = max(value(v).width for v in all_values)
    cw, ch = max(0.95, widest + 0.4), 1.0
    boxes = VGroup(*[RoundedRectangle(width=cw, height=ch, corner_radius=0.08, stroke_color=style.PRIMARY,
                                      stroke_width=3, fill_color=style.PRIMARY_SOFT, fill_opacity=1)
                     for _ in range(n)]).arrange(RIGHT, buff=0.1)
    values = [value(c).move_to(b) for c, b in zip(cells, boxes)]
    idx = VGroup(*[T(s, style.SMALL_SIZE, style.MUTED, font=style.MONO).next_to(b, DOWN, buff=0.18)
                   for s, b in zip(indexes, boxes)]) if indexes else VGroup()
    parts = [boxes, *values, idx]
    names = list(dict.fromkeys(name for s in states for name in s["pointers"]))
    zone = None
    if names:
        probe = T(max(names, key=len), 40, style.SECONDARY, bold=True, font=style.MONO)
        zone = Rectangle(width=boxes.width, height=probe.height + 0.75, stroke_opacity=0, fill_opacity=0)
        zone.next_to(boxes, UP, buff=0.05)
        parts.append(zone)
    name_m = None
    if label:
        name_m = text_box(label, 3.0, size, style.PRIMARY, bold=True).next_to(boxes, LEFT, buff=0.45)
        parts.append(name_m)
    core = VGroup(*parts)
    notes = [text_box(s["note"], W - 0.8, size, style.TEXT) if s["note"] else None for s in states]
    note_h = max([m.height for m in notes if m is not None], default=0)
    gap = 0.5 if note_h else 0
    natural = core.width
    ctx.place(core, height=ctx.area.height - note_h - gap, grow=1.5)
    k = core.width / natural
    if size * k < 20:
        raise ValueError(f"array: the cells do not fit at a readable size (shrunk to {k:.0%}): use fewer cells "
                         "or shorter values")
    top = ctx.area.center[1] + (core.height + gap + note_h) / 2
    core.shift(UP * (top - core.get_top()[1]))
    for m in notes:
        if m is not None:
            m.move_to([ctx.area.center[0], core.get_bottom()[1] - gap - m.height / 2, 0])

    pointers = {}                                          # name -> (index, mobject) on screen

    psize = max(34, 26 / k)                                # pointer names stay readable when the row shrinks

    def pointer_mob(name, x, cell):
        lab = T(name, psize, style.SECONDARY, bold=True, font=style.MONO).scale(k)
        lab.move_to([x, cell.get_top()[1] + 0.75 * k + lab.height / 2, 0])
        tip = [cell.get_center()[0] + (x - cell.get_center()[0]) * 0.3, cell.get_top()[1] + 0.04, 0]
        return VGroup(lab, Arrow(lab.get_bottom(), tip, buff=0.08, color=style.SECONDARY, stroke_width=5,
                                 max_tip_length_to_length_ratio=0.35))

    def pointer_targets(where):
        """name -> mobject at its place, pointers on the same cell side by side."""
        out = {}
        for i in sorted(set(where.values())):
            group = [nm for nm in where if where[nm] == i]
            widths = [T(nm, psize, font=style.MONO, bold=True).width * k for nm in group]
            total = sum(widths) + 0.25 * k * (len(group) - 1)
            x = boxes[i].get_center()[0] - total / 2
            for nm, w in zip(group, widths):
                out[nm] = pointer_mob(nm, x + w / 2, boxes[i])
                x += w + 0.25 * k
        return out

    marks = {"done": set(), "dim": set()}

    def restyle(highlight):
        anims = []
        for i, b in enumerate(boxes):
            if i in highlight:
                stroke, fill, width, op = style.HIGHLIGHT, style.HIGHLIGHT_SOFT, 6, 1
            elif i in marks["done"]:
                stroke, fill, width, op = style.POSITIVE, style.POSITIVE_SOFT, 3, 1
            elif i in marks["dim"]:
                stroke, fill, width, op = style.MUTED, style.NEUTRAL_SOFT, 2, 0.35
            else:
                stroke, fill, width, op = style.PRIMARY, style.PRIMARY_SOFT, 3, 1
            anims.append(b.animate.set_stroke(stroke, width, opacity=1).set_fill(fill, 1))
            anims.append(values[i].animate.set_opacity(op))
        return anims

    shown = {"note": None}

    def p_show(t):
        anims = [LaggedStart(*[FadeIn(VGroup(b, v), shift=UP * 0.15) for b, v in zip(boxes, values)],
                             lag_ratio=0.08)]
        if len(idx):
            anims.append(FadeIn(idx))
        if name_m is not None:
            anims.append(FadeIn(name_m))
        t.play(*anims, rt=0.9)

    def p_state(j):
        s = states[j]

        def run(t):
            marks["dim"] |= set(s["dim"])
            where = {nm: i for nm, (i, _) in pointers.items()}
            for nm, i in s["pointers"].items():
                if i is None:
                    where.pop(nm, None)
                else:
                    where[nm] = i
            targets = pointer_targets(where)
            anims = restyle(s["highlight"])
            for nm in list(pointers):
                if nm not in targets:
                    anims.append(FadeOut(pointers.pop(nm)[1]))
            for nm, mob in targets.items():
                if nm in pointers:
                    anims.append(Transform(pointers[nm][1], mob))
                    pointers[nm] = (where[nm], pointers[nm][1])
                else:
                    anims.append(FadeIn(mob, shift=DOWN * 0.2))
                    pointers[nm] = (where[nm], mob)
            if shown["note"] is not None:
                anims.append(FadeOut(shown["note"]))
                shown["note"] = None
            t.play(*anims, rt=0.6)
            if s["swap"]:
                a, b = s["swap"]
                t.play(values[a].animate(path_arc=-PI / 2).move_to(boxes[b]),
                       values[b].animate(path_arc=-PI / 2).move_to(boxes[a]), rt=0.9)
                values[a], values[b] = values[b], values[a]
            if s["set"]:
                anims = []
                for i, v in s["set"].items():
                    new = value(v).scale(k).move_to(boxes[i]).set_opacity(values[i].get_fill_opacity())
                    anims += [FadeOut(values[i], shift=UP * 0.3), FadeIn(new, shift=UP * 0.3)]
                    values[i] = new
                t.play(*anims, rt=0.6)
            anims = []
            if s["done"]:
                marks["done"] |= set(s["done"])
                anims += restyle(s["highlight"])
            if notes[j] is not None:
                anims.append(FadeIn(notes[j], shift=UP * 0.15))
                shown["note"] = notes[j]
            if anims:
                t.play(*anims, rt=0.5)
        return run

    run_phases(steps, [p_show] + [p_state(j) for j in range(len(states))])


# ------------------------------------------------------------------ code
def _token_style(ttype):
    """(color, bold) of a Pygments token type in the active theme."""
    from pygments.token import Comment, Keyword, Name, Number, String
    if ttype in Comment:
        return style.MUTED, False
    if ttype in Keyword or ttype in Name.Builtin:
        return style.PRIMARY, True
    if ttype in String:
        return style.POSITIVE, False
    if ttype in Number:
        return style.SECONDARY, False
    if ttype in Name.Function or ttype in Name.Class:
        return style.SECONDARY, True
    return style.TEXT, False


def _code_markup(lines, language):
    """Pango markup of each line, colored by token type (plain if the language is unknown to Pygments)."""
    from html import escape
    from pygments.lexers import TextLexer, get_lexer_by_name
    from pygments.util import ClassNotFound
    if language.strip().lower() in ("", "text", "plain", "pseudocode", "pseudo", "none"):
        lexer = TextLexer()
    else:
        try:
            lexer = get_lexer_by_name(language.strip().lower(), stripnl=False, ensurenl=False)
        except ClassNotFound:
            raise ValueError(f"code: unknown language '{language}' (e.g. python, c, cpp, java, javascript, "
                             "sql, bash, or \"text\" for pseudocode)") from None
    out = [[]]
    for ttype, value in lexer.get_tokens("\n".join(lines)):
        color, bold = _token_style(ttype)
        for k, piece in enumerate(value.split("\n")):
            if k:
                out.append([])
            if piece:
                weight = ' font_weight="bold"' if bold else ""
                out[-1].append(f'<span foreground="{color}"{weight}>{escape(piece, quote=False)}</span>')
    if len(out) != len(lines):
        return [escape(line, quote=False) for line in lines]
    return ["".join(parts) for parts in out]


@template(category="cs", use_for="a piece of code or pseudocode explained line by line: the listing, then the "
          "lines being discussed highlighted, with an optional note for each step",
          example={"title": "Il massimo di una lista",
                   "args": {"code": "def massimo(lista):\n    m = lista[0]\n    for x in lista[1:]:\n"
                                    "        if x > m:\n            m = x\n    return m",
                            "language": "python", "highlights": [[1], [2], [3, 4, 5], [6]],
                            "notes": ["Riceve una lista", "Primo candidato", "Uno più grande lo sostituisce",
                                      "Il risultato"]},
                   "say": ["Ecco una funzione che trova il valore più grande di una lista.",
                           "La prima riga la dichiara: riceve una lista.",
                           "Come primo candidato prendiamo il primo elemento.",
                           "Poi scorriamo gli altri: se uno è più grande, diventa il nuovo candidato.",
                           "Alla fine restituiamo il candidato: è il massimo."]})
def code(ctx, steps, code: str, language: str = "python", highlights: list[list[int]] | None = None,
         notes: list[str | None] | None = None):
    """A code listing with line numbers and syntax colors (language: a Pygments name such as python, c, java,
    javascript, sql, bash; "text" for pseudocode). About 12 lines of 60 characters fit at a readable size.
    highlights: one entry per phase after the first, the line numbers (1-based) to highlight (the other
    lines are dimmed; [] shows all lines plainly). notes (optional, one per highlight, may be null): a
    short label shown beside the highlighted lines.
    Phases: the listing, then one per highlights entry."""
    lines = [line.rstrip() for line in textwrap.dedent(code.expandtabs(4)).strip("\n").split("\n")]
    n = len(lines)
    if not code.strip():
        raise ValueError("code: the code is empty")
    if n > 40:
        raise ValueError(f"code: {n} lines; show only the relevant part (about 12 lines)")
    highlights = highlights or []
    for j, h in enumerate(highlights):
        bad = [x for x in h if not 1 <= x <= n]
        if bad:
            raise ValueError(f"code: highlights[{j}] has line numbers {bad} outside 1..{n}")
    if notes is not None and len(notes) > len(highlights):
        raise ValueError(f"code: {len(notes)} notes for {len(highlights)} highlights (one note per highlight)")
    notes = [x if isinstance(x, str) and x.strip() else None for x in (notes or [])]
    notes += [None] * (len(highlights) - len(notes))
    has_notes = any(notes)

    size = 32
    markup = _code_markup(lines, language)
    probe = MarkupText("│", font=style.MONO, font_size=size)
    pitch = probe.height * 1.2
    rows, nums = [], []
    for k, m in enumerate(markup):
        y = -k * pitch
        line = MarkupText("│" + m, font=style.MONO, font_size=size, color=style.TEXT)
        line.shift([-line[0].get_center()[0], y - line[0].get_center()[1], 0])
        line[0].set_opacity(0)              # the "│" only fixes the line height: invisible, not removed
        rows.append(line if len(line) > 1 else None)
        num = MarkupText("│" + str(k + 1), font=style.MONO, font_size=size, color=style.MUTED)
        num.shift([0, y - num[0].get_center()[1], 0])
        num[0].set_opacity(0)
        nums.append(num.shift(RIGHT * (-0.45 - num.get_right()[0])))
    text_w = max([r.get_right()[0] for r in rows if r is not None], default=0.5)
    left = min(m.get_left()[0] for m in nums) - 0.3
    right = max(text_w, 3.0) + 0.4
    top, bottom = pitch / 2 + 0.2, -(n - 1) * pitch - pitch / 2 - 0.2
    bg = RoundedRectangle(width=right - left, height=top - bottom, corner_radius=0.15, stroke_color=style.MUTED,
                          stroke_width=2, fill_color=style.NEUTRAL_SOFT, fill_opacity=1)
    bg.move_to([(left + right) / 2, (top + bottom) / 2, 0])
    rule = Line([-0.22, top - 0.1, 0], [-0.22, bottom + 0.1, 0], color=style.MUTED, stroke_width=1.5,
                stroke_opacity=0.6)
    bars = VGroup(*[Rectangle(width=right - 0.04 + 0.12, height=pitch, stroke_width=0, fill_color=style.HIGHLIGHT_SOFT,
                              fill_opacity=0).move_to([(-0.12 + right - 0.04) / 2, -k * pitch, 0])
                    for k in range(n)])
    stripes = VGroup(*[Rectangle(width=0.08, height=pitch, stroke_width=0, fill_color=style.HIGHLIGHT,
                                 fill_opacity=0).move_to([-0.12, -k * pitch, 0]) for k in range(n)])
    text = VGroup(*[r for r in rows if r is not None])
    listing = VGroup(bg, rule, bars, stripes, VGroup(*nums), text)
    W = ctx.area.width
    note_size = style.TEXT_SIZE - 4
    note_w = min(4.5, max([T(x, note_size).width + 0.1 for x in notes if x] or [0])) if has_notes else 0
    note_w = max(note_w, 2.5) if has_notes else 0
    natural = listing.height
    ctx.place(listing, width=W - note_w - (0.6 if has_notes else 0), grow=1.3)
    if size * listing.height / natural < 20:
        longest = max(len(line) for line in lines)
        raise ValueError(f"code: {n} lines, the longest of {longest} characters, do not fit at a readable size "
                         f"(shrunk to {listing.height / natural:.0%}): show about 12 lines of up to 60 characters "
                         "(keep the relevant part, shorten names, split it over two blocks)")
    if has_notes:                          # listing and notes centered together
        listing.set_x(ctx.area.center[0] - (note_w + 0.6) / 2 + (W - note_w - 0.6 - listing.width) / 2)
    note_mobs = []
    for j, note in enumerate(notes):
        if note is None or not highlights[j]:
            note_mobs.append(None)
            continue
        m = text_box(note, note_w, note_size, style.TEXT)
        lines_y = [bars[x - 1].get_center()[1] for x in highlights[j]]
        y = (max(lines_y) + min(lines_y)) / 2
        y = min(max(y, ctx.area.bottom + m.height / 2), ctx.area.top - m.height / 2)
        m.move_to([bg.get_right()[0] + 0.55 + m.width / 2, y, 0])
        link = Line([bg.get_right()[0] - 0.05, y, 0], [m.get_left()[0] - 0.12, y, 0], color=style.HIGHLIGHT,
                    stroke_width=5)
        note_mobs.append(VGroup(link, m))

    def p_show(t):
        t.play(FadeIn(bg), FadeIn(rule), rt=0.4)
        ctx.scene.add(bars, stripes)          # transparent until highlighted, behind the text
        t.play(LaggedStart(*[FadeIn(VGroup(nm, *([r] if r is not None else [])), shift=RIGHT * 0.1)
                             for nm, r in zip(nums, rows)], lag_ratio=0.12), rt=min(1.6, 0.25 + 0.1 * n))

    shown = {"note": None}

    def p_high(j):
        def run(t):
            on = set(highlights[j])
            anims = []
            for x in range(n):
                lit = x + 1 in on
                op = 1 if (lit or not on) else 0.35
                anims.append(bars[x].animate.set_fill(opacity=1 if lit else 0))
                anims.append(stripes[x].animate.set_fill(opacity=1 if lit else 0))
                anims.append(dim_to(nums[x], op))
                if rows[x] is not None:
                    anims.append(dim_to(rows[x], op))
            if shown["note"] is not None:
                anims.append(FadeOut(shown["note"]))
                shown["note"] = None
            t.play(*anims, rt=0.6)
            if note_mobs[j] is not None:
                t.play(Create(note_mobs[j][0]), FadeIn(note_mobs[j][1], shift=LEFT * 0.15), rt=0.5)
                shown["note"] = note_mobs[j]
        return run

    run_phases(steps, [p_show] + [p_high(j) for j in range(len(highlights))])
