"""Validation of what the agent (or a person) writes: narration pieces, scene code, the whole script.

Used by the agent tools (submissions are checked on the spot), by `./lezio check` and by the scene runner
(scene code is checked again before it runs).
"""
import ast
import re

from .script import normalize_piece
from .settings import DEPTHS, FORMATS, SPEAKERS, STYLES

MAX_WORDS = 70
PIECE_KEYS = {"say", "pause", "speaker"}
SEGMENT_ID = re.compile(r"^s\d{2,3}$")
SYMBOLS = re.compile(r"[()\[\]{}/\\*#_|<>=+~^@%&$€§]")

# ------------------------------------------------------------------ scene code: what it may use
ALLOWED_IMPORTS = {"manim", "numpy", "math", "random", "itertools", "colorsys", "lezio.scene"}
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr",
    "delattr", "input", "breakpoint", "help", "exit", "quit", "memoryview", "__builtins__", "builtins",
    "os", "sys", "subprocess", "socket", "pathlib", "Path", "shutil", "importlib", "ctypes", "signal",
    "threading", "multiprocessing", "config", "ImageMobject", "SVGMobject", "tempconfig",
}
FORBIDDEN_ATTRIBUTES = {
    "add_sound", "renderer", "file_writer", "system", "popen", "spawn", "remove_file", "unlink", "rmtree",
    "load", "loads", "save", "savez", "savez_compressed", "savetxt", "loadtxt", "genfromtxt", "fromfile",
    "tofile", "memmap", "ctypeslib", "os", "sys", "subprocess", "f_globals", "gi_frame", "tb_frame",
}
FORBIDDEN_KEYWORDS = {"file_name", "filename", "code_file", "svg_file", "image_file"}


