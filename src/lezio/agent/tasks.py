"""The agent tasks: what the model receives and the tools through which it works.

    plan     the material in scope -> title, outline, ordered segments (sources, goal, length, visual idea)
    write    one or a few segments -> narration + scene code, each submission checked and previewed
    review   final frames of rendered segments -> fixes

Texts live in agent/prompts/; this module assembles them with the task data and defines the tools. Every
tool validates what the model submits and answers "accepted" or with the problems, so mistakes are fixed
inside the same session. The model never touches files: the program saves what is accepted.

A task works on a `work` object with: lesson, script (dict, saved by the tools), material (Material),
plan_key, on_event(kind, data) (agent activity for the UI).
"""
import inspect
import json
import time

from ..config import CONFIG
from ..material import RefError
from ..script import find_segment, normalize_piece, save_script
from ..config import THEMES
from ..settings import DEPTHS, house_theme, lesson_theme
from ..validate import check_narration, check_scene_code, scene_code_warnings
from . import prompts
from .backends import Image, Task, Tool, ToolResult, task_options

ARRAY_OF_OBJECTS = {"type": "array", "items": {"type": "object"}}
MAX_VIEW = 6


# ======================================================================== shared pieces
def settings_block(work):
    s = work.script["settings"]
    block = (f"Lesson: {work.lesson.id}\nNarration language: {s['language']}\n"
             f"Depth: {s['depth']} ({DEPTHS[s['depth']]}) - {prompts.depth_rule(s['depth'])}")
    if s.get("instructions"):
        block += "\n\nINSTRUCTIONS FROM THE USER (priority over the default rules):\n" + \
                 "\n".join(f"- {line}" for line in s["instructions"].splitlines() if line.strip())
    return block


def make_task(work, kind, label, system, prompt, tools, max_turns):
    return Task(label, system, prompt, tools, max_turns=max_turns, log_path=work.lesson.agent / "log.jsonl",
                on_event=work.on_event, **task_options(kind))


def rejected(problems, intro="Rejected:"):
    return ToolResult([intro] + [f"- {p}" for p in problems[:40]], error=True)


def material_tools(work):
    """read, view, list_material: the model's only access to the study material."""
    m = work.material

    def read(args):
        try:
            return ToolResult([m.read(args.get("ref", ""))])
        except RefError as e:
            return ToolResult([str(e)], error=True)

    def view(args):
        refs = args.get("refs") or []
        if isinstance(refs, str):
            refs = [refs]
        content, shown = [], 0
        for ref in refs:
            try:
                pics = m.pictures(ref)
            except RefError as e:
                return ToolResult([str(e)], error=True)
            if not pics:
                content.append(f"{ref}: nothing to see (text only).")
            for label, path in pics:
                if shown == MAX_VIEW:
                    content.append(f"Only {MAX_VIEW} pictures per call: ask for the others in another call.")
                    return ToolResult(content)
                content += [f"{label}:", Image.from_file(path, max_width=1024)]
                shown += 1
        return ToolResult(content or ["Give some refs."])

    def list_material(args):
        return ToolResult([m.overview(work.script["settings"].get("focus"))])

    return [
        Tool("read", "Text of the material: a page or section (with its L-numbered lines and figures), a range "
             "(slides.pdf#p3-5) or a whole source.",
             {"type": "object", "properties": {"ref": {"type": "string"}}, "required": ["ref"]}, read),
        Tool("view", f"Pictures of pages, figures and picture sources (up to {MAX_VIEW} per call).",
             {"type": "object", "properties": {"refs": {"type": "array", "items": {"type": "string"}}},
              "required": ["refs"]}, view),
        Tool("list_material", "The list of the material in scope (one line per page, section or picture).",
             {"type": "object", "properties": {}}, list_material),
    ]


# ======================================================================== scene API reference
def _signature(fn, skip=0):
    params = list(inspect.signature(fn).parameters.values())[skip:]
    return "(" + ", ".join(str(p) for p in params) + ")"


