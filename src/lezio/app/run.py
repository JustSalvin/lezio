"""The program: from study material (or an existing lesson) to a finished video.

    1. material   new or changed sources -> build/material (pages, text, figures)     program
    2. plan       title, outline, segments (sources, goal, length, visual idea)          agent task (plan)
    3. write      template blocks + narration of a few segments at a time, with previews agent tasks (write)
    4. voice      speech synthesis with the configured TTS engine                        program
    5. video      render the segments that changed                                        program
    6. review     final frames judged, broken segments fixed                             agent task (review)
    7. join       output/<lesson>.mp4                                                     program

Per-video choices (depth, instructions, focus) come from the wizard or the options and are saved in
the lesson; configuration comes from config.toml. Every step is resumable: segments already written,
audio already generated and videos already rendered are kept.
"""
import hashlib
import json
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

from .. import material as mat
from ..agent import tasks
from ..agent.backends import get_backend, task_options
from ..config import CONFIG, INPUT, ROOT
from ..lesson import Lesson, all_lessons, lesson_exists, slugify, stored_path
from ..script import empty_script, find_segment, is_written, load_script, narration, save_script
from ..settings import DEPTHS, PLAN_CHOICES, house_theme, merge_settings, tts_label, tts_options
from ..validate import check_script
from ..video import render
from ..voice import client as voice
from ..voice import engines
from . import ui, wizard


def rel(p):
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:
        return str(p)


def input_files():
    """Supported files in input/ (subfolders included): [(path, label)]."""
    files = sorted(p for p in INPUT.rglob("*") if p.is_file() and mat.supported(p) and not p.name.startswith("."))
    return [(p, str(p.relative_to(INPUT))) for p in files]


def count_items(path):
    """(number, unit) of the parts of a source that a focus range can select, or None."""
    kind = mat.kind_of(path)
    if kind == "pdf":
        import pymupdf
        return pymupdf.open(path).page_count, "page"
    return None


