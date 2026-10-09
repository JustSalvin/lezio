"""The two kinds of settings, never mixed.

- Per-video choices (style, depth, instructions for the agent, focus on parts of the sources):
  given to the program (wizard or command-line options) and saved in lessons/<id>/script.json.
  The sources themselves are listed in lessons/<id>/lesson.json.
- Configuration (voices, language, LLM, video quality, tuning): config.toml only.

Pure Python (no heavy imports): used by both virtual environments.
"""
from .config import CONFIG
from .voice import engines

STYLES = {
    "animated": "full animations: diagrams, transformations, motion; no slide look",
    "slides": "clean generated slides revealed step by step with the voice",
    "whiteboard": "a board where everything is written and drawn by hand while talking",
    "auto": "the agent chooses animated, slides or whiteboard for each segment, switching along the video",
}
# Styles a segment can have: with "auto" the plan chooses one of these for every segment
SEGMENT_STYLES = ("animated", "slides", "whiteboard")
DEPTHS = {1: "extensive", 2: "faithful", 3: "condensed", 4: "short"}
DEPTH_HELP = {
    1: "everything in the material, plus explanations, examples and connections",
    2: "everything in the material, nothing added, nothing cut",
    3: "the main points, lightly summarized",
    4: "very concise, short-video style",
}
LESSON_CHOICES = ("style", "depth", "instructions", "focus")
DEFAULT_CHOICES = {"style": "auto", "depth": 2, "instructions": "", "focus": {}}
# Changing these makes the current plan and script obsolete (the lesson is rewritten, with a backup)
PLAN_CHOICES = ("style", "depth", "focus")


def segment_style(settings, segment):
    """The style of one segment: the lesson style, or with "auto" the one chosen in the plan."""
    if settings["style"] != "auto":
        return settings["style"]
    return segment.get("style") if segment.get("style") in SEGMENT_STYLES else "slides"


def default_settings():
    return {**DEFAULT_CHOICES, "language": CONFIG["narration"]["language"],
            "piece_gap": CONFIG["narration"]["piece_gap"]}


def merge_settings(saved):
    """Lesson choices on top of the defaults; anything else saved is ignored."""
    return {**default_settings(), **{k: v for k, v in (saved or {}).items() if k in LESSON_CHOICES}}


def settings_to_save(settings):
    out = {k: settings[k] for k in ("style", "depth")}
    if settings.get("focus"):
        out["focus"] = settings["focus"]
    if settings.get("instructions"):
        out["instructions"] = settings["instructions"]
    return out


def tts_options(overrides=None):
    """The configured TTS engine and its complete options: {"engine": ..., option: value, ...}.
    overrides (e.g. from ./lezio tts --try) may change the engine and any option."""
    overrides = overrides or {}
    return engines.resolve(CONFIG["tts"], None, overrides)


def tts_label(opts=None):
    opts = opts or tts_options()
    return f"{opts['engine']}: " + ", ".join(f"{k}={v}" for k, v in opts.items() if k not in ("engine", "model"))
