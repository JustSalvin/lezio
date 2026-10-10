# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Rendering: segment videos (Manim), previews of submissions, step sheets, change detection, final join.

A step sheet shows, for every narration piece, the frame in its middle and the frame at its end, with the
start of the sentence: it is what the agent looks at to judge a scene. Manim's working files are deleted
as soon as a render is copied out, so build/ only keeps what is needed.
"""
import functools
import hashlib
import json
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import CONFIG, FFMPEG, MANIM, OUTPUT, PACKAGE, ROOT, SUBPROCESS_ENV as ENV, THEMES
from ..script import find_segment, load_script, pieces, scene_name
from ..settings import house_theme

PREVIEW_FPS = 15                   # manim -ql


class RenderError(Exception):
    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report or {}


def video_duration(path):
    out = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def has_audio(path):
    out = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, text=True).stderr
    return "Audio:" in out


# ------------------------------------------------------------------ step sheets
def step_sheet(mp4, report, png, fps, width=1440):
    """Frames in the middle and at the end of every narration piece, two pieces per row, with captions."""
    from PIL import Image, ImageDraw, ImageFont
    infos = [p for p in report.get("pieces", []) if "end" in p]
    if not infos:
        return None
    times = []
    for p in infos:
        times += [(p["start"] + p["end"]) / 2, max(p["end"] - 0.05, p["start"])]
    numbers = [max(int(t * fps), 0) for t in times]
    tmp = png.parent / f".{png.stem}_frames"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    expr = "+".join(f"eq(n\\,{n})" for n in sorted(set(numbers)))
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-i", str(mp4), "-vf", f"select={expr},scale=480:-1",
                    "-fps_mode", "passthrough", str(tmp / "f%04d.jpg")], check=True)
    files = sorted(tmp.glob("f*.jpg"))
    by_number = dict(zip(sorted(set(numbers)), files))
    cell_w = (width - 5 * 6) // 4
    cell_h = round(cell_w * 9 / 16)
    cap_h = 22
    rows = (len(infos) + 1) // 2
    sheet = Image.new("RGB", (width, rows * (cell_h + cap_h + 8) + 6), (70, 70, 70))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(14)                 # the font bundled with Pillow: same on every system
    for k, p in enumerate(infos):
        x = 6 + (k % 2) * 2 * (cell_w + 6)
        y = 6 + (k // 2) * (cell_h + cap_h + 8)
        words = p["say"].split()
        caption = f"piece {p['index']} · {' '.join(words[:12])}" + ("…" if len(words) > 12 else "")
        while draw.textlength(caption, font=font) > 2 * cell_w and len(caption) > 10:
            caption = caption[:-2] + "…" if not caption.endswith("…") else caption[:-3] + "…"
        draw.text((x, y + 2), caption, fill=(235, 235, 235), font=font)
        for j in range(2):
            f = by_number.get(numbers[2 * k + j])
            if f is not None:
                im = Image.open(f).convert("RGB").resize((cell_w, cell_h))
                sheet.paste(im, (x + j * (cell_w + 6), y + cap_h))
    sheet.save(png)
    shutil.rmtree(tmp, ignore_errors=True)
    return png


# ------------------------------------------------------------------ change detection
@functools.lru_cache(maxsize=1)
def runtime_code():
    files = sorted((PACKAGE / "scene").rglob("*.py")) + [PACKAGE / "video" / "scene_runner.py",
                                                          PACKAGE / "material" / "__init__.py"]
    user = ROOT / "templates"
    files += sorted(user.glob("*.py")) if user.is_dir() else []
    h = hashlib.sha1()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest()


def fingerprint(lesson, script, segment):
    """Hash of everything that affects a segment's video: entry, audio, scene code, theme, runtime, material."""
    s = script["settings"]
    h = hashlib.sha1(json.dumps(segment, sort_keys=True, ensure_ascii=False).encode())
    v = CONFIG["video"]
    theme = THEMES / f"{house_theme()}.toml"
    h.update(f"{s['piece_gap']}|{v['width']}x{v['height']}@{v['fps']}|{v.get('subtitles') == 'burned'}".encode())
    h.update(theme.read_bytes() if theme.exists() else b"")
    meta = lesson.durations_meta()
    for key, _, _ in pieces(segment):
        h.update(f"{key}:{meta.get(key, {}).get('duration')}".encode())
    path = lesson.scene_file(scene_name(segment))
    h.update(path.read_bytes() if path.exists() and not segment.get("blocks") else b"")
    for f in sorted(lesson.templates.glob("*.py")) if lesson.templates.is_dir() else []:
        h.update(f.read_bytes())                      # the agent's templates of the lesson
    h.update(runtime_code().encode())
    if lesson.index.exists():
        index = json.loads(lesson.index.read_text())
        h.update("|".join(f"{x['id']}:{x['fingerprint']}:{x['version']}" for x in index["sources"]).encode())
    return h.hexdigest()


