"""The agent tasks: system prompts, messages and the tools through which the model works.

Everything the model needs is here or is passed by the program; the model has no access to files,
commands or the web. Each tool validates what the model submits and answers with "accepted" or with a
precise list of problems, so mistakes are fixed inside the same session.
"""
import ast
import inspect
import json

from .llm import Image, Task, Tool, ToolResult

# ======================================================================== shared knowledge
ROLE = """You are a component of slide-reader, a program that turns PDF slide decks into narrated, animated
video lectures (a synthetic voice reads your script while the slides are shown with highlights, plus
full-screen explanation animations). The program calls you for ONE task. You work only through the tools
you are given; you have no files, shell or web. Submitted work is validated by the program, which answers
"accepted" or lists problems to fix. When a tool tells you the task is complete, stop.
Everything you write for the video (narration, on-screen texts) is in the lesson language given in the
message. If the message contains instructions from the user, they take priority over these rules."""

VISUAL_RULES = {
    "slides": "Only the original slides are shown. NO anim beats. Highlight almost every beat; use image for "
              "figures and zoom for picture slides.",
    "mixed": "The slides are shown with highlights; add full-screen anim beats where seeing explains better "
             "than reading, then go back to the slide.",
    "animated": "The slides are NEVER shown: EVERY beat is an anim. Rebuild each slide's content with templates "
                "(title_card, bullets, diagram, flow, ...) and custom animations.",
}
DEPTH_RULES = {
    1: "EXTENSIVE: say everything on the slide, then go deeper: explain each term, give a concrete example or "
       "analogy, connect to earlier/later slides, ask rhetorical questions. Never summarize. About 1-3 min per "
       "content slide.",
    2: "FAITHFUL: say everything on the slide, rephrased naturally for speech. Clarify only what would be unclear "
       "when heard. No extra examples. Never summarize. About 0.5-1.5 min per content slide.",
    3: "CONDENSED: the main points of each slide, lightly summarized; merge minor details; drop repetitions. "
       "About 20-45 s per slide.",
    4: "SHORT: short-video style, the key idea only, punchy sentences, a hook at the start and a one-line "
       "takeaway at the end. About 5-15 s per slide.",
}

SCRIPT_FORMAT = """SCRIPT FORMAT
A slide entry is {"slide": <page number>, "beats": [...]}. A beat is one spoken piece (one audio file)
plus what is shown meanwhile:
  {"say": "...", "highlight": X}   the slide, with a yellow frame around lines X
  {"say": "...", "image": true}    the slide, framing its largest image ("image": 2 = image #2)
  {"say": "...", "zoom": true}     the slide with a slow zoom (picture slides, section dividers)
  {"say": "..."}                   the slide, no frame
  {"anim": "<name>", "args": {...}, "steps": ["sentence", {"say": "sentence", "pause": 2}, ...]}
                                   a full-screen animation; EACH STEP is one spoken piece
Highlight X: a line number (3), a range ([3, 5]) - preferred -, exactly some lines ({"lines": [2, 4, 6]},
e.g. one column of a two-column table whose lines are listed interleaved), or a phrase contained in one
line ("Accordo sulla semantica") / ["start phrase", "end phrase"]. Line numbers are the L-numbers given
in the message. "pause": seconds of silence after a beat or step. No other keys are allowed.

Example (Italian lesson):
{"slide": 9, "beats": [
  {"say": "Il linguaggio di un calcolatore. Notate le virgolette attorno alla parola linguaggio.", "highlight": 1},
  {"say": "Un moderno calcolatore è un sistema elettronico, digitale, programmabile.", "highlight": [2, 4]},
  {"anim": "flow", "args": {"items": ["Programma", "Istruzioni", "Dati", "Memoria"], "title": "Dentro la macchina"},
   "steps": ["Il programma è fatto di istruzioni,", "che lavorano sui dati,", "e tutto finisce in memoria.",
             "Scritto con zeri e uni."]},
  {"say": "E qui nasce una domanda: come vengono codificate le istruzioni?", "highlight": 5}]}"""

