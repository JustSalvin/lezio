"""The agent tasks: what the model receives and the tools through which it works.

Texts live in agent/prompts/; this module assembles them with the task data and defines the tools.
Every tool validates what the model submits and answers "accepted" or with the list of problems, so
mistakes are fixed inside the same session. The model never touches files.
"""
import ast
import inspect
import json

from ..config import CONFIG
from ..settings import DEPTHS
from ..validate import validate
from . import prompts
from .backends import Image, Task, Tool, ToolResult, task_options

KINDS = ("title", "agenda", "divider", "content", "diagram", "interactive", "references", "other")
ARRAY_OF_OBJECTS = {"type": "array", "items": {"type": "object"}}


def templates_reference():
    """Signature and docstring of every animation template (what the model knows about templates)."""
    from ..video import templates
    out = []
    for name, fn in templates.TEMPLATES.items():
        sig = str(inspect.signature(fn)).replace("(scene, steps, ", "(")
        out.append(f"- {name}{sig}\n    " + inspect.getdoc(fn).replace("\n", "\n    "))
    return "\n".join(out)


def settings_block(run):
    s = run.settings
    block = (f"Lesson: {run.lesson.id}  (PDF: {run.lesson.pdf.name})\n"
             f"Narration language: {s['language']}\n"
             f"Visual mode: {s['visual']} - {prompts.visual_rule(s['visual'])}\n"
             f"Depth: {s['depth']} ({DEPTHS[s['depth']]}) - {prompts.depth_rule(s['depth'])}")
    if s.get("instructions"):
        block += "\n\nINSTRUCTIONS FROM THE USER (priority over the default rules):\n" + \
                 "\n".join(f"- {line}" for line in s["instructions"].splitlines() if line.strip())
    return block


def slide_text(run, n):
    data = run.lines["slides"][str(n)]
    w, h = run.lines["page_size"]
    rows = [f"L{k}: {r['text']}" for k, r in enumerate(data["lines"], 1)] or ["(no text lines)"]
    rows += [f"image #{k}: {(b[2] - b[0]) * (b[3] - b[1]) / (w * h):.0%} of the slide"
             for k, b in enumerate(data["images"], 1)]
    return "\n".join(rows)


def make_task(run, kind, label, system, prompt, tools, max_turns):
    return Task(label, system, prompt, tools, max_turns=max_turns, log_path=run.lesson.agent / "log.jsonl",
                on_event=run.on_agent_event, **task_options(kind))


def view_slides_tool(run, allowed):
    def handler(args):
        numbers = args.get("numbers") or []
        if not numbers or any(n not in allowed for n in numbers):
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


def must_fix(errors, warnings):
    return errors + [w for w in warnings if "digits" in w or "words" in w]


# ======================================================================== plan
def plan_task(run):
    scope = run.scope
    lines = [f"Slide {n}: " + " | ".join(r["text"] for r in run.lines["slides"][str(n)]["lines"]) for n in scope]
    prompt = (settings_block(run) + f"\n\nPages in scope: {scope[0]}-{scope[-1]} ({len(scope)} pages)\n\n"
              "Text of the slides (repeated headers/footers removed):\n" + "\n".join(lines))

    def submit(args):
        items = args.get("slides")
        if not isinstance(items, list):
            return ToolResult(["slides must be a list"], error=True)
        problems = []
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
        run.save_plan({"title": args.get("title", ""), "outline": args["outline"], "slides": items})
        return ToolResult(["Plan accepted. The task is complete."], done=True)

    tools = [view_slides_tool(run, scope),
             Tool("submit_plan", "Submit the lesson plan (validated by the program).",
                  {"type": "object", "properties": {"title": {"type": "string"}, "outline": {"type": "string"},
                                                    "slides": ARRAY_OF_OBJECTS},
                   "required": ["title", "outline", "slides"]}, submit)]
    return make_task(run, "plan", "plan", prompts.compose("role", "plan"), prompt, tools, max_turns=30)


