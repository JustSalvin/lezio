"""The program behind `./sr make`.

The program owns the whole process. It calls the agent only for narrow tasks, each with given inputs
and an exact output file, and checks every result itself:

  1. init       PDF -> slide images, text lines, overview                      (program)
  2. plan       classify slides, outline, what to skip, visual ideas           (agent task, validated)
  3. write      script of one group of slides at a time                        (agent task per group)
     check      validation; problems are sent back to the agent                (program -> agent fix)
     animations rendered alone, then judged from contact sheets                (program -> agent judge)
  4. audio      local speech synthesis                                         (program)
  5. render     video of every slide + contact sheets                          (program)
  6. review     final frames judged, fixes re-rendered                         (agent task -> program)
  7. join       output/<lesson>.mp4                                            (program)

Every step is resumable: running ./sr make again continues where it stopped.
"""
import argparse
import ast
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import prompts
from .agent import ask, get_backend
from .cli import (DEPTHS, INPUT, ROOT, VISUAL_MODES, cmd_audio, cmd_init, cmd_join, cmd_render, contact_sheet,
                  die, run_manim, slugify)
from .config import CONFIG, Lesson
from .pdf_extract import load_lines
from .script_io import default_settings, load_script, parse_slide_list
from .validate import validate

KINDS = ("title", "agenda", "divider", "content", "diagram", "interactive", "references", "other")
ATTEMPTS = 3


def rel(p):
    return str(Path(p).relative_to(ROOT))


def read_json(path):
    try:
        return json.loads(Path(path).read_text()), None
    except FileNotFoundError:
        return None, f"{rel(path)} was not written"
    except json.JSONDecodeError as e:
        return None, f"{rel(path)} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg})"


