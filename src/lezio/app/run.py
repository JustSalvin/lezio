"""The program: from a PDF (or an existing lesson) to a finished video.

    1. read       PDF -> slide images and text lines                         program
    2. plan       classify slides, outline, what to skip, visual ideas       agent task (plan)
    3. write      script of one group of slides at a time                    agent tasks (write)
    4. voice      speech synthesis with the configured TTS engine            program
    5. video      render the slides that changed                             program
    6. review     final frames judged, broken slides fixed                   agent task (review)
    7. join       output/<lesson>.mp4                                        program

Per-video choices (pages, visual mode, depth, instructions) come from the wizard or the options and are
saved in the lesson; configuration comes from config.toml. Every step is resumable: slides already
written, audio already generated and videos already rendered are kept.
"""
import json
import shutil
import time
from pathlib import Path

from ..agent import tasks
from ..agent.backends import get_backend, task_options
from ..config import CONFIG, INPUT, ROOT
from ..lesson import Lesson, all_lessons, lesson_exists, slugify
from ..pdf import extract, load_lines
from ..script import load_script, parse_pages, save_script
from ..settings import (DEPTHS, default_settings, merge_settings, piece_tts, tts_label, tts_options)
from ..validate import validate
from ..video import render
from ..voice import client as voice
from ..voice import engines
from . import ui, wizard

KINDS_SHOWN = {"title": "title", "agenda": "agenda", "divider": "divider", "content": "content",
               "diagram": "diagram", "interactive": "interactive", "references": "refs", "other": "other"}
MINUTES_PER_SLIDE = {1: (0.8, 1.8), 2: (0.6, 1.5), 3: (0.3, 0.6), 4: (0.1, 0.25)}   # measured ranges


def rel(p):
    return str(Path(p).relative_to(ROOT))