def _doc(obj, indent="    "):
    doc = inspect.getdoc(obj) or ""
    return ("\n" + indent + doc.replace("\n", "\n" + indent)) if doc else ""


def scene_api():
    """Reference of the helpers available to scene code, generated from lezio.scene (what the model knows)."""
    from ..scene import layouts, material, style, sync
    out = ["Narration sync - t = steps() starts the next piece and returns its Timer t:"]
    for name in ("play", "wait", "until", "finish", "clear"):
        out.append(f"  t.{name}{_signature(getattr(sync.Timer, name), 1)}{_doc(getattr(sync.Timer, name))}")
    out.append("  t.duration, t.left, t.pause, t.say, t.index: speech length, speech left, silence after, text, number")
    out.append(f"  steps.take{_signature(sync.Steps.take, 1)}{_doc(sync.Steps.take)}")
    out.append("  steps.left: pieces not started yet")
    out.append("\nStudy material - `material`:")
    for name in ("page", "figure", "text", "lines"):
        fn = getattr(material.SceneMaterial, name)
        out.append(f"  material.{name}{_signature(fn, 1)}{_doc(fn)}")
    for name in ("mark", "point"):
        fn = getattr(material.Page, name)
        out.append(f"  page.{name}{_signature(fn, 1)}{_doc(fn)}")
    out.append("\nHouse style - the names below come from the lesson's theme; use them, never fixed colors:")
    out.append("  colors: BACKGROUND, TEXT (body text), MUTED (secondary text, labels), PRIMARY + PRIMARY_SOFT (titles, "
               "main elements; soft = fills), SECONDARY + SECONDARY_SOFT (a second contrasting family), HIGHLIGHT + "
               "HIGHLIGHT_SOFT (what is being talked about now), POSITIVE + POSITIVE_SOFT (correct, yes), NEGATIVE + "
               "NEGATIVE_SOFT (wrong, no), NEUTRAL_SOFT (neutral fills)")
    out.append("  fonts: FONT (text), TITLE_FONT, MONO (code, digits in columns), HAND (handwriting: board-like "
               "writing, annotations)   sizes: TITLE_SIZE, TEXT_SIZE, SMALL_SIZE")
    out.append("  frame: FRAME_WIDTH, FRAME_HEIGHT, SAFE_LEFT, SAFE_RIGHT, SAFE_BOTTOM, SAFE_TOP")
    for name in ("T", "MT", "heading", "wrap", "fit", "box", "arrow", "person", "check", "cross"):
        fn = getattr(style, name)
        out.append(f"  {name}{_signature(fn)}{_doc(fn)}")
    out.append("\nLayouts (optional) - " + (inspect.getdoc(layouts) or "").split("\n\n")[1].replace("\n", " "))
    for name, fn in layouts.LAYOUTS.items():
        out.append(f"  {name}{_signature(fn)}{_doc(fn)}")
    return "\n".join(out)


