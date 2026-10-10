"""Text and structure: title card, question, roadmap, bullets, definition, statement, recap quiz, predict."""
from manim import (DOWN, LEFT, RIGHT, UP, Circle, Create, FadeIn, GrowFromCenter, Line, Square, VGroup, Write)

from .. import style
from ..style import T, box, check, cross
from . import template
from .kit import focus_anims, frame, panel, run_phases, text_box


@template(category="text", use_for="the opening of the lesson or of a big part",
          example={"args": {"title": "Il sistema binario", "subtitle": "Come un calcolatore rappresenta i numeri"},
                   "say": ["Benvenuti! Oggi parliamo del sistema binario.", "Vedremo come un calcolatore rappresenta i numeri."]})
def title_card(ctx, steps, title: str, subtitle: str | None = None):
    """A full-screen title with an optional subtitle (use it without a block title).
    Phases: title, subtitle."""
    head = text_box(title, ctx.area.width - 1, 64, style.PRIMARY, bold=True, font=style.TITLE_FONT, align="center")
    line = Line(LEFT * 2.5, RIGHT * 2.5, color=style.HIGHLIGHT, stroke_width=6)
    parts = [head, line]
    sub = text_box(subtitle, ctx.area.width - 2, style.TEXT_SIZE, style.MUTED) if subtitle else None
    if sub is not None:
        parts.append(sub)
    group = ctx.place(VGroup(*parts).arrange(DOWN, buff=0.4))

    def p_title(t):
        t.play(Write(head), rt=1.0)
        t.play(Create(line), rt=0.4)

    def p_sub(t):
        t.play(FadeIn(sub, shift=UP * 0.2), rt=0.6)

    run_phases(steps, [p_title] + ([p_sub] if sub is not None else []))
    return group


@template(category="text", use_for="an opening puzzle, a question to predict before a reveal, a retrieval "
          "question with a pause to think (put \"pause\" on its piece), then the answer",
          example={"args": {"question": "Quanti simboli servono, come minimo, per scrivere qualsiasi numero?",
                            "hint": "Pensate a un interruttore", "answer": "Due: acceso e spento"},
                   "say": [{"say": "Una domanda prima di cominciare: quanti simboli servono, come minimo?", "pause": 3},
                           "Un indizio: pensate a un interruttore.", "Ne bastano due: acceso e spento."]})
def question(ctx, steps, question: str, answer: str | None = None, hint: str | None = None):
    """A big question in the middle; optionally a hint, then the answer revealed.
    Phases: question, hint, answer."""
    mark = T("?", 120, style.SECONDARY, bold=True)
    q = text_box(question, ctx.area.width - 2.2, 44, style.TEXT, bold=True)
    top = VGroup(mark, q).arrange(RIGHT, buff=0.5)
    parts = [top]
    h = text_box(hint, ctx.area.width - 3, style.TEXT_SIZE, style.MUTED) if hint else None
    a = box(answer, w=min(max(len(answer) * 0.28 + 1.2, 4), ctx.area.width - 1), h=1.2, size=36,
            color=style.POSITIVE, fill=style.POSITIVE_SOFT) if answer else None
    parts += [x for x in (h, a) if x is not None]
    ctx.place(VGroup(*parts).arrange(DOWN, buff=0.6))

    def p_q(t):
        t.play(GrowFromCenter(mark), FadeIn(q, shift=UP * 0.2), rt=0.8)

    phases = [p_q]
    if h is not None:
        phases.append(lambda t: t.play(FadeIn(h, shift=UP * 0.2), rt=0.5))
    if a is not None:
        phases.append(lambda t: t.play(FadeIn(a, scale=0.9), rt=0.6))
    run_phases(steps, phases)


@template(category="text", use_for="the map of the lesson at the start, or where we are when a new part begins",
          example={"title": "Di cosa parliamo", "args": {"items": ["I simboli", "L'alfabeto binario", "Le potenze di due"]},
                   "say": ["Prima i simboli,", "poi l'alfabeto binario,", "e infine le potenze di due."]})
def roadmap(ctx, steps, items: list[str], current: int | None = None):
    """The numbered parts of the lesson. Without `current` the parts appear one per phase; with `current`
    (0-based) all parts are shown and that one is highlighted (the others dimmed).
    Phases: one per part, or: all, highlight."""
    rows = []
    for k, item in enumerate(items):
        dot = Circle(radius=0.32, stroke_color=style.PRIMARY, stroke_width=3, fill_color=style.PRIMARY_SOFT,
                     fill_opacity=1)
        num = T(str(k + 1), 30, style.PRIMARY, bold=True).move_to(dot)
        label = text_box(item, ctx.area.width * 0.7, style.TEXT_SIZE)
        rows.append(VGroup(VGroup(dot, num), label).arrange(RIGHT, buff=0.4))
    group = ctx.place(VGroup(*rows).arrange(DOWN, buff=0.45, aligned_edge=LEFT), grow=1.5)
    if current is None:
        def phase(k):
            return lambda t: t.play(FadeIn(rows[k], shift=RIGHT * 0.2), *focus_anims(rows[:k], -1, 0.55), rt=0.6)
        run_phases(steps, [phase(k) for k in range(len(rows))])
    else:
        def show(t):
            t.play(*[FadeIn(r, shift=RIGHT * 0.2) for r in rows], rt=0.8)

        def highlight(t):
            t.play(*focus_anims(rows, current), FadeIn(frame(rows[current])), rt=0.6)
        run_phases(steps, [show, highlight])
    return group