class Run:
    def __init__(self, a):
        self.a = a
        self.interactive = wizard.interactive() and not a.yes
        self.backend = None
        self.step = None                 # the live UI step, if any (agent events are shown there)
        self.models = set()
        self.note = getattr(a, "note", None) or ""

    # ================================================================ what to work on
    def choose(self):
        a = self.a
        if a.target:
            path = Path(a.target).expanduser()
            if path.suffix.lower() == ".pdf":
                if not path.exists():
                    ui.fail(f"file not found: {a.target}")
                return str(path), a.id or slugify(path.stem)
            if lesson_exists(a.target):
                return None, a.target
            ui.fail(f"'{a.target}' is neither a PDF nor an existing lesson", "see ./lezio --help")
        if not self.interactive:
            ui.fail("tell me which PDF or lesson", "./lezio <file.pdf | lesson>   (see ./lezio --help)")
        lessons = []
        for lid in all_lessons():
            saved = json.loads((Lesson(lid).script).read_text())
            s, n = saved.get("settings", {}), len(saved.get("slides", []))
            lessons.append((lid, f"{Lesson(lid).pdf.name} · pages {s.get('pages') or 'all'} · "
                                 f"{s.get('visual', '?')} · depth {s.get('depth', '?')} · {n} slides"))
        pdfs = [(str(p), p.name) for p in sorted(INPUT.glob("*.pdf"))]
        if not lessons and not pdfs:
            ui.fail("no PDF in input/", "put a PDF in input/ or run ./lezio <file.pdf>")
        kind, value = wizard.choose_target(lessons, pdfs)
        if kind == "lesson":
            return None, value
        lid = slugify(Path(value).stem)
        if lesson_exists(lid):
            lid = slugify(wizard.lesson_name(lid + "-2"))
        return value, lid

    def resolve(self):
        a = self.a
        self.pdf_path, self.lesson_id = self.choose()
        self.is_new = not lesson_exists(self.lesson_id)
        if self.is_new:                  # nothing is created before the user confirms
            import pymupdf
            n_pages, saved, self.existing = pymupdf.open(self.pdf_path).page_count, {}, {}
            self.pdf_name = Path(self.pdf_path).name
        else:
            self.lesson = Lesson(self.lesson_id)
            self.lines = load_lines(self.lesson)
            n_pages, self.pdf_name = self.lines["pages"], self.lesson.pdf.name
            data = json.loads(self.lesson.script.read_text())
            saved, self.existing = data.get("settings", {}), {s["slide"]: s for s in data.get("slides", [])}
        base = merge_settings(saved)
        flags = {k: v for k, v in (("pages", a.pages), ("visual", a.visual), ("depth", a.depth),
                                   ("instructions", a.instructions)) if v is not None}
        self.rewrite = bool(a.rewrite)

        if self.interactive and not self.existing:
            ui.console.print(f"\n[bold]{self.pdf_name}[/] [muted]· {n_pages} pages[/]")
            flags.setdefault("pages", wizard.pages(n_pages, base["pages"]))
            flags.setdefault("visual", wizard.visual(base["visual"]))
            flags.setdefault("depth", wizard.depth(base["depth"]))
            flags.setdefault("instructions", wizard.instructions(base["instructions"]))
        elif self.interactive and not flags and not self.rewrite:
            action = wizard.existing_action(
                f"{self.lesson_id} · pages {base['pages'] or 'all'} · {base['visual']} · depth {base['depth']} · "
                f"{len(self.existing)} slides written")
            if action == "pages":
                flags["pages"] = wizard.pages(n_pages, base["pages"])
            elif action == "style":
                flags["visual"] = wizard.visual(base["visual"])
                flags["depth"] = wizard.depth(base["depth"])
            elif action == "instructions":
                flags["instructions"] = wizard.instructions(base["instructions"])
            elif action == "rewrite":
                self.rewrite = True

        self.settings = {**base, **flags}
        self.old_instructions = base["instructions"]
        if self.existing and any(saved.get(k) is not None and saved[k] != self.settings[k] for k in ("visual", "depth")):
            self.rewrite = True
        self.scope = parse_pages(self.settings["pages"], range(1, n_pages + 1))
        if not self.scope:
            ui.fail(f"no pages selected (the PDF has {n_pages})")
        tts = tts_options()
        problems = engines.get_engine(tts["engine"]).validate({k: v for k, v in tts.items() if k != "engine"})
        if problems:
            ui.fail("config.toml [tts]: " + "; ".join(problems), "see ./lezio tts")

    # ================================================================ summary
    def summary(self):
        s, kept = self.settings, ({} if self.rewrite else self.existing)
        in_scope = [n for n in self.scope if n in kept]
        removed = sorted(n for n in kept if n not in self.scope)
        to_write = [n for n in self.scope if n not in kept and n not in s["skip"]]
        low, high = (m * (len(in_scope) + len(to_write)) for m in MINUTES_PER_SLIDE[s["depth"]])
        voice_line = tts_label()
        if not self.is_new and self.lesson.durations.exists():
            stale = sum(1 for m in self.lesson.durations_meta().values() if piece_tts(m) != tts_options())
            if stale:
                voice_line += f"  [warn](changed in config.toml: {stale} pieces will be regenerated)[/]"
        script = f"{len(in_scope)} slides kept · {len(to_write)} to write"
        if removed:
            script += f" · [warn]{len(removed)} removed ({ui.fmt_pages(removed)})[/]"
        if self.rewrite and self.existing:
            script += "  [warn](rewrite: the current script is backed up)[/]"
        opts = task_options("write")
        rows = [("lesson", f"[bold]{self.lesson_id}[/]  [muted]{self.pdf_name}[/]"),
                ("pages", f"{ui.fmt_pages(self.scope)}  [muted]({len(self.scope)})[/]"),
                ("mode", f"{s['visual']} · depth {s['depth']} ({DEPTHS[s['depth']]})"),
                ("voice", voice_line),
                ("agent", f"{CONFIG['agent']['backend']} · model {opts['model'] or 'default'}"
                          + (f" · effort {opts['effort']}" if opts["effort"] else "")),
                ("instructions", s["instructions"] or "[muted]none[/]"),
                ("script", script),
                ("estimate", f"{low:.0f}-{high:.0f} min of video  [muted]→ output/{self.lesson_id}.mp4[/]")]
        if in_scope and s["instructions"] != self.old_instructions:
            rows.append(("note", "[muted]new instructions apply to slides written from now on "
                                 "(use rewrite or ./lezio redo for the others)[/]"))
        ui.console.print()
        ui.key_values(rows, title="summary")
        destructive = (self.rewrite and self.existing) or removed
        if self.interactive:
            if not wizard.confirm("Start?"):
                ui.info("Stopped, nothing changed.")
                raise SystemExit(0)
        elif destructive and not self.a.yes:
            ui.fail("this changes the existing script", "run again with --yes to confirm")

    # ================================================================ preparation
    def prepare(self):
        if self.is_new:
            with ui.step("Reading the PDF") as st:
                pdf = Path(self.pdf_path).resolve()
                INPUT.mkdir(exist_ok=True)
                if pdf.parent != INPUT.resolve():
                    shutil.copy2(pdf, INPUT / pdf.name)
                    pdf = INPUT / pdf.name
                self.lesson = Lesson.create(self.lesson_id, pdf)
                st.status("slide images and text lines")
                pages = extract(self.lesson)
                self.lines = load_lines(self.lesson)
                st.done(f"{pages} pages")
        self.lesson.agent.mkdir(parents=True, exist_ok=True)
        self.lesson.animations_dir.mkdir(parents=True, exist_ok=True)
        if self.rewrite or any(n not in self.scope for n in self.existing):
            self.backup()
        if self.rewrite:
            for f in list(self.lesson.agent.glob("plan.json")) + list(self.lesson.agent.glob("group_*")):
                f.unlink()
            for f in self.lesson.animations_dir.glob("group_*.py"):
                f.unlink()
            self.existing = {}
        self.slides = dict(self.existing)
        self.save_script()

    def backup(self):
        if self.lesson.script.exists() and self.existing:
            dst = self.lesson.agent / f"backup_{time.strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.lesson.script, dst)

    def save_script(self):
        slides = [self.slides[n] for n in self.scope if n in self.slides]
        save_script(self.lesson.script, self.settings, slides)
        return slides

    def save_plan(self, plan):
        (self.lesson.agent / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2))

    def take_group(self, group_file):
        for s in json.loads(group_file.read_text())["slides"]:
            self.slides[s["slide"]] = s
        self.save_script()

    # ================================================================ agent
    def run_task(self, task):
        if self.backend is None:
            self.backend = get_backend()
        outcome = self.backend.run(task)
        if outcome.model:
            self.models.add(outcome.model)
        return outcome

    def on_agent_event(self, kind, data):
        if self.step is None:
            return
        if kind == "model":
            self.models.add(data)
        elif kind == "tool":
            name, args = data
            text = {
                "view_slides": lambda: f"looking at slides {ui.fmt_pages(args.get('numbers') or [])}",
                "submit_plan": lambda: "submitting the plan",
                "submit_script": lambda: "submitting the script",
                "preview_animations": lambda: "rendering animation previews",
                "view_final": lambda: f"watching slide {args.get('slide')}",
                "replace_slide": lambda: f"fixing slide {(args.get('entry') or {}).get('slide', '')}",
                "finish": lambda: "finishing",
            }.get(name, lambda: name)()
            self.step.status(f"agent: {text}")
        elif kind == "rejected":
            self.step.status(f"agent: fixing → {data[1][:80]}")

    # ================================================================ 2. plan
    def plan_problems(self):
        plan_file = self.lesson.agent / "plan.json"
        if not plan_file.exists():
            return ["no plan"]
        plan = json.loads(plan_file.read_text())
        numbers = [i.get("slide") for i in plan.get("slides", [])]
        return [] if numbers == self.scope and plan.get("outline") else ["plan does not match the pages"]

    def plan(self):
        if not self.plan_problems():
            self.plan_data = json.loads((self.lesson.agent / "plan.json").read_text())
            return
        with ui.step("Planning the lesson") as st:
            self.step = st
            for _ in range(2):
                self.run_task(tasks.plan_task(self))
                if not self.plan_problems():
                    break
            else:
                ui.fail("the agent did not produce a valid plan", f"log: {rel(self.lesson.agent / 'log.jsonl')}")
            self.step = None
            self.plan_data = json.loads((self.lesson.agent / "plan.json").read_text())
            skipped = [i["slide"] for i in self.plan_data["slides"] if i["skip"]]
            st.done(f"{len(self.scope)} pages" + (f" · skipping {ui.fmt_pages(skipped)}" if skipped else ""))
        self.show_plan()
        if self.interactive and not wizard.confirm("Continue with this plan?"):
            ui.info(f"Stopped. You can edit {rel(self.lesson.agent / 'plan.json')} and run ./lezio again.")
            raise SystemExit(0)

    def show_plan(self):
        from rich.table import Table
        table = Table(box=None, padding=(0, 1), show_header=False)
        table.add_column(style="muted", justify="right")
        table.add_column(style="accent")
        table.add_column()
        for i in self.plan_data["slides"]:
            done = " [muted](written)[/]" if i["slide"] in self.slides else ""
            if i["skip"]:
                table.add_row(str(i["slide"]), "skip", f"[muted]{i.get('summary', '')[:90]}[/]")
            else:
                table.add_row(str(i["slide"]), KINDS_SHOWN.get(i["kind"], i["kind"]), i.get("summary", "")[:90] + done)
        ui.console.print(f"\n   [bold]{self.plan_data.get('title', '')}[/]")
        ui.console.print(table)
        ui.console.print()

    # ================================================================ 3. write
    def write(self, only=None):
        if not only and all(n in self.slides or n in self.settings["skip"] for n in self.scope):
            return
        self.plan()
        plan = {i["slide"]: i for i in self.plan_data["slides"]}
        if not only:
            self.settings["skip"] = [n for n in self.scope if plan[n]["skip"] and n not in self.slides]
        todo = [plan[n] for n in self.scope if (n in only if only else n not in self.slides and not plan[n]["skip"])]
        self.save_script()
        if not todo:
            return
        size = CONFIG["tuning"]["group_size"]
        groups = []
        for item in todo:                         # consecutive slides, at most `size` per group
            if groups and len(groups[-1]) < size and \
                    self.scope.index(item["slide"]) == self.scope.index(groups[-1][-1]["slide"]) + 1:
                groups[-1].append(item)
            else:
                groups.append([item])
        with ui.step("Writing the script", total=len(todo)) as st:
            self.step = st
            anims = 0
            for items in groups:
                numbers = [i["slide"] for i in items]
                st.status(f"slides {ui.fmt_pages(numbers)}")
                self.write_group(items, plan)
                n_anim = sum("anim" in b for n in numbers for b in self.slides[n]["beats"])
                anims += n_anim
                st.note(f"slides {ui.fmt_pages(numbers)} ✓" + (f"  {n_anim} animations" if n_anim else ""))
                st.advance(len(items))
            self.step = None
            st.done(f"{len(todo)} slides · {anims} animations")
        errors = validate(self.lesson, self.settings, self.save_script())[0]
        if errors:
            ui.fail("the script has errors: " + "; ".join(errors[:3]), f"./lezio check {self.lesson.id}")

    def context(self, items, plan):
        first, last = items[0]["slide"], items[-1]["slide"]
        narrated = [n for n in self.scope if n not in self.settings["skip"]]
        prev = [n for n in narrated if n < first and n in self.slides]
        if first == narrated[0]:
            before = "These slides open the video: begin with a short welcome and introduction."
        elif prev:
            said = " ".join(b.get("say", "") for b in self.slides[prev[-1]]["beats"][-2:] if "say" in b)
            before = (f"The previous slide ({prev[-1]}) ended with: \"{said[-300:]}\" - continue naturally, "
                      "do not welcome again.")
        else:
            before = "Earlier slides exist: continue naturally, do not welcome again."
        nxt = [n for n in narrated if n > last][:4]
        after = ("These slides close the video: end with a short closing (what was covered)." if not nxt else
                 "Next slides: " + "; ".join(f"{n}: {plan[n].get('summary', '')}" for n in nxt))
        return before, after

    def group_problems(self, group_file, numbers):
        try:
            slides = json.loads(group_file.read_text())["slides"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return ["not written"]
        if [s.get("slide") for s in slides] != numbers:
            return [f"must contain exactly the slides {numbers}"]
        errors, warnings = validate(self.lesson, self.settings, slides, coverage=False)
        return errors + [w for w in warnings if "digits" in w or "words" in w]

    def write_group(self, items, plan):
        numbers = [i["slide"] for i in items]
        group_file = self.lesson.agent / f"group_{numbers[0]:03d}.json"
        if not self.group_problems(group_file, numbers):          # written in a previous run
            self.take_group(group_file)
            return
        before, after = self.context(items, plan)
        for _ in range(2):
            self.run_task(tasks.write_task(self, items, self.plan_data["outline"], before, after, self.note))
            if not self.group_problems(group_file, numbers):
                return
        problems = self.group_problems(group_file, numbers)
        ui.fail(f"slides {ui.fmt_pages(numbers)}: the agent did not produce a valid script",
                "; ".join(problems[:3]) + f"   (log: {rel(self.lesson.agent / 'log.jsonl')})")

    # ================================================================ 4-7
    def build(self, review=True):
        settings, slides = load_script(self.lesson.script)
        errors = validate(self.lesson, settings, slides)[0]
        if errors:
            ui.fail("the script has errors: " + "; ".join(errors[:3]), f"./lezio check {self.lesson.id}")
        build_voice(self.lesson)
        rendered = build_video(self.lesson)
        if rendered and review and not self.a.no_review:
            self.review(rendered)
            build_voice(self.lesson, quiet=True)
            build_video(self.lesson, title="Re-rendering fixed slides", quiet=True)
        self.final_panel(build_join(self.lesson))

    def review(self, numbers):
        self.slides = {s["slide"]: s for s in load_script(self.lesson.script)[1]}
        size = CONFIG["tuning"]["review_group_size"]
        with ui.step("Reviewing the video", total=len(numbers)) as st:
            self.step = st
            changed = []
            for k in range(0, len(numbers), size):
                batch = numbers[k:k + size]
                task, fixed = tasks.review_task(self, batch)
                self.run_task(task)
                changed += fixed
                st.advance(len(batch))
            self.step = None
            st.done(f"fixed slides {ui.fmt_pages(changed)}" if changed else "no problems found")
        errors = validate(self.lesson, *load_script(self.lesson.script))[0]
        if errors:
            ui.fail("the script has errors after the review: " + "; ".join(errors[:3]))

    def final_panel(self, result):
        path, seconds, size = result
        rows = [("video", f"[bold]{rel(path)}[/]"), ("length", ui.fmt_seconds(seconds)),
                ("size", f"{size / 1e6:.0f} MB")]
        if self.models:
            rows.append(("agent model", ", ".join(sorted(self.models))))
        ui.console.print()
        ui.key_values(rows, title="[ok]done[/]")


# ==================================================================== building blocks (also used by commands)
def build_voice(lesson, quiet=False):
    with ui.step("Generating the voice", total=0) as st:
        state = {"generated": 0}

        def on_event(e):
            if e["event"] == "start":
                st.set_total(e["total"])
                st.status(e["tts"])
            elif e["event"] == "loading":
                st.status("loading the speech model")
            elif e["event"] == "piece":
                state["generated"] += 1
                st.advance()
                st.status(f"{e['key']} · {e['duration']:.1f}s")
        try:
            voice.synthesize_lesson(lesson, on_event=on_event)
        except voice.VoiceError as e:
            ui.fail(f"speech synthesis failed: {e}", f"log: {rel(lesson.logs / 'voice.txt')}")
        st.done(f"{state['generated']} new pieces" if state["generated"] else "up to date")


def build_video(lesson, title="Rendering the video", quiet=False, pages=None):
    settings, slides = load_script(lesson.script)
    todo = [s["slide"] for s in slides if render.is_outdated(lesson, settings, s)
            and (pages is None or s["slide"] in pages)]
    missing = render.missing_audio(lesson, [s for s in slides if s["slide"] in todo])
    if missing:
        ui.fail(f"{len(missing)} narration pieces are missing (e.g. {missing[0]})")
    if not todo:
        if not quiet:
            ui.console.print(f"[ok]✓[/] [bold]{title}[/]  up to date")
        return []
    with ui.step(title, total=len(todo)) as st:
        st.status(f"{len(todo)} slides, {CONFIG['tuning']['parallel_jobs']} at a time")
        try:
            done = render.render_slides(lesson, todo, on_done=lambda n, s: (st.advance(), st.status(f"slide {n} ✓")))
        except render.RenderError as e:
            ui.fail(f"render failed: {e}")
        st.done(f"{len(done)} slides")
    return done


def build_join(lesson):
    with ui.step("Assembling the final video") as st:
        try:
            result = render.join(lesson)
        except render.RenderError as e:
            ui.fail(str(e))
        st.done(f"{ui.fmt_seconds(result[1])}")
    return result


# ==================================================================== entry points
def make(a):
    run = Run(a)
    run.resolve()
    run.summary()
    run.prepare()
    run.write()
    run.build()


def redo(a):
    """./lezio redo <lesson> --slides 7,9 [--part script|voice|video] [--note "..."]"""
    a.target, a.rewrite, a.pages, a.visual, a.depth, a.instructions, a.id = a.lesson, False, None, None, None, None, None
    yes, a.yes = a.yes, True
    run = Run(a)
    run.resolve()
    run.interactive = wizard.interactive() and not yes
    slides = parse_pages(a.slides, sorted(run.existing))
    if not slides:
        ui.fail("choose slides that already have a script", "e.g. --slides 7 or --slides 3-5")
    what = {"script": "rewrite the script (agent)", "voice": "regenerate the voice", "video": "re-render the video"}
    ui.key_values([("lesson", run.lesson_id), ("slides", ui.fmt_pages(slides)), ("action", what[a.part])]
                  + ([("note", a.note)] if a.note else []), title="redo")
    if run.interactive and not wizard.confirm("Start?"):
        raise SystemExit(0)
    run.prepare()
    lesson = run.lesson
    if a.part == "script":
        run.backup()
        for n in slides:
            run.slides.pop(n, None)
        for f in lesson.agent.glob("group_*.json"):
            try:
                if any(s.get("slide") in slides for s in json.loads(f.read_text()).get("slides", [])):
                    f.unlink()
            except (json.JSONDecodeError, AttributeError):
                pass
        run.save_script()
        run.write(only=slides)
    elif a.part == "voice":
        meta = lesson.durations_meta()
        for key in [k for k in meta if int(k[1:3]) in slides]:
            meta.pop(key)
            (lesson.audio / f"{key}.wav").unlink(missing_ok=True)
        lesson.durations.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    else:
        for n in slides:
            (lesson.video / f"slide_{n:02d}.json").unlink(missing_ok=True)
    run.build()