# ======================================================================== plan
def plan_task(work):
    s = work.script["settings"]
    focus = s.get("focus") or {}
    scope = work.material.scope(focus)
    themes = sorted(p.stem for p in THEMES.glob("*.toml"))
    system = prompts.compose("role", "plan", "rules/teaching", house=house_theme(), themes=", ".join(themes))
    prompt = settings_block(work)
    units, described = work.material.size(focus)
    lo, hi = prompts.target_minutes(s["depth"], units)
    prompt += (f"\n\nTARGET LENGTH of the whole lesson: about {lo:.1f}-{hi:.1f} minutes ({described} in scope, "
               f"depth {s['depth']}). The \"minutes\" of the segments must add up to about this.")
    prompt += "\n\nMATERIAL IN SCOPE (refs, first line or heading, size):\n" + work.material.overview(focus)

    def submit(args):
        problems = []
        title, outline = str(args.get("title", "")).strip(), str(args.get("outline", "")).strip()
        visual_language = str(args.get("visual_language", "")).strip()
        segments, skipped = args.get("segments"), args.get("skipped") or []
        if not title:
            problems.append("title is empty")
        if not outline:
            problems.append("outline is empty")
        if not visual_language:
            problems.append("visual_language is empty")
        if not isinstance(segments, list) or not segments:
            return rejected(problems + ["segments must be a non-empty list"])
        covered, out = set(), []
        for k, seg in enumerate(segments, 1):
            where = f"segment {k}"
            if not isinstance(seg, dict):
                problems.append(f"{where}: must be an object")
                continue
            for key in ("title", "goal", "visual"):
                if not str(seg.get(key, "")).strip():
                    problems.append(f"{where}: \"{key}\" is empty")
            minutes = seg.get("minutes")
            if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or not 0 < minutes <= 15:
                problems.append(f"{where}: \"minutes\" must be a number between 0 and 15")
            refs = seg.get("sources")
            if not isinstance(refs, list) or not refs:
                problems.append(f"{where}: \"sources\" must be a non-empty list of refs")
                refs = []
            for ref in refs:
                try:
                    items = work.material.expand([ref])
                except RefError as e:
                    problems.append(f"{where}: {e}")
                    continue
                outside = [i for i in items if i not in scope]
                if outside:
                    problems.append(f"{where}: {ref} is outside the scope of the lesson")
                covered.update(items)
            entry = {"title": str(seg.get("title", "")).strip(), "goal": str(seg.get("goal", "")).strip(),
                     "sources": refs, "minutes": minutes, "visual": str(seg.get("visual", "")).strip()}
            out.append(entry)
        skipped_items, skipped_out = set(), []
        for x in skipped:
            ref = x.get("ref") if isinstance(x, dict) else x
            try:
                skipped_items.update(work.material.expand([ref]))
                skipped_out.append({"ref": ref, "reason": str(x.get("reason", "")) if isinstance(x, dict) else ""})
            except RefError as e:
                problems.append(f"skipped: {e}")
        theme = str(args.get("theme") or "").strip()
        if theme and theme not in themes:
            problems.append(f"theme must be one of {', '.join(themes)} (or omitted)")
        missing = [r for r in scope if r not in covered and r not in skipped_items]
        if missing:
            problems.append("not covered by any segment and not in skipped: " + ", ".join(missing[:30]))
        total = sum(e["minutes"] for e in out if isinstance(e["minutes"], (int, float)))
        if total > 1.5 * hi + 0.5:
            problems.append(f"the segments add up to {total:.1f} minutes: the target is about {lo:.1f}-{hi:.1f}")
        if problems:
            return rejected(problems, "Plan rejected:")
        for k, entry in enumerate(out, 1):
            entry["id"] = f"s{k:02d}"
        work.script.update(title=title, outline=outline, plan_key=work.plan_key, skipped=skipped_out, theme=theme,
                           visual_language=visual_language,
                           segments=[{"id": e.pop("id"), **e} for e in out])
        save_script(work.lesson.script, work.script)
        return ToolResult([f"Plan accepted ({len(out)} segments). The task is complete."], done=True)

    tools = material_tools(work) + [
        Tool("submit_plan", "Submit the lesson plan (checked by the program).",
             {"type": "object", "properties": {"title": {"type": "string"}, "outline": {"type": "string"},
                                               "visual_language": {"type": "string"},
                                               "segments": ARRAY_OF_OBJECTS, "skipped": ARRAY_OF_OBJECTS,
                                               "theme": {"type": "string"}},
              "required": ["title", "outline", "visual_language", "segments"]}, submit)]
    return make_task(work, "plan", "plan", system, prompt, tools, max_turns=60)


# ======================================================================== write and fix segments
def numbered(narration):
    rows = []
    for i, p in enumerate(normalize_piece(x) for x in narration or []):
        rows.append(f"  {i}. {p['say']}" + (f"  [pause {p['pause']} s]" if p["pause"] else ""))
    return "\n".join(rows)