@template(category="text", use_for="a list of points, properties, steps of a procedure, a definition broken "
          "into parts - one point per narration piece",
          example={"title": "Perché due simboli", "args": {"items": ["Due livelli di tensione sono facili da distinguere",
                                                                        "Il rumore non li confonde", "I circuiti sono semplici"]},
                   "say": ["Primo: due livelli di tensione si distinguono facilmente.", "Secondo: il rumore non li confonde.",
                           "Terzo: i circuiti restano semplici."]})
def bullets(ctx, steps, items: list[str], numbered: bool = False):
    """Points revealed one per phase; the point being discussed is in full color, the previous ones dimmed.
    Keep each point short (key words, not the narration). Phases: one per point."""
    rows = []
    for k, item in enumerate(items):
        if numbered:
            marker = T(f"{k + 1}.", style.TEXT_SIZE, style.PRIMARY, bold=True)
        else:
            marker = Square(0.16, fill_color=style.PRIMARY, fill_opacity=1, stroke_width=0)
        text = text_box(item, ctx.area.width * 0.72, style.TEXT_SIZE)
        marker.next_to(text[0] if len(text) else text, LEFT, buff=0.3)
        rows.append(VGroup(marker, text))
    group = VGroup(*rows).arrange(DOWN, buff=0.45, aligned_edge=LEFT)
    ctx.place(group, grow=1.5)
    group.align_to([ctx.area.left + 0.3, 0, 0], LEFT).align_to([0, ctx.area.top - 0.1, 0], UP)

    def phase(k):
        return lambda t: t.play(FadeIn(rows[k], shift=RIGHT * 0.2), *focus_anims(rows[:k], -1, 0.5), rt=0.6)

    run_phases(steps, [phase(k) for k in range(len(rows))])
    return group


@template(category="text", use_for="a new term: its definition, then an example and a non-example that differ "
          "in the critical feature",
          example={"title": "Un nuovo termine", "args": {"term": "Bit", "definition": "La cifra di un numero binario: vale zero oppure uno",
                                            "example": "1 in 1011", "non_example": "2 in 1021: non è un bit"},
                   "say": ["Un nuovo termine: il bit.", "È una cifra binaria, che vale zero oppure uno.",
                           "Per esempio, l'uno in uno zero uno uno.", "Il due invece non è un bit."]})
def definition(ctx, steps, term: str, definition: str, example: str | None = None, non_example: str | None = None):
    """A term, its definition, and optionally an example (✓) and a non-example (✗).
    Phases: term, definition, example, non-example."""
    w = ctx.area.width * 0.7
    t_term = T(term, 60, style.PRIMARY, bold=True, font=style.TITLE_FONT)
    t_def = text_box(definition, w, style.TEXT_SIZE)
    parts = [t_term, t_def]
    cards = []
    for text, good in ((example, True), (non_example, False)):
        if text:
            mark = check() if good else cross()
            label = text_box(text, w / 2 - 0.9, style.TEXT_SIZE)
            content = VGroup(mark.scale(0.8), label).arrange(RIGHT, buff=0.3)
            bg = panel(content.width + 0.6, content.height + 0.5, style.POSITIVE if good else style.NEGATIVE,
                       style.POSITIVE_SOFT if good else style.NEGATIVE_SOFT)
            cards.append(VGroup(bg, content.move_to(bg)))
    if cards:
        parts.append(VGroup(*cards).arrange(RIGHT, buff=0.5))
    ctx.place(VGroup(*parts).arrange(DOWN, buff=0.5), grow=1.5)
    phases = [lambda t: t.play(Write(t_term), rt=0.8), lambda t: t.play(FadeIn(t_def, shift=UP * 0.2), rt=0.7)]
    phases += [(lambda c: (lambda t: t.play(FadeIn(c, shift=UP * 0.2), rt=0.6)))(c) for c in cards]
    run_phases(steps, phases)


@template(category="text", use_for="a key idea or take-home message that must stick, said in a few words",
          example={"args": {"lines": ["Con k bit si scrivono 2ᵏ stringhe", "Ogni bit in più raddoppia le possibilità"]},
                   "say": ["Ecco l'idea da ricordare.", "Ogni bit in più raddoppia le possibilità."]})
def statement(ctx, steps, lines: list[str]):
    """Big centered sentences, one per phase; the first is the strongest. Markup allowed (<sup>, <sub>, <b>).
    Phases: one per sentence."""
    from ..style import MT
    mobs = []
    for k, line in enumerate(lines):
        m = MT(line, 48 if k == 0 else 40, style.PRIMARY if k == 0 else style.TEXT, bold=(k == 0))
        mobs.append(style.fit(m, ctx.area.width - 0.6))
    ctx.place(VGroup(*mobs).arrange(DOWN, buff=0.6))
    run_phases(steps, [(lambda m: (lambda t: t.play(FadeIn(m, shift=UP * 0.2), rt=0.8)))(m) for m in mobs])