class Run:
    def __init__(self, a):
        self.a = a
        self.interactive = wizard.interactive() and not getattr(a, "yes", False)
        self.backend = None
        self.step = None                 # the live UI step, if any (agent events are shown there)
        self.models = set()
        self.note = getattr(a, "note", None) or ""
        self.lesson = None

    # ================================================================ what to work on
    def choose(self):
        """-> (list of source paths for a new lesson or to add, lesson id)"""
        a = self.a
        targets = list(getattr(a, "targets", None) or [])
        if len(targets) == 1 and not Path(targets[0]).suffix and lesson_exists(targets[0]):
            return None, targets[0]
        if targets:
            paths = []
            for t in targets:
                p = Path(t).expanduser()
                if not p.exists():
                    ui.fail(f"'{t}' is neither a file nor an existing lesson", "./lezio help make")
                if not mat.supported(p):
                    ui.fail(f"unsupported file type: {p.name}", "supported: " + ", ".join(sorted(mat.KINDS)))
                paths.append(p.resolve())
            return paths, a.id or slugify(paths[0].stem)
        if not self.interactive:
            ui.fail("tell me which files or lesson", "./lezio make <files... | lesson>   (./lezio help make)")
        lessons = []
        for lid in all_lessons():
            s = load_script(Lesson(lid).script)
            names = ", ".join(Path(x).name for x in Lesson(lid).source_names)
            lessons.append((lid, f"{names} · depth {s['settings']['depth']} · "
                                 f"{len(s['segments'])} segments"))
        files = input_files()
        if not lessons and not files:
            ui.fail("no study material in input/", "put PDF, Markdown, text, DOCX or picture files in input/")
        kind, value = wizard.choose_target(lessons, bool(files))
        if kind == "lesson":
            return None, value
        paths = wizard.sources(files)
        lid = a.id or slugify(paths[0].stem)
        if lesson_exists(lid):
            lid = slugify(wizard.lesson_name(lid + "-2"))
        return paths, lid

    def resolve(self):
        a = self.a
        new_sources, self.lesson_id = self.choose()
        self.is_new = not lesson_exists(self.lesson_id)
        if self.is_new:                  # nothing is created before the user confirms
            self.sources = list(new_sources)
            saved = empty_script()
        else:
            self.lesson = Lesson(self.lesson_id)
            self.sources = [Path(p) for p in self.lesson.sources]
            for p in new_sources or []:                  # files given for an existing lesson are added
                if p not in [s.resolve() for s in self.sources]:
                    self.sources.append(p)
            saved = load_script(self.lesson.script)
        self.saved = saved
        base = saved["settings"]
        flags = {k: v for k, v in (("depth", getattr(a, "depth", None)),
                                   ("instructions", getattr(a, "instructions", None))) if v is not None}
        if getattr(a, "focus", None):
            flags["focus"] = self.parse_focus(a.focus, base.get("focus", {}))
        self.rewrite = bool(getattr(a, "rewrite", False))

        written = [s for s in saved["segments"] if narration(s)]
        if self.interactive and (self.is_new or not saved["segments"]) and "depth" not in flags:
            self.ask_focus(flags, base)
            flags.setdefault("depth", wizard.depth(base["depth"]))
            flags.setdefault("instructions", wizard.instructions(base["instructions"]))
        elif self.interactive and not flags and not self.rewrite and not new_sources:
            action = wizard.existing_action(
                f"{self.lesson_id} · depth {base['depth']} · "
                f"{len(written)}/{len(saved['segments'])} segments written")
            if action == "sources":
                files = input_files()
                current = [p.resolve() for p in self.sources]
                extra = [(p, rel(p)) for p in current if p not in [f for f, _ in files]]
                self.sources = wizard.sources(extra + files, checked=current)
                self.ask_focus(flags, base)
            elif action == "depth":
                flags["depth"] = wizard.depth(base["depth"])
            elif action == "instructions":
                flags["instructions"] = wizard.instructions(base["instructions"])
            elif action == "rewrite":
                self.rewrite = True

        self.settings = merge_settings({**base, **flags})
        names = {Path(stored_path(p)).name for p in self.sources}
        self.settings["focus"] = {k: v for k, v in self.settings["focus"].items() if Path(k).name in names and v}
        self.old_instructions = base["instructions"]
        changed_plan = any(self.settings[k] != base[k] for k in PLAN_CHOICES) or \
            (self.lesson is not None and [stored_path(p) for p in self.sources] != self.lesson.source_names)
        self.replan = self.rewrite or changed_plan or not saved["segments"]
        if written and changed_plan:
            self.rewrite = True
        problems = engines.get_engine(tts_options()["engine"]).validate(
            {k: v for k, v in tts_options().items() if k != "engine"})
        if problems:
            ui.fail("config.toml [tts]: " + "; ".join(problems), "see ./lezio tts or ./lezio config")

    def parse_focus(self, specs, current):
        focus = dict(current)
        for spec in specs:
            name, sep, pages = spec.rpartition(":")
            match = [p for p in self.sources if p.name == name or str(p).endswith(name)] if sep else []
            if not match:
                ui.fail(f"--focus {spec}: expected FILE:PAGES with FILE one of the sources",
                        "e.g. --focus \"slides.pdf:1-20\"")
            focus[self.focus_key(match[0])] = pages.strip()
        return focus

    def focus_key(self, path):
        """Focus is saved under the path the source will have in the lesson (input/<name> for new files)."""
        path = Path(path).resolve()
        if self.is_new or path not in [Path(p).resolve() for p in self.lesson.sources]:
            if INPUT.resolve() not in path.parents:
                return f"input/{path.name}"
        return stored_path(path)

    def ask_focus(self, flags, base):
        focus = dict(flags.get("focus", base.get("focus", {})))
        for p in self.sources:
            counted = count_items(p)
            if counted and counted[0] > 1:
                key = self.focus_key(p)
                focus[key] = wizard.focus(Path(p).name, counted[0], counted[1], focus.get(key, ""))
        flags["focus"] = focus

    # ================================================================ summary
    def summary(self):
        s = self.settings
        segs = [] if self.rewrite else self.saved["segments"]
        written = [x for x in segs if narration(x)]
        if self.replan:
            script = "a new plan" + (f"  [warn](the current lesson, {len(self.saved['segments'])} segments, is "
                                     "backed up and rewritten)[/]" if self.rewrite and self.saved["segments"] else "")
        else:
            script = f"{len(segs)} segments planned · {len(written)} written · {len(segs) - len(written)} to write"
        voice_line = tts_label()
        if self.lesson is not None and self.lesson.durations.exists():
            stale = sum(1 for m in self.lesson.durations_meta().values() if m.get("tts") != tts_options())
            if stale:
                voice_line += f"  [warn](changed in config.toml: {stale} pieces will be regenerated)[/]"
        opts = task_options("write")
        sources = []
        for p in self.sources:
            f = s["focus"].get(self.focus_key(p))
            outside = ROOT.resolve() not in Path(p).resolve().parents
            name = ui.escape(Path(p).name + "  [copied to input/]" if outside and self.is_new else rel(p))
            sources.append(name + (f"  [muted](pages {f})[/]" if f else ""))
        minutes = sum(x.get("minutes", 0) for x in segs) if segs and not self.replan else None
        rows = [("lesson", f"[bold]{self.lesson_id}[/]"),
                ("material", "\n".join(sources)),
                ("depth", f"{s['depth']} ({DEPTHS[s['depth']]})"),
                ("theme", house_theme()),
                ("voice", voice_line),
                ("agent", f"{CONFIG['agent']['backend']} · model {opts['model'] or 'default'}"
                          + (f" · effort {opts['effort']}" if opts["effort"] else "")),
                ("instructions", ui.escape(s["instructions"]) or "[muted]none[/]"),
                ("script", script),
                ("estimate", (f"about {minutes:.0f} min of video" if minutes else "known after the plan")
                 + f"  [muted]→ output/{self.lesson_id}.mp4[/]")]
        if written and not self.rewrite and s["instructions"] != self.old_instructions:
            rows.append(("note", "[muted]new instructions apply to segments written from now on "
                                 "(use rewrite or ./lezio redo for the others)[/]"))
        ui.console.print()
        ui.key_values(rows, title="summary")
        if self.interactive:
            if not wizard.confirm("Start?"):
                ui.info("Stopped, nothing changed.")
                raise SystemExit(0)
        elif self.rewrite and self.saved["segments"] and not getattr(self.a, "yes", False):
            ui.fail("this rewrites the existing lesson", "run again with --yes to confirm")

    # ================================================================ preparation
    def prepare(self):
        sources = []
        for p in self.sources:                      # new files outside input/ are copied there
            p = Path(p).resolve()
            if INPUT.resolve() not in p.parents and (self.lesson is None or stored_path(p) not in self.lesson.source_names):
                INPUT.mkdir(exist_ok=True)
                dst, n = INPUT / p.name, 2
                while dst.exists() and dst.read_bytes() != p.read_bytes():     # never overwrite another file
                    dst, n = INPUT / f"{p.stem}-{n}{p.suffix}", n + 1
                if not dst.exists():
                    shutil.copy2(p, dst)
                p = dst
            sources.append(p)
        if self.lesson is None:
            self.lesson = Lesson.create(self.lesson_id, sources)
        else:
            self.lesson.set_sources(sources)
        for d in (self.lesson.agent, self.lesson.scenes):
            d.mkdir(parents=True, exist_ok=True)
        with ui.step("Reading the material") as st:
            changed = mat.ingest(self.lesson, on_progress=lambda name: st.status(name))
            self.material = mat.Material(self.lesson)
            n = len(self.material.scope(self.settings["focus"]))
            st.done(f"{len(self.material.sources)} sources · {n} pages/sections in scope"
                    + (f" · {len(changed)} read now" if changed else ""))
        self.script = load_script(self.lesson.script) if not self.is_new else empty_script()
        self.script["settings"] = self.settings
        self.plan_key = self.compute_plan_key()
        if self.script["segments"] and self.script.get("plan_key") != self.plan_key and not self.replan:
            ui.info("The material or the choices changed since the lesson was planned: it is planned again.")
            self.replan = self.rewrite = True
        if self.rewrite and self.script["segments"]:
            dst = self.backup()
            for f in self.lesson.scenes.glob("*.py"):
                f.unlink()
            ui.info(f"Previous lesson backed up in {rel(dst)}")
        if self.replan:
            self.script.update(title="", outline="", plan_key="", segments=[], skipped=[])
        self.save()

    def compute_plan_key(self):
        index = json.loads(self.lesson.index.read_text())["sources"]
        data = {"sources": [(x["path"], x["fingerprint"]) for x in index],
                **{k: self.settings[k] for k in PLAN_CHOICES}}
        return hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    def backup(self):
        dst = self.lesson.agent / f"backup_{time.strftime('%Y%m%d_%H%M%S')}"
        dst.mkdir(parents=True, exist_ok=True)
        if self.lesson.script.exists():
            shutil.copy2(self.lesson.script, dst / "script.json")
        if self.lesson.scenes.is_dir():
            shutil.copytree(self.lesson.scenes, dst / "scenes", dirs_exist_ok=True)
        return dst

    def save(self):
        save_script(self.lesson.script, self.script)

    def work(self):
        return SimpleNamespace(lesson=self.lesson, script=self.script, material=self.material,
                               plan_key=self.plan_key, on_event=self.on_agent_event)

    # ================================================================ agent
    def run_task(self, task):
        if self.backend is None:
            self.backend = get_backend()
        outcome = self.backend.run(task)
        if outcome.model:
            self.models.add(outcome.model)
        self.last_error = outcome.error
        return outcome

    def agent_hint(self):
        log = f"log: {rel(self.lesson.agent / 'log.jsonl')}"
        return f"agent error: {ui.escape(self.last_error)} · {log}" if getattr(self, "last_error", "") else log

    def on_agent_event(self, kind, data):
        if self.step is None:
            return
        if kind == "model":
            self.models.add(data)
        elif kind == "tool":
            name, args = data
            text = {
                "read": lambda: f"reading {args.get('ref', '')}",
                "view": lambda: f"looking at {', '.join(args.get('refs') or [])[:60]}",
                "list_material": lambda: "listing the material",
                "submit_plan": lambda: "submitting the plan",
                "submit_segment": lambda: f"previewing {args.get('id', '')}",
                "view_final": lambda: f"watching {args.get('id', '')}",
                "replace_segment": lambda: f"fixing {args.get('id', '')}",
                "finish": lambda: "finishing",
            }.get(name, lambda: name)()
            self.step.status(f"agent: {ui.escape(text)}")
        elif kind == "rejected":
            self.step.status(f"agent: fixing → {ui.escape(str(data[1])[:80])}")

    # ================================================================ 2. plan
    def plan(self):
        if self.script["segments"] and self.script.get("plan_key") == self.plan_key:
            return
        with ui.step("Planning the lesson") as st:
            self.step = st
            for _ in range(2):
                self.run_task(tasks.plan_task(self.work()))
                if self.script["segments"]:
                    break
            else:
                ui.fail("the agent did not produce a valid plan", self.agent_hint())
            self.step = None
            minutes = sum(x["minutes"] for x in self.script["segments"])
            skipped = len(self.script["skipped"])
            st.done(f"{len(self.script['segments'])} segments · about {minutes:.0f} min"
                    + (f" · {skipped} parts skipped" if skipped else ""))
        self.show_plan()
        if self.interactive and not wizard.confirm("Continue with this plan?"):
            ui.info(f"Stopped. You can edit {rel(self.lesson.script)} and run ./lezio make {self.lesson.id} again.")
            raise SystemExit(0)

    def show_plan(self):
        ui.console.print(f"\n[bold]{ui.escape(self.script['title'])}[/]")
        ui.table(["", "", ""], [[f"[muted]{x['id']}[/]", ui.escape(x["title"]) + (" [muted](written)[/]" if
                                 is_written(self.lesson, x) else ""), f"[muted]{x['minutes']:g} min[/]"]
                                for x in self.script["segments"]])
        for x in self.script["skipped"]:
            ui.console.print(f"   [muted]skipped {ui.escape(x['ref'])}: {ui.escape(x.get('reason', ''))}[/]")
        ui.console.print()

    # ================================================================ 3. write
    def write(self, only=None):
        self.plan()
        todo = [x["id"] for x in self.script["segments"]
                if (x["id"] in only if only else not is_written(self.lesson, x))]
        if not todo:
            return
        size = CONFIG["tuning"]["segments_per_task"]
        order = [x["id"] for x in self.script["segments"]]
        groups = []
        for sid in todo:                       # consecutive segments, at most `size` per task
            if groups and len(groups[-1]) < size and order.index(sid) == order.index(groups[-1][-1]) + 1:
                groups[-1].append(sid)
            else:
                groups.append([sid])
        with ui.step("Writing the lesson", total=len(todo)) as st:
            self.step = st
            for group in groups:
                st.status(", ".join(group))
                ids = list(group)
                for _ in range(2):
                    task, _ = tasks.write_task(self.work(), ids, self.note)
                    self.run_task(task)
                    ids = [sid for sid in ids if not is_written(self.lesson, find_segment(self.script, sid))]
                    if not ids:
                        break
                if ids:
                    ui.fail(f"segments {', '.join(ids)}: the agent did not produce a valid scene",
                            self.agent_hint())
                st.note(f"{', '.join(group)} ✓  " + ui.escape(" · ".join(find_segment(self.script, sid)["title"]
                                                                        for sid in group)))
                st.advance(len(group))
            self.step = None
            pieces = sum(len(narration(find_segment(self.script, sid))) for sid in todo)
            st.done(f"{len(todo)} segments · {pieces} narration pieces")

    # ================================================================ 4-7
    def build(self, review=True):
        script = load_script(self.lesson.script)
        errors = check_script(self.lesson, script)[0]
        if errors:
            ui.fail("the lesson has errors: " + "; ".join(errors[:3]), f"./lezio tools check {self.lesson.id}")
        build_voice(self.lesson)
        rendered = build_video(self.lesson)
        if rendered and review and not getattr(self.a, "no_review", False):
            self.review(rendered)
            build_voice(self.lesson, quiet=True)
            build_video(self.lesson, title="Re-rendering fixed segments", quiet=True)
        self.final_panel(build_join(self.lesson))

    def review(self, ids):
        self.script = load_script(self.lesson.script)
        if not hasattr(self, "material"):
            self.material = mat.Material(self.lesson)
            self.plan_key = self.script.get("plan_key", "")
        size = CONFIG["tuning"]["review_group_size"]
        with ui.step("Reviewing the video", total=len(ids)) as st:
            self.step = st
            changed = []
            for k in range(0, len(ids), size):
                batch = ids[k:k + size]
                task, fixed = tasks.review_task(self.work(), batch)
                self.run_task(task)
                changed += fixed
                st.advance(len(batch))
            self.step = None
            st.done(f"fixed {', '.join(changed)}" if changed else "no problems found")

    def final_panel(self, result):
        path, seconds, size = result
        rows = [("video", f"[bold]{rel(path)}[/]"), ("length", ui.fmt_seconds(seconds)),
                ("size", f"{size / 1e6:.0f} MB")]
        if self.models:
            rows.append(("agent model", ", ".join(sorted(self.models))))
        ui.console.print()
        ui.key_values(rows, title="[ok]done[/]")