def theme_line(script):
    import tomllib
    name = lesson_theme(script)
    data = tomllib.loads((THEMES / f"{name}.toml").read_text())
    return f"{name} - {data.get('description', '')}"


def segment_brief(work, seg, with_text=True):
    lines = [f"### Segment {seg['id']}: {seg['title']}",
             f"Goal: {seg.get('goal', '')}",
             f"Length: about {seg.get('minutes', '?')} minutes",
             f"Visual idea from the plan: {seg.get('visual', '')}",
             f"Sources: {', '.join(seg.get('sources', []))}"]
    if with_text:
        texts = []
        for ref in seg.get("sources", []):
            try:
                texts.append(work.material.read(ref, limit=12000))
            except RefError as e:
                texts.append(f"{ref}: {e}")
        lines.append("Text of the sources:\n" + "\n\n".join(texts))
    return "\n".join(lines)


class SegmentSubmissions:
    """Checks a submission, renders its preview and saves it when it renders: shared by write and review."""

    def __init__(self, work, ids, rounds):
        self.work, self.ids, self.rounds = work, ids, rounds
        self.renders = {sid: 0 for sid in ids}
        self.accepted = {sid: False for sid in ids}

    def submit(self, sid, narration, code, next_hint):
        from ..video import render
        work = self.work
        if sid not in self.ids:
            return ToolResult([f"Choose a segment among {', '.join(self.ids)}."], error=True)
        if self.renders[sid] >= self.rounds:
            return ToolResult([f"No submissions left for {sid}: {next_hint}"], error=True)
        errors, warnings = check_narration(narration)
        warnings += scene_code_warnings(code) if isinstance(code, str) else []
        if not isinstance(code, str) or not code.strip():
            errors.append("code is empty")
        else:
            errors += [f"code: {p}" for p in check_scene_code(code)]
        if errors:
            return rejected(errors)
        self.renders[sid] += 1
        left = self.rounds - self.renders[sid]
        seg = find_segment(work.script, sid)
        candidate = {**seg, "narration": narration, "scene": sid}
        try:
            sheet, report = render.preview(work.lesson, candidate, code)
        except render.RenderError as e:
            report = e.report or {}
            return ToolResult([f"The scene failed while rendering: {e}"]
                              + [f"warning: {w}" for w in report.get("warnings", [])[:8]]
                              + [f"Fix it and submit again ({left} submissions left for {sid})."
                                 if left else f"No submissions left for {sid}."], error=True)
        seg.update(narration=narration, scene=sid)
        work.lesson.scenes.mkdir(parents=True, exist_ok=True)
        work.lesson.scene_file(sid).write_text(code.rstrip() + "\n")
        save_script(work.lesson.script, work.script)
        self.accepted[sid] = True
        notes = warnings + report.get("warnings", [])
        spoken = sum(len(normalize_piece(p)["say"].split()) for p in narration) / 2.5
        planned = 60 * (seg.get("minutes") or 0)
        if planned and spoken > 1.4 * planned + 10:
            notes.insert(0, f"the narration lasts about {spoken:.0f} s, the plan gives this segment {planned:.0f} s: "
                            "shorten it")
        content = [f"Segment {sid} accepted and saved. Preview: {report.get('seconds', '?')} s with estimated "
                   "timing; for every piece, the frame in its middle and the frame at its end:"]
        if sheet:
            content.append(Image.from_file(sheet, max_width=1440, quality=78))
        content += [f"warning: {w}" for w in notes[:12]]
        content.append(f"Check the frames. If something is wrong, fix it and submit again ({left} submissions left "
                       f"for {sid}); otherwise {next_hint}" if left else f"No submissions left for {sid}: {next_hint}")
        return ToolResult(content)

    def pending(self):
        return [sid for sid in self.ids if not self.accepted[sid] and self.renders[sid] < self.rounds]