# ======================================================================== write a group of slides
def write_task(run, items, outline, before, after, note=""):
    numbers = [i["slide"] for i in items]
    first = numbers[0]
    group_file = run.lesson.agent / f"group_{first:03d}.json"
    anim_file = run.lesson.animations_dir / f"group_{first:03d}.py"
    prefix = f"g{first:03d}_"
    rounds = CONFIG["tuning"]["animation_rounds"]
    state = {"accepted": False, "previews": 0, "previewed": False, "has_anims": False}

    system = prompts.compose("role", "write", "script_format", "writing_rules", "animations",
                             templates=templates_reference(), prefix=prefix)
    blocks = [f"### Slide {i['slide']} ({i['kind']})\nPlan: {i.get('summary', '')}  |  "
              f"Visual idea: {i.get('visual_idea', 'none')}\n{slide_text(run, i['slide'])}" for i in items]
    prompt = (settings_block(run) + f"\n\nLesson outline: {outline}\n\n"
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
        code = (args.get("animation_code") or "").strip()
        if code:
            try:
                names = [f.name for f in ast.parse(code).body if isinstance(f, ast.FunctionDef)]
                problems += [f"animation_code: function {f} must start with {prefix}" for f in names
                             if not f.startswith(prefix) and not f.startswith("_")]
            except SyntaxError as e:
                problems.append(f"animation_code: syntax error at line {e.lineno}: {e.msg}")
        if problems:
            return ToolResult(["Rejected:"] + [f"- {p}" for p in problems], error=True)
        if code:
            anim_file.write_text(code + "\n")
        else:
            anim_file.unlink(missing_ok=True)
        problems = must_fix(*validate(run.lesson, run.settings, slides, coverage=False))
        if problems:
            return ToolResult(["Rejected:"] + [f"- {p}" for p in problems[:40]], error=True)
        group_file.write_text(json.dumps({"slides": slides}, ensure_ascii=False, indent=2))
        run.take_group(group_file)
        state.update(accepted=True, previewed=False, has_anims=any("anim" in b for s in slides for b in s["beats"]))
        if state["has_anims"]:
            return ToolResult(["Script accepted. Now call preview_animations and check the frames."])
        return ToolResult(["Script accepted (no animations). The task is complete."], done=True)

    def preview(args):
        if not state["accepted"]:
            return ToolResult(["Submit an accepted script first."], error=True)
        if state["previews"] >= rounds:
            return ToolResult([f"Preview limit ({rounds}) reached: call finish."], error=True)
        state["previews"] += 1
        from ..video.render import render_animation_previews
        beats = [(n, k) for n in numbers for k, b in enumerate(run.slides[n]["beats"]) if "anim" in b]
        content = ["Frames of each animation in time order (left to right, top to bottom); timing is a "
                   "placeholder until the voice exists."]
        for n, k, sheet, err in render_animation_previews(run.lesson, beats):
            content.append(f"Slide {n}, beat {k} ({run.slides[n]['beats'][k]['anim']}):")
            content.append(f"RENDER FAILED: {err}" if err else Image.from_file(sheet, max_width=1440, quality=78))
        state["previewed"] = True
        return ToolResult(content)

    def finish(args):
        if not state["accepted"]:
            return ToolResult(["Submit an accepted script first."], error=True)
        if state["has_anims"] and not state["previewed"] and state["previews"] < rounds:
            return ToolResult(["Preview the animations of the last accepted script first."], error=True)
        (run.lesson.agent / f"group_{first:03d}_notes.txt").write_text(args.get("notes", ""))
        return ToolResult(["Done."], done=True)

    tools = [
        view_slides_tool(run, run.scope),
        Tool("submit_script", "Submit the script of the group (validated by the program). animation_code: Python "
             "source of the custom animations used by the script (omit if none).",
             {"type": "object", "properties": {"slides": ARRAY_OF_OBJECTS, "animation_code": {"type": "string"}},
              "required": ["slides"]}, submit),
        Tool("preview_animations", "Render every animation of the accepted script alone and show their frames.",
             {"type": "object", "properties": {}}, preview),
        Tool("finish", "Finish the task.", {"type": "object", "properties": {"notes": {"type": "string"}}}, finish),
    ]
    return make_task(run, "write", f"write slides {numbers}", system, prompt, tools, max_turns=60)


# ======================================================================== review
def review_task(run, numbers):
    changed = []
    system = prompts.compose("role", "review", "script_format") + "\n\nTEMPLATES:\n" + templates_reference()
    blocks = [f"### Slide {n}\n{slide_text(run, n)}\nScript: {json.dumps(run.slides[n], ensure_ascii=False)}"
              for n in numbers]
    prompt = settings_block(run) + f"\n\nReview slides {numbers}.\n\n" + "\n\n".join(blocks)

    def view_final(args):
        n = args.get("slide")
        if n not in numbers:
            return ToolResult([f"Choose a slide among {numbers}."], error=True)
        sheet = run.lesson.qa / f"final_slide_{n:02d}.png"
        return ToolResult([f"Final video of slide {n}:", Image.from_file(sheet, max_width=1440, quality=78)])

    def replace(args):
        entry = args.get("entry")
        if not isinstance(entry, dict) or entry.get("slide") not in numbers:
            return ToolResult([f"entry must be a slide entry of one of {numbers}"], error=True)
        problems = must_fix(*validate(run.lesson, run.settings, [entry], coverage=False))
        if problems:
            return ToolResult(["Rejected:"] + [f"- {p}" for p in problems], error=True)
        run.slides[entry["slide"]] = entry
        run.save_script()
        changed.append(entry["slide"])
        return ToolResult([f"Slide {entry['slide']} replaced; it will be re-rendered."])

    def finish(args):
        (run.lesson.agent / f"review_{numbers[0]:03d}.json").write_text(json.dumps(
            {"changed": changed, "notes": args.get("notes", "")}, ensure_ascii=False, indent=2))
        return ToolResult(["Done."], done=True)

    tools = [
        Tool("view_final", "Show frames of the final video of one slide.",
             {"type": "object", "properties": {"slide": {"type": "integer"}}, "required": ["slide"]}, view_final),
        view_slides_tool(run, numbers),
        Tool("replace_slide", "Replace the script entry of one slide (validated by the program).",
             {"type": "object", "properties": {"entry": {"type": "object"}}, "required": ["entry"]}, replace),
        Tool("finish", "Finish the review.", {"type": "object", "properties": {"notes": {"type": "string"}}}, finish),
    ]
    return make_task(run, "review", f"review slides {numbers}", system, prompt, tools, max_turns=40), changed
