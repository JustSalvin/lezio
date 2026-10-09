"""The two kinds of settings, never mixed.

- Per-video choices (style, format, depth, instructions for the agent, focus on parts of the sources):
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
    "mixed": "slides for the structure, animations where seeing explains better",
    "whiteboard": "a board where everything is written and drawn by hand while talking",
}
FORMATS = {
    "lecture": "one teacher explains",
    "dialogue": "a teacher and a student: questions, mistakes, answers",
    "review": "questions, a pause to think, then the answer: for revising",
}
DEPTHS = {1: "extensive", 2: "faithful", 3: "condensed", 4: "short"}
DEPTH_HELP = {
    1: "everything in the material, plus explanations, examples and connections",
    2: "everything in the material, nothing added, nothing cut",
    3: "the main points, lightly summarized",
    4: "very concise, short-video style",
}
SPEAKERS = {"lecture": ("teacher",), "dialogue": ("teacher", "student"), "review": ("teacher",)}
LESSON_CHOICES = ("style", "format", "depth", "instructions", "focus")
DEFAULT_CHOICES = {"style": "mixed", "format": "lecture", "depth": 2, "instructions": "", "focus": {}}
# Changing these makes the current plan and script obsolete (the lesson is rewritten, with a backup)
PLAN_CHOICES = ("style", "format", "depth", "focus")


def default_settings():
    return {**DEFAULT_CHOICES, "language": CONFIG["narration"]["language"],
            "piece_gap": CONFIG["narration"]["piece_gap"]}


def merge_settings(saved):
    """Lesson choices on top of the defaults; anything else saved is ignored."""
    return {**default_settings(), **{k: v for k, v in (saved or {}).items() if k in LESSON_CHOICES}}


def settings_to_save(settings):
    out = {k: settings[k] for k in ("style", "format", "depth")}
    if settings.get("focus"):
        out["focus"] = settings["focus"]
    if settings.get("instructions"):
        out["instructions"] = settings["instructions"]
    return out


def tts_options(speaker="teacher"):
    """The configured TTS engine and its complete options for a speaker: {"engine": ..., option: value}.

    [tts.<engine>] voice is the teacher's voice; [tts.<engine>.voices] gives the other speakers' voices.
    """
    tts = CONFIG["tts"]
    name = tts["engine"]
    section = {k: v for k, v in tts.get(name, {}).items() if k != "voices"}
    voices = tts.get(name, {}).get("voices", {})
    overrides = {"voice": voices[speaker]} if speaker in voices else {}
    return engines.resolve({**tts, name: section}, None, overrides)


def tts_label(opts=None):
    opts = opts or tts_options()
    return f"{opts['engine']}: " + ", ".join(f"{k}={v}" for k, v in opts.items() if k not in ("engine", "model"))


def voices_label(fmt):
    """'teacher it_male · student it_female' for the speakers of a format."""
    speakers = SPEAKERS.get(fmt, ("teacher",))
    if len(speakers) == 1:
        return tts_label()
    first = tts_options(speakers[0])
    rest = ", ".join(f"{k}={v}" for k, v in first.items() if k not in ("engine", "model", "voice"))
    return f"{first['engine']}: " + " · ".join(f"{s} {tts_options(s)['voice']}" for s in speakers) + \
        (f" · {rest}" if rest else "")
