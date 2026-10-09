"""Speech synthesis worker. Runs in .venv-tts (MLX), started by voice/client.py.

Prints one JSON event per line on stdout so that the program can show progress:
    {"event": "start", "total": N, "tts": "..."}   {"event": "loading"}
    {"event": "piece", "i": i, "key": "...", "duration": seconds}   {"event": "done"}
Only pieces that are new, or whose text or TTS configuration changed, are generated.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import soundfile as sf

from ..config import CONFIG
from ..lesson import Lesson
from ..script import audio_pieces, load_script, parse_pages
from ..settings import piece_tts, tts_label, tts_options
from . import engines


def emit(**event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def engine_for(opts):
    engine = engines.get_engine(opts["engine"])()
    params = {k: v for k, v in opts.items() if k != "engine"}
    problems = engine.validate(params)
    if problems:
        raise SystemExit("config.toml [tts]: " + "; ".join(problems))
    return engine, params


def stale_pieces(lesson, slides, opts):
    meta = lesson.durations_meta()
    return [(k, t) for k, t, _ in audio_pieces(slides)
            if not (lesson.audio / f"{k}.wav").exists() or meta.get(k, {}).get("text") != t
            or piece_tts(meta.get(k, {})) != opts]


def synthesize_lesson(lesson_id, pages):
    lesson = Lesson(lesson_id)
    _, slides = load_script(lesson.script)
    slides = [s for s in slides if s["slide"] in set(parse_pages(pages, [s["slide"] for s in slides]))]
    opts = tts_options()
    todo = stale_pieces(lesson, slides, opts)
    emit(event="start", total=len(todo), tts=tts_label(opts))
    if not todo:
        emit(event="done")
        return
    engine, params = engine_for(opts)
    emit(event="loading")
    engine.prepare(params)
    lesson.audio.mkdir(parents=True, exist_ok=True)
    meta = lesson.durations_meta()
    for i, (key, text) in enumerate(todo, 1):
        audio, sr = engine.synthesize(text, params)
        sf.write(lesson.audio / f"{key}.wav", audio, sr)
        meta[key] = {"text": text, "duration": round(len(audio) / sr, 3), "tts": opts}
        lesson.durations.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        emit(event="piece", i=i, key=key, duration=meta[key]["duration"])
    emit(event="done")


def sample(text, overrides, out):
    opts = engines.resolve(CONFIG["tts"], None, overrides)
    engine, params = engine_for(opts)
    emit(event="loading")
    engine.prepare(params)
    start = time.time()
    audio, sr = engine.synthesize(text, params)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, audio, sr)
    emit(event="sample", path=str(out), duration=round(len(audio) / sr, 2), seconds=round(time.time() - start, 1))


def download():
    engine, params = engine_for(tts_options())
    engine.download(params)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lesson")
    p.add_argument("lesson")
    p.add_argument("--pages", default="")
    p = sub.add_parser("sample")
    p.add_argument("text")
    p.add_argument("--out", required=True)
    p.add_argument("--set", default="{}", help="JSON object of option overrides")
    sub.add_parser("download")
    a = ap.parse_args()
    try:
        if a.cmd == "lesson":
            synthesize_lesson(a.lesson, a.pages)
        elif a.cmd == "sample":
            sample(a.text, json.loads(a.set), a.out)
        else:
            download()
    except SystemExit as e:
        if e.code not in (0, None):
            emit(event="error", message=str(e.code))
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
