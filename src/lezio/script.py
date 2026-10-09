"""The lesson script (lessons/<id>/script.json, version 2): loading, saving, narration pieces.

    {"version": 2,
     "settings": {"style": "mixed", "format": "lecture", "depth": 2, "instructions": "", "focus": {...}},
     "title": "...", "outline": "...", "plan_key": "...",
     "segments": [{"id": "s01", "title": "...", "goal": "...", "sources": ["slides.pdf#p1-3"], "minutes": 1.5,
                   "narration": ["...", {"say": "...", "pause": 2}, {"say": "...", "speaker": "student"}],
                   "scene": "s01"}],
     "skipped": [{"ref": "slides.pdf#p14", "reason": "live poll"}]}

A segment is planned when it has id/title/goal/sources, written when it also has narration and its scene
file (scenes/<scene>.py) exists. Every narration piece is one audio file, key "<segment>_<piece>".
Pure Python (no heavy imports): used by both virtual environments.
"""
import json
from pathlib import Path

from .settings import merge_settings, settings_to_save


def empty_script(settings=None):
    return {"version": 2, "settings": merge_settings(settings), "title": "", "outline": "", "plan_key": "",
            "segments": [], "skipped": []}


def load_script(path: Path):
    """The script with complete settings (defaults filled in). A missing file is an empty script."""
    if not path.exists():
        return empty_script()
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"{path.name}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}")
    if "segments" not in data:
        raise SystemExit(f"{path.name}: not a lezio script (no \"segments\" list)")
    script = {**empty_script(), **data}
    script["settings"] = merge_settings(data.get("settings"))
    return script


def save_script(path: Path, script):
    out = {"version": 2, "settings": settings_to_save(script["settings"])}
    out.update({k: script[k] for k in ("title", "outline", "plan_key", "segments", "skipped")})
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")


def normalize_piece(piece):
    """A narration piece as {"say", "pause", "speaker"} (a plain string is said by the teacher)."""
    if isinstance(piece, str):
        return {"say": piece, "pause": 0, "speaker": "teacher"}
    return {"say": piece.get("say", ""), "pause": piece.get("pause", 0) or 0,
            "speaker": piece.get("speaker", "teacher") or "teacher"}


def piece_key(segment_id, i):
    return f"{segment_id}_{i:02d}"


def pieces(segment):
    """[(key, text, pause_after, speaker)] for the narration of one segment."""
    return [(piece_key(segment["id"], i), p["say"], p["pause"], p["speaker"])
            for i, p in enumerate(normalize_piece(x) for x in segment.get("narration") or [])]


def audio_pieces(segments):
    """Flat, ordered list of (key, text, pause_after, speaker) for every spoken piece."""
    return [p for s in segments for p in pieces(s)]


def find_segment(script, segment_id):
    for s in script["segments"]:
        if s["id"] == segment_id:
            return s
    return None


def scene_name(segment):
    return segment.get("scene") or segment["id"]


def is_written(lesson, segment):
    return bool(segment.get("narration")) and lesson.scene_file(scene_name(segment)).exists()


def estimate_seconds(text):
    """Speaking time of a piece before its audio exists (about 150 words per minute)."""
    return max(1.5, len(text.split()) / 2.5)
