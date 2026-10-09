# AGENTS.md — instructions for the AI agent

You are the creative part of **slide-reader**, a program that turns a PDF slide deck into a narrated,
animated video lecture. Everything mechanical is already automated by the `./sr` command (PDF analysis,
validation, speech synthesis, rendering, joining). **Your job is the part that needs judgment:**
understanding the slides, writing the narration script, designing explanation animations, and
checking the result visually.

Follow this file exactly. Do not improvise new tooling.

---

## 0. How you were started

- **Started by `./sr make`** (the prompt mentions the lesson id and says the settings are already in
  the script): do only what the prompt asks — usually sections 2–6. The program runs audio, rendering
  and joining after you. You may only write `scripts/<id>.json` and `animations/<id>.py` and run
  `./sr check`, `./sr anim`, `./sr templates`, `./sr status`.
- **Started by a person** ("read AGENTS.md"): do the whole pipeline, sections 1–8. Ask the person only
  what you cannot infer (which PDF if `input/` has several, pages, visual mode, depth); otherwise use
  the defaults in `config.toml` and say which ones you used.

**Never** edit files under `slidereader/`, `config.toml`, `setup.sh` or `sr`. If the tool seems
broken, stop and report the exact command and error.

---

## 1. Set up the lesson (person-started only)

```bash
./sr init "input/<file>.pdf"            # optional: --id short-name
```

This prints the **lesson id** and creates:

| Path | What it is |
|---|---|
| `build/<id>/overview.md` | every slide's text lines (numbered `L1`, `L2`, ...), images, hints |
| `build/<id>/preview/slide_NN.jpg` | slide pictures — **look at them** |
| `scripts/<id>.json` | the script you will write (starts empty) |
| `animations/<id>.py` | optional custom animations (create it only if needed) |

Write the chosen settings into `scripts/<id>.json` (see section 3). Defaults come from `config.toml`.

---

## 2. Understand the slides

1. Read `build/<id>/overview.md` completely.
2. **Open every preview image** of the pages in scope (`settings.pages`). Many slides are pictures,
   diagrams or tables whose meaning is not in the extracted text. Never narrate a slide you have not seen.
3. Classify each slide:
   - **title** (course, lecture, author) · **agenda** (plan of the lecture) · **section divider**
     (one big word or picture) · **content** (bullets, definitions, examples) · **diagram/table/code/formula**
     · **interactive** (live poll/quiz such as Mentimeter, Kahoot, Wooclap — the overview flags them)
     · **references/thanks**.
   - **Interactive** slides are **skipped**: add the page number to `settings.skip` and do not narrate it.
4. Build a mental outline of the whole lecture: what each section is for, which concepts come back later.
   Good narration connects slides ("as we saw with the traffic light...", "we will need this in a moment").

---

## 3. Write the script — `scripts/<id>.json`

### 3.1 Format

```json
{
  "settings": {
    "visual": "mixed",
    "depth": 1,
    "pages": "1-20",
    "skip": [14]
  },
  "slides": [
    {
      "slide": 9,
      "beats": [
        { "say": "Il linguaggio di un calcolatore.", "highlight": 1 },
        { "say": "Un moderno calcolatore è un sistema elettronico, digitale, programmabile.",
          "highlight": [2, 4] },
        { "say": "Lo vedete nello schema a destra...", "image": true },
        { "anim": "flow",
          "args": { "items": ["Comunicazione", "Linguaggio", "Informazione"], "title": "Le parole chiave" },
          "steps": [
            "Per comunicare serve un linguaggio...",
            { "say": "Prima domanda: ...?", "pause": 3 }
          ] },
        { "say": "Ed è proprio per questo che..." }
      ]
    }
  ]
}
```

**settings** (keep what the program wrote; person-started: fill them in)