def video_meta(lesson, segment_id):
    path = lesson.video / f"{segment_id}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def is_outdated(lesson, script, segment):
    if not lesson.segment_video(segment["id"]).exists():
        return True
    return video_meta(lesson, segment["id"]).get("fingerprint") != fingerprint(lesson, script, segment)


def missing_audio(lesson, segments):
    meta = lesson.durations_meta()
    return [k for k, text, _ in (p for s in segments for p in pieces(s))
            if meta.get(k, {}).get("text") != text or not (lesson.audio / f"{k}.wav").exists()]


# ------------------------------------------------------------------ Manim
def run_scene(lesson, segment_id, final, name, draft=None, estimate=False):
    """Render one segment and return (mp4 path, report). Raises RenderError with a short message."""
    media = lesson.media / name
    shutil.rmtree(media, ignore_errors=True)
    media.mkdir(parents=True)
    lesson.qa.mkdir(parents=True, exist_ok=True)
    report_path = lesson.qa / f"{name}.json"
    report_path.unlink(missing_ok=True)
    env = {**ENV, "LEZIO_LESSON": lesson.id, "LEZIO_SEGMENT": segment_id, "LEZIO_REPORT": str(report_path)}
    if draft:
        env["LEZIO_DRAFT"] = str(draft)
    if estimate:
        env["LEZIO_ESTIMATE"] = "1"
    v = CONFIG["video"]
    quality = ["-r", f"{v['width']},{v['height']}", "--fps", str(v["fps"])] if final else ["-ql"]
    log = lesson.logs / f"{name}.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(MANIM), "render", *quality, "--disable_caching", "--media_dir", str(media), "-o", name,
           str(PACKAGE / "video" / "manim_entry.py"), "SegmentScene"]
    timeout = CONFIG["tuning"]["render_timeout_seconds"]
    with open(log, "w") as fh:
        try:
            rc = subprocess.run(cmd, env=env, cwd=media, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            shutil.rmtree(media, ignore_errors=True)
            raise RenderError(f"{name}: render stopped after {timeout} s (endless loop or far too many animations?)")
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    if rc != 0:
        shutil.rmtree(media, ignore_errors=True)
        lines = [l.strip() for l in log.read_text().splitlines() if re.search(r"Error|error:|Exception", l)]
        raise RenderError(report.get("error") or " | ".join(lines[-2:]) or f"{name}: render failed (log: {log})",
                          report)
    found = list(media.glob(f"videos/**/{name}.mp4"))
    if not found:
        raise RenderError(f"{name}: Manim produced no video (log: {log})", report)
    return found[0], report


def preview(lesson, segment, code=None):
    """Render a submission (not saved yet) at low resolution, with estimated timing where the voice does not
    exist yet: template blocks (segment["blocks"]) or scene code. Returns (step sheet or None, report);
    raises RenderError."""
    drafts = lesson.agent / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    code_path = None
    if code is not None:
        code_path = drafts / f"{segment['id']}.py"
        code_path.write_text(code)
    draft = drafts / f"{segment['id']}.json"
    draft.write_text(json.dumps({"segment": segment, "code": str(code_path) if code_path else None},
                                ensure_ascii=False))
    name = f"preview_{segment['id']}"
    mp4, report = run_scene(lesson, segment["id"], final=False, name=name, draft=draft, estimate=True)
    try:
        sheet = step_sheet(mp4, report, lesson.qa / f"{name}.png", PREVIEW_FPS)
        report["seconds"] = round(video_duration(mp4), 1)
        shutil.copy2(mp4, lesson.qa / f"{name}.mp4")          # kept for a closer look at single frames
    finally:
        shutil.rmtree(lesson.media / name, ignore_errors=True)
    return sheet, report


def piece_frame(lesson, segment_id, piece, final, where="end"):
    """One frame of a segment's preview (final=False) or final video, in the middle or at the end of a
    narration piece, as a JPEG file. Raises RenderError if there is no such video or piece."""
    name = segment_id if final else f"preview_{segment_id}"
    mp4 = lesson.segment_video(segment_id) if final else lesson.qa / f"{name}.mp4"
    report_path = lesson.qa / f"{name}.json"
    if not mp4.exists() or not report_path.exists():
        raise RenderError(f"no {'final video' if final else 'preview'} of {segment_id}")
    infos = {p["index"]: p for p in json.loads(report_path.read_text()).get("pieces", []) if "end" in p}
    if piece not in infos:
        raise RenderError(f"{segment_id} has pieces 0-{max(infos) if infos else 0}")
    p = infos[piece]
    t = (p["start"] + p["end"]) / 2 if where == "middle" else max(p["end"] - 0.05, p["start"])
    out = lesson.qa / f"frame_{name}_{piece}_{where}.jpg"
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1",
                    "-q:v", "3", str(out)], check=True)
    return out