# ==================================================================== building blocks (also used by commands)
def build_voice(lesson, quiet=False, segments=None):
    with ui.step("Generating the voice", total=0) as st:
        state = {"generated": 0}

        def on_event(e):
            if e["event"] == "start":
                st.set_total(e["total"])
                st.status(ui.escape(e["tts"]))
            elif e["event"] == "loading":
                st.status("loading the speech model")
            elif e["event"] == "piece":
                state["generated"] += 1
                st.advance()
                st.status(f"{e['key']} · {e['duration']:.1f}s")
        try:
            voice.synthesize_lesson(lesson, segments, on_event=on_event)
        except voice.VoiceError as e:
            ui.fail(f"speech synthesis failed: {ui.escape(str(e))}", f"log: {rel(lesson.logs / 'voice.txt')}")
        st.done(f"{state['generated']} new pieces" if state["generated"] else "up to date")


def build_video(lesson, title="Rendering the video", quiet=False, only=None):
    script = load_script(lesson.script)
    todo = [s["id"] for s in script["segments"] if render.is_outdated(lesson, script, s)
            and (only is None or s["id"] in only)]
    missing = render.missing_audio(lesson, [s for s in script["segments"] if s["id"] in todo])
    if missing:
        ui.fail(f"{len(missing)} narration pieces have no voice (e.g. {missing[0]})", f"./lezio tools audio {lesson.id}")
    if not todo:
        if not quiet:
            ui.console.print(f"[ok]✓[/] [bold]{title}[/]  up to date")
        return []
    with ui.step(title, total=len(todo)) as st:
        st.status(f"{len(todo)} segments, {CONFIG['tuning']['parallel_jobs']} at a time")
        try:
            done = render.render_segments(lesson, todo, on_done=lambda sid, s: (st.advance(), st.status(f"{sid} ✓")))
        except render.RenderError as e:
            ui.fail(f"render failed: {ui.escape(str(e))}", f"logs: {rel(lesson.logs)}")
        st.done(f"{len(done)} segments")
    return done


