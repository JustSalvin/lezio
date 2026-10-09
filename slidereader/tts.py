"""Speech synthesis (runs in .venv-tts). Used by `./sr` and `./sr tts --try`.

Only pieces that are new, or whose text or TTS settings changed, are generated.
"""
import argparse
import json
import time
from pathlib import Path

import soundfile as sf

from . import tts_engines
from .config import CONFIG, Lesson
from .script_io import audio_pieces, load_script, parse_slide_list, tts_options


def synthesize_lesson(lesson_id, slides_spec):
    lesson = Lesson(lesson_id)
    settings, slides = load_script(lesson.script)
    opts = tts_options(settings)
    engine = tts_engines.get_engine(opts["engine"])()
    params = {k: v for k, v in opts.items() if k != "engine"}
    chosen = set(parse_slide_list(slides_spec, [s["slide"] for s in slides]))
    lesson.audio.mkdir(parents=True, exist_ok=True)
    meta = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}

    def used_tts(m):                       # pieces generated before engines existed were Voxtral
        if "tts" in m:
            return m["tts"]
        if "voice" in m:
            return tts_engines.resolve(CONFIG["tts"], {"engine": "voxtral", "voice": m["voice"],
                                                       "temperature": m["temperature"]})
        return None

    todo = [(k, t) for k, t, _ in audio_pieces(slides) if int(k[1:3]) in chosen and
            (not (lesson.audio / f"{k}.wav").exists() or meta.get(k, {}).get("text") != t
             or used_tts(meta.get(k, {})) != opts)]
    shown = ", ".join(f"{k}={v}" for k, v in params.items() if k != "model")
    print(f"Audio: {len(todo)} piece(s) to generate ({opts['engine']}: {shown})", flush=True)
    if not todo:
        return
    engine.prepare(params)
    start = time.time()
    for i, (key, text) in enumerate(todo, 1):
        audio, sr = engine.synthesize(text, params)
        sf.write(lesson.audio / f"{key}.wav", audio, sr)
        meta[key] = {"text": text, "duration": round(len(audio) / sr, 3), "tts": opts}
        lesson.durations.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        eta = (time.time() - start) / i * (len(todo) - i)
        print(f"[{i}/{len(todo)}] {key}: {meta[key]['duration']:.1f}s  (about {eta / 60:.0f} min left)", flush=True)
    print("Audio done.", flush=True)


def sample(text, overrides, out):
    """Synthesize one sample with the configured engine, optionally overriding options."""
    opts = tts_engines.resolve(CONFIG["tts"], None, overrides)
    engine = tts_engines.get_engine(opts["engine"])()
    params = {k: v for k, v in opts.items() if k != "engine"}
    problems = engine.validate(params)
    if problems:
        raise SystemExit("; ".join(problems))
    engine.prepare(params)
    t = time.time()
    audio, sr = engine.synthesize(text, params)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, audio, sr)
    print(f"{out}  ({len(audio) / sr:.1f}s of audio, generated in {time.time() - t:.1f}s)", flush=True)


def download():
    opts = tts_engines.resolve(CONFIG["tts"])
    tts_engines.get_engine(opts["engine"])().download({k: v for k, v in opts.items() if k != "engine"})


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lesson")
    p.add_argument("lesson")
    p.add_argument("--slides", default="")
    p = sub.add_parser("sample")
    p.add_argument("text")
    p.add_argument("--out", required=True)
    p.add_argument("--set", default="{}", help="JSON object of option overrides")
    sub.add_parser("download")
    a = ap.parse_args()
    if a.cmd == "lesson":
        synthesize_lesson(a.lesson, a.slides)
    elif a.cmd == "sample":
        sample(a.text, json.loads(a.set), a.out)
    else:
        download()


if __name__ == "__main__":
    main()
