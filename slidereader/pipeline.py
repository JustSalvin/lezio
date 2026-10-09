"""The program behind `./sr`: from a PDF to a finished video.

The program owns the whole process. It calls an LLM only for narrow tasks (slidereader/tasks.py): each
task has a system prompt, a message with the data, and tools defined by the program. The model works only
through those tools - it sees slide pictures and rendered frames through them and submits its work
through them; the program validates every submission on the spot.

  1. read       PDF -> slide images, text lines                                (program)
  2. plan       classify slides, outline, what to skip, visual ideas           (LLM task: submit_plan)
  3. write      script of one group of slides at a time                        (LLM task: submit_script,
                animations previewed and fixed in the same session              preview_animations, finish)
  4. audio      speech synthesis with the configured TTS engine                (program)
  5. render     video of the slides that changed + contact sheets              (program)
  6. review     final frames judged, slides fixed                              (LLM task: replace_slide)
  7. join       output/<lesson>.mp4                                            (program)

Settings precedence: built-in defaults < config.toml < settings saved in the lesson < command-line options.
Every choice is saved in lessons/<lesson>/script.json, so running ./sr again resumes with the same choices.
Slides already written are kept; only missing slides are written (e.g. when the page range grows).
"""
import argparse
import ast
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import tasks, tts_engines
from .cli import (DEPTHS, INPUT, ROOT, VISUAL_MODES, cmd_audio, cmd_init, cmd_join, cmd_render, contact_sheet,
                  die, parse_kv, run_manim, slugify)
from .config import CONFIG, LESSONS, Lesson, lesson_exists
from .llm import get_backend
from .pdf_extract import load_lines
from .script_io import (agent_instructions, load_script, merge_settings, parse_slide_list, settings_to_save,
                        tts_options)
from .ui import ask
from .validate import validate

KINDS = ("title", "agenda", "divider", "content", "diagram", "interactive", "references", "other")
MINUTES_PER_SLIDE = {1: (0.8, 1.8), 2: (0.6, 1.5), 3: (0.3, 0.6), 4: (0.1, 0.25)}   # measured ranges
ATTEMPTS = 3


def stop(msg):
    """The user chose to stop: not an error."""
    print(msg)
    sys.exit(0)


def rel(p):
    return str(Path(p).relative_to(ROOT))


def read_json(path):
    try:
        return json.loads(Path(path).read_text()), None
    except FileNotFoundError:
        return None, f"{rel(path)} was not written"
    except json.JSONDecodeError as e:
        return None, f"{rel(path)} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg})"


def existing_lessons():
    """Existing lessons: {id: (pdf name, saved settings, number of slides)}."""
    out = {}
    for meta in sorted(LESSONS.glob("*/lesson.json")):
        lesson_id = meta.parent.name
        script = meta.parent / "script.json"
        data = json.loads(script.read_text()) if script.exists() else {}
        out[lesson_id] = (Path(json.loads(meta.read_text())["pdf"]).name, data.get("settings", {}),
                          len(data.get("slides", [])))
    return out


