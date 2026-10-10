"""Math, worked examples, tables: number_base, derivation, worked_example, number_line, table."""
import html
import re
from typing import Literal

from manim import (DOWN, LEFT, RIGHT, UP, Circle, Create, DashedLine, Dot, FadeIn, FadeOut, GrowFromCenter,
                   Indicate, LaggedStart, Line, Rectangle, RoundedRectangle, VGroup, Write)

from ...config import CONFIG
from .. import style
from ..style import MT, T, arrow
from . import template
from .kit import focus_anims, frame, run_phases, text_box


# ------------------------------------------------------------------ shared helpers (also used by data.py)
COMMA_LANGUAGES = {"italian", "german", "french", "spanish", "portuguese", "dutch", "russian", "polish", "czech",
                   "slovak", "slovenian", "croatian", "serbian", "romanian", "hungarian", "turkish", "greek",
                   "swedish", "danish", "norwegian", "finnish", "ukrainian", "catalan", "indonesian", "vietnamese"}


def fmt_number(v, decimals=None):
    """A number as shown on screen in the lesson language: decimal comma where the language uses it, a real
    minus sign, a space between thousands from 10 000 on."""
    v = float(v)
    if decimals is None:
        decimals = 0 if abs(v - round(v)) < 1e-9 else min(3, max(1, len(f"{abs(v):.6g}".split(".")[-1])))
    s = f"{abs(v):,.{decimals}f}"
    whole, _, frac = s.partition(".")
    whole = whole.replace(",", " " if abs(v) >= 10000 else "")
    comma = str(CONFIG.get("narration", {}).get("language", "")).strip().lower() in COMMA_LANGUAGES
    out = whole + ((("," if comma else ".") + frac) if frac else "")
    return ("−" if v < 0 and float(s.replace(",", "")) != 0 else "") + out


def decimals_for(values):
    """Decimals needed to show all the values (at most 3)."""
    out = 0
    for v in values:
        if v is not None and abs(float(v) - round(float(v))) > 1e-9:
            out = max(out, min(3, len(f"{abs(float(v)):.6g}".split(".")[-1])))
    return out


_TAGS = ("b", "big", "i", "s", "sub", "sup", "small", "tt", "u", "span", "hl")
_STRAY_LT = re.compile(r"<(?!/?(?:%s)\b)" % "|".join(_TAGS))
_STRAY_AMP = re.compile(r"&(?!#?\w+;)")
_TOKENS = re.compile(r"<[^>]*>|&#?\w+;|[\s\S]")
RELATIONS = "=≠≤≥<>≈≡"


def clean_markup(text):
    """Escape a bare & or < that is not markup (an agent may write "x < 3")."""
    return _STRAY_LT.sub("&lt;", _STRAY_AMP.sub("&amp;", str(text)))


def _scan(markup, mark_scripts=False):
    """Remove the <hl> tags of a markup text. Returns (markup, visible characters, [(first, end) glyph ranges of
    the <hl> parts]); with mark_scripts, characters in <sup>/<sub> are given as "^"."""
    out, glyphs, ranges, start, script = [], [], [], None, 0
    for tok in _TOKENS.findall(markup):
        if tok == "<hl>":
            start = len(glyphs)
            continue
        if tok == "</hl>":
            if start is not None and len(glyphs) > start:
                ranges.append((start, len(glyphs)))
            start = None
            continue
        out.append(tok)
        if tok.startswith("<") and len(tok) > 1:
            name = tok.strip("</>").split()[0] if tok.strip("</>") else ""
            if name in ("sup", "sub"):
                script += -1 if tok.startswith("</") else 1
            continue
        ch = html.unescape(tok)
        if not ch.isspace():
            glyphs.append("^" if mark_scripts and script > 0 else ch)
    return "".join(out), glyphs, ranges


def _mt(markup, size, color=None, bold=False, font=None):
    try:
        mob = MT(f'<span font_features="liga=0,clig=0">{markup}</span>', size, color, bold=bold, font=font)
    except Exception:  # noqa: BLE001 - Pango's message (on the markup as written) names the problem
        try:
            MT(markup, size, color, bold=bold, font=font)
            message = "not valid Pango markup"
        except Exception as e:  # noqa: BLE001
            message = str(e)
        raise ValueError(f"invalid markup {markup!r}: {message} (tags: <b> <i> <sup> <sub> <span>; write < as "
                         "&lt; and & as &amp;)") from None
    mob.chars_plain = _scan(markup, mark_scripts=True)[1]
    return mob


def formula(markup, size=None, color=None, bold=False):
    """One line of Pango markup as a mobject whose glyphs can be addressed: `.hl` = VGroups of the parts written
    inside <hl>...</hl>, `.rel` = the glyph of the first relation sign (= < > ≤ ≥ ≠ ≈ ≡) or None."""
    size = size or style.TEXT_SIZE
    body, glyphs, ranges = _scan(clean_markup(markup))
    mob = _mt(body, size, color, bold)
    if len(mob.submobjects) == len(glyphs):
        mob.hl = [VGroup(*mob.submobjects[a:b]) for a, b in ranges]
        k = next((i for i, c in enumerate(glyphs) if c in RELATIONS), None)
        mob.rel = mob.submobjects[k] if k is not None else None
    else:                                   # glyphs cannot be matched: color the <hl> parts instead
        marked = clean_markup(markup).replace("<hl>", f'<span color="{style.SECONDARY}">').replace("</hl>", "</span>")
        mob = _mt(marked, size, color, bold)
        mob.hl, mob.rel = [], None
    return mob


