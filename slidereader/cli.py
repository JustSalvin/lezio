"""slide-reader command line, used through the ./sr wrapper.

    ./sr                          wizard
    ./sr <pdf | lesson> [options] make or update a video (asks only what is missing)
    ./sr status | redo | build | tts ...
    ./sr help tools               low-level commands
"""
import argparse
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .config import CONFIG, FFMPEG, INPUT, MANIM, OUTPUT, ROOT, TTS_PY, Lesson
from .script_io import (DEPTHS, VISUAL_MODES, agent_instructions, audio_pieces, load_script, parse_slide_list,
                        piece_key, tts_options)

ENV = {**os.environ, "PATH": f"{ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}", "PYTHONPATH": str(ROOT),
       "PYTHONUNBUFFERED": "1"}
STUB = {"settings": {}, "slides": []}

HELP = """slide-reader - PDF slides -> narrated, animated video lecture

  ./sr                            wizard: choose a PDF (or a lesson) and the options
  ./sr <file.pdf | lesson> [...]  make or update a video; asks only what is missing

Options
  --pages 1-20          pages to cover (default: all)
  --visual MODE         slides | mixed | animated
  --depth N             1 extensive | 2 faithful | 3 condensed | 4 short
  --instructions "..."  instructions for the agent, saved in the lesson
                        (e.g. "Skip Mentimeter slides. Never read e-mail addresses.")
  --voice NAME          voice of the TTS engine (see ./sr tts)
  --engine NAME         TTS engine: voxtral | edge
  --tts KEY=VALUE       any option of the TTS engine (repeatable), e.g. --tts temperature=0.6
  --id NAME             lesson name (default: from the PDF file name)
  --rewrite             write the script again from scratch (the old one is backed up)
  --no-review           skip the final review of the frames
  -y, --yes             no questions and no confirmation

More
  ./sr status <lesson>                          what is done, missing or outdated
  ./sr redo <lesson> --slides 7 [--part script|voice|video] [--note "more examples"]
  ./sr build <lesson>                           rebuild after editing scripts/<lesson>.json by hand
  ./sr tts [--engine NAME]                      TTS engines, their options and voices
  ./sr tts --try "Ciao a tutti" [--voice X]     listen to a voice before using it
  ./sr help tools                               low-level commands (debugging)

Settings precedence: defaults < config.toml < lesson settings < options.
"""

TOOLS_HELP = """Low-level commands (the program runs them for you):
  ./sr init <pdf> [--id NAME]                 analyse a PDF: slide images, text lines, overview
  ./sr check <lesson>                         validate the script
  ./sr audio <lesson> [--slides 1,3-5]        generate missing/changed narration audio
  ./sr render <lesson> [--slides] [--preview] [--outdated]   render slides + contact sheets (build/<lesson>/qa)
  ./sr anim <lesson> --all | --slide N [--beat K]            render animations alone + contact sheets
  ./sr join <lesson> [--small]                concatenate the slide videos into output/<lesson>.mp4
  ./sr templates                              animation templates and their arguments
"""


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "lesson"


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_kv(items):
    """['temperature=0.6', 'voice=it_female'] -> {'temperature': 0.6, 'voice': 'it_female'}"""
    out = {}
    for item in items or []:
        if "=" not in item:
            die(f"expected KEY=VALUE, got '{item}'")
        k, v = item.split("=", 1)
        try:
            out[k.strip()] = json.loads(v)
        except json.JSONDecodeError:
            out[k.strip()] = v
    return out


def video_duration(path):
    out = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def contact_sheet(video, png, frames=16):
    """Grid of frames sampled evenly from a video, for visual checks."""
    png.parent.mkdir(parents=True, exist_ok=True)
    every = max(video_duration(video) / frames, 0.5)
    rows = math.ceil(frames / 4)
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-i", str(video), "-vf",
                    f"fps=1/{every:.3f},scale=480:-1,tile=4x{rows}:padding=4:color=gray", "-frames:v", "1", str(png)],
                   check=True)
    return png


