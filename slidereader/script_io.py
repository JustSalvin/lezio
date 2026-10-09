"""Loading and flattening a lesson script (scripts/<lesson>.json).

Pure Python (no Manim / MLX imports) so that both virtual environments can use it.
"""
import json
from pathlib import Path

from .config import CONFIG

VISUAL_KEYS = ("highlight", "image", "zoom")


def default_settings():
    return {
        "language": CONFIG["narration"]["language"],
        "visual": CONFIG["narration"]["visual"],
        "depth": CONFIG["narration"]["depth"],
        "pages": "",
        "voice": CONFIG["tts"]["voice"],
        "temperature": CONFIG["tts"]["temperature"],
        "beat_gap": CONFIG["narration"]["beat_gap"],
        "skip": [],
    }


VISUAL_MODES = ("slides", "mixed", "animated")
DEPTHS = {1: "extensive", 2: "faithful", 3: "condensed", 4: "short"}


def load_script(path: Path):
    """Return (settings, slides) from a JSON script."""
    if not path.exists():
        raise SystemExit(f"Script not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"{path.name}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}")
    if "slides" not in data:
        raise SystemExit(f"{path.name}: missing \"slides\" list")
    return {**default_settings(), **data.get("settings", {})}, data["slides"]


def normalize_step(step):
    return step if isinstance(step, dict) else {"say": step}


def piece_key(slide, beat, step=None):
    k = f"s{slide:02d}_b{beat:02d}"
    return k if step is None else f"{k}_{step}"


def audio_pieces(slides):
    """Flat, ordered list of (key, text, pause_after) for every spoken piece."""
    out = []
    for s in slides:
        n = s["slide"]
        for k, beat in enumerate(s["beats"]):
            if "anim" in beat:
                for j, st in enumerate(beat["steps"]):
                    st = normalize_step(st)
                    out.append((piece_key(n, k, j), st["say"], st.get("pause", 0)))
            else:
                out.append((piece_key(n, k), beat["say"], beat.get("pause", 0)))
    return out


def parse_slide_list(spec, available):
    """'1,3,5-8' -> [1,3,5,6,7,8] (only those present in `available`)."""
    if not spec:
        return list(available)
    wanted = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            wanted.update(range(int(a), int(b) + 1))
        elif part:
            wanted.add(int(part))
    return [n for n in available if n in wanted]