def _ensure_audio(mp4):
    """Segments without any voice (e.g. tests) get a silent track, so that all segments can be joined."""
    if has_audio(mp4):
        return
    tmp = mp4.with_name(mp4.stem + ".tmp.mp4")
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-i", str(mp4), "-f", "lavfi", "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000", "-c:v", "copy", "-c:a", "aac", "-shortest",
                    str(tmp)], check=True)
    tmp.replace(mp4)


def render_segments(lesson, ids, on_done=None, estimate=False):
    """Final render of some segments, in parallel. on_done(id, seconds) as each finishes.
    Returns the ids rendered; raises RenderError listing the failures."""
    script = load_script(lesson.script)
    lesson.video.mkdir(parents=True, exist_ok=True)

    def job(sid):
        segment = find_segment(script, sid)
        mp4, report = run_scene(lesson, sid, final=True, name=sid, estimate=estimate)
        try:
            _ensure_audio(mp4)
            shutil.copy2(mp4, lesson.segment_video(sid))
            step_sheet(mp4, report, lesson.qa / f"final_{sid}.png", CONFIG["video"]["fps"])
            seconds = video_duration(mp4)
        finally:
            shutil.rmtree(lesson.media / sid, ignore_errors=True)
        (lesson.video / f"{sid}.json").write_text(json.dumps(
            {"fingerprint": fingerprint(lesson, script, segment), "seconds": round(seconds, 1),
             "warnings": report.get("warnings", [])}, ensure_ascii=False, indent=1))
        return sid, seconds

    done, failed = [], []
    with ThreadPoolExecutor(CONFIG["tuning"]["parallel_jobs"]) as pool:
        futures = {pool.submit(job, sid): sid for sid in ids}
        for f in as_completed(futures):
            try:
                sid, seconds = f.result()
                done.append(sid)
                if on_done:
                    on_done(sid, seconds)
            except RenderError as e:
                failed.append(f"{futures[f]}: {e}")
    if failed:
        raise RenderError("; ".join(failed))
    return [s["id"] for s in script["segments"] if s["id"] in done]


# ------------------------------------------------------------------ final video
def join(lesson):
    """Concatenate the segment videos (script order) into output/<id>.mp4 with normalized loudness."""
    script = load_script(lesson.script)
    files = [lesson.segment_video(s["id"]) for s in script["segments"]]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise RenderError(f"missing segment videos: {missing}")
    from . import subtitles
    lst = lesson.build / "concat.txt"
    lst.write_text("".join(f"file '{f}'\n" for f in files))
    OUTPUT.mkdir(exist_ok=True)
    srt = lesson.output.with_suffix(".srt")
    mode = subtitles.mode()
    inputs, extra, vf = ["-f", "concat", "-safe", "0", "-i", str(lst)], [], []
    if mode == "off":
        srt.unlink(missing_ok=True)
    else:
        subtitles.write_srt(subtitles.cues(lesson), srt)
        if mode == "track":
            inputs += ["-i", str(srt)]
            extra = ["-map", "0:v", "-map", "0:a", "-map", "1:s", "-c:s", "mov_text",
                     "-metadata:s:s:0", f"language={subtitles.language_code()}",
                     "-metadata:s:s:0", f"title={CONFIG['narration']['language']}"]
        else:
            vf = ["-vf", subtitles.burn_filter(srt)]
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", *inputs, *vf,
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    *extra, "-movflags", "+faststart", str(lesson.output)], check=True)
    (lesson.build / "joined.json").write_text(json.dumps(
        {"segments": [[s["id"], video_meta(lesson, s["id"]).get("fingerprint")] for s in script["segments"]],
         "time": time.strftime("%Y-%m-%d %H:%M")}))
    return lesson.output, video_duration(lesson.output), lesson.output.stat().st_size


def video_state(lesson, script):
    """State of the lesson's final video, from the lesson itself (never from output/):
    "done" (assembled from the current segments), "outdated" (assembled, then something changed),
    "none" (never assembled)."""
    path = lesson.build / "joined.json"
    if not path.exists():
        return "none"
    joined = json.loads(path.read_text()).get("segments")
    current = [[s["id"], video_meta(lesson, s["id"]).get("fingerprint")] for s in script["segments"]]
    if joined != current or any(is_outdated(lesson, script, s) for s in script["segments"]):
        return "outdated"
    return "done"