def missing_audio(lesson, slides, numbers):
    have = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}
    return [k for k, _, _ in audio_pieces(slides) if int(k[1:3]) in numbers
            and (k not in have or not (lesson.audio / f"{k}.wav").exists())]


def fingerprint(lesson, settings, slide):
    """Hash of everything that affects a slide's video: script entry, audio, animations, engine code."""
    from .validate import animation_files
    h = hashlib.sha1(json.dumps(slide, sort_keys=True, ensure_ascii=False).encode())
    h.update(f"{settings['visual']}|{settings['beat_gap']}".encode())
    have = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}
    for k, _, _ in audio_pieces([slide]):
        h.update(f"{k}:{have.get(k, {}).get('duration')}".encode())
    for f in [ROOT / "slidereader" / f for f in ("engine.py", "templates.py", "anim_api.py")] + animation_files(lesson):
        h.update(f.read_bytes())
    return h.hexdigest()


def is_outdated(lesson, settings, slide):
    meta = lesson.video / f"slide_{slide['slide']:02d}.json"
    if not lesson.slide_video(slide["slide"]).exists() or not meta.exists():
        return True
    return json.loads(meta.read_text()).get("fingerprint") != fingerprint(lesson, settings, slide)


def run_manim(lesson, n, final, only_beat=None, fake=None, name=None):
    name = name or f"slide_{n:02d}"
    media = lesson.media / name
    if media.exists():
        shutil.rmtree(media)
    env = {**ENV, "SR_LESSON": lesson.id, "SR_SLIDE": str(n)}
    if only_beat is not None:
        env["SR_ONLY_BEAT"] = str(only_beat)
    if fake:
        env["SR_FAKE_AUDIO"] = str(fake)
    v = CONFIG["video"]
    quality = ["-r", f"{v['width']},{v['height']}", "--fps", str(v["fps"])] if final else ["-ql"]
    log = lesson.build / "logs" / f"{name}.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(MANIM), "render", *quality, "--disable_caching", "--media_dir", str(media), "-o", name,
           str(ROOT / "slidereader" / "manim_entry.py"), "LessonScene"]
    with open(log, "w") as fh:
        rc = subprocess.run(cmd, env=env, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        text = log.read_text()
        tail = [l for l in text.splitlines() if re.search(r"Error|error:|Exit|Missing|unknown|not found", l)]
        raise RuntimeError(f"{name}: render failed. {' | '.join(tail[-3:])}\n  full log: {log.relative_to(ROOT)}")
    return next(media.glob(f"videos/**/{name}.mp4"))


# ================================================================ main command and advanced commands
def cmd_make(a):
    from .pipeline import make
    make(a)


def cmd_redo(a):
    from .pipeline import redo
    redo(a)


def cmd_build(a):
    cmd_audio(a)
    a.preview, a.outdated = False, True
    cmd_render(a)
    cmd_join(a)


def cmd_status(a):
    lesson = Lesson(a.lesson)
    settings, slides = load_script(lesson.script)
    have = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}
    pieces = audio_pieces(slides)
    tts = tts_options(settings)
    print(f"Lesson {lesson.id} ({lesson.pdf.name})")
    print(f"  pages {settings['pages'] or 'all'}, {settings['visual']}, depth {settings['depth']} "
          f"({DEPTHS[settings['depth']]}), skipped {settings['skip'] or 'none'}")
    print(f"  voice: {tts['engine']} " + ", ".join(f"{k}={v}" for k, v in tts.items() if k not in ("engine", "model")))
    if agent_instructions(settings):
        print(f"  instructions: {agent_instructions(settings)}")
    print("\n slide  beats  audio     video")
    for s in slides:
        n = s["slide"]
        keys = [k for k, t, _ in pieces if int(k[1:3]) == n]
        ok = [k for k, t, _ in pieces if int(k[1:3]) == n and have.get(k, {}).get("text") == t]
        state = ("-" if not lesson.slide_video(n).exists()
                 else "OUTDATED" if is_outdated(lesson, settings, s) else "up to date")
        print(f" {n:5d}  {len(s['beats']):5d}  {len(ok):3d}/{len(keys):<3d}  {state}")
    total = sum(v["duration"] for k, v in have.items())
    print(f"\nAudio generated: {total / 60:.1f} min.  Output: "
          f"{lesson.output.relative_to(ROOT) if lesson.output.exists() else 'not joined yet'}")


