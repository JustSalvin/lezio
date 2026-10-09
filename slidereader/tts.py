"""Speech synthesis for a lesson (runs in .venv-tts). Use `./sr audio <lesson>`.

Only pieces that are new, or whose text/voice/temperature changed, are generated.
"""
import argparse
import json
import time

import numpy as np
import soundfile as sf

from .config import CONFIG, Lesson
from .script_io import audio_pieces, load_script, parse_slide_list


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lesson")
    ap.add_argument("--slides", default="")
    args = ap.parse_args()

    lesson = Lesson(args.lesson)
    settings, slides = load_script(lesson.script)
    chosen = set(parse_slide_list(args.slides, [s["slide"] for s in slides]))
    lesson.audio.mkdir(parents=True, exist_ok=True)
    meta = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}

    def stale(key, text):
        m = meta.get(key, {})
        return (not (lesson.audio / f"{key}.wav").exists() or m.get("text") != text
                or m.get("voice", settings["voice"]) != settings["voice"]
                or m.get("temperature", settings["temperature"]) != settings["temperature"])

    todo = [(k, t) for k, t, _ in audio_pieces(slides) if int(k[1:3]) in chosen and stale(k, t)]
    print(f"Audio: {len(todo)} piece(s) to generate (voice {settings['voice']}, "
          f"temperature {settings['temperature']})", flush=True)
    if not todo:
        return

    from mlx_audio.tts.utils import load_model
    model = load_model(CONFIG["tts"]["model"])
    start = time.time()
    for i, (key, text) in enumerate(todo, 1):
        parts, sr = [], None
        for r in model.generate(text=text, voice=settings["voice"], temperature=settings["temperature"],
                                max_tokens=4096):
            parts.append(np.array(r.audio, dtype=np.float32))
            sr = r.sample_rate
        audio = np.concatenate(parts)
        sf.write(lesson.audio / f"{key}.wav", audio, sr)
        meta[key] = {"text": text, "duration": round(len(audio) / sr, 3),
                     "voice": settings["voice"], "temperature": settings["temperature"]}
        lesson.durations.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
        eta = (time.time() - start) / i * (len(todo) - i)
        print(f"[{i}/{len(todo)}] {key}: {meta[key]['duration']:.1f}s  (about {eta / 60:.0f} min left)", flush=True)
    print("Audio done.", flush=True)


if __name__ == "__main__":
    main()