class Run:
    """One execution of ./sr (make or update a lesson)."""

    def __init__(self, a):
        self.a = a
        self.interactive = sys.stdin.isatty() and not a.yes
        self.agent_cfg = CONFIG["agent"]
        self.backend = None          # created only when an agent task is needed
        self.user_note = getattr(a, "note", None) or ""

    # ================================================================ choosing what to do
    def choose_target(self):
        a = self.a
        if a.target:
            path = Path(a.target).expanduser()
            if path.suffix.lower() == ".pdf":
                if not path.exists():
                    die(f"file not found: {a.target}")
                return str(path), a.id or slugify(path.stem)
            if lesson_exists(a.target):
                return None, a.target
            die(f"'{a.target}' is neither a PDF nor an existing lesson")
        if not sys.stdin.isatty():
            die("tell me which PDF or lesson: ./sr <file.pdf | lesson> (see ./sr --help)")
        lessons, pdfs = existing_lessons(), sorted(INPUT.glob("*.pdf"))
        options = []
        if lessons:
            print("Existing lessons:")
            for lesson_id, (pdf, s, n) in lessons.items():
                options.append((None, lesson_id))
                print(f"  {len(options)}. {lesson_id}  ({pdf}; pages {s.get('pages') or 'all'}, "
                      f"{s.get('visual', '?')}, depth {s.get('depth', '?')}, {n} slides written)")
        if pdfs:
            print("New lesson from a PDF in input/:")
            for f in pdfs:
                options.append((str(f), slugify(f.stem)))
                print(f"  {len(options)}. {f.name}")
        if not options:
            die("put a PDF in input/ first (or pass its path: ./sr file.pdf)")
        pdf, lesson_id = options[int(ask("Choose", list(range(1, len(options) + 1)), 1)) - 1]
        if pdf and lesson_exists(lesson_id):
            lesson_id = ask("A lesson with this name exists; name for the new lesson", default=lesson_id + "-2")
        return pdf, lesson_id

    def resolve(self):
        a = self.a
        pdf, lesson_id = self.choose_target()
        self.lesson_id, self.pdf_path = lesson_id, pdf
        self.is_new = not lesson_exists(lesson_id)
        if self.is_new:                       # nothing is created before the user confirms
            import pymupdf
            n_pages, current, self.pdf_name = pymupdf.open(pdf).page_count, {}, Path(pdf).name
        else:
            self.lesson = lesson = Lesson(lesson_id)
            lesson.agent.mkdir(parents=True, exist_ok=True)
            lesson.animations_dir.mkdir(parents=True, exist_ok=True)
            self.lines = load_lines(lesson)
            n_pages, self.pdf_name = self.lines["pages"], lesson.pdf.name
            current = json.loads(lesson.script.read_text())
        saved = current.get("settings", {})
        self.existing = {s["slide"]: s for s in current.get("slides", [])}
        base = merge_settings(saved)
        flags = {k: v for k, v in (("pages", a.pages), ("visual", a.visual), ("depth", a.depth),
                                   ("instructions", a.instructions)) if v is not None}
        tts_flags = {**({"engine": a.engine} if a.engine else {}), **({"voice": a.voice} if a.voice else {}),
                     **parse_kv(a.tts)}
        if tts_flags:      # switching engine drops the options of the previous engine
            flags["tts"] = ({} if "engine" in tts_flags else dict(base["tts"])) | tts_flags
        self.rewrite = bool(a.rewrite)
        self.old_instructions = base["instructions"]

        if not self.existing:                      # new (or still empty) lesson: ask only what is missing
            print(f"\n{self.pdf_name}: {n_pages} pages")
            if "pages" not in flags and self.interactive:
                flags["pages"] = ask("Pages to cover (e.g. 1-20, empty = all)", default=saved.get("pages", ""))
            if "visual" not in flags and self.interactive:
                flags["visual"] = ask("Visual mode: slides | mixed | animated", list(VISUAL_MODES), base["visual"])
            if "depth" not in flags and self.interactive:
                flags["depth"] = int(ask("Depth: 1 extensive, 2 faithful, 3 condensed, 4 short",
                                         [1, 2, 3, 4], base["depth"]))
            if "instructions" not in flags and self.interactive:
                flags["instructions"] = ask("Instructions for the agent (optional, e.g. 'skip interactive slides such as polls')",
                                            default=base["instructions"]) or ""
        elif not flags and not self.rewrite and self.interactive:   # existing lesson, nothing specified
            print(f"\nLesson {lesson_id}: pages {base['pages'] or 'all'}, {base['visual']}, depth {base['depth']}, "
                  f"{len(self.existing)} slides written")
            print("  1. update the video (write what is missing, rebuild what changed)\n"
                  "  2. change the pages\n"
                  "  3. change visual mode or depth (rewrites the script)\n"
                  "  4. change the instructions for the agent\n"
                  "  5. rewrite the script from scratch")
            choice = ask("What do you want to do", [1, 2, 3, 4, 5], 1)
            if choice == "2":
                flags["pages"] = ask(f"Pages to cover (now {base['pages'] or 'all'})", default=base["pages"])
            elif choice == "3":
                flags["visual"] = ask("Visual mode", list(VISUAL_MODES), base["visual"])
                flags["depth"] = int(ask("Depth", [1, 2, 3, 4], base["depth"]))
            elif choice == "4":
                flags["instructions"] = ask("Instructions for the agent (empty = none)", default="") or ""
            elif choice == "5":
                self.rewrite = True

        self.settings = {**base, **flags}
        self.settings["depth"] = int(self.settings["depth"])
        tts = tts_options(self.settings)
        problems = tts_engines.get_engine(tts["engine"]).validate({k: v for k, v in tts.items() if k != "engine"})
        if problems:
            die("TTS: " + "; ".join(problems) + "  (see ./sr tts)")
        if self.settings["depth"] not in DEPTHS or self.settings["visual"] not in VISUAL_MODES:
            die("invalid visual mode or depth")
        style_changed = bool(self.existing) and any(saved.get(k) is not None and saved.get(k) != self.settings[k]
                                                    for k in ("visual", "depth"))
        self.rewrite = self.rewrite or style_changed
        self.scope = parse_slide_list(self.settings["pages"], range(1, n_pages + 1))
        if not self.scope:
            die(f"no pages selected (the PDF has {n_pages})")

    def summary(self):
        s, kept = self.settings, ({} if self.rewrite else self.existing)
        in_scope = [n for n in self.scope if n in kept]
        removed = sorted(n for n in kept if n not in self.scope)
        to_write = [n for n in self.scope if n not in kept and n not in s["skip"]]
        low, high = (m * (len(in_scope) + len(to_write)) for m in MINUTES_PER_SLIDE[s["depth"]])
        tts = tts_options(s)
        voice = f"{tts['engine']}: " + ", ".join(f"{k}={v}" for k, v in tts.items() if k not in ("engine", "model"))
        print(f"""
Summary
  lesson     {self.lesson_id}   ({self.pdf_name})
  pages      {s['pages'] or 'all'}  ({len(self.scope)} pages)
  visual     {s['visual']}   depth {s['depth']} ({DEPTHS[s['depth']]})
  voice      {voice}
  agent      {agent_instructions(s) or 'no extra instructions'}
  script     {len(in_scope)} slides kept, {len(to_write)} to write"""
              + (f", {len(removed)} removed from the video {removed}" if removed else "")
              + ("   (REWRITE: the current script is backed up)" if self.rewrite and self.existing else "")
              + f"\n  estimate   {low:.0f}-{high:.0f} min of video   ->  output/{self.lesson_id}.mp4")
        if in_scope and s["instructions"] != self.old_instructions:
            print("  note       new instructions apply to slides written from now on "
                  "(--rewrite or ./sr redo to apply them to the existing ones)")
        destructive = (self.rewrite and self.existing) or removed
        if self.interactive:
            if (ask("Proceed", ["y", "n"], "y") or "y") != "y":
                stop("Stopped, nothing changed.")
        elif destructive and not self.a.yes:
            die("this changes the existing script; run again with --yes to confirm")

    # ================================================================ agent
    def run_task(self, task):
        """Run one agent task through the configured LLM backend."""
        if self.backend is None:
            self.backend = get_backend()
        print(f"    agent task: {task.label}", flush=True)
        outcome = self.backend.run(task)
        if outcome.error:
            print(f"    agent stopped: {outcome.error}")
        return outcome

    # ================================================================ script on disk
    def save_script(self):
        """Write settings + slides in scope order (kept slides and newly written ones)."""
        slides = [self.slides[n] for n in self.scope if n in self.slides]
        self.lesson.script.write_text(json.dumps({"settings": settings_to_save(self.settings), "slides": slides},
                                                 ensure_ascii=False, indent=2) + "\n")
        return slides

    def backup(self):
        if self.lesson.script.exists() and self.existing:
            dst = self.lesson.agent / f"backup_{time.strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.lesson.script, dst)
            print(f"    previous script saved in {rel(dst)}")

    def prepare(self):
        if self.is_new:
            print("\n== 1. Reading the PDF")
            cmd_init(argparse.Namespace(pdf=self.pdf_path, id=self.lesson_id))
            self.lesson = Lesson(self.lesson_id)
            self.lesson.agent.mkdir(parents=True, exist_ok=True)
            self.lines = load_lines(self.lesson)
        if self.rewrite or any(n not in self.scope for n in self.existing):
            self.backup()
        if self.rewrite:
            for f in list(self.lesson.agent.glob("plan.json")) + list(self.lesson.agent.glob("group_*.json")):
                f.unlink()
            for f in self.lesson.animations_dir.glob("group_*.py"):
                f.unlink()
            self.existing = {}
        self.slides = dict(self.existing)
        self.save_script()

    # ================================================================ 2. plan
    def plan(self):
        out = self.lesson.agent / "plan.json"

        def check():
            data, err = read_json(out)
            if err:
                return [err]
            items = data.get("slides") if isinstance(data, dict) else None
            if not isinstance(items, list):
                return ['the plan needs a "slides" list']
            problems = []
            numbers = [i.get("slide") for i in items if isinstance(i, dict)]
            if numbers != self.scope:
                problems.append(f"plan slides must be exactly {self.scope} in order (got {numbers})")
            for i in items:
                if isinstance(i, dict) and i.get("kind") not in KINDS:
                    problems.append(f"slide {i.get('slide')}: kind must be one of {KINDS}")
                if isinstance(i, dict) and not isinstance(i.get("skip"), bool):
                    problems.append(f"slide {i.get('slide')}: skip must be true or false")
            if not isinstance(data.get("outline"), str) or not data["outline"].strip():
                problems.append('the plan needs an "outline" text')
            return problems

        if not check():
            self.plan_data = json.loads(out.read_text())
            return
        print("\n== 2. Planning the lesson (agent)")
        for _ in range(2):
            self.run_task(tasks.plan_task(self))
            if not check():
                break
        else:
            die(f"the agent did not produce a valid plan: {'; '.join(check())}")
        plan = json.loads(out.read_text())
        print(f"\n    {plan.get('title', '')}\n    {plan['outline'][:300]}")
        for i in plan["slides"]:
            done = " (already written)" if i["slide"] in self.slides else ""
            print(f"    {i['slide']:3d}  {'skip' if i['skip'] else i['kind']:11s} {i.get('summary', '')[:65]}{done}")
        if self.interactive and (ask("Continue with this plan", ["y", "n"], "y") or "y") != "y":
            stop(f"Stopped. Edit {rel(out)} if you want, then run ./sr again.")
        self.plan_data = plan

    # ================================================================ 3. write
    def write(self, only=None):
        """Write every slide in scope that has no script yet (or exactly the slides in `only`)."""
        if not only and all(n in self.slides or n in self.settings["skip"] for n in self.scope):
            return
        self.plan()
        plan = {i["slide"]: i for i in self.plan_data["slides"]}
        if not only:
            self.settings["skip"] = [n for n in self.scope if plan[n]["skip"] and n not in self.slides]
        todo = [plan[n] for n in self.scope
                if (n in only if only else n not in self.slides and not plan[n]["skip"])]
        if not todo:
            self.save_script()
            return
        size = self.agent_cfg["group_size"]
        groups = []
        for item in todo:                         # groups of consecutive slides, at most `size` each
            if groups and len(groups[-1]) < size and \
                    self.scope.index(item["slide"]) == self.scope.index(groups[-1][-1]["slide"]) + 1:
                groups[-1].append(item)
            else:
                groups.append([item])
        print(f"\n== 3. Writing the script (agent, {len(todo)} slides in {len(groups)} groups)")
        for k, items in enumerate(groups, 1):
            self.write_group(k, len(groups), items, plan)
        slides = self.save_script()
        errors = validate(self.lesson, self.settings, slides)[0]
        if errors:
            die("the script has errors: " + "; ".join(errors[:5]) + f"  (./sr check {self.lesson.id})")

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
        after = ("These slides close the video: end with a short closing (what was covered)."
                 if not nxt else "Next slides: " + "; ".join(f"{n}: {plan[n].get('summary', '')}" for n in nxt))
        return before, after

    def group_problems(self, group_file, numbers):
        data, err = read_json(group_file)
        if err:
            return [err]
        slides = data.get("slides") if isinstance(data, dict) else None
        if not isinstance(slides, list) or [s.get("slide") for s in slides if isinstance(s, dict)] != numbers:
            return [f"the group must contain exactly the slides {numbers}"]
        errors, warnings = validate(self.lesson, self.settings, slides, coverage=False)
        return errors + [w for w in warnings if "digits" in w or "words" in w]

    def write_group(self, k, total, items, plan):
        numbers = [i["slide"] for i in items]
        group_file = self.lesson.agent / f"group_{numbers[0]:03d}.json"
        print(f"\n  group {k}/{total}: slides {numbers}")
        if not self.group_problems(group_file, numbers):
            print("    reusing the script already written for these slides")
            self.take_group(group_file)
            return
        before, after = self.context(items, plan)
        for _ in range(2):
            self.run_task(tasks.write_task(self, items, self.plan_data["outline"], before, after, self.user_note))
            if not self.group_problems(group_file, numbers):
                return
        die(f"slides {numbers}: the agent did not produce a valid script ({'; '.join(self.group_problems(group_file, numbers)[:3])})")

    def take_group(self, group_file):
        data = json.loads(group_file.read_text())
        for s in data["slides"]:
            self.slides[s["slide"]] = s
        self.save_script()

    def render_animations(self, beats, names=None):
        """Render animation beats alone (placeholder timing); returns (slide, beat, name, sheet, error)."""
        def one(i):
            n, k = beats[i]
            label = f"anim_s{n:02d}_b{k:02d}"
            mp4 = run_manim(self.lesson, n, False, only_beat=k, fake=self.agent_cfg["placeholder_seconds"], name=label)
            return contact_sheet(mp4, self.lesson.qa / f"{label}.png", frames=12)

        out = []
        with ThreadPoolExecutor(CONFIG["video"]["parallel_jobs"]) as pool:
            futures = [pool.submit(one, i) for i in range(len(beats))]
            for i, fut in enumerate(futures):
                n, k = beats[i]
                name = names[i] if names else ""
                try:
                    out.append((n, k, name, fut.result(), None))
                except Exception as e:  # noqa: BLE001
                    out.append((n, k, name, None, str(e)[:400]))
        return out

    # ================================================================ 4-7
    def build(self):
        if validate(self.lesson, *load_script(self.lesson.script))[0]:
            die(f"the script has errors: ./sr check {self.lesson.id}")
        args = argparse.Namespace(lesson=self.lesson.id, slides="", preview=False, outdated=True, small=True)
        print("\n== 4. Narration audio")
        cmd_audio(args)
        print("\n== 5. Video")
        rendered = cmd_render(args) or []
        if rendered and self.agent_cfg["review"] and not self.a.no_review:
            print(f"\n== 6. Final review of the {len(rendered)} re-rendered slides (agent)")
            self.review(sorted(rendered))
            cmd_audio(args)                       # the program re-checks what changed, whatever the agent says
            cmd_render(args)
        print("\n== 7. Final video")
        cmd_join(args)
        print(f"\nDone: {rel(self.lesson.output)}")

    def review(self, numbers):
        size = self.agent_cfg["review_group_size"]
        for k in range(0, len(numbers), size):
            batch = numbers[k:k + size]
            task, state = tasks.review_task(self, batch)
            self.run_task(task)
            if state["changed"]:
                print(f"    changed slides {state['changed']}")
        errors = validate(self.lesson, *load_script(self.lesson.script))[0]
        if errors:
            die("the script has errors after the review: " + "; ".join(errors[:5]))


