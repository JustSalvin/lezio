"""Script validation, shared by `./lezio check` and by the program while it collects the agent's work."""
import importlib.util
import inspect
import re
from types import SimpleNamespace

from .pdf import load_lines, resolve_highlight, resolve_image
from .script import normalize_step, parse_pages
from .settings import DEPTHS, VISUAL_MODES, tts_options
from .video import templates
from .voice import engines

BEAT_KEYS = {"say", "highlight", "image", "zoom", "pause"}
ANIM_KEYS = {"anim", "steps", "args"}


def animation_files(lesson):
    return sorted(lesson.animations_dir.glob("*.py")) if lesson.animations_dir.is_dir() else []


def load_custom_animations(lesson):
    """All public functions of lessons/<id>/animations/*.py, as one namespace."""
    found = {}
    for path in animation_files(lesson):
        spec = importlib.util.spec_from_file_location(f"custom_{lesson.id.replace('-', '_')}_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, obj in vars(module).items():
            if inspect.isfunction(obj) and obj.__module__ == module.__name__ and not name.startswith("_"):
                found[name] = obj
    return SimpleNamespace(**found)


def find_animation(name, custom):
    if custom is not None and hasattr(custom, name):
        return getattr(custom, name)
    if name in templates.TEMPLATES:
        return templates.TEMPLATES[name]
    raise ValueError(f"unknown animation '{name}' (not a template, not a function in the animations files)")


def validate(lesson, settings, slides, coverage=True):
    """Return (errors, warnings) for a list of script slides."""
    lines = load_lines(lesson)
    pages = lines["pages"]
    errors, warnings = [], []
    try:
        custom = load_custom_animations(lesson)
    except Exception as e:  # noqa: BLE001
        custom = None
        errors.append(f"custom animations cannot be imported: {e!r}")

    def check_text(where, text):
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{where}: empty or missing \"say\"")
            return
        if re.search(r"\d", text):
            warnings.append(f"{where}: digits in narration - write numbers as words: {text[:60]!r}")
        if len(text.split()) > 70:
            warnings.append(f"{where}: {len(text.split())} words - split into shorter beats")

    visual = settings["visual"]
    if visual not in VISUAL_MODES:
        errors.append(f"settings.visual must be one of {tuple(VISUAL_MODES)}")
    if settings["depth"] not in DEPTHS:
        errors.append(f"settings.depth must be one of {sorted(DEPTHS)}")
    if not isinstance(settings.get("instructions", ""), str):
        errors.append("settings.instructions must be a text")
    try:
        tts = tts_options()
        errors += [f"settings.tts: {p}" for p in
                   engines.get_engine(tts["engine"]).validate({k: v for k, v in tts.items() if k != "engine"})]
    except SystemExit as e:
        errors.append(f"settings.tts: {e}")

    seen = []
    for s in slides:
        n = s.get("slide") if isinstance(s, dict) else None
        if not isinstance(n, int) or not 1 <= n <= pages:
            errors.append(f"slide entry {str(s)[:60]}: \"slide\" must be a page number 1..{pages}")
            continue
        if n in seen:
            errors.append(f"slide {n}: appears twice")
        seen.append(n)
        beats = s.get("beats")
        if not beats:
            errors.append(f"slide {n}: no beats")
            continue
        data = lines["slides"][str(n)]
        for k, beat in enumerate(beats):
            where = f"slide {n} beat {k}"
            if "anim" in beat and visual == "slides":
                errors.append(f"{where}: visual mode \"slides\" allows no animations")
            if "anim" not in beat and visual == "animated":
                errors.append(f"{where}: visual mode \"animated\" needs an \"anim\" in every beat")
            if "anim" in beat:
                if set(beat) - ANIM_KEYS:
                    errors.append(f"{where}: unknown keys {sorted(set(beat) - ANIM_KEYS)}")
                if not beat.get("steps"):
                    errors.append(f"{where}: animation without \"steps\"")
                for j, st in enumerate(beat.get("steps", [])):
                    check_text(f"{where} step {j}", normalize_step(st).get("say"))
                try:
                    fn = find_animation(beat["anim"], custom)
                    inspect.signature(fn).bind(None, None, **beat.get("args", {}))
                except ValueError as e:
                    errors.append(f"{where}: {e}")
                except TypeError as e:
                    errors.append(f"{where}: wrong args for '{beat['anim']}': {e}")
                continue
            if set(beat) - BEAT_KEYS:
                errors.append(f"{where}: unknown keys {sorted(set(beat) - BEAT_KEYS)}")
            if len([key for key in ("highlight", "image", "zoom") if key in beat]) > 1:
                errors.append(f"{where}: use only one of highlight / image / zoom")
            check_text(where, beat.get("say"))
            try:
                if "highlight" in beat:
                    resolve_highlight(data, beat["highlight"])
                if "image" in beat:
                    resolve_image(data, beat["image"])
            except ValueError as e:
                errors.append(f"{where}: {e}")
    if seen != sorted(seen):
        warnings.append("slides are not in ascending order (the video follows the script order)")
    if coverage:
        in_scope = parse_pages(settings["pages"], range(1, pages + 1))
        missing = sorted(set(in_scope) - set(seen) - set(settings["skip"]))
        if missing:
            warnings.append(f"pages neither narrated nor in settings.skip: {missing}")
    return errors, warnings
