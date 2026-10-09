"""slide-reader command line. Use it through the ./sr wrapper (see README.md and AGENTS.md)."""
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
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .config import CONFIG, FFMPEG, INPUT, MANIM, OUTPUT, ROOT, SCRIPTS, TTS_PY, Lesson
from .script_io import (DEPTHS, VISUAL_MODES, audio_pieces, load_script, normalize_step,
                        parse_slide_list, piece_key)

ENV = {**os.environ, "PATH": f"{ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}", "PYTHONPATH": str(ROOT)}
STUB = {"settings": {"skip": []}, "slides": []}


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "lesson"


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


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
    h = hashlib.sha1(json.dumps(slide, sort_keys=True, ensure_ascii=False).encode())
    h.update(f"{settings['visual']}|{settings['beat_gap']}".encode())
    have = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}
    for k, _, _ in audio_pieces([slide]):
        h.update(f"{k}:{have.get(k, {}).get('duration')}".encode())
    code = [ROOT / "slidereader" / f for f in ("engine.py", "templates.py", "anim_api.py")]
    from .validate import animation_files
    for f in code + animation_files(lesson):
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


# ---------------------------------------------------------------- commands
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
    SCRIPTS.mkdir(exist_ok=True)
    if not lesson.script.exists():
        lesson.script.write_text(json.dumps(STUB, indent=2) + "\n")
    rel = lambda p: p.relative_to(ROOT)
    print(f"""
Lesson id: {lesson.id}   ({pages} slides)
  overview (text lines + hints): {rel(lesson.overview)}
  slide previews:                {rel(lesson.preview)}/slide_NN.jpg
  script:                        {rel(lesson.script)}""")


def cmd_check(a):
    from .validate import validate
    lesson = Lesson(a.lesson)
    settings, slides = load_script(lesson.script)
    errors, warnings = validate(lesson, settings, slides)
    visual = settings["visual"]
    seen = [s["slide"] for s in slides if isinstance(s, dict) and "slide" in s]
    words = sum(len(t.split()) for _, t, _ in audio_pieces(slides))
    print(f"Mode: visual={visual}, depth={settings['depth']} ({DEPTHS.get(settings['depth'], '?')}), "
          f"pages={settings['pages'] or 'all'}")
    print(f"{len(seen)} slides, {len(audio_pieces(slides))} spoken pieces, {words} words "
          f"(about {words / 150:.0f} min of video)")
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  ERROR:   {e}")
    if errors:
        sys.exit(1)
    print("Script OK" + (" (with warnings)" if warnings else ""))


def cmd_audio(a):
    rc = subprocess.run([str(TTS_PY), "-m", "slidereader.tts", a.lesson, "--slides", a.slides or ""],
                        cwd=ROOT, env=ENV).returncode
    if rc:
        sys.exit(rc)


def cmd_render(a):
    lesson = Lesson(a.lesson)
    settings, slides = load_script(lesson.script)
    numbers = parse_slide_list(a.slides, [s["slide"] for s in slides])
    by_number = {s["slide"]: s for s in slides}
    if getattr(a, "outdated", False):
        numbers = [n for n in numbers if is_outdated(lesson, settings, by_number[n])]
        if not numbers:
            print("All slide videos are up to date.")
            return
    if not numbers:
        die("no slides selected")
    miss = missing_audio(lesson, slides, set(numbers))
    if miss:
        die(f"{len(miss)} audio piece(s) missing (e.g. {miss[0]}). Run: ./sr audio {lesson.id}")
    final = not a.preview
    kind = "final" if final else "preview"
    lesson.video.mkdir(parents=True, exist_ok=True)
    failed = []

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
                print(f"  ok slide {n:2d}  {d:6.1f}s   check: {sheet.relative_to(ROOT)}", flush=True)
            except Exception as e:  # noqa: BLE001
                failed.append(futures[f])
                print(f"  FAILED slide {futures[f]}: {e}", flush=True)
    if failed:
        die(f"slides failed: {sorted(failed)}")


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
        die(f"missing final renders: {missing}. Run: ./sr render {lesson.id}")
    lst = lesson.build / "concat.txt"
    lst.write_text("".join(f"file '{f}'\n" for f in files))
    OUTPUT.mkdir(exist_ok=True)
    audio = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", *audio, "-movflags", "+faststart",
                    str(lesson.output)], check=True)
    print(f"Video: {lesson.output.relative_to(ROOT)}  ({video_duration(lesson.output) / 60:.1f} min, "
          f"{lesson.output.stat().st_size / 1e6:.0f} MB)")
    if a.small:
        h = CONFIG["video"]["small_height"]
        subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-i", str(lesson.output), "-vf", f"scale=-2:{h}",
                        "-c:v", "libx264", "-crf", "29", "-preset", "medium", "-c:a", "aac", "-b:a", "96k",
                        "-movflags", "+faststart", str(lesson.output_small)], check=True)
        print(f"Small copy: {lesson.output_small.relative_to(ROOT)}  "
              f"({lesson.output_small.stat().st_size / 1e6:.0f} MB)")


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
    print(f"Lesson {lesson.id}: {len(slides)} slides in the script")
    print(" slide  beats  audio     final video")
    for s in slides:
        n = s["slide"]
        keys = [k for k, t, _ in pieces if int(k[1:3]) == n]
        ok = [k for k, t, _ in pieces if int(k[1:3]) == n and have.get(k, {}).get("text") == t]
        if not lesson.slide_video(n).exists():
            state = "-"
        else:
            state = "OUTDATED (re-render)" if is_outdated(lesson, settings, s) else "up to date"
        print(f" {n:5d}  {len(s['beats']):5d}  {len(ok):3d}/{len(keys):<3d}  {state}")
    total = sum(v["duration"] for k, v in have.items())
    print(f"Audio generated: {total / 60:.1f} min.  Output: "
          f"{lesson.output.relative_to(ROOT) if lesson.output.exists() else 'not joined yet'}")


