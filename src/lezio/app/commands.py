"""The commands other than make and redo (run.py): your lessons (list, status, rename, copy, delete),
build, config, voices, themes, templates, tools.
All output goes through ui.py, so every command looks the same."""
import json
import subprocess
import time
from argparse import Namespace

from .. import material as mat
from ..config import CONFIG, ROOT
from ..lesson import Lesson, all_lessons, slugify
from ..script import is_written, load_script, narration, pieces
from ..settings import DEPTHS, house_theme, lesson_theme, tts_label, tts_options
from ..validate import check_script
from ..video import render
from ..voice import client as voice
from ..voice import engines
from . import ui
from .run import Run, build_join, build_video, build_voice, rel


# ------------------------------------------------------------------ status
def status(a):
    if not a.lesson:
        return lessons_list()
    lesson = Lesson(a.lesson)
    script = load_script(lesson.script)
    s = script["settings"]
    meta = lesson.durations_meta()
    opts = tts_options()
    focus = s.get("focus") or {}
    ui.key_values([
        ("lesson", f"[bold]{lesson.id}[/]  {ui.escape(script['title'])}"),
        ("material", "\n".join(ui.escape(p) + (f"  [muted](pages {focus[p]})[/]" if p in focus else "")
                               for p in lesson.source_names)),
        ("depth", f"{s['depth']} ({DEPTHS[s['depth']]})"),
        ("theme", lesson_theme(script) + ("  [muted](chosen for this lesson)[/]" if script.get("theme") else "")),
        ("voice", ui.escape(tts_label())),
        ("instructions", ui.escape(s["instructions"]) or "[muted]none[/]"),
        ("video", rel(lesson.output) if lesson.output.exists() else "[muted]not assembled yet[/]"),
    ], title="status")
    rows = []
    for seg in script["segments"]:
        keys = pieces(seg)
        ok = sum(1 for k, t, _ in keys if meta.get(k, {}).get("text") == t and meta[k].get("tts") == opts
                 and (lesson.audio / f"{k}.wav").exists())
        if not is_written(lesson, seg):
            voice_state, state = "[muted]—[/]", "[warn]not written[/]"
        else:
            voice_state = f"{ok}/{len(keys)}" if ok == len(keys) else f"[warn]{ok}/{len(keys)}[/]"
            if not lesson.segment_video(seg["id"]).exists():
                state = "[muted]—[/]"
            elif render.is_outdated(lesson, script, seg):
                state = "[warn]outdated[/]"
            else:
                state = "[ok]up to date[/]"
        title = seg["title"] if len(seg["title"]) <= 44 else seg["title"][:43] + "…"
        rows.append([f"[muted]{seg['id']}[/]", ui.escape(title), str(len(keys) or ""), voice_state, state])
    ui.table(["segment", "title", ">pieces", ">voice", "video"], rows)
    if any(not is_written(lesson, x) for x in script["segments"]) or not lesson.output.exists():
        ui.hint(f"continue: ./lezio make {lesson.id}")


def lessons_list():
    ids = all_lessons()
    if not ids:
        ui.info("No lessons yet.")
        ui.hint("start one: ./lezio make   (or ./lezio make input/<files>)")
        return
    rows = []
    for lid in ids:
        lesson = Lesson(lid)
        script = load_script(lesson.script)
        segs = script["segments"]
        written = sum(1 for x in segs if is_written(lesson, x))
        video = "[ok]✓[/]" if lesson.output.exists() else "[muted]—[/]"
        title = script["title"] if len(script["title"]) <= 34 else script["title"][:33] + "…"
        rows.append([f"[accent]{lid}[/]", ui.escape(title) or "[muted]not planned[/]",
                     f"{written}/{len(segs)}" if segs else "[muted]—[/]", str(script["settings"]["depth"]), video])
    ui.table(["lesson", "title", ">written", ">depth", "video"], rows)
    ui.info("videos in output/<lesson>.mp4")
    ui.hint("details: ./lezio status <lesson>     continue: ./lezio make <lesson>")


