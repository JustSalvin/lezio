"""The two kinds of settings, never mixed.

- Per-video choices (pages, visual mode, depth, agent instructions, skipped pages): given to the program
  (wizard or command-line options) and saved in lessons/<id>/script.json.
- Configuration (voice, language, LLM, video quality, tuning): config.toml only.

Pure Python (no heavy imports): used by both virtual environments.
"""
from .config import CONFIG
from .voice import engines

VISUAL_MODES = {
    "slides": "the original slides, with a highlight following the voice",
    "mixed": "slides + full-screen explanation animations",
    "animated": "only animations; the slides are the source but are never shown",
}
DEPTHS = {1: "extensive", 2: "faithful", 3: "condensed", 4: "short"}
DEPTH_HELP = {
    1: "everything on the slides, plus explanations, examples and connections",
    2: "everything on the slides, nothing added, nothing cut",
    3: "the main points, lightly summarized",
    4: "very concise, short-video style",
}
LESSON_CHOICES = ("pages", "visual", "depth", "instructions", "skip")
DEFAULT_CHOICES = {"pages": "", "visual": "mixed", "depth": 2, "instructions": "", "skip": []}


def default_settings():
    return {**DEFAULT_CHOICES, "language": CONFIG["narration"]["language"],
            "beat_gap": CONFIG["narration"]["beat_gap"]}


def merge_settings(saved):
    """Lesson choices on top of the defaults; anything else saved by older versions is ignored."""
    return {**default_settings(), **{k: v for k, v in saved.items() if k in LESSON_CHOICES}}


def settings_to_save(settings):
    out = {k: settings[k] for k in ("pages", "visual", "depth", "skip")}
    if settings.get("instructions"):
        out["instructions"] = settings["instructions"]
    return out


def tts_options():
    """The configured TTS engine and its complete options: {"engine": ..., option: value, ...}."""
    return engines.resolve(CONFIG["tts"])


def tts_label(opts=None):
    opts = opts or tts_options()
    return f"{opts['engine']}: " + ", ".join(f"{k}={v}" for k, v in opts.items() if k not in ("engine", "model"))


def piece_tts(meta_entry):
    """TTS options an audio piece was generated with (pieces from before engines existed were Voxtral)."""
    if "tts" in meta_entry:
        return meta_entry["tts"]
    if "voice" in meta_entry:
        return engines.resolve({**CONFIG["tts"], "engine": "voxtral"}, None,
                               {"voice": meta_entry["voice"], "temperature": meta_entry["temperature"]})
    return None
