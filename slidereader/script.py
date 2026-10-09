"""The narration script (lessons/<id>/script.json): loading, saving and the list of spoken pieces.

A script is {"settings": {...per-video choices...}, "slides": [{"slide": n, "beats": [...]}, ...]}.
Pure Python (no heavy imports): used by both virtual environments.
"""
import json
from pathlib import Path

from .settings import merge_settings, settings_to_save


def load_script(path: Path):
    """Return (settings, slides)."""
    if not path.exists():
        raise SystemExit(f"Script not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"{path.name}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}")
    if "slides" not in data:
        raise SystemExit(f"{path.name}: missing \"slides\" list")
    return merge_settings(data.get("settings", {})), data["slides"]


def save_script(path: Path, settings, slides):
    path.write_text(json.dumps({"settings": settings_to_save(settings), "slides": slides},
                               ensure_ascii=False, indent=2) + "\n")


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


def parse_pages(spec, available):
    """'1,3,5-8' -> [1,3,5,6,7,8] (only those present in `available`); empty = all."""
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