def frame_tool(work, ids, final):
    """view_frame: one frame at full size, to check details the step sheet is too small to show."""
    def handler(args):
        from ..video import render
        sid, piece, where = args.get("id"), args.get("piece"), args.get("where", "end")
        if sid not in ids or not isinstance(piece, int) or where not in ("middle", "end"):
            return ToolResult([f"Give id (one of {', '.join(ids)}), piece (a number) and where (middle | end)."],
                              error=True)
        try:
            path = render.piece_frame(work.lesson, sid, piece, final, where)
        except render.RenderError as e:
            return ToolResult([str(e)], error=True)
        return ToolResult([f"{sid}, piece {piece}, {where} ({'final video' if final else 'last preview'}):",
                           Image.from_file(path, max_width=1280, quality=80)])
    return Tool("view_frame", "One frame of the " + ("final video" if final else "last preview") + " of a segment "
                "at full size (the middle or the end of a narration piece): to check small text and details.",
                {"type": "object", "properties": {"id": {"type": "string"}, "piece": {"type": "integer"},
                                                  "where": {"type": "string", "enum": ["middle", "end"]}},
                 "required": ["id", "piece"]}, handler)


def write_task(work, ids, note=""):
    script, s = work.script, work.script["settings"]
    segs = [find_segment(script, sid) for sid in ids]
    order = [x["id"] for x in script["segments"]]
    first, last = order.index(ids[0]), order.index(ids[-1])
    system = prompts.compose("role", "write", "rules/teaching", "rules/writing", "rules/narration_format",
                             "rules/scene_api", api=scene_api())
    prompt = settings_block(work) + f"\nTheme of the lesson: {theme_line(script)}"
    plan = "\n".join(f"  {x['id']}  {x['title']}" + ("   <- write now" if x["id"] in ids else "")
                     for x in script["segments"])
    prompt += f"\n\nLESSON: {script['title']}\n{script['outline']}\n"
    if script.get("visual_language"):
        prompt += f"Visual language of the lesson (follow it): {script['visual_language']}\n"
    prompt += f"Segments:\n{plan}\n"
    if first == 0:
        prompt += "\nThe first segment to write opens the lesson: welcome the viewer and say what the lesson is about."
    else:
        prev = script["segments"][first - 1]
        said = " ".join(normalize_piece(p)["say"] for p in (prev.get("narration") or [])[-2:])
        prompt += (f"\nThe previous segment ({prev['id']}, {prev['title']}) ends with: \"{said[-400:]}\" - continue "
                   "naturally, do not welcome again." if said else
                   f"\nThe previous segment is {prev['id']} ({prev['title']}): continue naturally, do not welcome again.")
    if last == len(order) - 1:
        prompt += "\nThe last segment to write closes the lesson: end it with a short recap."
    if note:
        prompt += f"\n\nREQUEST FROM THE USER FOR THESE SEGMENTS: {note}"
    prompt += "\n\n" + "\n\n".join(segment_brief(work, seg) for seg in segs)

    subs = SegmentSubmissions(work, ids, CONFIG["tuning"]["preview_rounds"])

    def submit(args):
        sid = args.get("id")
        rest = [x for x in ids if x != sid and not subs.accepted.get(x)]
        hint = f"go on with segment {rest[0]}." if rest else "call finish."
        return subs.submit(sid, args.get("narration"), args.get("code"), hint)

    def finish(args):
        pending = subs.pending()
        if pending:
            return ToolResult([f"Segment {pending[0]} is not accepted yet: submit it."], error=True)
        notes = work.lesson.agent / "notes.jsonl"
        with open(notes, "a") as fh:
            fh.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M"), "task": f"write {','.join(ids)}",
                                 "notes": args.get("notes", "")}, ensure_ascii=False) + "\n")
        return ToolResult(["Done."], done=True)

    tools = material_tools(work) + [
        frame_tool(work, ids, final=False),
        Tool("submit_segment", "Submit the narration and scene code of one segment: checked, rendered as a "
             "low-resolution preview and saved if it renders. You get the frames back.",
             {"type": "object", "properties": {
                 "id": {"type": "string"},
                 "narration": {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "object"}]}},
                 "code": {"type": "string"}}, "required": ["id", "narration", "code"]}, submit),
        Tool("finish", "Finish the task (when every segment is accepted).",
             {"type": "object", "properties": {"notes": {"type": "string"}}}, finish),
    ]
    return make_task(work, "write", f"write {', '.join(ids)}", system, prompt, tools, max_turns=80), subs