class Make:
    def __init__(self, a):
        self.a = a
        self.backend = get_backend()
        self.agent_cfg = CONFIG["agent"]

    # ------------------------------------------------------------ setup
    def setup(self):
        a = self.a
        pdf = a.pdf
        if not pdf:
            pdfs = sorted(INPUT.glob("*.pdf"))
            if not pdfs:
                die("put a PDF in input/ first (or pass its path: ./sr make file.pdf)")
            print("PDFs in input/:")
            for i, f in enumerate(pdfs, 1):
                print(f"  {i}. {f.name}")
            pdf = str(pdfs[int(ask("Which PDF", list(range(1, len(pdfs) + 1)), 1)) - 1])
        d = default_settings()
        pages = a.pages if a.pages is not None else ask("Pages to cover (e.g. 1-20, empty = all)", default="")
        visual = a.visual or ask("Visual mode: slides | mixed | animated", list(VISUAL_MODES), d["visual"])
        depth = int(a.depth or ask("Depth: 1 extensive, 2 faithful, 3 condensed, 4 short", [1, 2, 3, 4], d["depth"]))

        print("\n== 1. Reading the PDF")
        cmd_init(argparse.Namespace(pdf=pdf, id=a.id))
        self.lesson = lesson = Lesson(a.id or slugify(Path(pdf).stem))
        lesson.agent.mkdir(parents=True, exist_ok=True)
        lesson.animations_dir.mkdir(parents=True, exist_ok=True)
        current = json.loads(lesson.script.read_text())
        old = current.get("settings", {})
        changed_mode = any(old.get(k) not in (None, v) for k, v in
                           (("visual", visual), ("depth", depth), ("pages", pages or "")))
        self.fresh = bool(a.rewrite or changed_mode)
        if current.get("slides") and not self.fresh:
            answer = ask(f"{rel(lesson.script)} already exists. Keep it (k) or write a new one (n)", ["k", "n"], "k")
            self.fresh = answer == "n"
        if self.fresh:
            for f in list(lesson.agent.glob("*.json")) + (list(lesson.animations_dir.glob("group_*.py"))
                                                          if lesson.animations_dir.is_dir() else []):
                f.unlink()
            current = {"slides": []}
        self.settings = {**d, **old, "visual": visual, "depth": depth, "pages": pages or ""}
        self.scope = parse_slide_list(self.settings["pages"], range(1, load_lines(lesson)["pages"] + 1))
        self.write_script(current.get("slides", []))
        self.lines = load_lines(lesson)

    def write_script(self, slides):
        keep = {k: self.settings[k] for k in ("visual", "depth", "pages", "skip")}
        for k in ("voice", "temperature", "beat_gap"):
            if self.settings[k] != default_settings()[k]:
                keep[k] = self.settings[k]
        self.lesson.script.write_text(json.dumps({"settings": keep, "slides": slides}, ensure_ascii=False,
                                                 indent=2) + "\n")

    def fmt(self, **extra):
        s = self.settings
        return dict(id=self.lesson.id, language=s["language"], visual=s["visual"],
                    visual_rule=prompts.VISUAL_RULES[s["visual"]], depth=s["depth"],
                    depth_name=DEPTHS[s["depth"]], depth_rule=prompts.DEPTH_RULES[s["depth"]], **extra)

    def task(self, label, prompt, writable):
        print(f"    agent task: {label}", flush=True)
        return self.backend.run(prompt, [rel(w) for w in writable], self.lesson.agent / "log.jsonl")

    def fix_until_valid(self, label, target, check, writable, extra_note=""):
        """Run check(); send its problems back to the agent until there are none (or give up)."""
        for attempt in range(ATTEMPTS):
            problems = check()
            if not problems:
                return True
            if attempt == ATTEMPTS - 1:
                break
            print(f"    {len(problems)} problem(s) found - asking the agent to fix them")
            self.task(f"fix {label}", prompts.FIX.format(
                **self.fmt(), target=rel(target), extra=extra_note,
                problems="\n".join(f"- {p}" for p in problems[:40])), writable)
        print(f"    could not fix {label}:")
        for p in check()[:10]:
            print(f"      - {p}")
        return False

    # ------------------------------------------------------------ 2. plan
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

        print("\n== 2. Planning the lesson (agent)")
        if check():
            self.task("plan", prompts.PLAN.format(**self.fmt(), overview=rel(self.lesson.overview),
                                                  preview_dir=rel(self.lesson.preview),
                                                  pages=", ".join(map(str, self.scope)), output=rel(out)), [out])
        else:
            print("    reusing the existing plan")
        if not self.fix_until_valid("plan", out, check, [out]):
            die(f"the plan is not valid; edit {rel(out)} and run ./sr make again")
        plan = json.loads(out.read_text())
        print(f"\n    {plan.get('title', '')}\n    {plan['outline'][:300]}")
        for i in plan["slides"]:
            flag = "skip" if i["skip"] else i["kind"]
            print(f"    {i['slide']:3d}  {flag:11s} {i.get('summary', '')[:70]}")
        if (ask("Continue with this plan", ["y", "n"], "y") or "y") != "y":
            die(f"stopped. Edit {rel(out)} if you want, then run ./sr make again")
        self.plan_data = plan
        self.settings["skip"] = [i["slide"] for i in plan["slides"] if i["skip"]]

    # ------------------------------------------------------------ 3. write
    def groups(self):
        size = self.agent_cfg["group_size"]
        todo = [i for i in self.plan_data["slides"] if not i["skip"]]
        return [todo[k:k + size] for k in range(0, len(todo), size)]

    def group_paths(self, g):
        return (self.lesson.agent / f"group_{g:02d}.json", self.lesson.animations_dir / f"group_{g:02d}.py",
                f"g{g:02d}_")

    def group_slides(self, g):
        data, err = read_json(self.group_paths(g)[0])
        if err:
            return None
        return data.get("slides") if isinstance(data, dict) else data

    def merge(self):
        slides = []
        for g in range(1, len(self.all_groups) + 1):
            slides += self.group_slides(g) or []
        self.write_script(slides)
        return slides

    def slide_block(self, item):
        n = item["slide"]
        data = self.lines["slides"][str(n)]
        rows = [f"### Slide {n} ({item['kind']})",
                f"Plan: {item.get('summary', '')}  |  Visual idea: {item.get('visual_idea', 'none')}",
                f"Picture (open it): {rel(self.lesson.preview)}/slide_{n:02d}.jpg"]
        rows += [f"L{k}: {r['text']}" for k, r in enumerate(data["lines"], 1)] or ["(no text lines)"]
        w, h = self.lines["page_size"]
        rows += [f"image #{k}: {(b[2] - b[0]) * (b[3] - b[1]) / (w * h):.0%} of the slide"
                 for k, b in enumerate(data["images"], 1)]
        return "\n".join(rows)

    def write_group(self, g, items):
        out, anim_file, prefix = self.group_paths(g)
        numbers = [i["slide"] for i in items]
        writable = [out, anim_file]
        print(f"\n  group {g}/{len(self.all_groups)}: slides {numbers}")

        def check():
            data, err = read_json(out)
            if err:
                return [err]
            slides = data.get("slides") if isinstance(data, dict) else data
            if not isinstance(slides, list):
                return ['the file must be {"slides": [...]}']
            got = [s.get("slide") for s in slides if isinstance(s, dict)]
            problems = [] if got == numbers else [f"slides must be exactly {numbers} in this order (got {got})"]
            if anim_file.exists():
                try:
                    names = [n.name for n in ast.parse(anim_file.read_text()).body if isinstance(n, ast.FunctionDef)]
                    problems += [f"{rel(anim_file)}: function {n} must start with {prefix}" for n in names
                                 if not n.startswith(prefix) and not n.startswith("_")]
                except SyntaxError as e:
                    problems.append(f"{rel(anim_file)}: syntax error line {e.lineno}: {e.msg}")
            if problems:
                return problems
            errors, warnings = validate(self.lesson, self.settings, slides, coverage=False)
            return errors + [w for w in warnings if "digits" in w or "words" in w]

        if check():
            prev = self.merge()
            before = ("This group opens the video: begin with a short welcome and introduction."
                      if g == 1 or not prev else
                      f"Previous slide ({prev[-1]['slide']}) ended with: \""
                      + " ".join(b.get("say", "") for b in prev[-1]["beats"][-2:] if "say" in b)[-300:]
                      + "\" - continue naturally, do not welcome again.")
            nxt = self.all_groups[g] if g < len(self.all_groups) else None
            after = ("This group closes the video: end with a short closing (what was covered)."
                     if nxt is None else
                     "Next slides: " + "; ".join(f"{i['slide']}: {i.get('summary', '')}" for i in nxt))
            self.task(f"write slides {numbers}", prompts.WRITE.format(
                **self.fmt(), slide_list=numbers, group=g, groups=len(self.all_groups),
                outline=self.plan_data["outline"], slide_blocks="\n\n".join(self.slide_block(i) for i in items),
                before=before, after=after, output=rel(out), anim_file=rel(anim_file), prefix=prefix), writable)
        else:
            print("    reusing the existing script of this group")
        if not self.fix_until_valid(f"slides {numbers}", out, check, writable, f" (and {rel(anim_file)} if needed)"):
            die(f"group {g} still has problems; fix {rel(out)} and run ./sr make again")
        self.merge()
        self.judge_animations(g, numbers, check)

    def judge_animations(self, g, numbers, check):
        out, anim_file, _ = self.group_paths(g)
        judged = self.lesson.agent / f"group_{g:02d}_judge.json"
        if judged.exists():
            return
        for round_ in range(self.agent_cfg["animation_rounds"]):
            beats = [(s["slide"], k) for s in self.group_slides(g) for k, b in enumerate(s["beats"]) if "anim" in b]
            if not beats:
                return
            sheets = self.render_animations(beats)
            judged.unlink(missing_ok=True)
            self.task(f"judge animations of slides {numbers}", prompts.JUDGE_ANIMATIONS.format(
                **self.fmt(), slide_list=numbers, output=rel(judged), group_file=rel(out),
                anim_file_note=f" or {rel(anim_file)}" if anim_file.exists() else "",
                sheets="\n".join(sheets)), [judged, out, anim_file])
            verdict, err = read_json(judged)
            if err or not verdict.get("changed"):
                print(f"    animations: {'ok' if not err else err} - {(verdict or {}).get('notes', '')[:120]}")
                return
            print(f"    animations changed: {verdict.get('notes', '')[:120]}")
            self.fix_until_valid(f"slides {numbers}", out, check, [out, anim_file])
            self.merge()

    def render_animations(self, beats):
        def one(sb):
            n, k = sb
            name = f"anim_s{n:02d}_b{k:02d}"
            mp4 = run_manim(self.lesson, n, False, only_beat=k, fake=self.agent_cfg["placeholder_seconds"], name=name)
            return f"- slide {n} beat {k}: {rel(contact_sheet(mp4, self.lesson.qa / f'{name}.png', frames=12))}"

        out = []
        with ThreadPoolExecutor(CONFIG["video"]["parallel_jobs"]) as pool:
            for sb, fut in [(sb, pool.submit(one, sb)) for sb in beats]:
                try:
                    out.append(fut.result())
                except Exception as e:  # noqa: BLE001
                    out.append(f"- slide {sb[0]} beat {sb[1]}: RENDER FAILED: {str(e)[:300]}")
        return out

    def write_all(self):
        self.all_groups = self.groups()
        print(f"\n== 3. Writing the script (agent, {len(self.all_groups)} groups of slides)")
        for g, items in enumerate(self.all_groups, 1):
            self.write_group(g, items)
        slides = self.merge()
        errors, warnings = validate(self.lesson, self.settings, slides)
        if errors:
            self.fix_until_valid("the whole script", self.lesson.script,
                                 lambda: validate(self.lesson, *load_script(self.lesson.script))[0],
                                 [self.lesson.script, self.lesson.animations_dir / "**"])

    # ------------------------------------------------------------ 4-7
    def build(self, review=True):
        args = argparse.Namespace(lesson=self.lesson.id, slides="", preview=False, outdated=True, small=True)
        print("\n== 4. Narration audio")
        cmd_audio(args)
        print("\n== 5. Video")
        cmd_render(args)
        if review and self.agent_cfg["review"] and not self.a.no_review:
            print("\n== 6. Final review (agent)")
            self.review()
            # whatever the agent says, the program re-checks what changed and rebuilds only that
            cmd_audio(args)
            cmd_render(args)
        print("\n== 7. Final video")
        cmd_join(args)

    def review(self):
        _, slides = load_script(self.lesson.script)
        numbers = [s["slide"] for s in slides]
        size, changed = self.agent_cfg["review_group_size"], False
        writable = [self.lesson.script, self.lesson.animations_dir / "**"]
        for k in range(0, len(numbers), size):
            batch = numbers[k:k + size]
            out = self.lesson.agent / f"review_{batch[0]:02d}.json"
            if out.exists():
                continue
            sheets = "\n".join(f"- slide {n}: {rel(self.lesson.qa / f'final_slide_{n:02d}.png')}" for n in batch)
            self.task(f"review slides {batch}", prompts.REVIEW.format(
                **self.fmt(), slide_list=batch, sheets=sheets, script=rel(self.lesson.script), output=rel(out),
                anim_note=f" or animations/{self.lesson.id}/*.py"), writable + [out])
            verdict, err = read_json(out)
            if verdict and verdict.get("changed"):
                changed = True
                print(f"    changed: {verdict.get('notes', '')[:150]}")
                self.fix_until_valid("the whole script", self.lesson.script,
                                     lambda: validate(self.lesson, *load_script(self.lesson.script))[0], writable)
        return changed


def make(a):
    m = Make(a)
    m.setup()
    if m.fresh or not json.loads(m.lesson.script.read_text()).get("slides"):
        m.plan()
        m.write_all()
    else:
        print("\n== 2-3. Keeping the existing script")
        errors = validate(m.lesson, *load_script(m.lesson.script))[0]
        if errors:
            die("the script has errors: run ./sr check " + m.lesson.id)
    m.build()
    print(f"\nDone: {rel(m.lesson.output)}")


if __name__ == "__main__":
    sys.exit(make(argparse.Namespace()))