def cmd_tts(a):
    from . import tts_engines
    current = tts_engines.resolve(CONFIG["tts"])
    name = a.engine or current["engine"]
    engine = tts_engines.get_engine(name)
    overrides = {"engine": name, **parse_kv(a.set), **({"voice": a.voice} if a.voice else {})}

    if a.try_text is None:
        print("TTS engines:")
        for e in tts_engines.ENGINES.values():
            mark = "*" if e.name == current["engine"] else " "
            print(f" {mark} {e.name:8s} [{e.runs}]  {e.description}")
        opts = tts_engines.resolve(CONFIG["tts"], None, {"engine": name})
        print(f"\nOptions of '{name}' (current values from config.toml [tts.{name}]):")
        for key, o in engine.options.items():
            allowed = (", ".join(map(str, o.choices)) if o.choices else
                       f"{o.minimum}..{o.maximum}" if o.minimum is not None else "free")
            print(f"  {key:12s} = {opts[key]!r}\n      {o.help}\n      allowed: {allowed}")
        if getattr(engine, "suggested_voices", None):
            print(f"\n  suggested voices: {', '.join(engine.suggested_voices)}")
        print(f"""
Try a voice:       ./sr tts --try "Ciao a tutti, iniziamo." [--engine {name}] [--voice X] [--set key=value] [--play]
Change the default: edit [tts] / [tts.{name}] in config.toml
One lesson only:    ./sr <lesson> --engine {name} --voice X --tts key=value""")
        return

    problems = engine.validate({k: v for k, v in overrides.items() if k != "engine"})
    if problems:
        die("; ".join(problems))
    label = "_".join(str(v) for k, v in overrides.items() if k in ("engine", "voice"))
    out = ROOT / "voice-samples" / f"try_{slugify(label)}_{time.strftime('%H%M%S')}.wav"
    rc = subprocess.run([str(TTS_PY), "-m", "slidereader.tts", "sample", a.try_text, "--out", str(out),
                         "--set", json.dumps(overrides)], cwd=ROOT, env=ENV).returncode
    if rc:
        sys.exit(rc)
    if a.play:
        subprocess.run(["afplay", str(out)])


# ================================================================ low-level tools
def cmd_init(a):
    pdf = Path(a.pdf).expanduser().resolve()
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        die(f"not a PDF file: {a.pdf}")
    INPUT.mkdir(exist_ok=True)
    if pdf.parent != INPUT.resolve():
        shutil.copy2(pdf, INPUT / pdf.name)
        pdf = INPUT / pdf.name
        print(f"Copied the PDF to input/{pdf.name}")
    lesson = Lesson.create(a.id or slugify(pdf.stem), pdf)
    from .pdf_extract import extract
    pages = extract(lesson)
    if not lesson.script.exists():
        lesson.script.write_text(json.dumps(STUB, indent=2) + "\n")
    print(f"Lesson {lesson.id}: {pages} pages analysed ({lesson.overview.relative_to(ROOT)})")


def cmd_check(a):
    from .validate import validate
    lesson = Lesson(a.lesson)
    settings, slides = load_script(lesson.script)
    errors, warnings = validate(lesson, settings, slides)
    words = sum(len(t.split()) for _, t, _ in audio_pieces(slides))
    print(f"Mode: visual={settings['visual']}, depth={settings['depth']} ({DEPTHS.get(settings['depth'], '?')}), "
          f"pages={settings['pages'] or 'all'}")
    print(f"{len(slides)} slides, {len(audio_pieces(slides))} spoken pieces, {words} words "
          f"(about {words / 150:.0f} min of video)")
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  ERROR:   {e}")
    if errors:
        sys.exit(1)
    print("Script OK" + (" (with warnings)" if warnings else ""))