# ==================================================================== entry points
def make(a):
    """./sr [pdf | lesson] [options]: create or update a lesson video."""
    run = Run(a)
    run.resolve()
    run.summary()
    run.prepare()
    run.write()
    run.build()


def redo(a):
    """./sr redo <lesson> --slides 7,9 [--part script|voice|video] [--note "..."]"""
    a.target, a.rewrite = a.lesson, False
    a.pages = a.visual = a.depth = a.voice = a.engine = a.instructions = a.id = None
    a.tts = []
    yes = a.yes
    a.yes = True                                  # nothing to ask while resolving the lesson
    run = Run(a)
    run.resolve()
    run.interactive = sys.stdin.isatty() and not yes
    slides = parse_slide_list(a.slides, sorted(run.existing))
    if not slides:
        die("choose slides that already have a script, e.g. --slides 7 or --slides 3-5")
    lesson = run.lesson
    what = {"script": "rewrite the script (agent)", "voice": "regenerate the voice",
            "video": "re-render the video"}[a.part]
    print(f"\nRedo slides {slides}: {what}" + (f"\n  note for the agent: {a.note}" if a.note else ""))
    if run.interactive and (ask("Proceed", ["y", "n"], "y") or "y") != "y":
        stop("Stopped, nothing changed.")
    run.prepare()
    if a.part == "script":
        run.backup()
        for n in slides:
            run.slides.pop(n, None)
        for f in lesson.agent.glob("group_*.json"):        # do not reuse an old version of these slides
            data, _ = read_json(f)
            if data and any(s.get("slide") in slides for s in data.get("slides", [])):
                f.unlink()
                f.with_name(f.stem + "_judge.json").unlink(missing_ok=True)
        run.save_script()
        run.write(only=slides)
    elif a.part == "voice":
        have = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}
        for key in [k for k in have if int(k[1:3]) in slides]:
            have.pop(key)
            (lesson.audio / f"{key}.wav").unlink(missing_ok=True)
        lesson.durations.write_text(json.dumps(have, ensure_ascii=False, indent=1))
    else:
        for n in slides:
            (lesson.video / f"slide_{n:02d}.json").unlink(missing_ok=True)
    run.build()