def build(a):
    lesson = Lesson(a.lesson)
    script = load_script(lesson.script)
    errors = check_script(lesson, script)[0]
    if errors:
        ui.fail("the lesson has errors: " + ui.escape("; ".join(errors[:3])), f"./lezio tools check {lesson.id}")
    build_voice(lesson)
    build_video(lesson)
    Run(Namespace(yes=True, note="")).final_panel(build_join(lesson))


# ------------------------------------------------------------------ configuration
def config(a):
    if getattr(a, "show", None) == "show":
        return config_show()
    from .configure import configure
    configure()


def config_show():
    from ..agent.backends import task_options
    v, n, ag = CONFIG["video"], CONFIG["narration"], CONFIG["agent"]
    overrides = ", ".join(f"{t} {o['model']}/{o['effort']}" for t in ("plan", "write", "review")
                          for o in [task_options(t)] if t in ag)
    ui.key_values([
        ("voice", ui.escape(tts_label())),
        ("narration", f"{n['language']} · {n['piece_gap']} s between pieces"),
        ("agent", f"{ag['backend']} · {ag['model']} · effort {ag['effort']}"
                  + (f"  [muted]({ui.escape(overrides)})[/]" if overrides else "")),
        ("video", f"theme {house_theme()} · subtitles {v.get('subtitles', 'track')} · {v['width']}x{v['height']} · "
                  f"{v['fps']} fps"),
        ("tuning", " · ".join(f"{k} {val}" for k, val in CONFIG["tuning"].items())),
    ], title="config.toml")
    ui.hint("change it: ./lezio config   (or edit config.toml)")


def voices(a):
    current = tts_options()
    name = a.engine or current["engine"]
    engine = engines.get_engine(name)
    overrides = {"engine": name, **_kv(a.set), **({"voice": a.voice} if a.voice else {})}
    if a.try_text is None:
        ui.table(["", "engine", "runs", ""], [["[ok]●[/]" if e.name == current["engine"] else "", f"[accent]{e.name}[/]",
                                              e.runs, ui.escape(e.description)] for e in engines.ENGINES.values()])
        opts = tts_options({"engine": name})
        rows = []
        for key, o in engine.options.items():
            allowed = (", ".join(map(str, o.choices)) if o.choices else
                       f"{o.minimum} … {o.maximum}" if o.minimum is not None else "free")
            rows.append([f"[accent]{key}[/]", f"[bold]{ui.escape(str(opts[key]))}[/]",
                         f"[muted]{ui.escape(o.help)} · allowed: {ui.escape(allowed)}[/]"])
        ui.table(["", "value", ""], rows, title=f"{name}: options in config.toml")
        if getattr(engine, "suggested_voices", None):
            ui.info("voices: " + ", ".join(engine.suggested_voices))
        ui.hint(f'listen:  ./lezio voices --try "Ciao a tutti, iniziamo." --engine {name} --voice NAME --play')
        ui.hint("change:  ./lezio config")
        return
    problems = engine.validate({k: v for k, v in tts_options(overrides).items() if k != "engine"})
    if problems:
        ui.fail("; ".join(problems), "./lezio voices")
    label = "_".join(str(v) for k, v in overrides.items() if k in ("engine", "voice"))
    out = ROOT / "voice-samples" / f"try_{slugify(label)}_{time.strftime('%H%M%S')}.wav"
    with ui.step("Generating a sample") as st:
        result = {}

        def on_event(e):
            if e["event"] == "loading":
                st.status("loading the speech model")
            elif e["event"] == "sample":
                result.update(e)
        try:
            voice.sample(a.try_text, overrides, out, on_event)
        except voice.VoiceError as e:
            ui.fail(ui.escape(str(e)))
        st.done(f"{rel(out)}  [muted]{result.get('duration')}s of audio[/]")
    if a.play:
        subprocess.run(["afplay", str(out)])


def themes(a):
    from ..config import THEMES
    if a.preview:
        preview_theme(a.preview)                      # prints where the picture is; nothing is opened
        return
    import tomllib
    rows = []
    for path in sorted(THEMES.glob("*.toml")):
        data = tomllib.loads(path.read_text())
        rows.append(["[ok]●[/]" if path.stem == house_theme() else "", f"[accent]{path.stem}[/]",
                     ui.escape(data.get("description", ""))])
    ui.table(["", "theme", ""], rows)
    ui.info(ui.escape(f"● the house theme (config.toml [video] theme); a lesson can ask for another in its "
                      "instructions"))
    ui.hint("preview:  ./lezio themes --preview NAME")
    ui.hint("change:   ./lezio config      your own: copy themes/light.toml to themes/NAME.toml")


