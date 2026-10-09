"""Commands other than the main one: status, check, build, tts, config, and the low-level tools."""
import json
import subprocess
import time
from argparse import Namespace

from rich.table import Table

from .. import material as mat
from ..config import CONFIG, ROOT
from ..lesson import Lesson, slugify
from ..script import is_written, load_script, pieces
from ..settings import DEPTHS, house_theme, lesson_theme, tts_label, tts_options
from ..validate import check_script
from ..video import render
from ..voice import client as voice
from ..voice import engines
from . import ui
from .run import Run, build_join, build_video, build_voice, rel


def status(a):
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
    table = Table(box=None, padding=(0, 1))
    for col, width in (("segment", 7), ("title", None), ("pieces", 6), ("voice", 6), ("video", 11)):
        table.add_column(col, style="muted" if col in ("segment", "pieces") else None, no_wrap=True,
                         overflow="ellipsis", min_width=width, max_width=30 if width is None else None,
                         justify="right" if col in ("pieces", "voice") else "left")
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
        table.add_row(seg["id"], ui.escape(seg["title"][:60]), str(len(keys) or ""),
                      voice_state, state)
    ui.console.print(table)


def check(a):
    lesson = Lesson(a.lesson)
    script = load_script(lesson.script)
    errors, warnings = check_script(lesson, script)
    all_pieces = [p for seg in script["segments"] for p in pieces(seg)]
    words = sum(len(t.split()) for _, t, _ in all_pieces)
    ui.console.print(f"{len(script['segments'])} segments · {len(all_pieces)} spoken pieces · {words} words "
                     f"[muted](about {words / 150:.0f} min)[/]")
    for w in warnings:
        ui.console.print(f"  [warn]warning[/] {ui.escape(w)}")
    for e in errors:
        ui.console.print(f"  [err]error[/]   {ui.escape(e)}")
    if errors:
        raise SystemExit(1)
    ui.console.print("[ok]✓ lesson OK[/]" + (" [muted](with warnings)[/]" if warnings else ""))


def build(a):
    lesson = Lesson(a.lesson)
    script = load_script(lesson.script)
    errors = check_script(lesson, script)[0]
    if errors:
        ui.fail("the lesson has errors: " + ui.escape("; ".join(errors[:3])), f"./lezio check {lesson.id}")
    build_voice(lesson)
    build_video(lesson)
    Run(Namespace(yes=True, note="")).final_panel(build_join(lesson))


def tts(a):
    current = tts_options()
    name = a.engine or current["engine"]
    engine = engines.get_engine(name)
    overrides = {"engine": name, **_kv(a.set), **({"voice": a.voice} if a.voice else {})}
    if a.try_text is None:
        table = Table(box=None, padding=(0, 2), show_header=False)
        for e in engines.ENGINES.values():
            mark = "[ok]●[/]" if e.name == current["engine"] else " "
            table.add_row(mark, f"[bold]{e.name}[/]", f"[muted]{e.runs}[/]", e.description)
        ui.console.print(table)
        opts = tts_options({"engine": name})
        rows = []
        for key, o in engine.options.items():
            allowed = (", ".join(map(str, o.choices)) if o.choices else
                       f"{o.minimum} … {o.maximum}" if o.minimum is not None else "free")
            rows.append((key, f"[bold]{ui.escape(str(opts[key]))}[/]\n[muted]{ui.escape(o.help)}\n"
                              f"allowed: {ui.escape(allowed)}[/]"))
        if getattr(engine, "suggested_voices", None):
            rows.append(("voices", ", ".join(engine.suggested_voices)))
        ui.console.print()
        ui.key_values(rows, title=ui.escape(f"{name} · values from config.toml [tts.{name}]"))
        ui.info(f'try:     ./lezio tts --try "Ciao a tutti, iniziamo." --engine {name} --voice X --set key=value --play')
        ui.info("change:  ./lezio config   (or edit config.toml)")
        return
    problems = engine.validate({k: v for k, v in tts_options(overrides).items() if k != "engine"})
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
            ui.fail(ui.escape(str(e)))
        st.done(f"{rel(out)}  [muted]{result.get('duration')}s of audio[/]")
    if a.play:
        subprocess.run(["afplay", str(out)])


def themes(a):
    from ..config import THEMES
    if a.preview:
        subprocess.run(["open", str(preview_theme(a.preview))])
        return
    import tomllib
    table = Table(box=None, padding=(0, 2), show_header=False)
    for path in sorted(THEMES.glob("*.toml")):
        data = tomllib.loads(path.read_text())
        mark = "[ok]●[/]" if path.stem == house_theme() else " "
        table.add_row(mark, f"[bold]{path.stem}[/]", ui.escape(data.get("description", "")))
    ui.console.print(table)
    ui.info(ui.escape(f"house theme: {house_theme()} (config.toml [video] theme, or ./lezio config)"))
    ui.info("preview: ./lezio themes --preview NAME     your own: copy themes/light.toml to themes/NAME.toml")


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


def config(a):
    from .configure import configure
    configure()


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
                try:
                    sheet, report = render.preview(lesson, seg, lesson.scene_file(sid).read_text())
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