def markup_box(markup, max_width, size=None, color=None, bold=False):
    """Pango markup wrapped so that it is at most max_width wide (like kit.text_box, with <sup>, <sub>, <b>...).
    <hl> parts are colored SECONDARY."""
    size = size or style.TEXT_SIZE
    markup = clean_markup(markup).replace("<hl>", f'<span color="{style.SECONDARY}">').replace("</hl>", "</span>")
    words = re.findall(r"(?:<[^>]*>|[^\s<])+", markup)
    plain = [len(html.unescape(re.sub(r"<[^>]*>", "", w))) for w in words]

    def wrapped(limit):
        lines, cur, n = [], [], 0
        for w, k in zip(words, plain):
            if cur and n + 1 + k > limit:
                lines.append(" ".join(cur))
                cur, n = [], 0
            cur.append(w)
            n += k + (1 if n else 0)
        lines.append(" ".join(cur))
        return "\n".join(lines)

    best, lo, hi = None, 6, max(sum(plain) + len(plain), 6)
    while lo <= hi:
        mid = (lo + hi) // 2
        m = _mt(wrapped(mid), size, color, bold)
        if m.width <= max_width:
            best, lo = m, mid + 1
        else:
            hi = mid - 1
    return best if best is not None else style.fit(_mt(wrapped(6), size, color, bold), max_width)


def family(name, default="primary"):
    """(stroke, fill) of a color family of the active theme: primary, secondary, highlight, positive, negative,
    neutral."""
    fams = {"primary": (style.PRIMARY, style.PRIMARY_SOFT), "secondary": (style.SECONDARY, style.SECONDARY_SOFT),
            "highlight": (style.HIGHLIGHT, style.HIGHLIGHT_SOFT), "positive": (style.POSITIVE, style.POSITIVE_SOFT),
            "negative": (style.NEGATIVE, style.NEGATIVE_SOFT), "neutral": (style.MUTED, style.NEUTRAL_SOFT)}
    if name is not None and name not in fams:
        raise ValueError(f"unknown color {name!r} (colors: {', '.join(fams)})")
    return fams[name or default]


def pace(t, seconds):
    """Factor (0.5-1) that fits animations lasting `seconds` into what is left of the piece being spoken."""
    return min(1.0, max(0.5, 0.9 * t.left / max(seconds, 1e-6)))


def _write_time(mob):
    return min(1.4, 0.5 + 0.035 * len(mob.submobjects))


_FLAT = set("abcdefhiklmnorstuvwxzABCDEFGHIKLMNOPRSTUVWXYZ0123456789àèéìòùÀÈÉÌÒÙ")