WRITING_RULES = """WRITING RULES
Write for the ear - a speech synthesizer reads the text:
- numbers in words ("mille e ventiquattro", "uno a uno"): digits are REJECTED by the program;
- symbols and formulas spoken ("o grande di enne", "a più bi", "due alla decima");
- acronyms as pronounced (decide per acronym: "ALU" as a word, "GPS" letter by letter);
- foreign names written phonetically ("von Noiman" for von Neumann); code read like a teacher would
  ("l'istruzione add, ci, a, bi");
- no parentheses, slashes, bullet symbols, markdown or emoji: commas and full stops only.
Beats: one beat = one idea = one highlight; 1-3 sentences, about 8-60 words (more than 70 is rejected).
The frame must be on the line being talked about: title beat, then one beat per bullet (with its
sub-bullets, or sub-bullets in their own beats).
Tone: a clear, warm university lecturer ("vediamo", "notate", rhetorical questions, emphasis on key
points); vary sentence openings; no filler. Never contradict or invent facts; added examples must be
correct and clearly examples. Refer to the slides' author in the third person.
Special slides: title -> welcome, lecture title, course, author (do not read e-mail addresses, say they are
on the slide); agenda -> one beat per item; section divider / picture -> zoom, say which part starts,
describe the picture briefly; diagram/table -> image highlight, then walk through it in reading order;
references -> one short beat.
At depth 1-2 EVERY text element of the slide must be spoken (title, bullets, sub-bullets, diagram labels,
examples): check slide by slide against the numbered lines before submitting."""

ANIMATION_RULES = """ANIMATIONS
Use an animation when SEEING explains better than reading: processes, transformations, encodings,
architectures and data flows, comparisons, cause -> effect, a concrete example of an abstract rule.
Depth 1: about one every one or two content slides; depth 2: only for diagrams/processes; depth 3: rare;
depth 4: a few strong ones. Never just decoration. Prefer templates; templates spread their phases over
the steps, so give one step per phase (flow with four items -> four steps).

TEMPLATES (name(arguments) and what they do):
{templates}

CUSTOM ANIMATIONS - only when no template fits. Submit them as `animation_code` (Python source) with
submit_script; every function name must start with the prefix given in the message. Example:

from slidereader.anim_api import *   # Manim + house style + helpers

def {prefix}segment_decay(scene, steps):          # used as {"anim": "{prefix}segment_decay", "steps": [s1, s2]}
    t = steps()                                    # step 1 starts: its audio plays now
    eight = T("8", 160, RED, bold=True)
    t.play(FadeIn(eight), rt=0.6)                  # rt = run time in seconds
    t.until(0.5)                                   # wait until half of this step's audio
    t.play(Indicate(eight), rt=0.8)
    t = steps()                                    # step 2
    t.play(Transform(eight, T("3", 160, RED, bold=True)), rt=0.8)

- Signature (scene, steps, **args); call steps() exactly once per step, in order; leftover time is
  waited automatically.
- Helpers: T(text, size, color, bold=False, font=FONT|MONO), box(text, w, h, size, color, fill),
  arrow(start, end, color, double=False), person(color), check(), cross(), wrap(text, width).
  Colors: BLUE, BLUE_LIGHT, ORANGE, ORANGE_LIGHT, GREEN, GREEN_LIGHT, YELLOW, YELLOW_LIGHT, RED, DARK, GREY;
  white background. All of Manim is available (VGroup, Arrow, Circle, FadeIn, Transform, LaggedStart, ...).
- Layout: frame x in [-7.1, 7.1], y in [-4, 4]; keep everything inside x in [-6.6, 6.6], y in [-3.6, 3.4].
  Sizes: titles 36-44, body 28-36, big symbols 90-160.
- Pitfalls: Text does not wrap (use wrap()); NO LaTeX (no MathTex/Tex); do not animate the same object twice
  in one t.play(...); on-screen texts are short labels; never FadeOut/remove scene.mobjects (it contains the
  slide) - fade out the groups you created."""


def templates_reference():
    from . import templates
    out = []
    for name, fn in templates.TEMPLATES.items():
        sig = str(inspect.signature(fn)).replace("(scene, steps, ", "(")
        doc = inspect.getdoc(fn).replace("\n", "\n    ")
        out.append(f"- {name}{sig}\n    {doc}")
    return "\n".join(out)


def _sheet_image(png_path):
    """Contact sheet as a compact JPEG for the model."""
    return Image.from_file(png_path, max_width=1440, quality=78)


def _settings_block(run):
    s = run.settings
    from .script_io import DEPTHS, agent_instructions
    text = agent_instructions(s)
    block = f"""Lesson: {run.lesson.id}  (PDF: {run.lesson.pdf.name})
Narration language: {s['language']}
Visual mode: {s['visual']} - {VISUAL_RULES[s['visual']]}
Depth: {s['depth']} ({DEPTHS[s['depth']]}) - {DEPTH_RULES[s['depth']]}"""
    if text:
        block += "\n\nINSTRUCTIONS FROM THE USER (priority over the default rules):\n" + \
                 "\n".join(f"- {line}" for line in text.splitlines())
    return block