def preview_theme(name):
    """Render a still image showing a theme: title, text, colors, boxes, a highlight, handwriting."""
    from ..config import MANIM, PACKAGE, SUBPROCESS_ENV, THEMES
    if not (THEMES / f"{name}.toml").exists():
        ui.fail(f"unknown theme '{name}'", "./lezio themes")
    media = ROOT / "voice-samples" / ".theme-preview"
    with ui.step(f"Rendering a preview of {name}") as st:
        env = {**SUBPROCESS_ENV, "LEZIO_THEME": name}
        r = subprocess.run([str(MANIM), "render", "-qm", "-s", "--disable_caching", "--media_dir", str(media), "-o",
                            f"theme_{name}", str(PACKAGE / "video" / "theme_preview.py"), "ThemePreview"],
                           env=env, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            ui.fail("preview failed", ui.escape((r.stdout + r.stderr)[-400:]))
        png = next(media.glob(f"images/**/theme_{name}*.png"))
        out = ROOT / "output" / f"theme_{name}.png"
        out.parent.mkdir(exist_ok=True)
        png.replace(out)
        st.done(rel(out))
    return out


def _kv(items):
    out = {}
    for item in items or []:
        if "=" not in item:
            ui.fail(f"expected KEY=VALUE, got '{item}'")
        k, v = item.split("=", 1)
        try:
            out[k.strip()] = json.loads(v)
        except json.JSONDecodeError:
            out[k.strip()] = v
    return out


# ------------------------------------------------------------------ low-level tools
def tools(a):
    {"check": tool_check, "ingest": tool_ingest, "audio": tool_audio, "render": tool_render, "join": tool_join,
     "scene-api": tool_scene_api}[a.tool](a)


def tool_check(a):
    lesson = Lesson(a.lesson)
    script = load_script(lesson.script)
    errors, warnings = check_script(lesson, script)
    all_pieces = [p for seg in script["segments"] for p in pieces(seg)]
    words = sum(len(t.split()) for _, t, _ in all_pieces)
    ui.info(f"{len(script['segments'])} segments · {len(all_pieces)} spoken pieces · {words} words "
            f"(about {words / 150:.0f} min)")
    for w in warnings:
        ui.warn(ui.escape(w))
    for e in errors:
        ui.console.print(f"[err]✗[/] {ui.escape(e)}")
    if errors:
        raise SystemExit(1)
    ui.done("lesson OK" + (" [muted](with warnings)[/]" if warnings else ""))


def tool_ingest(a):
    lesson = Lesson(a.lesson)
    with ui.step("Reading the material") as st:
        changed = mat.ingest(lesson, on_progress=lambda name: st.status(name))
        st.done(f"{len(changed)} sources read → {rel(lesson.index)}")
    script = load_script(lesson.script)
    ui.console.print(ui.escape(mat.Material(lesson).overview(script["settings"].get("focus"))))


def tool_audio(a):
    build_voice(Lesson(a.lesson))


def tool_render(a):
    lesson = Lesson(a.lesson)
    script = load_script(lesson.script)
    ids = [x.strip() for x in a.segments.split(",") if x.strip()] or [s["id"] for s in script["segments"]]
    if a.preview:
        with ui.step("Preview render", total=len(ids)) as st:
            for sid in ids:
                seg = next(s for s in script["segments"] if s["id"] == sid)
                code = None if seg.get("blocks") else lesson.scene_file(sid).read_text()
                try:
                    sheet, report = render.preview(lesson, seg, code)
                except render.RenderError as e:
                    ui.fail(f"{sid}: {ui.escape(str(e))}")
                for w in report.get("warnings", []):
                    st.note(f"{sid}: {ui.escape(w)}")
                st.advance()
            st.done(f"step sheets in {rel(lesson.qa)}")
    else:
        for sid in ids:
            (lesson.video / f"{sid}.json").unlink(missing_ok=True)
        build_video(lesson, only=set(ids))


def tool_join(a):
    path, seconds, size = build_join(Lesson(a.lesson))
    ui.info(f"{rel(path)} · {ui.fmt_seconds(seconds)} · {size / 1e6:.0f} MB")


def tool_scene_api(a):
    from ..agent.tasks import scene_api
    ui.console.print(ui.escape(scene_api()))


# ------------------------------------------------------------------ templates
DEMO_LESSON = "_templates"


def demo_lesson():
    """The internal lesson used to render template examples (a generated PDF page and picture as material)."""
    from ..config import LESSONS
    from ..lesson import lesson_exists
    from ..script import empty_script, save_script
    if not lesson_exists(DEMO_LESSON):
        import pymupdf
        from PIL import Image, ImageDraw, ImageFont
        src = LESSONS / DEMO_LESSON / "sources"
        src.mkdir(parents=True, exist_ok=True)
        doc = pymupdf.open()
        pg = doc.new_page(width=640, height=360)
        pg.insert_text((40, 60), "Il sistema binario", fontsize=26, color=(0.08, 0.27, 0.63))
        for k, line in enumerate(["Usiamo due simboli: 0 e 1", "Ogni cifra binaria si chiama bit",
                                  "Con k bit si scrivono 2^k stringhe", "Il rumore non confonde i due livelli"]):
            pg.insert_text((50, 110 + k * 32), "- " + line, fontsize=16)
        for k, label in enumerate(["CPU", "Memoria", "I/O"]):
            r = pymupdf.Rect(400 + (k % 2) * 110, 120 + (k // 2) * 90, 490 + (k % 2) * 110, 170 + (k // 2) * 90)
            pg.draw_rect(r, color=(0.08, 0.27, 0.63), fill=(0.89, 0.93, 0.98), width=1.5)
            pg.insert_text((r.x0 + 12, r.y0 + 30), label, fontsize=14)
        pg.draw_line((490, 145), (510, 145), color=(0.3, 0.3, 0.3), width=1.5)
        pg.draw_line((445, 170), (445, 210), color=(0.3, 0.3, 0.3), width=1.5)
        doc.save(src / "demo.pdf")
        im = Image.new("RGB", (1200, 700), "white")
        d = ImageDraw.Draw(im)
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 44)
        d.ellipse([150, 150, 550, 550], outline=(20, 70, 160), width=8)
        d.ellipse([650, 150, 1050, 550], outline=(232, 89, 12), width=8)
        d.text((290, 320), "A", fill=(20, 70, 160), font=font)
        d.text((830, 320), "B", fill=(232, 89, 12), font=font)
        im.save(src / "figure.png")
        lesson = Lesson.create(DEMO_LESSON, [src / "demo.pdf", src / "figure.png"])
        mat.ingest(lesson)
        save_script(lesson.script, empty_script())
    return Lesson(DEMO_LESSON)


def demo_template(lesson, name):
    """Render the example of a template. Returns (sheet, report, problems)."""
    from ..scene import templates as tpls
    from ..validate import check_blocks
    tpl = tpls.find(name, lesson)
    ex = tpl.example or {}
    block = {"template": name, "args": ex.get("args", {}), "say": ex.get("say") or ["Esempio."]}
    if ex.get("title"):
        block["title"] = ex["title"]
    errors, _ = check_blocks([block], lesson)
    if errors:
        return None, {}, errors
    try:
        sheet, report = render.preview(lesson, {"id": name, "blocks": [block]})
    except render.RenderError as e:
        return None, e.report, [str(e)]
    return sheet, report, []


def templates(a):
    from concurrent.futures import ThreadPoolExecutor
    from ..scene import templates as tpls
    tpls.load_library()
    for f, err in tpls.LOAD_ERRORS:
        ui.console.print(f"[err]✗[/] cannot load {ui.escape(f)}: {ui.escape(err)}")
    if not a.demo:
        for cat, label in tpls.CATEGORIES.items():
            group = [t for t in tpls.REGISTRY.values() if t.category == cat]
            if group:
                ui.section(label)
                ui.table(["", ""], [[f"[accent]{t.name}[/]" + ("" if t.source == "built-in" else f" [muted]({t.source})[/]"),
                                     ui.escape(t.use_for)] for t in group])
        ui.console.print()
        ui.info(f"{len(tpls.REGISTRY)} templates. The agent can also write its own for a lesson.")
        ui.hint("see one:   ./lezio templates --demo NAME      test all: ./lezio templates --demo all")
        ui.hint("your own:  a file in templates/ (see AGENTS.md, \"Template\")")
        return
    lesson = demo_lesson()
    names = list(tpls.REGISTRY) if a.demo == "all" else [n.strip() for n in a.demo.split(",")]
    unknown = [n for n in names if n not in tpls.REGISTRY]
    if unknown:
        ui.fail(f"unknown templates: {', '.join(unknown)}", "./lezio templates")
    results = {}
    with ui.step("Rendering template examples", total=len(names)) as st:
        with ThreadPoolExecutor(CONFIG["tuning"]["parallel_jobs"]) as pool:
            for name, res in zip(names, pool.map(lambda n: demo_template(lesson, n), names)):
                results[name] = res
                st.advance()
        bad = [n for n, (_, _, p) in results.items() if p]
        st.done(f"{len(names) - len(bad)} ok" + (f" · [err]{len(bad)} failed[/]" if bad else ""))
    rows = []
    for name, (sheet, report, problems) in results.items():
        mark = "[err]✗[/]" if problems else ("[warn]![/]" if report.get("warnings") else "[ok]✓[/]")
        notes = "; ".join(ui.escape(str(p)) for p in problems + report.get("warnings", [])[:2])
        rows.append([mark, f"[accent]{name}[/]", f"[muted]{rel(sheet)}[/]" if sheet else "", notes])
    ui.table(["", "template", "step sheet", ""], rows)
    if any(p for _, _, p in results.values()):
        raise SystemExit(1)


# ------------------------------------------------------------------ your lessons
def lessons(a):
    lessons_list()


def _size(path):
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _new_id(name):
    from ..lesson import lesson_exists
    new = slugify(name)
    if lesson_exists(new):
        ui.fail(f"a lesson called '{new}' already exists", "./lezio list")
    return new


def rename(a):
    """Renames the lesson only: the videos already in output/ are not touched."""
    import shutil
    lesson = Lesson(a.lesson)
    new = _new_id(a.name)
    shutil.move(str(lesson.dir), str(lesson.dir.parent / new))
    ui.done(f"{lesson.id} → [accent]{new}[/]")
    if lesson.output.exists():
        ui.info(f"{rel(lesson.output)} keeps its name; the next video of the lesson goes to output/{new}.mp4")


def copy(a):
    import shutil
    lesson = Lesson(a.lesson)
    new = _new_id(a.name)
    dst = lesson.dir.parent / new
    with ui.step(f"Copying {lesson.id}") as st:
        shutil.copytree(lesson.dir, dst, ignore=shutil.ignore_patterns("media", "drafts", "log.jsonl", "backup_*"))
        st.done(f"→ [accent]{new}[/]  [muted]material, voice and renders are reused[/]")
    ui.hint(f"change it, e.g.: ./lezio make {new} --instructions \"...\"   (the video goes to output/{new}.mp4)")


def delete(a):
    """Moves the lesson folder to the Trash; the videos in output/ and the material in input/ stay."""
    import shutil
    from . import wizard
    lesson = Lesson(a.lesson)
    ui.key_values([("lesson", f"[bold]{lesson.id}[/]  {rel(lesson.dir)}"),
                   ("size", f"{_size(lesson.dir) / 1e6:.0f} MB"),
                   ("kept", "its videos in output/ and the study material in input/")], title="delete")
    if not a.yes:
        if not wizard.interactive():
            ui.fail("deleting a lesson needs a confirmation", f"./lezio delete {lesson.id} --yes")
        if not wizard.confirm(f"Move {lesson.id} to the Trash?", default=False):
            ui.info("Nothing deleted.")
            return
    trash = __import__("pathlib").Path.home() / ".Trash"
    target = trash / f"lezio-{lesson.id}-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.move(str(lesson.dir), str(target))
    ui.done(f"{lesson.id} moved to the Trash  [muted]({target.name})[/]")
