SCENES: TEMPLATE BLOCKS
The scene of a segment is a list of BLOCKS, played in order. A block is one template filled with data,
with an optional title and the narration pieces said while it is on screen:

  {"template": "bullets", "title": "Perché due simboli",
   "args": {"items": ["Due livelli si distinguono bene", "Il rumore non li confonde"]},
   "say": ["Primo: due livelli di tensione si distinguono facilmente.", "Secondo: il rumore non li confonde."]}

- "say": the narration of the block (see NARRATION FORMAT), usually one piece per phase of the template
  (each template says its phases); fewer or more pieces also work.
- "title": the screen title; it stays on screen while consecutive blocks keep the same title. Omit it for
  full-screen blocks (title_card, question, statement, page...).
- Between blocks the previous content fades out; "keep": true keeps it (rarely needed).
- Choose the template that teaches the content best (teaching guidelines), not the first that fits; vary
  them along the lesson. Texts on screen are short (key words, labels, formulas), the voice explains.
- The visual language of the lesson tells which theme colors mean what; templates already use the theme.

TEMPLATES (name(arguments), when to use it, phases, an example):
$templates

YOUR OWN TEMPLATES
When no template fits (a special animation, a process that must move, a diagram of its own), write one
with define_template, then use it in blocks like any other. It is Python for Manim Community 0.22:

from lezio.scene import *

@template(use_for="a binary counter ticking up")
def binary_counter(ctx, steps, bits: int = 4, upto: int = 5):
    """A row of bits counting from 0 to upto, one value per phase."""
    cells = VGroup(*[box("0", w=1.1, h=1.1, size=48, font=MONO) for _ in range(bits)]).arrange(RIGHT, buff=0.2)
    ctx.place(cells, height=2)
    def show(n):
        def run(t):
            if n == 0:
                t.play(FadeIn(cells), rt=0.6)
            digits = format(n, f"0{bits}b")
            t.play(*[Transform(c[1], T(d, 48, PRIMARY, font=MONO).move_to(c[1])) for c, d in zip(cells, digits)], rt=0.5)
        return run
    run_phases(steps, [show(n) for n in range(upto + 1)])

- `def name(ctx, steps, <args with type annotations>)`, decorated with @template(...); the args are what
  blocks pass in "args". Build mobjects first; add and animate them inside the phases (t = steps(), or
  run_phases(steps, phases) to spread phases over the block's pieces). Lay out inside ctx.area with
  ctx.place(...). Fade out nothing at the end: the next block does it.
- Imports allowed: manim, numpy, math, random, itertools, colorsys, lezio.scene. No files, no `config`,
  no ImageMobject/SVGMobject (use ctx.material.page / figure), no add_sound.
- House style: colors, fonts and sizes from the theme by name (PRIMARY, HIGHLIGHT, TEXT, FONT, HAND,
  TEXT_SIZE, ...), never fixed colors.
- Frame: x from -7.1 to 7.1, y from -4 to 4. Text does not wrap (text_box wraps to a width); there is NO
  LaTeX (MathTex and Tex fail): formulas with MT and <sup>/<sub> - MT("2<sup>k-1</sup>") - and Unicode
  symbols (×, ÷, ≤, ≥, ≠, √, π, →, ∑, ⌈ ⌉), never Unicode superscript letters (ᵏ ⁿ ⁻); do not animate the same
  mobject twice in one t.play; Transform keeps the first mobject on screen.

API FOR YOUR TEMPLATES
$api
