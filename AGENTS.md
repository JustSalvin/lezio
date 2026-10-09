# AGENTS.md — reference for agent tasks

**slide-reader is a program, not an agent workflow.** The program (`./sr make`) runs the whole process:
it reads the PDF, splits the work, validates everything, synthesizes the voice, renders and edits the
video. It calls an AI agent only for the steps that need judgment, **one narrow task at a time**:

| Task | The agent receives | The agent writes |
|---|---|---|
| plan | overview of the slides, slide pictures | `build/<id>/agent/plan.json` |
| write | one group of 3–5 slides (text lines, pictures, plan notes, context) | `build/<id>/agent/group_NN.json` (+ optional `animations/<id>/group_NN.py`) |
| fix | a list of problems found by the program | the file named in the task |
| judge animations | contact sheets of the rendered animations | a verdict JSON (+ fixes) |
| review | contact sheets of the final video | a verdict JSON (+ fixes in the script) |

The task prompt always names the sections of this file to read, the inputs, and the **only files you may
write**. You cannot run commands: the program validates and renders after you, and sends problems back
in a fix task. Do exactly the task, write the output file, reply with one short line, stop.

All instructions here are in English; **everything you write for the video (narration, on-screen texts)
is in the lesson language** given in the task (default Italian).

---

## 1. Inputs you can read

| Path | Content |
|---|---|
| `build/<id>/overview.md` | every page: text lines numbered `L1, L2, ...` (repeated headers/footers removed), images, hints |
| `build/<id>/preview/slide_NN.jpg` | picture of page NN — **open the ones of your task**; many slides are pictures or diagrams |
| `build/<id>/agent/plan.json` | the lesson plan (after the plan task) |
| `scripts/<id>.json` | the script assembled so far by the program |
| `slidereader/templates.py` | animation templates with full argument documentation |
| `animations/b1-rappresentazione-informazione.py` | complete examples of custom animations |
| `scripts/b1-rappresentazione-informazione.json` | a complete example script (visual `mixed`, depth 1, Italian) |

---

## 2. Plan task

Read the overview and **open every slide picture in scope**. Then write the plan file:

```json
{
  "title": "Rappresentazione dell'informazione",
  "outline": "Three to six sentences: what the lecture is about, its parts, how they connect.",
  "slides": [
    {"slide": 1, "kind": "title", "skip": false, "summary": "Course, lecture title and author.", "visual_idea": "none"},
    {"slide": 10, "kind": "diagram", "skip": false,
     "summary": "Harvard vs von Neumann: separate memories vs a single memory.",
     "visual_idea": "custom: the two memories merge; one word read as number or instruction"},
    {"slide": 14, "kind": "interactive", "skip": true, "summary": "Mentimeter quiz.", "visual_idea": "none"}
  ]
}
```

- One entry per page in scope, in page order. `kind`: `title`, `agenda`, `divider`, `content`, `diagram`,
  `interactive`, `references`, `other`.
- `skip: true` for interactive slides (live polls/quizzes: Mentimeter, Kahoot, Wooclap, Slido...) and,
  at depth 4, for minor slides. Everything else `false`.
- `summary`: one sentence on what the slide says (it is given to the writer of neighbouring slides).
- `visual_idea`: `none`, `template <name>: <what it shows>` or `custom: <what it shows>` (see section 5).
  Visual mode `slides`: always `none`. Mode `animated`: never `none`.

---

## 3. Script format (write task)

A group file is `{"slides": [ ... ]}` with exactly the slides of the task, in the given order:

```json
{
  "slides": [
    {
      "slide": 9,
      "beats": [
        {"say": "Il linguaggio di un calcolatore.", "highlight": 1},
        {"say": "Un moderno calcolatore è un sistema elettronico, digitale, programmabile.", "highlight": [2, 4]},
        {"say": "Lo vedete nello schema a destra.", "image": true},
        {"anim": "flow",
         "args": {"items": ["Programma", "Istruzioni", "Memoria"], "title": "Dal programma alla memoria"},
         "steps": ["Prima frase della spiegazione animata...", {"say": "E voi, che cosa ne pensate?", "pause": 2}]},
        {"say": "Ed è proprio per questo che..."}
      ]
    }
  ]
}
```