def cmd_make(a):
    from .pipeline import make
    make(a)


def cmd_templates(a):
    from . import templates
    for name, fn in templates.TEMPLATES.items():
        sig = str(inspect.signature(fn)).replace("(scene, steps, ", "(")
        print(f"\n=== {name}{sig}\n{inspect.getdoc(fn)}")


def main():
    ap = argparse.ArgumentParser(prog="./sr", description="Turn PDF slides into a narrated video lecture.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("make", help="THE PROGRAM: PDF -> finished video (calls the agent for the writing)")
    p.add_argument("pdf", nargs="?", help="PDF path (default: choose from input/)")
    p.add_argument("--id", help="lesson id (default: derived from the file name)")
    p.add_argument("--pages", help="pages to cover, e.g. 1-20 (default: all)")
    p.add_argument("--visual", choices=VISUAL_MODES)
    p.add_argument("--depth", type=int, choices=sorted(DEPTHS))
    p.add_argument("--rewrite", action="store_true", help="discard an existing script and write a new one")
    p.add_argument("--no-review", action="store_true", help="skip the final review of the rendered frames")
    p.set_defaults(fn=cmd_make)

    p = sub.add_parser("init", help="register a PDF: slide images, text lines, overview, empty script")
    p.add_argument("pdf")
    p.add_argument("--id", help="lesson id (default: derived from the file name)")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("check", help="validate the script (JSON, highlights, animations, coverage)")
    p.add_argument("lesson")
    p.set_defaults(fn=cmd_check)

    for name, fn, hlp in (("audio", cmd_audio, "generate narration audio (only new/changed pieces)"),
                          ("render", cmd_render, "render slides to video + contact sheets in build/<id>/qa"),
                          ("build", cmd_build, "audio + final render + join, all in one")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("lesson")
        p.add_argument("--slides", default="", help="e.g. 1,3,5-8 (default: all)")
        if name == "render":
            p.add_argument("--preview", action="store_true", help="fast low-resolution render")
            p.add_argument("--outdated", action="store_true", help="only slides whose script/audio changed")
        if name == "build":
            p.add_argument("--small", action="store_true", help="also write a lightweight copy")
        p.set_defaults(fn=fn)

    p = sub.add_parser("anim", help="render animation beats alone (fast) + contact sheet")
    p.add_argument("lesson")
    p.add_argument("--slide", type=int)
    p.add_argument("--beat", type=int)
    p.add_argument("--all", action="store_true")
    p.add_argument("--seconds", type=float, default=5.0, help="placeholder step length when audio is missing")
    p.set_defaults(fn=cmd_anim)

    p = sub.add_parser("join", help="concatenate the final slide renders into output/<id>.mp4")
    p.add_argument("lesson")
    p.add_argument("--small", action="store_true", help="also write a lightweight copy")
    p.set_defaults(fn=cmd_join)

    p = sub.add_parser("status", help="what is generated / missing / outdated")
    p.add_argument("lesson")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("templates", help="list the ready-made animation templates and their arguments")
    p.set_defaults(fn=cmd_templates)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
