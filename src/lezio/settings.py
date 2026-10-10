"""The two kinds of settings, never mixed.

- Per-video choices (depth, instructions for the agent, focus on parts of the sources): everything else
  the user wants for a video goes in the instructions. They are given to the program (wizard or
  command-line options) and saved in lessons/<id>/script.json.
  The sources themselves are listed in lessons/<id>/lesson.json.
- Configuration (voices, language, LLM, video quality, tuning): config.toml only.

Pure Python (no heavy imports): used by both virtual environments.
"""
from .config import CONFIG, THEMES
from .voice import engines

DEPTHS = {1: "extensive", 2: "faithful", 3: "condensed", 4: "short"}
DEPTH_HELP = {
    1: "everything in the material, plus explanations, examples and connections",
    2: "everything in the material, nothing added, nothing cut",
    3: "the main points, lightly summarized",
    4: "very concise, short-video style",
}
LESSON_CHOICES = ("depth", "instructions", "focus")
DEFAULT_CHOICES = {"depth": 2, "instructions": "", "focus": {}}
# Changing these makes the current plan and script obsolete (the lesson is rewritten, with a backup)
PLAN_CHOICES = ("depth", "focus")


def house_theme():
    """The theme of config.toml [video] theme (light if missing)."""
    name = CONFIG.get("video", {}).get("theme", "light")
    return name if (THEMES / f"{name}.toml").exists() else "light"


def lesson_theme(script):
    """The theme a lesson is rendered with: the one chosen in its plan, else the house theme."""
    name = script.get("theme")
    return name if name and (THEMES / f"{name}.toml").exists() else house_theme()


def default_settings():
    return {**DEFAULT_CHOICES, "language": CONFIG["narration"]["language"],
            "piece_gap": CONFIG["narration"]["piece_gap"]}


def merge_settings(saved):
    """Lesson choices on top of the defaults; anything else saved is ignored."""
    return {**default_settings(), **{k: v for k, v in (saved or {}).items() if k in LESSON_CHOICES}}


def settings_to_save(settings):
    out = {"depth": settings["depth"]}
    if settings.get("focus"):
        out["focus"] = settings["focus"]
    if settings.get("instructions"):
        out["instructions"] = settings["instructions"]
    return out


def tts_options(overrides=None):
    """The configured TTS engine and its complete options: {"engine": ..., option: value, ...}.
    overrides (e.g. from ./lezio voices --try) may change the engine and any option."""
    overrides = overrides or {}
    return engines.resolve(CONFIG["tts"], None, overrides)


def tts_label(opts=None):
    opts = opts or tts_options()
    return f"{opts['engine']}: " + ", ".join(f"{k}={v}" for k, v in opts.items() if k not in ("engine", "model"))