# ======================================================================== review
def review_task(work, ids):
    script = work.script
    segs = [find_segment(script, sid) for sid in ids]
    system = prompts.compose("role", "review", "rules/teaching", "rules/writing", "rules/narration_format",
                             "rules/scene_api", api=scene_api())
    blocks = []
    for seg in segs:
        code = work.lesson.scene_file(seg["id"]).read_text()
        blocks.append(segment_brief(work, seg, with_text=False) + f"\nNarration:\n{numbered(seg['narration'])}"
                      f"\nScene code:\n```python\n{code}\n```")
    prompt = settings_block(work) + f"\nTheme of the lesson: {theme_line(script)}" + \
        f"\n\nLESSON: {script['title']}\nVisual language: {script.get('visual_language') or '-'}" + \
        f"\n\nReview the segments {', '.join(ids)}.\n\n" + \
        "\n\n".join(blocks)
    subs = SegmentSubmissions(work, ids, CONFIG["tuning"]["preview_rounds"])
    changed = []

    def view_final(args):
        sid = args.get("id")
        if sid not in ids:
            return ToolResult([f"Choose a segment among {', '.join(ids)}."], error=True)
        sheet = work.lesson.qa / f"final_{sid}.png"
        meta = work.lesson.video / f"{sid}.json"
        warnings = json.loads(meta.read_text()).get("warnings", []) if meta.exists() else []
        content = [f"Final video of {sid}: for every piece, the frame in its middle and the frame at its end."]
        content += [Image.from_file(sheet, max_width=1440, quality=78)] if sheet.exists() else ["(no frames)"]
        content += [f"warning: {w}" for w in warnings[:12]] or ["No automatic warnings."]
        return ToolResult(content)

    def replace(args):
        sid = args.get("id")
        seg = find_segment(script, sid) if sid in ids else None
        if seg is None:
            return ToolResult([f"Choose a segment among {', '.join(ids)}."], error=True)
        narration = args.get("narration") or seg["narration"]
        code = args.get("code") or work.lesson.scene_file(sid).read_text()
        result = subs.submit(sid, narration, code, "go on with the review or call finish.")
        if not result.error and sid not in changed:
            changed.append(sid)
        return result

    def finish(args):
        (work.lesson.agent / f"review_{ids[0]}.json").write_text(json.dumps(
            {"changed": changed, "notes": args.get("notes", "")}, ensure_ascii=False, indent=2))
        return ToolResult(["Done."], done=True)

    tools = material_tools(work) + [
        Tool("view_final", "Frames of the final video of one segment, with the automatic warnings.",
             {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}, view_final),
        frame_tool(work, ids, final=True),
        Tool("replace_segment", "Replace the code and/or the narration of a segment (omitted = unchanged): "
             "checked, previewed and saved like when writing it.",
             {"type": "object", "properties": {
                 "id": {"type": "string"},
                 "narration": {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "object"}]}},
                 "code": {"type": "string"}}, "required": ["id"]}, replace),
        Tool("finish", "Finish the review.", {"type": "object", "properties": {"notes": {"type": "string"}}}, finish),
    ]
    return make_task(work, "review", f"review {', '.join(ids)}", system, prompt, tools, max_turns=60), changed