def _view_slides_tool(run, allowed):
    def handler(args):
        numbers = args.get("numbers") or []
        bad = [n for n in numbers if n not in allowed]
        if bad or not numbers:
            return ToolResult([f"Choose pages among {allowed}."], error=True)
        content = []
        for n in numbers[:6]:
            content += [f"Slide {n}:", Image.from_file(run.lesson.preview / f"slide_{n:02d}.jpg")]
        if len(numbers) > 6:
            content.append("Only the first 6 are shown; ask for the others in another call.")
        return ToolResult(content)
    return Tool("view_slides", "Show the pictures of some slides (up to 6 per call). Look at every slide you "
                "work on: many slides are pictures, diagrams or tables.",
                {"type": "object", "properties": {"numbers": {"type": "array", "items": {"type": "integer"}}},
                 "required": ["numbers"]}, handler)


# ======================================================================== plan task
KINDS = ("title", "agenda", "divider", "content", "diagram", "interactive", "references", "other")


def plan_task(run):
    scope = run.scope
    system = ROLE + """

TASK: plan the lesson.
Look at every slide in scope (view_slides), then call submit_plan once with:
- title: the lecture title;
- outline: 3-6 sentences on what the lecture is about, its parts and how they connect;
- slides: one entry per page in scope, in page order:
  {"slide": n, "kind": "title|agenda|divider|content|diagram|interactive|references|other",
   "skip": true|false, "summary": "one sentence on what the slide says",
   "visual_idea": "none" | "template <name>: <what it shows>" | "custom: <what it shows>"}
skip = true for interactive slides (live polls/quizzes: Mentimeter, Kahoot, Wooclap, Slido...), at depth 4
for minor slides, and for whatever the user's instructions say to skip; otherwise false.
visual_idea: "none" in visual mode slides; never "none" in visual mode animated. Templates: title_card,
bullets, statement, flow, mapping, compare, cards, encode, translate, number_base, diagram.
The summaries are given to whoever writes the neighbouring slides, so make them informative."""
    lines = []
    for n in scope:
        data = run.lines["slides"][str(n)]
        lines.append(f"Slide {n}: " + (" | ".join(r["text"] for r in data["lines"]) or "(no text)")
                     + (f"  [{len(data['images'])} image(s)]" if data["images"] else ""))
    prompt = _settings_block(run) + f"\n\nPages in scope: {scope[0]}-{scope[-1]} ({len(scope)} pages)\n\n" \
        "Text of the slides (repeated headers/footers removed):\n" + "\n".join(lines)

    def submit(args):
        problems = []
        items = args.get("slides")
        if not isinstance(items, list):
            return ToolResult(["slides must be a list"], error=True)
        numbers = [i.get("slide") for i in items if isinstance(i, dict)]
        if numbers != scope:
            problems.append(f"slides must be exactly the pages {scope} in order (got {numbers})")
        for i in items:
            if isinstance(i, dict) and i.get("kind") not in KINDS:
                problems.append(f"slide {i.get('slide')}: kind must be one of {KINDS}")
            if isinstance(i, dict) and not isinstance(i.get("skip"), bool):
                problems.append(f"slide {i.get('slide')}: skip must be true or false")
        if not str(args.get("outline", "")).strip():
            problems.append("outline is empty")
        if problems:
            return ToolResult(["Plan rejected:"] + [f"- {p}" for p in problems], error=True)
        (run.lesson.agent / "plan.json").write_text(json.dumps(
            {"title": args.get("title", ""), "outline": args["outline"], "slides": items},
            ensure_ascii=False, indent=2))
        return ToolResult(["Plan accepted. The task is complete."], done=True)

    tools = [_view_slides_tool(run, scope),
             Tool("submit_plan", "Submit the lesson plan (validated by the program).",
                  {"type": "object", "properties": {"title": {"type": "string"}, "outline": {"type": "string"},
                                                    "slides": {"type": "array", "items": {"type": "object"}}},
                   "required": ["title", "outline", "slides"]}, submit)]
    return Task("plan", system, prompt, tools, max_turns=30, log_path=run.lesson.agent / "log.jsonl")