def _baseline(mob):
    """y of the baseline of a one-line text (the bottom of its letters without descenders), None if unknown."""
    chars = getattr(mob, "chars_plain", None)
    glyphs = mob.submobjects
    if chars is None or len(chars) != len(glyphs):
        return None
    bottoms = sorted(round(g.get_bottom()[1], 3) for g, c in zip(glyphs, chars) if c in _FLAT)
    return bottoms[len(bottoms) // 2] if bottoms else None


def on_baseline(m, text, y, cap_h):
    """Move a text vertically so that its (first) line sits on the baseline y (cap_h: height of a capital)."""
    m.chars_plain = [c for c in str(text) if not c.isspace()]
    b = _baseline(m) if "\n" not in getattr(m, "text", "") else None
    m.shift(UP * (y - b) if b is not None else UP * (y + cap_h - m.get_top()[1]))
    return m


# ------------------------------------------------------------------ templates
@template(category="math", use_for="a number written in another base, with positional weights and the sum",
          example={"args": {"number": 13, "base": 2, "claim": "Stesso numero, due scritture"},
                   "say": ["Prendiamo il numero tredici.", "In binario si scrive uno uno zero uno: i pesi sono otto, quattro, due e uno.",
                           "Stesso numero, due scritture diverse."]})
def number_base(ctx, steps, number: int, base: int = 2, claim: str | None = None):
    """A decimal number and its digits in another base (2..16), with the weight of each position and the sum.
    Phases: the number, digits + weights + sum, the claim."""
    digits, x = [], number
    while True:
        digits.append("0123456789ABCDEF"[x % base])
        x //= base
        if x == 0:
            break
    digits = digits[::-1]
    weights = [base ** k for k in range(len(digits) - 1, -1, -1)]
    dec = T(str(number), 140, style.PRIMARY, bold=True)
    lab_d = T("base 10", 30, style.MUTED).next_to(dec, DOWN, buff=0.3)
    ds = VGroup(*[T(d, 110, style.SECONDARY, bold=True, font=style.MONO) for d in digits]).arrange(RIGHT, buff=0.35)
    lab_b = T(f"base {base}", 30, style.MUTED).next_to(ds, DOWN, buff=0.3)
    ws = VGroup(*[T(str(w), 32, style.MUTED).next_to(d, UP, buff=0.3) for w, d in zip(weights, ds)])
    left, right = VGroup(dec, lab_d), VGroup(ws, ds, lab_b)
    top = VGroup(left, right).arrange(RIGHT, buff=2.2)
    nonzero = [(int(d, 16), w) for d, w in zip(digits, weights) if d != "0"]
    terms = " + ".join(str(w) if v == 1 else f"{v}×{w}" for v, w in nonzero)
    total = MT(f"{terms} = {number}", 42, style.TEXT)
    parts = [top, total]
    claim_m = T(claim, 38, style.PRIMARY, bold=True) if claim else None
    if claim_m is not None:
        parts.append(claim_m)
    ctx.place(VGroup(*parts).arrange(DOWN, buff=0.6))
    link = arrow(dec.get_right() + RIGHT * 0.2, ds.get_left() + LEFT * 0.2, style.MUTED, double=True)

    def p_dec(t):
        t.play(Write(dec), FadeIn(lab_d), rt=1.0)

    def p_digits(t):
        t.play(GrowFromCenter(link), rt=0.5)
        t.play(LaggedStart(*[Write(d) for d in ds], lag_ratio=0.3), FadeIn(lab_b), rt=1.2)
        t.until(0.35)
        t.play(LaggedStart(*[FadeIn(w, shift=DOWN * 0.2) for w in ws], lag_ratio=0.3), rt=1.0)
        t.until(0.65)
        t.play(*[Indicate(d, color=style.HIGHLIGHT, scale_factor=1.2) for d, g in zip(ds, digits) if g != "0"], rt=0.8)
        t.play(Write(total), rt=1.0)

    phases = [p_dec, p_digits] + ([lambda t: t.play(FadeIn(claim_m, shift=UP * 0.2), rt=0.6)] if claim_m else [])
    run_phases(steps, phases)


@template(category="math", use_for="a formula transformed step by step (simplifying, solving an equation, proving an "
          "identity): one transformation per piece, the changed part highlighted, earlier lines kept on screen",
          example={"title": "Il quadrato di un binomio",
                   "args": {"lines": ["(a + b)<sup>2</sup> = (a + b)(a + b)",
                                      "= a<sup>2</sup> + <hl>ab + ba</hl> + b<sup>2</sup>",
                                      "= a<sup>2</sup> + <hl>2ab</hl> + b<sup>2</sup>"],
                            "notes": ["il quadrato è un prodotto", "proprietà distributiva", "ab e ba sono uguali"]},
                   "say": ["Il quadrato di a più b è il prodotto di a più b per sé stesso.",
                           "Con la proprietà distributiva moltiplichiamo ogni termine per ogni termine.",
                           "I due termini centrali sono uguali: insieme fanno due a b."]})
def derivation(ctx, steps, lines: list[str], notes: list[str] | None = None, align: bool = True):
    """A formula transformed line by line, up to 8 lines. Each line is Pango markup (x<sup>2</sup>, a<sub>n</sub>,
    <b>, "&lt;" for <); wrap the part that changed in <hl>...</hl> to frame it. align: line up the first relation
    sign (= < > ≤ ≥ ≠ ≈ ≡) of every line - a line may start with "=" to continue a chain; false: lines start at
    the left. notes: an optional short "why" for each line, shown at its right ("" for none; a few words).
    The newest line is in full color with its <hl> part framed; earlier lines stay, a little dimmed.
    Phases: one per line (with its note)."""
    if not lines:
        raise ValueError("derivation: give at least one line")
    if len(lines) > 8:
        raise ValueError(f"derivation: {len(lines)} lines do not fit on one screen (at most 8): split the "
                         "derivation into two blocks")
    notes = [str(n or "").strip() for n in (notes or [])]
    if len(notes) > len(lines):
        raise ValueError(f"derivation: {len(notes)} notes for {len(lines)} lines (one note per line at most)")
    notes += [""] * (len(lines) - len(notes))
    base = 46
    forms = [formula(line, base) for line in lines]
    for f in forms:                                       # left edge at x = 0, relation sign at x = anchor
        f.shift(-f.get_left())
    if align:
        anchor = max((f.rel.get_center()[0] for f in forms if f.rel is not None), default=0)
        for f in forms:
            if f.rel is not None:
                f.shift(RIGHT * (anchor - f.rel.get_center()[0]))
    left = min(f.get_left()[0] for f in forms)
    for f in forms:
        if f.rel is None or not align:
            f.shift(RIGHT * (left - f.get_left()[0]))
    width_f = max(f.get_right()[0] for f in forms) - left
    gap, row_gap, cache = 0.9, (0.3 if len(lines) <= 5 else 0.2), {}
    W, H = ctx.area.width, ctx.area.height

    def notes_at(width):
        if width not in cache:
            cache[width] = [text_box(n, width, style.SMALL_SIZE + 4, style.MUTED) if n else None for n in notes]
        return cache[width]

    def measure(size, width):                             # (width, height, row heights) of the block
        k, mobs = size / base, notes_at(width)
        fh = max(f.height for f in forms) * k             # one rhythm for all lines; taller rows for long notes
        rows = [max(fh, n.height if n is not None else 0) for n in mobs]
        w = width_f * k + (gap + max(n.width for n in mobs if n is not None) if any(notes) else 0)
        return w, sum(rows) + row_gap * (len(rows) - 1), rows

    # the largest formulas that fit, with notes on as few lines as possible
    options = [(size, width) for size in (62, 56, 50, 44, 38) for width in (7.0, 5.6, 4.6, 3.6)]
    choice = next((o for o in options if measure(*o)[0] <= 0.95 * W and measure(*o)[1] <= 0.92 * H), None)
    if choice is None:
        choice = max(options[-4:], key=lambda o: min(W / measure(*o)[0], H / measure(*o)[1]))
        w, h, _ = measure(*choice)
        if min(W / w, H / h) < 0.85:
            raise ValueError("derivation: these lines and notes do not fit on one screen at a readable size: "
                             "shorten the notes, use fewer lines, or split the derivation into two blocks")
    VGroup(*forms).scale(choice[0] / base, about_point=[left, 0, 0])
    note_mobs, (_, _, rows) = notes_at(choice[1]), measure(*choice)
    right = max(f.get_right()[0] for f in forms)
    y = 0
    for f, n, h in zip(forms, note_mobs, rows):
        ref = f.rel.get_center()[1] if f.rel is not None else f.get_center()[1]
        center = y - h / 2
        f.shift(UP * (center - ref))
        if f.get_top()[1] > y or f.get_bottom()[1] < y - h:      # superscripts: keep the line inside its row
            f.shift(UP * (y - h / 2 - f.get_center()[1]))
        if n is not None:
            n.move_to([right + gap, center, 0], aligned_edge=LEFT)
        y -= h + row_gap
    group = VGroup(*forms, *[n for n in note_mobs if n is not None])
    ctx.place(group, grow=1.0)
    frames = [[frame(h, buff=0.08, stroke_width=3) for h in f.hl] for f in forms]

    def phase(i):
        def run(t):
            k = pace(t, _write_time(forms[i]) + 0.5 * bool(frames[i]) + 0.5 * (note_mobs[i] is not None))
            anims = [Write(forms[i])]
            if i > 0:
                anims.append(forms[i - 1].animate.set_opacity(0.5))
                anims += [FadeOut(fr) for fr in frames[i - 1]]
                if note_mobs[i - 1] is not None:
                    anims.append(note_mobs[i - 1].animate.set_opacity(0.5))
            t.play(*anims, rt=_write_time(forms[i]) * k)
            if frames[i]:
                t.play(*[Create(fr) for fr in frames[i]], rt=0.5 * k)
            if note_mobs[i] is not None:
                t.play(FadeIn(note_mobs[i], shift=LEFT * 0.2), rt=0.5 * k)
        return run

    run_phases(steps, [phase(i) for i in range(len(forms))])


@template(category="math", use_for="a worked example: a problem solved step by step under short subgoal labels, the "
          "result boxed, then optionally a similar problem for the viewer to try (pause) and its answer",
          example={"title": "Velocità media",
                   "args": {"problem": "Un treno percorre 180 km in 2 ore e 15 minuti. Qual è la sua velocità media?",
                            "stages": [{"label": "Tempo in ore", "work": "15 min = 0,25 h  →  t = 2,25 h",
                                        "why": "un quarto d'ora"},
                                       {"label": "Formula", "work": "v = s / t"},
                                       {"label": "Sostituisci e calcola",
                                        "work": "v = 180 km / 2,25 h = <hl>80 km/h</hl>"}],
                            "result": "v = 80 km/h",
                            "try_problem": "Un'auto percorre 150 km in 1 ora e 40 minuti. "
                                           "Qual è la sua velocità media?",
                            "try_answer": "v = 150 km / 1,67 h ≈ 90 km/h"},
                   "say": ["Un treno percorre centottanta chilometri in due ore e un quarto. "
                           "Quanto va veloce, in media?",
                           "Primo passo: il tempo in ore. Quindici minuti sono un quarto d'ora.",
                           "Secondo passo: la velocità media è lo spazio diviso il tempo.",
                           "Terzo passo: centottanta diviso due virgola venticinque fa ottanta.",
                           "Il treno viaggia in media a ottanta chilometri orari.",
                           {"say": "Ora tocca a te: un'auto fa centocinquanta chilometri in un'ora e quaranta minuti. "
                                   "Segui gli stessi tre passi. Metti in pausa e prova.", "pause": 3},
                           "Viene circa novanta chilometri orari. Ci sei riuscito?"]})
def worked_example(ctx, steps, problem: str, stages: list[dict], result: str, try_problem: str | None = None,
                   try_answer: str | None = None, try_label: str = "Ora prova tu"):
    """A problem solved step by step. problem: the statement, on a card on top (keep it to one or two lines).
    stages: 1-6 steps [{"label": short subgoal, "work": the math of the step (markup: x<sup>2</sup>,
    <hl>changed part</hl>), "why": optional short reason}], numbered; the current one in full color, the earlier
    ones dimmed a little. result: boxed under the work (markup). try_problem: optional similar problem for the
    viewer: the solution clears and the problem appears under try_label (write it in the lesson language) with
    the subgoal labels of the example as a guide; put a "pause" on its piece. try_answer: its answer, revealed
    after the pause.
    Phases: problem, one per stage, result, try problem, try answer."""
    if not stages:
        raise ValueError("worked_example: give at least one stage")
    if len(stages) > 6:
        raise ValueError(f"worked_example: {len(stages)} stages do not fit (at most 6): group steps or split the "
                         "example into two blocks")
    if try_answer and not try_problem:
        raise ValueError("worked_example: try_answer needs try_problem")
    for k, s in enumerate(stages):
        if not isinstance(s, dict) or not str(s.get("work", "")).strip():
            raise ValueError(f"worked_example: stage {k} must be {{\"label\", \"work\", \"why\"}} with a \"work\"")
    W, H = ctx.area.width, ctx.area.height
    texts = [str(s.get("label") or "").strip() for s in stages]

    def build(size):
        """The solution screen with text of `size` (labels and reasons a little smaller)."""
        small = max(style.SMALL_SIZE, size - 6)
        # the problem, on a card across the top
        prob = markup_box(problem, W - 0.9, size, style.TEXT)
        prob_bg = RoundedRectangle(width=W, height=prob.height + 0.4, corner_radius=0.18, stroke_color=style.PRIMARY,
                                   stroke_width=3, fill_color=style.PRIMARY_SOFT, fill_opacity=1)
        prob.move_to(prob_bg).align_to(prob_bg, LEFT).shift(RIGHT * 0.4)
        # one row per stage: number + subgoal label | work (+ why at its right, or below if it does not fit)
        natural = max([T(x, small, bold=True).width for x in texts if x] + [0])
        label_w = min(natural + 0.8, 0.4 * W)
        work_x, work_w = label_w + 0.35, W - label_w - 0.35
        line_h = T("Ag", size).height
        heads, bodies = [], []
        for k, st in enumerate(stages):
            dot = Circle(radius=0.27 * size / 40, stroke_color=style.PRIMARY, stroke_width=3,
                         fill_color=style.PRIMARY_SOFT, fill_opacity=1)
            head = VGroup(VGroup(dot, T(str(k + 1), round(28 * size / 40), style.PRIMARY, bold=True).move_to(dot)))
            if texts[k]:
                head.add(text_box(texts[k], label_w - 0.75, small, style.PRIMARY, bold=True))
                head.arrange(RIGHT, buff=0.2)
                cap_h = T("H", small).height
                on_baseline(head[1], texts[k], dot.get_center()[1] - cap_h / 2, cap_h)
            work = markup_box(str(st["work"]), work_w, size, style.TEXT)
            body = VGroup(work)
            why = str(st.get("why") or "").strip()
            if why:
                note = T(why, max(style.SMALL_SIZE, small - 2), style.MUTED)
                if work.width + 0.6 + note.width <= work_w:
                    body.add(note.next_to(work, RIGHT, buff=0.6).align_to(work, DOWN))
                else:
                    body.add(text_box(why, work_w, max(style.SMALL_SIZE, small - 2), style.MUTED)
                             .next_to(work, DOWN, buff=0.1, aligned_edge=LEFT))
            body.move_to([work_x, 0, 0], aligned_edge=LEFT + UP)
            head.move_to([0, work.get_top()[1] - line_h / 2, 0], aligned_edge=LEFT)
            heads.append(head)
            bodies.append(body)
        rows = [VGroup(h, b) for h, b in zip(heads, bodies)]
        stage_col = VGroup(*rows).arrange(DOWN, buff=0.3 if len(rows) <= 4 else 0.2, aligned_edge=LEFT)
        res_text = markup_box(result, work_w - 0.8, size + 2, style.TEXT, bold=True)
        res_bg = RoundedRectangle(width=res_text.width + 0.7, height=res_text.height + 0.4, corner_radius=0.18,
                                  stroke_color=style.POSITIVE, stroke_width=4, fill_color=style.POSITIVE_SOFT,
                                  fill_opacity=1)
        res_box = VGroup(res_bg, res_text.move_to(res_bg))
        # the result under the steps; if that is too tall, at the right of the last step when there is room
        res_box.next_to(stage_col, DOWN, buff=0.35).align_to(bodies[0], LEFT)
        whole = VGroup(VGroup(prob_bg, prob), VGroup(stage_col, res_box)).arrange(DOWN, buff=0.35, aligned_edge=LEFT)
        x0 = stage_col.get_left()[0]
        if whole.height > H and bodies[-1].get_right()[0] - x0 + 0.8 + res_box.width <= W:
            res_box.move_to([x0 + W, rows[-1].get_bottom()[1], 0], aligned_edge=RIGHT + DOWN)
            whole = VGroup(VGroup(prob_bg, prob), VGroup(stage_col, res_box)).arrange(DOWN, buff=0.35,
                                                                                      aligned_edge=LEFT)
        return whole, VGroup(prob_bg, prob), heads, bodies, rows, res_box

    # the largest text that fits (larger only for a short example); below a readable size it must be split
    for size in (style.TEXT_SIZE + 6, style.TEXT_SIZE, style.TEXT_SIZE - 4, style.SMALL_SIZE + 2):
        whole, prob_card, heads, bodies, rows, res_box = build(size)
        if whole.height <= (H if size <= style.TEXT_SIZE else 0.7 * H) and whole.width <= W + 0.01:
            break
    else:
        if H / whole.height < 0.9:
            raise ValueError("worked_example: too much text for one screen at a readable size: shorten the problem "
                             "and the reasons (why), or split the stages into two blocks")
    ctx.place(whole, at="top", grow=1.0)

    # the "try it" screen: a new problem, the subgoal labels as a guide, then the answer
    try_parts, guide, ans = None, [], None
    if try_problem:
        t_head = T(try_label, style.TEXT_SIZE + 4, style.SECONDARY, bold=True)
        t_prob = markup_box(try_problem, W - 0.9, style.TEXT_SIZE, style.TEXT)
        t_bg = RoundedRectangle(width=W, height=t_prob.height + 0.45, corner_radius=0.18, stroke_color=style.SECONDARY,
                                stroke_width=3, fill_color=style.SECONDARY_SOFT, fill_opacity=1)
        t_prob.move_to(t_bg).align_to(t_bg, LEFT).shift(RIGHT * 0.4)
        guide = [h.copy().set_opacity(1) for h in heads]
        g_row = VGroup(*guide).arrange(RIGHT, buff=0.6)
        if g_row.width > W:
            g_row.arrange_in_grid(cols=(len(guide) + 1) // 2, buff=(0.6, 0.3), cell_alignment=LEFT)
        g_row.scale(min(1.3, W / g_row.width))
        parts = [t_head, VGroup(t_bg, t_prob), g_row]
        if try_answer:
            a_text = markup_box(try_answer, W - 1.6, style.TEXT_SIZE + 4, style.TEXT, bold=True)
            a_bg = RoundedRectangle(width=a_text.width + 0.8, height=a_text.height + 0.45, corner_radius=0.18,
                                    stroke_color=style.POSITIVE, stroke_width=4, fill_color=style.POSITIVE_SOFT,
                                    fill_opacity=1)
            ans = VGroup(a_bg, a_text.move_to(a_bg))
            parts.append(ans)
        try_parts = VGroup(*parts).arrange(DOWN, buff=0.45)
        t_head.align_to(t_bg, LEFT)
        ctx.place(try_parts, at="top", grow=1.0)

    def p_problem(t):
        t.play(FadeIn(prob_card, shift=DOWN * 0.15), rt=0.7)

    def p_stage(k):
        def run(t):
            f = pace(t, 0.6 + _write_time(bodies[k][0]) + 0.5 * (len(bodies[k]) > 1))
            t.play(FadeIn(heads[k], shift=RIGHT * 0.2), *focus_anims(rows[:k], -1, 0.5), rt=0.6 * f)
            t.play(Write(bodies[k][0]), rt=_write_time(bodies[k][0]) * f)
            if len(bodies[k]) > 1:
                t.play(FadeIn(bodies[k][1], shift=LEFT * 0.1), rt=0.5 * f)
        return run

    def p_result(t):
        t.play(*focus_anims(rows, -1, 0.5), FadeIn(res_box, scale=0.9), rt=0.7)

    def p_try(t):
        f = pace(t, 1.4)
        t.play(FadeOut(prob_card), FadeOut(res_box), *[FadeOut(b) for b in bodies], rt=0.5 * f)
        t.play(FadeIn(try_parts[0]), FadeIn(try_parts[1], shift=DOWN * 0.15),
               *[h.animate.become(g) for h, g in zip(heads, guide)], rt=0.9 * f)

    phases = [p_problem] + [p_stage(k) for k in range(len(rows))] + [p_result]
    if try_parts is not None:
        phases.append(p_try)
    if ans is not None:
        phases.append(lambda t: t.play(FadeIn(ans, scale=0.9), rt=0.7))
    run_phases(steps, phases)


@template(category="math", use_for="numbers on a line: ordering and comparing values, distances, the solutions of an "
          "inequality, intervals; one mark per piece",
          example={"title": "Le soluzioni di 2x − 1 > 3",
                   "args": {"start": -3, "end": 6, "step": 1,
                            "marks": [{"value": 2, "label": "x = 2", "open": True},
                                      {"from": 2, "label": "x > 2", "include": [False, False]},
                                      {"value": 0, "label": "0: no", "color": "negative"},
                                      {"value": 4, "label": "4: sì", "color": "positive"}]},
                   "say": ["Il confine è x uguale due, dove i due lati sono uguali.",
                           "Le soluzioni sono tutti i numeri maggiori di due: "
                           "il pallino vuoto dice che il due è escluso.",
                           "Verifichiamo: con zero la disuguaglianza è falsa,", "con quattro invece è vera."]})
def number_line(ctx, steps, start: float, end: float, step: float, marks: list[dict] | None = None):
    """A number line from start to end with a tick every step (at most 40 ticks), and marks appearing one per
    phase (at most 10). A point: {"value": 2.5, "label": "markup", "open": false (hollow dot), "color": "primary"};
    an interval: {"from": 2, "to": 5, "label": "...", "include": [true, false] (closed / open ends), "color":
    "secondary"}, where a missing "from"/"to" runs off the end of the line (an arrow). Colors: primary, secondary,
    highlight, positive, negative, neutral.
    Phases: one per mark (the line comes with the first)."""
    marks = list(marks or [])
    if not end > start:
        raise ValueError(f"number_line: end ({end}) must be greater than start ({start})")
    if step <= 0:
        raise ValueError("number_line: step must be positive")
    n = int((end - start) / step + 1e-9)
    if n > 40:
        raise ValueError(f"number_line: {n + 1} ticks are too many (at most 40): use a larger step")
    if len(marks) > 10:
        raise ValueError(f"number_line: {len(marks)} marks are too many (at most 10)")
    W = ctx.area.width
    L = W - 1.4
    x_of = lambda v: -L / 2 + (v - start) / (end - start) * L          # noqa: E731
    ticks = [start + k * step for k in range(n + 1)]
    dec = decimals_for(ticks)
    axis = Line([x_of(start) - 0.4, 0, 0], [x_of(end) + 0.55, 0, 0], color=style.MUTED, stroke_width=4)
    axis.add_tip(tip_length=0.25, tip_width=0.22)
    labels = [T(fmt_number(v, dec), style.TEXT_SIZE - 2, style.TEXT) for v in ticks]
    room = L / max(n, 1)
    every = next((k for k in (1, 2, 4, 5, 10, 20, 40) if max(m.width for m in labels) + 0.3 <= k * room), 40)
    ref = 0 if start <= 0 <= end else start
    tick_mobs, label_mobs = VGroup(), VGroup()
    for v, lab in zip(ticks, labels):
        major = round((v - ref) / step) % every == 0
        h = 0.15 if major else 0.09
        tick_mobs.add(Line([x_of(v), -h, 0], [x_of(v), h, 0], color=style.MUTED, stroke_width=3))
        if major:
            label_mobs.add(lab.move_to([x_of(v), -0.55, 0]))
    # the marks
    items, placed, bars, spans = [], [], [], {}            # bars: (x0, x1, level) of the intervals drawn
    for k, m in enumerate(marks):
        if not isinstance(m, dict) or not ("value" in m or "from" in m or "to" in m):
            raise ValueError(f"number_line: mark {k} must be a point {{\"value\", \"label\"}} or an interval "
                             "{\"from\", \"to\", \"label\"}")
        is_point = "value" in m
        color = family(m.get("color"), "primary" if is_point else "secondary")[0]
        for key in ("value", "from", "to"):
            v = m.get(key)
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not start <= v <= end):
                raise ValueError(f"number_line: mark {k}: {key} = {v!r} is not a number between {start} and {end}")
        shapes = VGroup()
        if is_point:
            dot = Dot([x_of(m["value"]), 0, 0], radius=0.16, color=color)
            if m.get("open"):
                dot.set_fill(style.BACKGROUND, 1).set_stroke(color, 5)
            shapes.add(dot)
            x0 = x1 = x_of(m["value"])
            y = 0
        else:
            a, b = m.get("from"), m.get("to")
            if a is not None and b is not None and b < a:
                raise ValueError(f"number_line: mark {k}: from ({a}) is greater than to ({b})")
            x0 = x_of(a) if a is not None else x_of(start) - 0.35
            x1 = x_of(b) if b is not None else x_of(end) + 0.45
            level = next(j for j in range(12) if all(j != lv or x1 < p0 - 0.1 or x0 > p1 + 0.1 for p0, p1, lv in bars))
            bars.append((x0, x1, level))
            spans[k] = (x0, x1)
            y = 0.32 * level
            body = Line([x0, y, 0], [x1, y, 0], color=color, stroke_width=11) if a is not None else \
                Line([x1, y, 0], [x0, y, 0], color=color, stroke_width=11)
            if a is None or b is None:
                body.add_tip(tip_length=0.28, tip_width=0.3)
            shapes.add(body)
            include = list(m.get("include") or [True, True]) + [True, True]
            for v, inc in ((a, include[0]), (b, include[1])):
                if v is not None:
                    end_dot = Dot([x_of(v), y, 0], radius=0.16, color=color)
                    if not inc:
                        end_dot.set_fill(style.BACKGROUND, 1).set_stroke(color, 5)
                    shapes.add(end_dot)
            if level:
                for v in (a, b):
                    if v is not None:
                        shapes.add(DashedLine([x_of(v), 0, 0], [x_of(v), y, 0], color=color, stroke_width=2))
        lab = None
        if str(m.get("label") or "").strip():
            lab = formula(str(m["label"]), style.TEXT_SIZE + 2, color, bold=True)
            if lab.width > W * 0.45:
                lab = markup_box(str(m["label"]), W * 0.45, style.TEXT_SIZE + 2, color, bold=True)
            items.append((k, lab, (x0 + x1) / 2))
        placed.append((is_point, shapes, lab))
    base = max([0.32 * lv for _, _, lv in bars] + [0]) + 0.55
    taken = []                                             # (x0, x1, level) of the labels placed

    def free(x0, x1, level):
        return x0 >= -W / 2 and x1 <= W / 2 and all(lv != level or x1 < p0 - 0.3 or x0 > p1 + 0.3
                                                     for p0, p1, lv in taken)

    def crosses(x, level):                                 # a stem at x up to `level` would cross a lower label
        return any(lv < level and p0 - 0.1 < x < p1 + 0.1 for p0, p1, lv in taken)

    # points first (their labels must stay above them), then intervals (anywhere along their visible part)
    for k, lab, cx in sorted(items, key=lambda it: not placed[it[0]][0]):
        w, is_point = lab.width, placed[k][0]
        if is_point:
            cands = [cx, cx + w / 2 - 0.2, cx - w / 2 + 0.2]
        else:
            x0, x1 = spans[k]
            span = max(x1 - x0 - w, 0)
            cands = [cx + d * span / 2 * f for f in (0, 0.35, 0.7, 1.0) for d in (1, -1)]
        best = None
        for level in range(8):
            for c in cands:
                if free(c - w / 2, c + w / 2, level) and not (is_point and crosses(cx, level)):
                    best = (c, level)
                    break
            if best:
                break
        c, level = best or (cx, len(taken))
        taken.append((c - w / 2, c + w / 2, level))
        lab.move_to([c, base + level * 0.75 + lab.height / 2, 0])
        if level and is_point:                             # a stem from a raised label down to its point
            placed[k][1].add(DashedLine([cx, 0.2, 0], [cx, lab.get_bottom()[1] - 0.08, 0], color=style.MUTED,
                                        stroke_width=2))
    group = VGroup(axis, tick_mobs, label_mobs, *[VGroup(s, *([lb] if lb is not None else [])) for _, s, lb in placed])
    ctx.place(group, grow=1.0)

    def show_line(t, f=1.0):
        t.play(Create(axis), FadeIn(tick_mobs), rt=0.8 * f)
        t.play(LaggedStart(*[FadeIn(lab, shift=UP * 0.1) for lab in label_mobs], lag_ratio=0.05), rt=0.6 * f)

    def phase(k):
        def run(t):
            is_point, shapes, lab = placed[k]
            f = pace(t, 1.4 * (k == 0) + (0.5 if is_point else 1.2) + 0.5 * (lab is not None))
            if k == 0:
                show_line(t, f)
            if is_point:
                t.play(*[GrowFromCenter(s) if isinstance(s, Dot) else Create(s) for s in shapes], rt=0.5 * f)
            else:
                t.play(Create(shapes[0]), rt=0.8 * f)
                if len(shapes) > 1:
                    t.play(*[GrowFromCenter(s) if isinstance(s, Dot) else Create(s) for s in shapes[1:]], rt=0.4 * f)
            if lab is not None:
                t.play(FadeIn(lab, shift=DOWN * 0.15), rt=0.5 * f)
        return run

    run_phases(steps, [phase(k) for k in range(len(placed))] if placed else [show_line])


_NUMERIC = re.compile(r"^[−\-+±~≈<>≤≥]?\s*[\d.,  ]*\d[\d.,  ]*\s*(%|‰|°|°C|e[−\-+]?\d+)?$")


@template(category="math", use_for="exact values to read and compare: a table built row by row (or all at once), "
          "then rows, columns or cells highlighted one at a time",
          example={"title": "Galleggia o affonda?",
                   "args": {"header": ["Materiale", "Densità (g/cm³)", "In acqua"],
                            "rows": [["Sughero", "0,24", "galleggia"], ["Ghiaccio", "0,92", "galleggia"],
                                     ["Acqua", "1,00", "—"], ["Ferro", "7,87", "affonda"]],
                            "highlights": [{"row": 2}, {"col": 1}]},
                   "say": ["Ecco la densità di alcuni materiali, in grammi per centimetro cubo.",
                           "Il sughero è molto leggero.", "Il ghiaccio è un po' più leggero dell'acqua.",
                           "L'acqua vale esattamente uno.", "Il ferro quasi otto.",
                           "L'acqua è il riferimento.",
                           "Chi ha densità minore di uno galleggia, gli altri affondano."]})
def table(ctx, steps, header: list[str], rows: list[list[str]], highlights: list[dict] | None = None,
          reveal: Literal["rows", "all"] = "rows"):
    """A table (up to 7 columns and 12 rows; cells are short texts or markup). Columns whose cells are all
    numbers are right-aligned in a monospaced font. reveal: "rows" (the header, then one row per phase) or
    "all" (the whole table in one phase). highlights: one per phase after that, each {"row": i} or {"col": j}
    or {"cell": [i, j]} (0-based; rows count from the first row under the header); one highlight at a time.
    Phases: header, one per row (or: the table), one per highlight."""
    nc = len(header)
    if not 1 <= nc <= 7:
        raise ValueError(f"table: {nc} columns (between 1 and 7)")
    if not 1 <= len(rows) <= 12:
        raise ValueError(f"table: {len(rows)} rows (between 1 and 12): split a longer table")
    for i, r in enumerate(rows):
        if len(r) != nc:
            raise ValueError(f"table: row {i} has {len(r)} cells, the header has {nc}")
    highlights = list(highlights or [])
    for h in highlights:
        ok = isinstance(h, dict) and (
            (isinstance(h.get("row"), int) and 0 <= h["row"] < len(rows)) or
            (isinstance(h.get("col"), int) and 0 <= h["col"] < nc) or
            (isinstance(h.get("cell"), list) and len(h["cell"]) == 2 and 0 <= h["cell"][0] < len(rows)
             and 0 <= h["cell"][1] < nc))
        if not ok:
            raise ValueError(f"table: highlight {h!r} must be {{\"row\": i}}, {{\"col\": j}} or "
                             f"{{\"cell\": [i, j]}} with i < {len(rows)} and j < {nc}")
    numeric = [all(_NUMERIC.match(str(r[j]).strip()) or str(r[j]).strip() in ("", "—", "-", "–") for r in rows)
               and any(_NUMERIC.match(str(r[j]).strip()) for r in rows) for j in range(nc)]
    W, H = ctx.area.width, ctx.area.height
    pad_x, pad_y = 0.3, (0.16 if len(rows) <= 6 else 0.1)

    texts = [[str(t).strip() or " " for t in r] for r in [header] + rows]

    def build(size, order):
        """Cells at `size`, too wide columns wrapped (widest first): long headers, long texts, in `order`."""
        def cell(i, j, cap):
            if i == 0:
                return markup_box(texts[i][j], cap, size, style.PRIMARY, bold=True)
            if numeric[j]:
                return _mt(clean_markup(texts[i][j]), size, style.TEXT, font=style.MONO)
            return markup_box(texts[i][j], cap, size, style.TEXT)

        cells = [[cell(i, j, W) for j in range(nc)] for i in range(len(texts))]
        data_w = [max(c[j].width for c in cells[1:]) for j in range(nc)]
        widths = lambda: [max(c[j].width for c in cells) + 2 * pad_x for j in range(nc)]   # noqa: E731
        col_w = widths()
        for stage in order:
            fixed = set()
            while sum(col_w) > W:
                if stage == "header":
                    free = [j for j in range(nc) if j not in fixed and cells[0][j].width > max(data_w[j], 1.8) + 0.05]
                else:
                    free = [j for j in range(nc) if j not in fixed and not numeric[j] and data_w[j] > 2.2]
                if not free:
                    break
                j = max(free, key=lambda k: col_w[k])
                before = col_w[j]
                if stage == "header":
                    cells[0][j] = cell(0, j, max(1.8, data_w[j], cells[0][j].width * 0.8))
                else:
                    for i in range(1, len(texts)):
                        cells[i][j] = cell(i, j, max(2.2, data_w[j] * 0.8))
                    data_w[j] = max(c[j].width for c in cells[1:])
                col_w = widths()
                if col_w[j] > before - 0.02:
                    fixed.add(j)
        cap_h, full_h = T("H", size).height, T("Hg", size).height
        row_h = [max([full_h] + [c.height for c in line if c.height > 1.6 * full_h]) + 2 * pad_y for line in cells]
        return cells, col_w, row_h, cap_h

    for size in (style.TEXT_SIZE, style.TEXT_SIZE - 4, style.SMALL_SIZE + 2, style.SMALL_SIZE):
        # wrapping the headers grows one row, wrapping texts grows many: keep the lower table
        cells, col_w, row_h, cap_h = min((build(size, order) for order in (("header", "data"), ("data", "header"))),
                                         key=lambda b: (sum(b[1]) > W + 0.01, sum(b[2])))
        if sum(col_w) <= W and sum(row_h) <= H:
            break
    else:
        if min(W / sum(col_w), H / sum(row_h)) < 0.85:
            raise ValueError("table: too much text for one screen at a readable size: use fewer or shorter columns, "
                             "fewer rows, or split the table into two blocks")
    total_w, full_h = sum(col_w), T("Hg", size).height
    xs = [sum(col_w[:j]) for j in range(nc)]
    tops = [-sum(row_h[:i]) for i in range(len(row_h))]
    backs = []
    for i, line in enumerate(cells):
        fill = style.PRIMARY_SOFT if i == 0 else (style.NEUTRAL_SOFT if i % 2 == 0 else style.BACKGROUND)
        back = Rectangle(width=total_w, height=row_h[i], stroke_width=0, fill_color=fill, fill_opacity=1)
        backs.append(back.move_to([total_w / 2, tops[i] - row_h[i] / 2, 0]))
        for j, m in enumerate(line):
            right_aligned = numeric[j]
            m.move_to([xs[j] + col_w[j] - pad_x if right_aligned else xs[j] + pad_x, 0, 0],
                      aligned_edge=RIGHT if right_aligned else LEFT)
            if m.height > 1.6 * full_h:                                       # wrapped text: top aligned
                m.align_to([0, tops[i] - pad_y, 0], UP)
            elif _baseline(m) is not None:                                    # one line: on the row's baseline
                m.shift(UP * (tops[i] - pad_y - cap_h - _baseline(m)))
            else:                                                             # symbols only: at mid x-height
                m.set_y(tops[i] - pad_y - cap_h * 0.65)
    rule = Line([0, tops[0] - row_h[0], 0], [total_w, tops[0] - row_h[0], 0], color=style.PRIMARY, stroke_width=3)
    bottom = Line([0, tops[-1] - row_h[-1], 0], [total_w, tops[-1] - row_h[-1], 0], color=style.MUTED, stroke_width=2)
    # the areas a highlight frames (invisible; placed with the table)
    targets = []
    for h in highlights:
        if "row" in h:
            i = h["row"] + 1
            box_ = Rectangle(width=total_w, height=row_h[i]).move_to(backs[i])
        elif "col" in h:
            j = h["col"]
            box_ = Rectangle(width=col_w[j], height=-tops[-1] + row_h[-1]).move_to(
                [xs[j] + col_w[j] / 2, (tops[-1] - row_h[-1]) / 2, 0])
        else:
            i, j = h["cell"][0] + 1, h["cell"][1]
            box_ = Rectangle(width=col_w[j], height=row_h[i]).move_to([xs[j] + col_w[j] / 2, backs[i].get_y(), 0])
        targets.append(box_.set_opacity(0))
    row_groups = [VGroup(backs[i], *cells[i]) for i in range(len(cells))]
    row_groups[0].add(rule)
    ctx.place(VGroup(*row_groups, bottom, *targets), at="top", buff=0.05, grow=1.3)
    frames = [frame(b, buff=0.0, stroke_width=5, fill_opacity=0.15) for b in targets]

    def show_all(t):
        t.play(LaggedStart(*[FadeIn(r, shift=DOWN * 0.1) for r in row_groups], lag_ratio=0.15), FadeIn(bottom), rt=1.2)

    def show_row(i):
        def run(t):
            t.play(FadeIn(row_groups[i], shift=DOWN * 0.1), *([FadeIn(bottom)] if i == len(row_groups) - 1 else []),
                   rt=0.5)
        return run

    def show_highlight(k):
        def run(t):
            t.play(Create(frames[k]), *([FadeOut(frames[k - 1])] if k > 0 else []), rt=0.6)
        return run

    phases = [show_row(i) for i in range(len(row_groups))] if reveal == "rows" else [show_all]
    run_phases(steps, phases + [show_highlight(k) for k in range(len(frames))])