@template(category="text", use_for="the closing recap (or a check in the middle): each question is asked, the "
          "viewer thinks (pause on its piece), then the answer appears",
          example={"title": "Riepilogo", "args": {"questions": [["Quanti simboli, minimo?", "Due: 0 e 1"],
                                                                 ["Quante stringhe con k bit?", "2ᵏ"]]},
                   "say": [{"say": "Prima domanda: quanti simboli servono, come minimo?", "pause": 3}, "Due, zero e uno.",
                           {"say": "Seconda: quante stringhe si scrivono con kappa bit?", "pause": 3}, "Due alla kappa."]})
def recap_quiz(ctx, steps, questions: list[list[str]]):
    """Questions with their answers: questions[i] = [question, answer]. Each question appears highlighted,
    then its answer. Phases: question 1, answer 1, question 2, answer 2, ..."""
    from ..style import MT
    qs, ans, rows = [], [], []
    qw = ctx.area.width * 0.58
    for q, a in questions:
        qm = text_box(q, qw, style.TEXT_SIZE)
        am = style.fit(MT(a, style.TEXT_SIZE, style.SECONDARY, bold=True), ctx.area.width - qw - 0.8)
        am.next_to(qm, RIGHT, buff=0.6)
        qs.append(qm)
        ans.append(am)
        rows.append(VGroup(qm, am))
    group = VGroup(*rows).arrange(DOWN, buff=0.45, aligned_edge=LEFT)
    for qm, am in zip(qs, ans):
        am.align_to([group.get_left()[0] + qw + 0.6, 0, 0], LEFT)
    ctx.place(group, at="top", buff=0.1)
    phases = []
    for k, (qm, am) in enumerate(zip(qs, ans)):
        phases.append((lambda k, qm: lambda t: t.play(FadeIn(qm, shift=RIGHT * 0.2),
                                                      *focus_anims(qs[:k], -1, 0.6), rt=0.5))(k, qm))
        phases.append((lambda am: lambda t: t.play(FadeIn(am, scale=0.9), rt=0.5))(am))
    run_phases(steps, phases)


@template(category="text", use_for="make the viewer commit to a prediction before the answer: a question with "
          "options, a pause (on its piece), then the right option revealed and explained",
          example={"args": {"question": "Con 3 bit, quante stringhe diverse?", "options": ["3", "6", "8", "9"],
                            "correct": 2, "explanation": "2 · 2 · 2 = 8"},
                   "say": [{"say": "Con tre bit, quante stringhe diverse si possono scrivere?", "pause": 3},
                           "La risposta è otto.", "Due possibilità per ogni bit: due per due per due."]})
def predict(ctx, steps, question: str, options: list[str], correct: int, explanation: str | None = None):
    """A multiple-choice question; then the correct option (0-based index) is marked and the others dimmed;
    then an optional explanation. Phases: question and options, reveal, explanation."""
    if not 2 <= len(options) <= 6 or not 0 <= correct < len(options):
        raise ValueError("predict: 2 to 6 options and `correct` the 0-based index of one of them")
    q = text_box(question, ctx.area.width - 0.6, 44, bold=True, align="center")
    letters = "ABCDEFGH"
    cards = VGroup(*[box(f"{letters[k]}   {o}", w=min(5.8, (ctx.area.width - 0.6) / min(len(options), 2) - 0.4),
                         h=1.2, color=style.MUTED, fill=style.NEUTRAL_SOFT, bold=False)
                     for k, o in enumerate(options)])
    cards.arrange_in_grid(cols=2 if len(options) > 2 else len(options), buff=0.35)
    parts = [q, cards]
    ex = text_box(explanation, ctx.area.width - 1, style.TEXT_SIZE, style.MUTED) if explanation else None
    if ex is not None:
        parts.append(ex)
    ctx.place(VGroup(*parts).arrange(DOWN, buff=0.55))

    def ask(t):
        t.play(FadeIn(q, shift=UP * 0.2), rt=0.5)
        t.play(*[FadeIn(c, shift=UP * 0.2) for c in cards], rt=0.6)

    def reveal(t):
        good = cards[correct]
        mark = check().scale(0.7).move_to(good[0].get_right() + LEFT * 0.55)
        t.play(*[c.animate.set_opacity(0.35) for k, c in enumerate(cards) if k != correct],
               good[0].animate.set_stroke(style.POSITIVE, 5).set_fill(style.POSITIVE_SOFT, 1),
               good[1].animate.set_color(style.POSITIVE), Create(mark), rt=0.7)

    phases = [ask, reveal] + ([lambda t: t.play(FadeIn(ex, shift=UP * 0.2), rt=0.6)] if ex is not None else [])
    run_phases(steps, phases)