# ======================================================================== write task
def write_task(run, items, outline, before, after, note=""):
    from .validate import validate
    numbers = [i["slide"] for i in items]
    first = numbers[0]
    group_file = run.lesson.agent / f"group_{first:03d}.json"
    anim_file = run.lesson.animations_dir / f"group_{first:03d}.py"
    prefix = f"g{first:03d}_"
    state = {"accepted": False, "previews": 0, "previewed_since_submit": False, "has_anims": False}

    system = "\n\n".join([
        ROLE,
        "TASK: write the narration script of a group of slides.\n"
        "1. Look at the slides (view_slides).\n"
        "2. Write their script and call submit_script; fix every reported problem and submit again.\n"
        "3. If the accepted script contains animations, call preview_animations, look at the frames, fix real "
        "defects (overlaps, text cut off or outside the frame, elements that never appear or never leave, "
        "content that does not match the narration) by submitting again, then preview again.\n"
        "4. Call finish.",
        SCRIPT_FORMAT, WRITING_RULES,
        ANIMATION_RULES.replace("{templates}", templates_reference()).replace("{prefix}", prefix),
    ])
    blocks = []
    w, h = run.lines["page_size"]
    for item in items:
        n = item["slide"]
        data = run.lines["slides"][str(n)]
        rows = [f"### Slide {n} ({item['kind']})",
                f"Plan: {item.get('summary', '')}  |  Visual idea: {item.get('visual_idea', 'none')}"]
        rows += [f"L{k}: {r['text']}" for k, r in enumerate(data["lines"], 1)] or ["(no text lines)"]
        rows += [f"image #{k}: {(b[2] - b[0]) * (b[3] - b[1]) / (w * h):.0%} of the slide"
                 for k, b in enumerate(data["images"], 1)]
        blocks.append("\n".join(rows))
    prompt = (_settings_block(run) + f"\n\nLesson outline: {outline}\n\n"
              f"Write the script of slides {numbers}. Custom animation functions must start with \"{prefix}\".\n"
              f"Context: {before}\n{after}\n"
              + (f"\nRequest from the user for these slides: {note}\n" if note else "")
              + "\n" + "\n\n".join(blocks))

    def submit(args):
        slides = args.get("slides")
        if not isinstance(slides, list):
            return ToolResult(["slides must be a list of slide entries"], error=True)
        got = [s.get("slide") for s in slides if isinstance(s, dict)]
        problems = [] if got == numbers else [f"slides must be exactly {numbers} in this order (got {got})"]
        code = args.get("animation_code") or ""
        if code.strip():
            try:
                names = [f.name for f in ast.parse(code).body if isinstance(f, ast.FunctionDef)]
                problems += [f"animation_code: function {f} must start with {prefix}" for f in names
                             if not f.startswith(prefix) and not f.startswith("_")]
            except SyntaxError as e:
                problems.append(f"animation_code: syntax error at line {e.lineno}: {e.msg}")
        if problems:
            return ToolResult(["Rejected:"] + [f"- {p}" for p in problems], error=True)
        if code.strip():
            anim_file.write_text(code)
        else:
            anim_file.unlink(missing_ok=True)
        errors, warnings = validate(run.lesson, run.settings, slides, coverage=False)
        problems = errors + [w for w in warnings if "digits" in w or "words" in w]
        if problems:
            return ToolResult(["Rejected:"] + [f"- {p}" for p in problems[:40]], error=True)
        group_file.write_text(json.dumps({"slides": slides}, ensure_ascii=False, indent=2))
        run.take_group(group_file)
        state.update(accepted=True, previewed_since_submit=False,
                     has_anims=any("anim" in b for s in slides for b in s["beats"]))
        if state["has_anims"]:
            return ToolResult(["Script accepted. Now call preview_animations and check the frames."])
        return ToolResult(["Script accepted (no animations). The task is complete."], done=True)

    def preview(args):
        if not state["accepted"]:
            return ToolResult(["Submit an accepted script first."], error=True)
        limit = run.agent_cfg["animation_rounds"]
        if state["previews"] >= limit:
            return ToolResult([f"Preview limit ({limit}) reached: call finish."], error=True)
        state["previews"] += 1
        beats = [(n, k, b["anim"]) for n in numbers for k, b in enumerate(run.slides[n]["beats"]) if "anim" in b]
        content = ["Frames of each animation in time order (left to right, top to bottom); "
                   "timing is a placeholder until the voice exists."]
        for n, k, name, sheet, err in run.render_animations([(n, k) for n, k, _ in beats], names=[b[2] for b in beats]):
            content.append(f"Slide {n}, beat {k} ({name}):")
            content.append(f"RENDER FAILED: {err}" if err else _sheet_image(sheet))
        state["previewed_since_submit"] = True
        return ToolResult(content)

    def finish(args):
        if not state["accepted"]:
            return ToolResult(["Submit an accepted script first."], error=True)
        if state["has_anims"] and not state["previewed_since_submit"] and state["previews"] < run.agent_cfg["animation_rounds"]:
            return ToolResult(["Preview the animations of the last accepted script first."], error=True)
        (run.lesson.agent / f"group_{first:03d}_notes.txt").write_text(args.get("notes", ""))
        return ToolResult(["Done."], done=True)

    tools = [
        _view_slides_tool(run, run.scope),
        Tool("submit_script", "Submit the script of the group (validated by the program). animation_code: Python "
             "source of the custom animations used by the script (omit if none).",
             {"type": "object", "properties": {"slides": {"type": "array", "items": {"type": "object"}},
                                               "animation_code": {"type": "string"}},
              "required": ["slides"]}, submit),
        Tool("preview_animations", "Render every animation of the accepted script alone and show their frames.",
             {"type": "object", "properties": {}}, preview),
        Tool("finish", "Finish the task.", {"type": "object", "properties": {"notes": {"type": "string"}}}, finish),
    ]
    return Task(f"write slides {numbers}", system, prompt, tools, max_turns=60,
                log_path=run.lesson.agent / "log.jsonl")