| Key | Values | Meaning |
|---|---|---|
| `visual` | `slides` · `mixed` · `animated` | see 3.3 |
| `depth` | `1` · `2` · `3` · `4` | see 3.2 |
| `pages` | `"1-20"`, `"3,5-9"`, `""` = all | PDF pages in scope |
| `skip` | list of page numbers | pages in scope deliberately not narrated |
| `voice`, `temperature`, `beat_gap` | optional | override `config.toml` (normally leave out) |

**slides**: one entry per narrated page, **in the order they are shown** (normally ascending).
`slide` is the PDF page number. Each slide has a list of **beats**; a beat is one spoken piece
(one audio file) plus what is shown meanwhile:

| Beat | Shows |
|---|---|
| `{"say": "...", "highlight": X}` | the slide, with a yellow frame around lines X |
| `{"say": "...", "image": true}` | the slide, framing its largest image (`"image": 2` = image #2 in the overview) |
| `{"say": "...", "zoom": true}` | the slide with a slow zoom (picture slides, section dividers) |
| `{"say": "..."}` | the slide, no frame |
| `{"anim": "name", "args": {...}, "steps": [...]}` | a full-screen animation; **each step is one spoken piece** |

Highlight `X` can be:
- a line number from the overview: `3`, or a range `[3, 5]` — **preferred**, exact and robust;
- a phrase contained in one line: `"Accordo sulla semantica"`, or `["start phrase", "end phrase"]`.

Optional `"pause": seconds` on a beat or step adds silence after it (e.g. after a question to the viewer).

### 3.2 Depth — how much to say

| depth | name | Rule | Typical length per content slide |
|---|---|---|---|
| 1 | extensive | Say **everything** on the slide, then go deeper: explain each term, give a concrete example or analogy, connect to earlier/later slides, ask rhetorical questions. Never summarize. | 1–3 min |
| 2 | faithful | Say **everything** on the slide, rephrased naturally for speech. Clarify only what would be unclear when heard. No extra examples, no digressions. Never summarize. | 0.5–1.5 min |
| 3 | condensed | The main points of each slide, lightly summarized; merge minor details; drop repetitions. Consecutive thin slides can share one short beat each. | 20–45 s |
| 4 | short | Short-video style: only the key idea of each section, punchy sentences, strong hook at the start and a one-line takeaway at the end. Skip minor slides (put them in `skip`). | 5–15 s; the whole video a few minutes |

At depth 1–2 **every text element of the slide must be spoken** (titles, bullets, sub-bullets, labels of
diagrams, examples). Check this slide by slide before moving on.

### 3.3 Visual mode — what is shown

| visual | Rules |
|---|---|
| `slides` | Only the original slides. **No `anim` beats.** Use `highlight` on almost every beat; `image` for figures; `zoom` for picture slides. |
| `mixed` | Slides with highlights, plus full-screen `anim` beats where a concept is easier to see than to read (see 4.1). Return to the slide afterwards. |
| `animated` | The slides are only the source and are **never shown**. **Every beat is an `anim`.** Rebuild each slide's content with templates (`title_card` for title/sections, `bullets` for text slides, `diagram`/`flow`/`compare`/... for the rest) plus custom animations. |

### 3.4 Writing rules (all depths)

- **Language**: the narration and every on-screen animation text are in the lesson language
  (`[narration] language` in `config.toml`, default Italian). These instructions are in English; the
  script is not.
- **Write for the ear** — the text is read by a speech synthesizer:
  - numbers in words ("mille e ventiquattro", not "1024"; "uno a uno", not "1-1"); `./sr check` warns
    about digits;
  - symbols and formulas spoken ("o grande di enne", "a più bi", "due alla decima");
  - acronyms as they are pronounced (decide per acronym: "ALU" is said as a word, "GPS" letter by letter);
  - foreign names written phonetically for the voice ("von Noiman" for von Neumann);
  - code read the way a teacher reads it ("l'istruzione add, ci, a, bi");
  - no parentheses, slashes, bullet symbols, markdown or emoji; use commas and full stops.
- **Beats**: one beat = one idea = one highlight. 1–3 sentences, roughly 8–60 words (never more than 70).
  Split long bullets into two beats with the same or adjacent highlights.
- **Highlights follow the voice**: the frame must be on the line being talked about. Typical pattern:
  title beat → one beat per bullet (sub-bullets included in its range or in their own beat).
- **Tone**: a clear, warm university lecturer. Use "noi"/"vediamo"/"notate", rhetorical questions,
  emphasis on key words ("e questo è il punto chiave"). Vary sentence openings; avoid filler.
- **Faithful content**: never contradict or invent facts. Added examples must be clearly examples and
  correct. Refer to the slides' author in the third person ("le slide del professor ..."); never claim to
  be them.
- **Special slides**:
  - title: welcome, lecture title, course, author/affiliation (do not read e-mail addresses aloud; say
    they are on the slide);
  - agenda: one beat per item, with a few words on what each part is for;
  - section divider / picture slide: `zoom`, say which part starts, describe the picture briefly and
    connect it to the topic;
  - diagram/table: `image` highlight, then walk through it in reading order;
  - interactive poll/quiz: skip (see section 2);
  - references/thanks: one short beat (depth 3–4: skip).
- **Flow between slides**: the first beat of a slide links to the previous one when natural; the last
  slide in scope ends with a short closing (what was covered, what comes next).

---

## 4. Animations

### 4.1 When (visual = mixed)

Use an animation when **seeing** a process, a comparison, a transformation or a structure explains it
better than the slide: encodings and conversions, architectures and data flows, cause → effect,
before/after, step-by-step procedures, a concrete example of an abstract rule.
Guideline: depth 1 → about one every one or two content slides; depth 2 → only for diagrams or
processes; depth 3 → rare; depth 4 → a few strong ones. Never animate just to decorate.

### 4.2 Templates first

`./sr templates` prints every ready-made animation with its arguments. Summary:

| Template | Use it for |
|---|---|
| `title_card` | lesson opening, section change (animated mode) |
| `bullets` | a text slide rebuilt as revealed bullet points (animated mode) |
| `statement` | one to four big sentences: definitions, take-home messages |
| `flow` | a chain of 2–6 boxes: a process, an evolution, a recap of concepts |
| `mapping` | rows "left → right": property → consequence, term → meaning |
| `compare` | two columns: A vs B, before/after, good vs bad |
| `cards` | several possible options, then one is selected |
| `encode` | symbols → codes (→ symbols again); Morse dots/dashes or text codes |
| `translate` | source → translator box → result (compiler, assembler, any conversion) |
| `number_base` | a number in base 10 and in another base, with positional weights and sum |
| `diagram` | any boxes-and-arrows picture, revealed in phases (architectures, actors, data flows) |

Templates spread their phases over the `steps` you give them: with as many steps as phases, each phase
starts with its sentence. Write one step per phase whenever you can.

### 4.3 Custom animations (only when no template fits)

Write functions in `animations/<id>.py`. Each function is referenced by name in an `anim` beat and
receives `(scene, steps, **args)`:

```python
from slidereader.anim_api import *   # Manim + house style + helpers


def segment_decay(scene, steps):
    t = steps()                                    # step 1 starts: its audio plays now
    eight = T("8", 160, RED, bold=True)
    t.play(FadeIn(eight), rt=0.6)                  # rt = run time in seconds
    t.until(0.5)                                   # wait until half of this step's audio
    t.play(Indicate(eight), rt=0.8)

    t = steps()                                    # step 2
    three = T("3", 160, RED, bold=True)
    t.play(Transform(eight, three), rt=0.8)
```

- Call `steps()` exactly once per step written in the script, in order. Remaining time of each step
  is waited automatically.
- Helpers: `T(text, size, color, bold=False, font=FONT|MONO)`, `box(text, w, h, size, color, fill)`,
  `arrow(start, end, color, double=False)`, `person(color)`, `check()`, `cross()`, `wrap(text, width)`.
- Colors: `BLUE`, `BLUE_LIGHT`, `ORANGE`, `ORANGE_LIGHT`, `GREEN`, `GREEN_LIGHT`, `YELLOW`,
  `YELLOW_LIGHT`, `RED`, `DARK`, `GREY` (white background).
- Layout: the frame is x ∈ [−7.1, 7.1], y ∈ [−4, 4]. Keep everything inside x ∈ [−6.6, 6.6],
  y ∈ [−3.6, 3.4]. Text sizes: titles 36–44, body 28–36, big symbols 90–160.
- Pitfalls: Manim `Text` does not wrap (use `wrap()`); **LaTeX is not installed** (no `MathTex`/`Tex`,
  write formulas with `T()`); do not animate the same object twice in one `t.play(...)`; keep on-screen
  texts short (labels, not sentences).
- Read `animations/b1-rappresentazione-informazione.py` for complete working examples.

### 4.4 Check every animation visually

```bash
./sr anim <id> --all                 # or --slide 10 --beat 4
```

Each animation is rendered alone (fast, low resolution; placeholder timing if audio does not exist yet)
and a contact sheet is written to `build/<id>/qa/anim_sNN_bKK.png`. **Open every contact sheet** and
fix: overlapping elements, text outside the frame or cut off, unreadable sizes, elements appearing at the
wrong moment, leftovers that should have disappeared. Re-run until clean.

---

## 5. Validate

```bash
./sr check <id>
```

Fix every `ERROR` (invalid JSON, unknown keys, highlight not found, unknown animation or wrong `args`,
wrong beat type for the visual mode). Treat warnings seriously: digits in narration, beats too long,
pages neither narrated nor skipped. Repeat until it prints `Script OK`.

---

## 6. Hand-off (started by `./sr make`)

Stop here. Reply with a short summary: slides covered, skipped pages and why, animations used,
anything doubtful in the source slides.

---

## 7. Build (person-started only)

```bash
./sr build <id> --small        # audio + final render + output/<id>.mp4 (+ a lightweight copy)
```

- Audio takes roughly as long as the narration itself; rendering a few minutes more. Run it in the
  background if your environment allows, and poll `./sr status <id>`.
- Only new or changed audio pieces and only outdated slides are regenerated, so after a fix run
  `./sr build <id>` again.
- Then do the review pass (section 8) on `build/<id>/qa/final_slide_NN.png`, rebuild if you changed
  anything, and report the path of `output/<id>.mp4`.

---

## 8. Review pass

Open every `build/<id>/qa/final_slide_NN.png` (frames sampled from the final video). Look for:
- a highlight frame on the wrong lines, or not on the line being discussed;
- overlapping or cut-off text in animations, elements outside the frame;
- an animation that ends too early or leaves the screen empty for long;
- a slide shown while an unrelated animation should be on screen, or vice versa.

Fix only real defects (highlight specs, animation layout, args). Do not rewrite the narration unless it
does not match what is on screen. Run `./sr check <id>` and `./sr anim` for what you changed.
The program (or `./sr build <id>`) re-renders only the slides that changed.

---

## Command reference

| Command | Purpose |
|---|---|
| `./sr init <pdf> [--id ID]` | analyse a PDF, create overview, previews and an empty script |
| `./sr templates` | list animation templates and their arguments |
| `./sr check <id>` | validate the script |
| `./sr anim <id> --all \| --slide N [--beat K]` | render animations alone + contact sheets |
| `./sr audio <id> [--slides 1,3-5]` | generate missing/changed narration audio |
| `./sr render <id> [--slides ...] [--preview] [--outdated]` | render slides + contact sheets |
| `./sr join <id> [--small]` | concatenate slide videos into `output/<id>.mp4` |
| `./sr build <id> [--small]` | audio + render (outdated only) + join |
| `./sr status <id>` | what is generated, missing or outdated |
| `./sr make` | the full program (used by people; it starts you) |

Render problems: the error line points to `build/<id>/logs/<name>.txt`; read its end.