def cmd_audio(a):
    rc = subprocess.run([str(TTS_PY), "-m", "slidereader.tts", "lesson", a.lesson, "--slides", a.slides or ""],
                        cwd=ROOT, env=ENV).returncode
    if rc:
        sys.exit(rc)


def cmd_render(a):
    """Render slides; returns the list of slide numbers rendered."""
    lesson = Lesson(a.lesson)
    settings, slides = load_script(lesson.script)
    numbers = parse_slide_list(a.slides, [s["slide"] for s in slides])
    by_number = {s["slide"]: s for s in slides}
    if getattr(a, "outdated", False):
        numbers = [n for n in numbers if is_outdated(lesson, settings, by_number[n])]
        if not numbers:
            print("All slide videos are up to date.")
            return []
    if not numbers:
        die("no slides selected")
    miss = missing_audio(lesson, slides, set(numbers))
    if miss:
        die(f"{len(miss)} audio piece(s) missing (e.g. {miss[0]}). Run: ./sr audio {lesson.id}")
    final = not a.preview
    kind = "final" if final else "preview"
    lesson.video.mkdir(parents=True, exist_ok=True)
    done, failed = [], []

    def job(n):
        mp4 = run_manim(lesson, n, final)
        if final:
            shutil.copy2(mp4, lesson.slide_video(n))
            (lesson.video / f"slide_{n:02d}.json").write_text(
                json.dumps({"fingerprint": fingerprint(lesson, settings, by_number[n])}))
        sheet = contact_sheet(mp4, lesson.qa / f"{kind}_slide_{n:02d}.png")
        return n, video_duration(mp4), sheet

    print(f"Rendering {len(numbers)} slide(s), {kind} quality...", flush=True)
    with ThreadPoolExecutor(CONFIG["video"]["parallel_jobs"]) as pool:
        futures = {pool.submit(job, n): n for n in numbers}
        for f in as_completed(futures):
            try:
                n, d, sheet = f.result()
                done.append(n)
                print(f"  ok slide {n:2d}  {d:6.1f}s   check: {sheet.relative_to(ROOT)}", flush=True)
            except Exception as e:  # noqa: BLE001
                failed.append(futures[f])
                print(f"  FAILED slide {futures[f]}: {e}", flush=True)
    if failed:
        die(f"slides failed: {sorted(failed)}")
    return done


def cmd_anim(a):
    lesson = Lesson(a.lesson)
    _, slides = load_script(lesson.script)
    targets = []
    for s in slides:
        for k, beat in enumerate(s["beats"]):
            if "anim" in beat and (a.all or (s["slide"] == a.slide and (a.beat is None or a.beat == k))):
                targets.append((s["slide"], k, len(beat["steps"])))
    if not targets:
        die("no animation beat matches (use --slide N [--beat K] or --all)")
    have = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}

    def job(t):
        n, k, steps = t
        real = all(piece_key(n, k, j) in have for j in range(steps))
        name = f"anim_s{n:02d}_b{k:02d}"
        mp4 = run_manim(lesson, n, False, only_beat=k, fake=None if real else a.seconds, name=name)
        return t, contact_sheet(mp4, lesson.qa / f"{name}.png", frames=12), real

    with ThreadPoolExecutor(CONFIG["video"]["parallel_jobs"]) as pool:
        for f in as_completed([pool.submit(job, t) for t in targets]):
            try:
                (n, k, _), sheet, real = f.result()
                timing = "real audio timing" if real else f"placeholder {a.seconds}s per step"
                print(f"  ok slide {n} beat {k} ({timing})   check: {sheet.relative_to(ROOT)}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"  FAILED: {e}", flush=True)


def cmd_join(a):
    lesson = Lesson(a.lesson)
    _, slides = load_script(lesson.script)
    files = [lesson.slide_video(s["slide"]) for s in slides]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        die(f"missing final renders: {missing}. Run: ./sr build {lesson.id}")
    lst = lesson.build / "concat.txt"
    lst.write_text("".join(f"file '{f}'\n" for f in files))
    OUTPUT.mkdir(exist_ok=True)
    audio = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", *audio, "-movflags", "+faststart",
                    str(lesson.output)], check=True)
    print(f"Video: {lesson.output.relative_to(ROOT)}  ({video_duration(lesson.output) / 60:.1f} min, "
          f"{lesson.output.stat().st_size / 1e6:.0f} MB)")
    if getattr(a, "small", True):
        h = CONFIG["video"]["small_height"]
        subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-i", str(lesson.output), "-vf", f"scale=-2:{h}",
                        "-c:v", "libx264", "-crf", "29", "-preset", "medium", "-c:a", "aac", "-b:a", "96k",
                        "-movflags", "+faststart", str(lesson.output_small)], check=True)
        print(f"Small copy: {lesson.output_small.relative_to(ROOT)}  "
              f"({lesson.output_small.stat().st_size / 1e6:.0f} MB)")


