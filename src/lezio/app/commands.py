"""Commands other than the main one: status, check, tts, build, and the low-level tools."""
import inspect
import json
import subprocess
import time
from argparse import Namespace

from rich.markup import escape
from rich.table import Table

from ..config import CONFIG, ROOT
from ..lesson import Lesson, slugify
from ..pdf import extract
from ..script import audio_pieces, load_script, parse_pages
from ..settings import DEPTHS, tts_label
from ..validate import validate
from ..video import render
from ..voice import client as voice
from ..voice import engines
from . import ui
from .run import Run, build_join, build_video, build_voice


def status(a):
    lesson = Lesson(a.lesson)
    settings, slides = load_script(lesson.script)
    meta = lesson.durations_meta()
    pieces = audio_pieces(slides)
    ui.key_values([
        ("lesson", f"[bold]{lesson.id}[/]  [muted]{lesson.pdf.name}[/]"),
        ("pages", f"{settings['pages'] or 'all'}" + (f"  [muted](skipped {ui.fmt_pages(settings['skip'])})[/]"
                                                      if settings["skip"] else "")),
        ("mode", f"{settings['visual']} · depth {settings['depth']} ({DEPTHS[settings['depth']]})"),
        ("voice", tts_label()),
        ("instructions", settings["instructions"] or "[muted]none[/]"),
        ("video", str(lesson.output.relative_to(ROOT)) if lesson.output.exists() else "[muted]not assembled yet[/]"),
    ], title="status")
    table = Table(box=None, padding=(0, 2))
    for col in ("slide", "beats", "voice", "video"):
        table.add_column(col, style="muted" if col == "beats" else None, justify="right" if col != "video" else "left")
    for s in slides:
        n = s["slide"]
        keys = [(k, t) for k, t, _ in pieces if int(k[1:3]) == n]
        ok = sum(1 for k, t in keys if meta.get(k, {}).get("text") == t)
        if not lesson.slide_video(n).exists():
            state = "[muted]—[/]"
        elif render.is_outdated(lesson, settings, s):
            state = "[warn]outdated[/]"
        else:
            state = "[ok]up to date[/]"
        table.add_row(str(n), str(len(s["beats"])), f"{ok}/{len(keys)}" if ok == len(keys) else f"[warn]{ok}/{len(keys)}[/]", state)
    ui.console.print(table)


def check(a):
    lesson = Lesson(a.lesson)
    settings, slides = load_script(lesson.script)
    errors, warnings = validate(lesson, settings, slides)
    words = sum(len(t.split()) for _, t, _ in audio_pieces(slides))
    ui.console.print(f"{len(slides)} slides · {len(audio_pieces(slides))} spoken pieces · {words} words "
                     f"[muted](about {words / 150:.0f} min)[/]")
    for w in warnings:
        ui.console.print(f"  [warn]warning[/] {w}")
    for e in errors:
        ui.console.print(f"  [err]error[/]   {e}")
    if errors:
        raise SystemExit(1)
    ui.console.print("[ok]✓ script OK[/]" + (" [muted](with warnings)[/]" if warnings else ""))


def build(a):
    lesson = Lesson(a.lesson)
    settings, slides = load_script(lesson.script)
    errors = validate(lesson, settings, slides)[0]
    if errors:
        ui.fail("the script has errors: " + "; ".join(errors[:3]), f"./lezio check {lesson.id}")
    build_voice(lesson)
    build_video(lesson)
    run = Run(Namespace(yes=True, note=""))
    run.final_panel(build_join(lesson))


def tts(a):
    current = engines.resolve(CONFIG["tts"])
    name = a.engine or current["engine"]
    engine = engines.get_engine(name)
    overrides = {"engine": name, **_kv(a.set), **({"voice": a.voice} if a.voice else {})}
    if a.try_text is None:
        table = Table(box=None, padding=(0, 2), show_header=False)
        for e in engines.ENGINES.values():
            mark = "[ok]●[/]" if e.name == current["engine"] else " "
            table.add_row(mark, f"[bold]{e.name}[/]", f"[muted]{e.runs}[/]", e.description)
        ui.console.print(table)
        opts = engines.resolve(CONFIG["tts"], None, {"engine": name})
        rows = []
        for key, o in engine.options.items():
            allowed = (", ".join(map(str, o.choices)) if o.choices else
                       f"{o.minimum} … {o.maximum}" if o.minimum is not None else "free")
            rows.append((key, f"[bold]{opts[key]}[/]\n[muted]{o.help}\nallowed: {allowed}[/]"))
        if getattr(engine, "suggested_voices", None):
            rows.append(("voices", ", ".join(engine.suggested_voices)))
        ui.console.print()
        ui.key_values(rows, title=escape(f"{name} · values from config.toml [tts.{name}]"))
        ui.info(f'try:    ./lezio tts --try "Ciao a tutti, iniziamo." --engine {name} --voice X --set key=value --play')
        ui.info(escape(f"use it: set [tts] engine and [tts.{name}] in config.toml"))
        return
    problems = engine.validate({k: v for k, v in overrides.items() if k != "engine"})
    if problems:
        ui.fail("; ".join(problems))
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
            ui.fail(str(e))
        st.done(f"{out.relative_to(ROOT)}  [muted]{result.get('duration')}s of audio[/]")
    if a.play:
        subprocess.run(["afplay", str(out)])


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
def tool_init(a):
    from pathlib import Path
    pdf = Path(a.pdf).expanduser().resolve()
    lesson = Lesson.create(a.id or slugify(pdf.stem), pdf)
    with ui.step("Reading the PDF") as st:
        st.done(f"{extract(lesson)} pages → {lesson.overview.relative_to(ROOT)}")


def tool_audio(a):
    build_voice(Lesson(a.lesson))


def tool_render(a):
    lesson = Lesson(a.lesson)
    _, slides = load_script(lesson.script)
    numbers = parse_pages(a.slides, [s["slide"] for s in slides])
    if a.preview:
        with ui.step("Preview render", total=len(numbers)) as st:
            render.render_slides(lesson, numbers, final=False, on_done=lambda n, s: st.advance())
            st.done(f"contact sheets in {lesson.qa.relative_to(ROOT)}")
    else:
        for n in numbers:
            (lesson.video / f"slide_{n:02d}.json").unlink(missing_ok=True)
        build_video(lesson, pages=set(numbers))


def tool_anim(a):
    lesson = Lesson(a.lesson)
    _, slides = load_script(lesson.script)
    beats = [(s["slide"], k) for s in slides for k, b in enumerate(s["beats"])
             if "anim" in b and (a.all or (s["slide"] == a.slide and (a.beat is None or a.beat == k)))]
    if not beats:
        ui.fail("no animation matches", "use --slide N [--beat K] or --all")
    with ui.step("Rendering animations", total=len(beats)) as st:
        results = render.render_animation_previews(lesson, beats)
        st.done(f"{len(beats)} animations")
    for n, k, sheet, err in results:
        ui.console.print(f"  slide {n} beat {k}: " + (f"[err]{err}[/]" if err else str(sheet.relative_to(ROOT))))


def tool_join(a):
    lesson = Lesson(a.lesson)
    path, seconds, size = build_join(lesson)
    ui.info(f"{path.relative_to(ROOT)} · {ui.fmt_seconds(seconds)} · {size / 1e6:.0f} MB")


def tool_templates(a):
    from ..video import templates
    for name, fn in templates.TEMPLATES.items():
        sig = str(inspect.signature(fn)).replace("(scene, steps, ", "(")
        ui.console.print(f"\n[bold accent]{name}[/]{sig}\n[muted]{inspect.getdoc(fn)}[/]")