# ======================================================================== review task
def review_task(run, numbers):
    from .validate import validate
    state = {"changed": []}
    system = "\n\n".join([
        ROLE,
        "TASK: review the final video of some slides.\n"
        "For each slide call view_final (frames sampled from the rendered video, in time order, left to right, "
        "top to bottom). Look for real defects: a highlight on the wrong lines or not on the line being "
        "discussed, overlapping or cut-off text in animations, a screen left empty for long, an animation that "
        "does not match what is said. Fix a slide by sending its corrected entry with replace_slide (you can "
        "change highlights, template args, beat texts, or replace a broken custom animation with a template; "
        "you cannot edit custom animation code). Do not rewrite narration that is fine. Then call finish.",
        SCRIPT_FORMAT,
        "TEMPLATES:\n" + templates_reference(),
    ])
    current = {n: run.slides[n] for n in numbers}
    blocks = []
    for n in numbers:
        data = run.lines["slides"][str(n)]
        blocks.append(f"### Slide {n}\n" + "\n".join(f"L{k}: {r['text']}" for k, r in enumerate(data["lines"], 1))
                      + "\nScript: " + json.dumps(current[n], ensure_ascii=False))
    prompt = _settings_block(run) + f"\n\nReview slides {numbers}.\n\n" + "\n\n".join(blocks)

    def view_final(args):
        n = args.get("slide")
        if n not in numbers:
            return ToolResult([f"Choose a slide among {numbers}."], error=True)
        return ToolResult([f"Final video of slide {n}:", _sheet_image(run.lesson.qa / f"final_slide_{n:02d}.png")])

    def replace(args):
        entry = args.get("entry")
        if not isinstance(entry, dict) or entry.get("slide") not in numbers:
            return ToolResult([f"entry must be a slide entry of one of {numbers}"], error=True)
        errors, warnings = validate(run.lesson, run.settings, [entry], coverage=False)
        problems = errors + [w for w in warnings if "digits" in w or "words" in w]
        if problems:
            return ToolResult(["Rejected:"] + [f"- {p}" for p in problems], error=True)
        run.slides[entry["slide"]] = entry
        run.save_script()
        state["changed"].append(entry["slide"])
        return ToolResult([f"Slide {entry['slide']} replaced; it will be re-rendered."])

    def finish(args):
        (run.lesson.agent / f"review_{numbers[0]:03d}.json").write_text(json.dumps(
            {"changed": state["changed"], "notes": args.get("notes", "")}, ensure_ascii=False, indent=2))
        return ToolResult(["Done."], done=True)

    tools = [
        Tool("view_final", "Show frames of the final video of one slide.",
             {"type": "object", "properties": {"slide": {"type": "integer"}}, "required": ["slide"]}, view_final),
        _view_slides_tool(run, numbers),
        Tool("replace_slide", "Replace the script entry of one slide (validated by the program).",
             {"type": "object", "properties": {"entry": {"type": "object"}}, "required": ["entry"]}, replace),
        Tool("finish", "Finish the review.", {"type": "object", "properties": {"notes": {"type": "string"}}}, finish),
    ]
    return Task(f"review slides {numbers}", system, prompt, tools, max_turns=40,
                log_path=run.lesson.agent / "log.jsonl"), state