def cmd_templates(a):
    from . import templates
    for name, fn in templates.TEMPLATES.items():
        sig = str(inspect.signature(fn)).replace("(scene, steps, ", "(")
        print(f"\n=== {name}{sig}\n{inspect.getdoc(fn)}")


# ================================================================ argument parsing
def make_parser():
    p = argparse.ArgumentParser(prog="./sr", add_help=False)
    p.add_argument("target", nargs="?")
    p.add_argument("--pages")
    p.add_argument("--visual", choices=VISUAL_MODES)
    p.add_argument("--depth", type=int, choices=sorted(DEPTHS))
    p.add_argument("--instructions")
    p.add_argument("--voice")
    p.add_argument("--engine")
    p.add_argument("--tts", action="append", default=[])
    p.add_argument("--id")
    p.add_argument("--rewrite", action="store_true")
    p.add_argument("--no-review", action="store_true")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(fn=cmd_make)
    return p


def sub_parser():
    ap = argparse.ArgumentParser(prog="./sr")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status")
    p.add_argument("lesson")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("redo")
    p.add_argument("lesson")
    p.add_argument("--slides", required=True)
    p.add_argument("--part", choices=("script", "voice", "video"), default="script")
    p.add_argument("--note", help="request for the agent when rewriting, e.g. 'add a concrete example'")
    p.add_argument("--no-review", action="store_true")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(fn=cmd_redo)

    p = sub.add_parser("build")
    p.add_argument("lesson")
    p.add_argument("--slides", default="")
    p.set_defaults(fn=cmd_build, small=True)

    p = sub.add_parser("tts")
    p.add_argument("--engine")
    p.add_argument("--try", dest="try_text")
    p.add_argument("--voice")
    p.add_argument("--set", action="append", default=[])
    p.add_argument("--play", action="store_true")
    p.set_defaults(fn=cmd_tts)

    p = sub.add_parser("init")
    p.add_argument("pdf")
    p.add_argument("--id")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("check")
    p.add_argument("lesson")
    p.set_defaults(fn=cmd_check)

    for name, fn in (("audio", cmd_audio), ("render", cmd_render)):
        p = sub.add_parser(name)
        p.add_argument("lesson")
        p.add_argument("--slides", default="")
        if name == "render":
            p.add_argument("--preview", action="store_true")
            p.add_argument("--outdated", action="store_true")
        p.set_defaults(fn=fn)

    p = sub.add_parser("anim")
    p.add_argument("lesson")
    p.add_argument("--slide", type=int)
    p.add_argument("--beat", type=int)
    p.add_argument("--all", action="store_true")
    p.add_argument("--seconds", type=float, default=5.0)
    p.set_defaults(fn=cmd_anim)

    p = sub.add_parser("join")
    p.add_argument("lesson")
    p.add_argument("--small", action="store_true")
    p.set_defaults(fn=cmd_join)

    p = sub.add_parser("templates")
    p.set_defaults(fn=cmd_templates)
    return ap


SUBCOMMANDS = {"status", "redo", "build", "tts", "init", "check", "audio", "render", "anim", "join", "templates"}


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help", "help"):
        print(TOOLS_HELP if argv[1:2] == ["tools"] else HELP)
        return
    if argv and argv[0] in SUBCOMMANDS:
        a = sub_parser().parse_args(argv)
    else:
        a = make_parser().parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