A **beat** is one spoken piece (one audio file) plus what is shown meanwhile:

| Beat | Shows |
|---|---|
| `{"say": ..., "highlight": X}` | the slide with a yellow frame around lines X |
| `{"say": ..., "image": true}` | the slide, framing its largest image (`"image": 2` = image #2 of the overview) |
| `{"say": ..., "zoom": true}` | the slide with a slow zoom (picture slides, section dividers) |
| `{"say": ...}` | the slide, no frame |
| `{"anim": name, "args": {...}, "steps": [...]}` | a full-screen animation; **each step is one spoken piece** |

- Highlight `X`: a line number of the overview (`3`) or a range (`[3, 5]`) — preferred; or exactly some
  lines (`{"lines": [2, 4, 6]}`, e.g. one column of a two-column table, whose lines the overview lists
  interleaved); or a phrase contained in one line (`"Accordo sulla semantica"`) or
  `["start phrase", "end phrase"]`. The frame is the rectangle enclosing the chosen lines.
- `"pause": seconds` on a beat or step adds silence after it.
- Keys are exactly these; anything else is rejected by the program.

**Visual mode rules**

| visual | Rules |
|---|---|
| `slides` | no `anim` beats; highlight almost every beat; `image` for figures; `zoom` for picture slides |
| `mixed` | slides with highlights + `anim` beats where seeing beats reading (section 5); then back to the slide |
| `animated` | **every beat is an `anim`**; the slide is never shown — rebuild its content with `title_card`, `bullets`, `diagram`, `flow`, ... and custom animations |

---

## 4. Writing rules (write task)

### 4.1 Depth

| depth | Rule | Typical length per content slide |
|---|---|---|
| 1 extensive | Say **everything** on the slide, then go deeper: explain each term, give a concrete example or analogy, connect to earlier/later slides, ask rhetorical questions. Never summarize. | 1–3 min |
| 2 faithful | Say **everything** on the slide, rephrased naturally for speech. Clarify only what would be unclear when heard. No extra examples. Never summarize. | 0.5–1.5 min |
| 3 condensed | Main points of each slide, lightly summarized; merge minor details; drop repetitions. | 20–45 s |
| 4 short | Short-video style: the key idea only, punchy sentences, a hook at the start, a one-line takeaway at the end. | 5–15 s |

At depth 1–2 **every text element of the slide is spoken**: title, bullets, sub-bullets, labels of
diagrams, examples. Check each slide line by line against the overview before finishing.

### 4.2 Write for the ear (the text is read by a speech synthesizer)

- Numbers in words ("mille e ventiquattro", "uno a uno"). **Digits are rejected by the program.**
- Symbols and formulas spoken ("o grande di enne", "a più bi", "due alla decima").
- Acronyms as pronounced: decide per acronym ("ALU" as a word, "GPS" letter by letter).
- Foreign names written phonetically ("von Noiman" for von Neumann).
- Code read like a teacher reads it ("l'istruzione add, ci, a, bi").
- No parentheses, slashes, bullet symbols, markdown or emoji: commas and full stops only.

### 4.3 Beats and highlights

- One beat = one idea = one highlight. 1–3 sentences, about 8–60 words (more than 70 is rejected).
- The frame must be on the line being talked about: title beat, then one beat per bullet (a bullet and
  its sub-bullets together, or sub-bullets in their own beats).
- Prefer line numbers from the overview for highlights.

### 4.4 Tone and content

- A clear, warm university lecturer: "vediamo", "notate", rhetorical questions, emphasis on key points.
  Vary sentence openings, no filler.
- Never contradict or invent facts. Added examples must be correct and clearly examples.
- Refer to the slides' author in the third person; never claim to be them.
- Special slides: **title** — welcome, lecture title, course, author (do not read e-mail addresses,
  say they are on the slide); **agenda** — one beat per item; **divider/picture** — `zoom`, say which part
  starts, describe the picture briefly; **diagram/table** — `image`, then walk through it in reading
  order; **references** — one short beat.
- Continuity: the task tells you how the previous slide ended and what comes next. Link naturally; do not
  welcome again after the first group; the last group ends with a short closing.

---

## 5. Animations (write task)

### 5.1 When

Use an animation when **seeing** explains better than reading: processes, transformations, encodings,
architectures and data flows, comparisons, cause → effect, a concrete example of an abstract rule.
Depth 1: about one every one or two content slides; depth 2: only for diagrams/processes; depth 3: rare;
depth 4: a few strong ones. Never just decoration. Follow the plan's `visual_idea` unless you find better.

### 5.2 Templates first

Full arguments: docstrings in `slidereader/templates.py`.

| Template | Use it for |
|---|---|
| `title_card` | lecture opening, section change (animated mode) |
| `bullets` | a text slide rebuilt as revealed bullet points (animated mode) |
| `statement` | one to four big sentences: definitions, take-home messages |
| `flow` | a chain of 2–6 boxes: a process, an evolution, a recap |
| `mapping` | rows "left → right": property → consequence, term → meaning |
| `compare` | two columns: A vs B, before/after |
| `cards` | several possible options, then one is selected |
| `encode` | symbols → codes (→ symbols again); Morse dots/dashes or text codes |
| `translate` | source → translator box → result (compiler, assembler, conversion) |
| `number_base` | a number in base 10 and in another base, with weights and sum |
| `diagram` | any boxes-and-arrows picture revealed in phases (coordinates x −6.5..6.5, y −3.5..3.2) |

Templates spread their phases over the steps: give one step per phase whenever possible
(`flow` with four items → four steps).

### 5.3 Custom animations (only when no template fits)

Write them in the animation file named by the task; every function name must start with the prefix
given in the task (e.g. `g03_`). Signature `(scene, steps, **args)`:

```python
from slidereader.anim_api import *   # Manim + house style + helpers


def g03_segment_decay(scene, steps):
    t = steps()                                    # step 1 starts: its audio plays now
    eight = T("8", 160, RED, bold=True)
    t.play(FadeIn(eight), rt=0.6)                  # rt = run time in seconds
    t.until(0.5)                                   # wait until half of this step's audio
    t.play(Indicate(eight), rt=0.8)

    t = steps()                                    # step 2
    t.play(Transform(eight, T("3", 160, RED, bold=True)), rt=0.8)
```

- Call `steps()` exactly once per step of the beat, in order; leftover time is waited automatically.
- Helpers: `T(text, size, color, bold=False, font=FONT|MONO)`, `box(text, w, h, size, color, fill)`,
  `arrow(start, end, color, double=False)`, `person(color)`, `check()`, `cross()`, `wrap(text, width)`.
- Colors: `BLUE`, `BLUE_LIGHT`, `ORANGE`, `ORANGE_LIGHT`, `GREEN`, `GREEN_LIGHT`, `YELLOW`,
  `YELLOW_LIGHT`, `RED`, `DARK`, `GREY`; white background.
- Layout: frame x ∈ [−7.1, 7.1], y ∈ [−4, 4]; keep everything inside x ∈ [−6.6, 6.6], y ∈ [−3.6, 3.4].
  Sizes: titles 36–44, body 28–36, big symbols 90–160.
- Pitfalls: `Text` does not wrap (use `wrap()`); **no LaTeX** (no `MathTex`/`Tex`); do not animate the
  same object twice in one `t.play(...)`; on-screen texts are short labels, not sentences.
- Clean-up is done by the program: never `FadeOut`/`remove` `scene.mobjects` (that list also contains
  the slide). To clear your own elements mid-animation, fade out the groups you created.

---

## 6. Judge animations task

The program rendered each animation of your group alone and gives you contact sheets (frames in time
order, left to right, top to bottom; placeholder timing before the audio exists). Open every sheet and
look for: overlapping elements, text outside the frame or cut off, unreadable sizes, elements that never
appear or never leave, an empty or confusing result, content that does not match the narration.
Fix real defects in the group file (`args`) or in the group's animation file, then write the verdict
`{"changed": true|false, "notes": "..."}`. Do not rewrite narration that is fine.

---

## 7. Review task

The program gives you contact sheets of the final video of a few slides. Look for: a highlight on the
wrong lines, overlaps or cut-off text in animations, a screen left empty for long, an animation that does
not match what is said. Fix only real defects in `scripts/<id>.json` (only the slides of your task) or in
the lesson's animation files, then write the verdict JSON. The program re-validates, regenerates the
changed audio and re-renders only the slides that changed.
