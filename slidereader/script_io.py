"""Loading and flattening a lesson script (scripts/<lesson>.json), and the lesson settings.

Pure Python (no Manim / MLX imports) so that both virtual environments can use it.
"""
import json
from pathlib import Path

from . import tts_engines
from .config import CONFIG

VISUAL_MODES = ("slides", "mixed", "animated")
DEPTHS = {1: "extensive", 2: "faithful", 3: "condensed", 4: "short"}
SAVED_KEYS = ("visual", "depth", "pages", "skip", "instructions", "tts", "beat_gap")


def default_settings():
    """Settings of a lesson before anything is saved in it (config.toml values)."""
    n = CONFIG["narration"]
    return {"language": n["language"], "visual": n["visual"], "depth": n["depth"], "beat_gap": n["beat_gap"],
            "pages": "", "skip": [], "instructions": "", "tts": {}}


def merge_settings(saved):
    s = {**default_settings(), **saved}
    if "voice" in saved and "tts" not in saved:          # scripts written before engines existed
        s["tts"] = {k: saved[k] for k in ("voice", "temperature") if k in saved}
    return s


def tts_options(settings):
    """Complete TTS configuration of a lesson: {"engine": ..., option: value, ...}."""
    return tts_engines.resolve(CONFIG["tts"], settings.get("tts"))


def agent_instructions(settings):
    """Global instructions (config.toml) followed by the lesson's own."""
    return "\n".join(t.strip() for t in (CONFIG["agent"].get("instructions", ""), settings.get("instructions", ""))
                     if t and t.strip())


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
    return merge_settings(data.get("settings", {})), data["slides"]


def settings_to_save(settings):
    """Only what belongs to the lesson (no copies of config defaults, except the per-video choices)."""
    d = default_settings()
    out = {k: settings[k] for k in ("visual", "depth", "pages", "skip")}
    for k in ("instructions", "tts", "beat_gap"):
        if settings.get(k) not in (None, d[k]):
            out[k] = settings[k]
    return out


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
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            wanted.update(range(int(a), int(b) + 1))
        elif part:
            wanted.add(int(part))
    return [n for n in available if n in wanted]
