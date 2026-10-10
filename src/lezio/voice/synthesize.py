"""Speech synthesis worker. Runs in .venv-tts (MLX), started by voice/client.py.

Prints one JSON event per line on stdout so that the program can show progress:
    {"event": "start", "total": N, "tts": "..."}   {"event": "loading"}
    {"event": "piece", "i": i, "key": "...", "duration": seconds}   {"event": "done"}
Only pieces that are new, or whose text or TTS options (engine, voice, ...) changed, are generated.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import soundfile as sf

from ..lesson import Lesson
from ..script import audio_pieces, load_script, narration
from ..settings import tts_label, tts_options
from . import engines


def emit(**event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


class Engines:
    """Engines prepared once (per engine and model)."""

    def __init__(self):
        self.ready = {}

    def get(self, opts):
        params = {k: v for k, v in opts.items() if k != "engine"}
        key = (opts["engine"], params.get("model"))
        if key not in self.ready:
            engine = engines.get_engine(opts["engine"])()
            problems = engine.validate(params)
            if problems:
                raise SystemExit("config.toml [tts]: " + "; ".join(problems))
            emit(event="loading")
            engine.prepare(params)
            self.ready[key] = engine
        return self.ready[key], params


def stale_pieces(lesson, segments):
    """[(key, text, options)] of the pieces to generate."""
    meta = lesson.durations_meta()
    opts = tts_options()
    out = []
    for key, text, _ in audio_pieces(segments):
        m = meta.get(key, {})
        if not (lesson.audio / f"{key}.wav").exists() or m.get("text") != text or m.get("tts") != opts:
            out.append((key, text, opts))
    return out


def synthesize_lesson(lesson_id, segment_ids):
    lesson = Lesson(lesson_id)
    script = load_script(lesson.script)
    wanted = set(filter(None, segment_ids.split(","))) if segment_ids else None
    segments = [s for s in script["segments"] if narration(s) and (wanted is None or s["id"] in wanted)]
    todo = stale_pieces(lesson, segments)
    emit(event="start", total=len(todo), tts=tts_label())
    lesson.audio.mkdir(parents=True, exist_ok=True)
    meta = lesson.durations_meta()
    if wanted is None:                      # drop the audio of pieces no longer in the script
        keys = {k for k, _, _ in audio_pieces(script["segments"])}
        for key in [k for k in meta if k not in keys]:
            meta.pop(key)
            (lesson.audio / f"{key}.wav").unlink(missing_ok=True)
        lesson.durations.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    ready = Engines()
    for i, (key, text, opts) in enumerate(todo, 1):
        engine, params = ready.get(opts)
        audio, sr = engine.synthesize(text, params)
        sf.write(lesson.audio / f"{key}.wav", audio, sr)
        meta[key] = {"text": text, "duration": round(len(audio) / sr, 3), "tts": opts}
        lesson.durations.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        emit(event="piece", i=i, key=key, duration=meta[key]["duration"])
    emit(event="done")


def sample(text, overrides, out):
    opts = tts_options(overrides)
    engine, params = Engines().get(opts)
    start = time.time()
    audio, sr = engine.synthesize(text, params)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, audio, sr)
    emit(event="sample", path=str(out), duration=round(len(audio) / sr, 2), seconds=round(time.time() - start, 1))


def download():
    opts = tts_options()
    engines.get_engine(opts["engine"])().download({k: v for k, v in opts.items() if k != "engine"})


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lesson")
    p.add_argument("lesson")
    p.add_argument("--segments", default="")
    p = sub.add_parser("sample")
    p.add_argument("text")
    p.add_argument("--out", required=True)
    p.add_argument("--set", default="{}", help="JSON object of option overrides")
    sub.add_parser("download")
    a = ap.parse_args()
    try:
        if a.cmd == "lesson":
            synthesize_lesson(a.lesson, a.segments)
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