def check_scene_code(code):
    """Static checks of scene code. Returns a list of problems (empty = fine)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"syntax error at line {e.lineno}: {e.msg}"]
    problems = []

    def bad(node, text):
        problems.append(f"line {getattr(node, 'lineno', '?')}: {text}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS and not alias.name.startswith("lezio.scene."):
                    bad(node, f"import of '{alias.name}' is not allowed (allowed: {', '.join(sorted(ALLOWED_IMPORTS))})")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level or (mod not in ALLOWED_IMPORTS and not mod.startswith("lezio.scene.")):
                bad(node, f"import from '{mod}' is not allowed (allowed: {', '.join(sorted(ALLOWED_IMPORTS))})")
            for alias in node.names:
                if alias.name in FORBIDDEN_NAMES:
                    bad(node, f"'{alias.name}' is not allowed")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            hint = " (use material.page / material.figure)" if node.id in ("ImageMobject", "SVGMobject") else \
                " (use FRAME_WIDTH, FRAME_HEIGHT)" if node.id == "config" else ""
            bad(node, f"'{node.id}' is not allowed{hint}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in FORBIDDEN_ATTRIBUTES:
                hint = " (narration audio is played by steps())" if node.attr == "add_sound" else ""
                bad(node, f"attribute '.{node.attr}' is not allowed{hint}")
        elif isinstance(node, ast.keyword) and node.arg in FORBIDDEN_KEYWORDS:
            bad(node, f"argument '{node.arg}=' is not allowed (no file access)")
        elif isinstance(node, (ast.Global, ast.Nonlocal)) and any(n.startswith("__") for n in node.names):
            bad(node, "dunder names are not allowed")

    problems.sort(key=lambda p: int(p.split(":")[0][5:]) if p[5:].split(":")[0].isdigit() else 0)
    builds = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build"]
    if not builds:
        problems.append("no top-level function `def build(scene, steps, material):`")
    else:
        args = [a.arg for a in builds[0].args.args]
        if args[:3] != ["scene", "steps", "material"]:
            problems.append(f"build must be `def build(scene, steps, material):` (got build({', '.join(args)}))")
    if not problems:
        try:
            compile(tree, "<scene>", "exec")
        except SyntaxError as e:
            problems.append(f"line {e.lineno}: {e.msg}")
    return problems


# ------------------------------------------------------------------ narration
def check_narration(narration, fmt="lecture"):
    """Narration rules. Returns (errors, warnings)."""
    errors, warnings = [], []
    if not isinstance(narration, list) or not narration:
        return ["narration must be a non-empty list of pieces"], []
    speakers = SPEAKERS.get(fmt, ("teacher",))
    used = set()
    for i, raw in enumerate(narration):
        where = f"piece {i}"
        if isinstance(raw, dict):
            unknown = set(raw) - PIECE_KEYS
            if unknown:
                errors.append(f"{where}: unknown keys {sorted(unknown)} (allowed: say, pause, speaker)")
        elif not isinstance(raw, str):
            errors.append(f"{where}: must be a string or {{\"say\": ..., \"pause\": ..., \"speaker\": ...}}")
            continue
        p = normalize_piece(raw)
        text = p["say"]
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{where}: empty \"say\"")
            continue
        if re.search(r"\d", text):
            errors.append(f"{where}: digits in the narration - write numbers as words: {text[:60]!r}")
        sym = sorted(set(SYMBOLS.findall(text)))
        if sym:
            errors.append(f"{where}: symbols {' '.join(sym)} cannot be spoken - write them as words: {text[:60]!r}")
        words = len(text.split())
        if words > MAX_WORDS:
            errors.append(f"{where}: {words} words - split it into pieces of at most {MAX_WORDS} words")
        if not isinstance(p["pause"], (int, float)) or isinstance(p["pause"], bool) or not 0 <= p["pause"] <= 10:
            errors.append(f"{where}: pause must be a number of seconds between 0 and 10")
        if p["speaker"] not in speakers:
            errors.append(f"{where}: speaker '{p['speaker']}' is not allowed in format {fmt} "
                          f"(speakers: {', '.join(speakers)})")
        used.add(p["speaker"])
    if fmt == "dialogue" and not errors and used != set(speakers):
        warnings.append("a dialogue segment should give pieces to both the teacher and the student")
    return errors, warnings


# ------------------------------------------------------------------ the whole script
def check_settings(settings):
    errors = []
    if settings["style"] not in STYLES:
        errors.append(f"settings.style must be one of {', '.join(STYLES)}")
    if settings["format"] not in FORMATS:
        errors.append(f"settings.format must be one of {', '.join(FORMATS)}")
    if settings["depth"] not in DEPTHS:
        errors.append(f"settings.depth must be one of {sorted(DEPTHS)}")
    if not isinstance(settings.get("instructions", ""), str):
        errors.append("settings.instructions must be a text")
    if not isinstance(settings.get("focus", {}), dict):
        errors.append("settings.focus must be an object {\"source path\": \"page range\"}")
    return errors


def check_script(lesson, script, material=None):
    """Return (errors, warnings) for a whole script: settings, segments, narration, scene code, refs."""
    from .material import Material, RefError
    from .script import scene_name
    material = material or Material(lesson)
    errors = check_settings(script["settings"])
    warnings = []
    seen = set()
    for seg in script["segments"]:
        sid = seg.get("id")
        if not isinstance(sid, str) or not SEGMENT_ID.match(sid):
            errors.append(f"segment {str(seg)[:50]}: id must look like s01")
            continue
        if sid in seen:
            errors.append(f"{sid}: id used twice")
        seen.add(sid)
        for ref in seg.get("sources", []):
            try:
                material.resolve(ref)
            except RefError as e:
                errors.append(f"{sid}: sources: {e}")
        if not seg.get("narration"):
            warnings.append(f"{sid}: not written yet")
            continue
        e, w = check_narration(seg["narration"], script["settings"]["format"])
        errors += [f"{sid}: {x}" for x in e]
        warnings += [f"{sid}: {x}" for x in w]
        path = lesson.scene_file(scene_name(seg))
        if not path.exists():
            errors.append(f"{sid}: scene file {path.name} is missing")
        else:
            errors += [f"{sid}: {path.name}: {x}" for x in check_scene_code(path.read_text())]
    return errors, warnings
