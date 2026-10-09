"""Rendering: slide videos (Manim), animation previews, contact sheets, change detection, final join.

Manim's working files are deleted as soon as a render is copied out, so build/ only keeps what is needed.
"""
import hashlib
import json
import math
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import CONFIG, FFMPEG, MANIM, OUTPUT, PACKAGE, ROOT, SUBPROCESS_ENV as ENV
from ..script import audio_pieces, load_script


class RenderError(Exception):
    pass


def video_duration(path):
    out = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def contact_sheet(video, png, frames=16):
    """Grid of frames sampled evenly from a video (used for visual checks)."""
    png.parent.mkdir(parents=True, exist_ok=True)
    every = max(video_duration(video) / frames, 0.5)
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-i", str(video), "-vf",
                    f"fps=1/{every:.3f},scale=480:-1,tile=4x{math.ceil(frames / 4)}:padding=4:color=gray",
                    "-frames:v", "1", str(png)], check=True)
    return png


# ------------------------------------------------------------------ change detection
def fingerprint(lesson, settings, slide):
    """Hash of everything that affects a slide's video: script entry, audio, animations, rendering code."""
    from ..validate import animation_files
    h = hashlib.sha1(json.dumps(slide, sort_keys=True, ensure_ascii=False).encode())
    h.update(f"{settings['visual']}|{settings['beat_gap']}".encode())
    meta = lesson.durations_meta()
    for k, _, _ in audio_pieces([slide]):
        h.update(f"{k}:{meta.get(k, {}).get('duration')}".encode())
    code = [PACKAGE / "video" / f for f in ("scene.py", "templates.py", "anim_api.py")]
    for f in code + animation_files(lesson):
        h.update(f.read_bytes())
    return h.hexdigest()


def is_outdated(lesson, settings, slide):
    meta = lesson.video / f"slide_{slide['slide']:02d}.json"
    if not lesson.slide_video(slide["slide"]).exists() or not meta.exists():
        return True
    return json.loads(meta.read_text()).get("fingerprint") != fingerprint(lesson, settings, slide)


def missing_audio(lesson, slides):
    meta = lesson.durations_meta()
    return [k for k, _, _ in audio_pieces(slides) if k not in meta or not (lesson.audio / f"{k}.wav").exists()]


# ------------------------------------------------------------------ Manim
def run_manim(lesson, n, final, only_beat=None, fake=None, name=None):
    """Render one slide (or one animation beat) and return the path of the produced mp4."""
    name = name or f"slide_{n:02d}"
    media = lesson.media / name
    shutil.rmtree(media, ignore_errors=True)
    env = {**ENV, "SR_LESSON": lesson.id, "SR_SLIDE": str(n)}
    if only_beat is not None:
        env["SR_ONLY_BEAT"] = str(only_beat)
    if fake:
        env["SR_FAKE_AUDIO"] = str(fake)
    v = CONFIG["video"]
    quality = ["-r", f"{v['width']},{v['height']}", "--fps", str(v["fps"])] if final else ["-ql"]
    log = lesson.logs / f"{name}.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(MANIM), "render", *quality, "--disable_caching", "--media_dir", str(media), "-o", name,
           str(PACKAGE / "video" / "manim_entry.py"), "LessonScene"]
    with open(log, "w") as fh:
        rc = subprocess.run(cmd, env=env, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT).returncode
    if rc != 0:
        lines = [l.strip() for l in log.read_text().splitlines()
                 if re.search(r"Error|error:|Exit|Missing|unknown|not found", l)]
        raise RenderError(f"{name}: {' | '.join(lines[-2:]) or 'render failed'} (log: {log.relative_to(ROOT)})")
    return next(media.glob(f"videos/**/{name}.mp4"))


def render_slides(lesson, numbers, final=True, on_done=None):
    """Render slides in parallel. on_done(n, seconds) is called as each finishes. Returns rendered numbers."""
    settings, slides = load_script(lesson.script)
    by_number = {s["slide"]: s for s in slides}
    lesson.video.mkdir(parents=True, exist_ok=True)
    kind = "final" if final else "preview"

    def job(n):
        mp4 = run_manim(lesson, n, final)
        if final:
            shutil.copy2(mp4, lesson.slide_video(n))
            (lesson.video / f"slide_{n:02d}.json").write_text(
                json.dumps({"fingerprint": fingerprint(lesson, settings, by_number[n])}))
        contact_sheet(mp4, lesson.qa / f"{kind}_slide_{n:02d}.png")
        seconds = video_duration(mp4)
        shutil.rmtree(lesson.media / f"slide_{n:02d}", ignore_errors=True)
        return n, seconds

    done, failed = [], []
    with ThreadPoolExecutor(CONFIG["tuning"]["parallel_jobs"]) as pool:
        futures = {pool.submit(job, n): n for n in numbers}
        for f in as_completed(futures):
            try:
                n, seconds = f.result()
                done.append(n)
                if on_done:
                    on_done(n, seconds)
            except RenderError as e:
                failed.append(str(e))
    if failed:
        raise RenderError("; ".join(failed))
    return sorted(done)


def render_animation_previews(lesson, beats, seconds_per_step=None):
    """Render animation beats alone at low resolution. Returns [(slide, beat, contact_sheet, error)]."""
    seconds_per_step = seconds_per_step or CONFIG["tuning"]["placeholder_seconds"]

    def job(nk):
        n, k = nk
        name = f"anim_s{n:02d}_b{k:02d}"
        # real audio timing where the voice exists, placeholder timing otherwise
        mp4 = run_manim(lesson, n, False, only_beat=k, fake=seconds_per_step, name=name)
        sheet = contact_sheet(mp4, lesson.qa / f"{name}.png", frames=12)
        shutil.rmtree(lesson.media / name, ignore_errors=True)
        return sheet

    out = []
    with ThreadPoolExecutor(CONFIG["tuning"]["parallel_jobs"]) as pool:
        futures = [(nk, pool.submit(job, nk)) for nk in beats]
        for (n, k), fut in futures:
            try:
                out.append((n, k, fut.result(), None))
            except RenderError as e:
                out.append((n, k, None, str(e)))
    return out


# ------------------------------------------------------------------ final video
def join(lesson):
    """Concatenate the slide videos (script order) into output/<id>.mp4 with normalized loudness."""
    _, slides = load_script(lesson.script)
    files = [lesson.slide_video(s["slide"]) for s in slides]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise RenderError(f"missing slide videos: {missing}")
    lst = lesson.build / "concat.txt"
    lst.write_text("".join(f"file '{f}'\n" for f in files))
    OUTPUT.mkdir(exist_ok=True)
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    "-movflags", "+faststart", str(lesson.output)], check=True)
    for old in OUTPUT.glob(f"{lesson.id}_*p.mp4"):        # lightweight copies made by older versions
        old.unlink()
    return lesson.output, video_duration(lesson.output), lesson.output.stat().st_size