def build_join(lesson):
    with ui.step("Assembling the final video") as st:
        try:
            result = render.join(lesson)
        except render.RenderError as e:
            ui.fail(ui.escape(str(e)))
        st.done(f"{ui.fmt_seconds(result[1])}")
    return result


# ==================================================================== entry points
def make(a):
    if not a.targets and wizard.interactive() and not a.yes:
        ui.banner()
    run = Run(a)
    run.resolve()
    run.summary()
    run.prepare()
    run.write()
    run.build()


def redo(a):
    """./lezio redo <lesson> s03,s05 [--part script|voice|video] [--note "..."]"""
    yes = a.yes
    a.targets, a.yes = [a.lesson], True
    run = Run(a)
    run.resolve()
    run.interactive = wizard.interactive() and not yes
    script = run.saved
    ids = [x.strip() for x in a.segments.split(",") if x.strip()]
    unknown = [x for x in ids if not find_segment(script, x)]
    if not ids or unknown:
        ui.fail(f"unknown segments: {', '.join(unknown) or 'none given'}",
                f"segments of {run.lesson_id}: {', '.join(s['id'] for s in script['segments'])}")
    what = {"script": "rewrite narration and scene (agent)", "voice": "regenerate the voice",
            "video": "re-render the video"}
    ui.key_values([("lesson", run.lesson_id), ("segments", ", ".join(ids)), ("action", what[a.part])]
                  + ([("note", ui.escape(a.note))] if a.note else []), title="redo")
    if run.interactive and not wizard.confirm("Start?"):
        raise SystemExit(0)
    run.prepare()
    lesson = run.lesson
    if a.part == "script":
        run.backup()
        for sid in ids:
            seg = find_segment(run.script, sid)
            for key in ("narration", "blocks", "scene"):
                seg.pop(key, None)
            lesson.scene_file(sid).unlink(missing_ok=True)
        run.save()
        run.write(only=ids)
    elif a.part == "voice":
        meta = lesson.durations_meta()
        for key in [k for k in meta if k.rsplit("_", 1)[0] in ids]:
            meta.pop(key)
            (lesson.audio / f"{key}.wav").unlink(missing_ok=True)
        lesson.durations.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    else:
        for sid in ids:
            (lesson.video / f"{sid}.json").unlink(missing_ok=True)
    run.build()
