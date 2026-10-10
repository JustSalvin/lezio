# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Validation of what the agent (or a person) writes: narration pieces, scene code, the whole script.

Used by the agent tools (submissions are checked on the spot), by `./lezio tools check` and by the scene runner
(scene code is checked again before it runs).
"""
import ast
import re

from .script import normalize_piece
from .settings import DEPTHS

MAX_WORDS = 70
PIECE_KEYS = {"say", "pause"}
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


def check_scene_code(code, entry="build"):
    """Static checks of scene code (entry "build") or of a template (entry = the template name).
    Returns a list of problems (empty = fine)."""
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
    found = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == entry]
    if entry == "build":
        if not found:
            problems.append("no top-level function `def build(scene, steps, material):`")
        else:
            args = [a.arg for a in found[0].args.args]
            if args[:3] != ["scene", "steps", "material"]:
                problems.append(f"build must be `def build(scene, steps, material):` (got build({', '.join(args)}))")
    elif not found:
        problems.append(f"no top-level function `def {entry}(ctx, steps, ...)` decorated with @template(...)")
    else:
        fn = found[0]
        if [a.arg for a in fn.args.args][:2] != ["ctx", "steps"]:
            problems.append(f"the template must be `def {entry}(ctx, steps, ...)`")
        if not any((isinstance(d, ast.Call) and getattr(d.func, "id", "") == "template")
                   or (isinstance(d, ast.Name) and d.id == "template") for d in fn.decorator_list):
            problems.append(f"{entry} must be decorated with @template(...)")
    if not problems:
        try:
            compile(tree, "<scene>", "exec")
        except SyntaxError as e:
            problems.append(f"line {e.lineno}: {e.msg}")
    return problems


HEX_COLOR = re.compile(r"""["']#[0-9a-fA-F]{6}["']""")


def scene_code_warnings(code):
    """Advice on scene code that works but does not follow the house style."""
    if HEX_COLOR.search(code):
        return ["the code uses fixed colors (#rrggbb): use the theme colors (PRIMARY, HIGHLIGHT, ...) so that the "
                "lesson follows the house style"]
    return []


# ------------------------------------------------------------------ narration
def check_narration(narration):
    """Narration rules. Returns (errors, warnings)."""
    errors, warnings = [], []
    if not isinstance(narration, list) or not narration:
        return ["narration must be a non-empty list of pieces"], []
    for i, raw in enumerate(narration):
        where = f"piece {i}"
        if isinstance(raw, dict):
            unknown = set(raw) - PIECE_KEYS
            if unknown:
                errors.append(f"{where}: unknown keys {sorted(unknown)} (allowed: say, pause)")
        elif not isinstance(raw, str):
            errors.append(f"{where}: must be a string or {{\"say\": ..., \"pause\": ...}}")
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
    return errors, warnings


# ------------------------------------------------------------------ template blocks
BLOCK_KEYS = {"template", "title", "args", "say", "keep"}


def check_blocks(blocks, lesson=None):
    """Template blocks of a segment. Returns (errors, warnings)."""
    from .scene import templates
    if not isinstance(blocks, list) or not blocks:
        return ["blocks must be a non-empty list"], []
    errors, warnings = [], []
    for k, b in enumerate(blocks):
        where = f"block {k}"
        if not isinstance(b, dict):
            errors.append(f"{where}: must be an object {{\"template\", \"title\", \"args\", \"say\"}}")
            continue
        unknown = set(b) - BLOCK_KEYS
        if unknown:
            errors.append(f"{where}: unknown keys {sorted(unknown)} (allowed: {', '.join(sorted(BLOCK_KEYS))})")
        name = b.get("template")
        tpl = templates.find(name, lesson) if isinstance(name, str) else None
        if tpl is None:
            errors.append(f"{where}: unknown template {name!r}")
        else:
            errors += [f"{where} ({name}): {p}" for p in templates.check_args(tpl, b.get("args", {}))]
        if b.get("title") is not None and not isinstance(b.get("title"), str):
            errors.append(f"{where}: title must be a text")
        if not b.get("say"):
            errors.append(f"{where}: \"say\" must list the narration pieces of the block (at least one)")
        else:
            e, w = check_narration(b["say"])
            errors += [f"{where} {x}" for x in e]
            warnings += [f"{where} {x}" for x in w]
    return errors, warnings


# ------------------------------------------------------------------ the whole script
def check_settings(settings):
    errors = []
    if settings["depth"] not in DEPTHS:
        errors.append(f"settings.depth must be one of {sorted(DEPTHS)}")
    if not isinstance(settings.get("instructions", ""), str):
        errors.append("settings.instructions must be a text")
    if not isinstance(settings.get("focus", {}), dict):
        errors.append("settings.focus must be an object {\"source path\": \"page range\"}")
    return errors


def check_script(lesson, script, material=None):
    """Return (errors, warnings) for a whole script: settings, segments, blocks, narration, scene code, refs."""
    from .material import Material, RefError
    from .script import scene_name
    material = material or Material(lesson)
    errors = check_settings(script["settings"])
    warnings = []
    for path in sorted(lesson.templates.glob("*.py")) if lesson.templates.is_dir() else []:
        errors += [f"template {path.stem}: {p}" for p in check_scene_code(path.read_text(), entry=path.stem)]
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
        if seg.get("blocks"):
            e, w = check_blocks(seg["blocks"], lesson)
            errors += [f"{sid}: {x}" for x in e]
            warnings += [f"{sid}: {x}" for x in w]
            continue
        if not seg.get("narration"):
            warnings.append(f"{sid}: not written yet")
            continue
        e, w = check_narration(seg["narration"])
        errors += [f"{sid}: {x}" for x in e]
        warnings += [f"{sid}: {x}" for x in w]
        path = lesson.scene_file(scene_name(seg))
        if not path.exists():
            errors.append(f"{sid}: scene file {path.name} is missing")
        else:
            errors += [f"{sid}: {path.name}: {x}" for x in check_scene_code(path.read_text())]
    return errors, warnings
