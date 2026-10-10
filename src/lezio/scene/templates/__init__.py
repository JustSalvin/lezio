# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Templates: reusable, data-driven scene blocks.

A segment's scene is a list of BLOCKS. Each block is one template filled with data, with its own title and
narration:

    {"template": "bullets", "title": "Le potenze di 2", "args": {"items": ["...", "..."]},
     "say": ["first piece", {"say": "second piece", "pause": 2}]}

The program runs the blocks in order: the title stays while it does not change, the previous block's
content fades out (unless "keep": true), and the template gets the area below the title.

Writing a template (built-in: a module in this package; your own: a file in templates/ at the project
root; the agent's own: lessons/<id>/templates/<name>.py):

    from lezio.scene import *

    @template(category="text", use_for="a single key idea that must stick",
              example={"args": {"text": "Due simboli bastano"}, "say": ["Ecco l'idea chiave."]})
    def big_idea(ctx, steps, text: str):
        '''One big sentence in the middle. Phases: the sentence.'''
        t = steps()                                  # call steps() before adding anything
        line = ctx.place(T(text, 60, PRIMARY, bold=True))
        t.play(Write(line), rt=1.0)

- `ctx` gives the scene, the material, the area to use (ctx.area, ctx.place) and helpers; `steps` are
  the narration pieces of the block (use them all, or let run_phases spread phases over them).
- Arguments are JSON values; annotate them (str, int, float, bool, list[str], list[list[str]],
  list[dict], Literal[...], X | None) so the program can check what the agent passes.
- The docstring and `use_for` are what the agent reads; `example` is shown to it and rendered by
  ./lezio templates --demo <name> (the test of a template).
"""
import ast
import importlib
import importlib.util
import inspect
import pkgutil
import threading
import typing
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ...config import ROOT
from .. import style

USER_TEMPLATES = ROOT / "templates"
CATEGORIES = {"text": "Text and structure", "diagram": "Diagrams and processes", "compare": "Comparing and reasoning",
              "math": "Math, worked examples, tables", "data": "Data and charts", "cs": "Computing",
              "material": "Original pages and figures", "other": "Other"}


@dataclass
class Template:
    name: str
    fn: object
    category: str = "other"
    use_for: str = ""
    example: dict = field(default_factory=dict)
    source: str = "built-in"           # built-in | user | lesson
    doc: str = ""
    params: list = field(default_factory=list)   # [(name, annotation text, has default, default)]


REGISTRY: dict = {}
_loading = {"source": "built-in"}
_loaded = {"done": False}
_LOCK = threading.RLock()


def template(name=None, *, category="other", use_for="", example=None):
    """Register a function (ctx, steps, **args) as a template."""
    def register(fn):
        params = []
        for p in list(inspect.signature(fn).parameters.values())[2:]:
            params.append((p.name, _annotation_text(p.annotation), p.default is not inspect.Parameter.empty,
                           None if p.default is inspect.Parameter.empty else p.default))
        t = Template(name or fn.__name__, fn, category, use_for, example or {}, _loading["source"],
                     inspect.getdoc(fn) or "", params)
        REGISTRY[t.name] = t
        fn.template = t
        return fn
    return register


def _annotation_text(a):
    if a is inspect.Parameter.empty:
        return ""
    if isinstance(a, type):
        return a.__name__
    return str(a).replace("typing.", "")


LOAD_ERRORS: list = []        # (file, error) of template files that could not be loaded


def load_library():
    """Import the built-in template modules and the user's templates/ folder (once). A file that fails is
    reported in LOAD_ERRORS and skipped, so one broken template does not stop the others."""
    with _LOCK:
        if not _loaded["done"]:
            _load_all()
            _loaded["done"] = True
    return REGISTRY


def _load_all():
    for mod in pkgutil.iter_modules(__path__):
        if not mod.name.startswith("_") and mod.name != "kit":
            try:
                importlib.import_module(f"{__name__}.{mod.name}")
            except Exception as e:  # noqa: BLE001
                LOAD_ERRORS.append((f"{mod.name}.py", f"{type(e).__name__}: {e}"))
    if USER_TEMPLATES.is_dir():
        _loading["source"] = "user"
        for path in sorted(USER_TEMPLATES.glob("*.py")):
            try:
                spec = importlib.util.spec_from_file_location(f"lezio_user_templates.{path.stem}", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:  # noqa: BLE001
                LOAD_ERRORS.append((f"templates/{path.name}", f"{type(e).__name__}: {e}"))
        _loading["source"] = "built-in"


def load_lesson_templates(lesson):
    """Execute the agent's templates of a lesson (scene runner only: the code is checked first)."""
    from ...validate import check_scene_code
    _loading["source"] = "lesson"
    try:
        for path in sorted((lesson.dir / "templates").glob("*.py")):
            code = path.read_text()
            problems = check_scene_code(code, entry=path.stem)
            if problems:
                raise ValueError(f"template {path.stem}: " + "; ".join(problems))
            exec(compile(code, str(path), "exec"), {"__name__": f"lezio_lesson_template_{path.stem}"})  # noqa: S102
    finally:
        _loading["source"] = "built-in"


def lesson_template_params(path):
    """Parameters of an agent template read from its source (without running it): [(name, has default)]."""
    tree = ast.parse(path.read_text())
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == path.stem), None)
    if fn is None:
        return None
    args = fn.args.args[2:]
    first_default = len(args) - len(fn.args.defaults)
    params = [(a.arg, ast.unparse(a.annotation) if a.annotation else "", i >= first_default, None)
              for i, a in enumerate(args)]
    params += [(a.arg, ast.unparse(a.annotation) if a.annotation else "", d is not None, None)
               for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults)]
    return params


def lesson_templates(lesson):
    """{name: Template (metadata only)} of the agent's templates of a lesson."""
    out = {}
    for path in sorted((lesson.dir / "templates").glob("*.py")) if (lesson.dir / "templates").is_dir() else []:
        try:
            params = lesson_template_params(path)
        except SyntaxError:
            params = None
        if params is not None:
            doc = ""
            try:
                fn = next(n for n in ast.parse(path.read_text()).body
                          if isinstance(n, ast.FunctionDef) and n.name == path.stem)
                doc = ast.get_docstring(fn) or ""
            except (SyntaxError, StopIteration):
                pass
            out[path.stem] = Template(path.stem, None, "lesson", "", {}, "lesson", doc, params)
    return out


def find(name, lesson=None):
    load_library()
    if name in REGISTRY:
        return REGISTRY[name]
    if lesson is not None:
        return lesson_templates(lesson).get(name)
    return None


# ------------------------------------------------------------------ argument checks
def _type_ok(value, a):
    if a is inspect.Parameter.empty or a is typing.Any:
        return True
    origin = typing.get_origin(a)
    if origin is typing.Union or (origin is not None and str(origin) == "<class 'types.UnionType'>"):
        return any(_type_ok(value, x) for x in typing.get_args(a))
    if a is type(None):
        return value is None
    if origin is typing.Literal:
        return value in typing.get_args(a)
    if a is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if a is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if origin in (list, tuple):
        inner = typing.get_args(a)
        return isinstance(value, list) and (not inner or all(_type_ok(v, inner[0]) for v in value))
    if origin is dict:
        return isinstance(value, dict)
    if isinstance(a, type):
        return isinstance(value, a)
    return True


def check_args(tpl, args):
    """Problems with the args of a block for a template (unknown, missing, wrong type)."""
    if not isinstance(args, dict):
        return ["args must be an object"]
    names = [p[0] for p in tpl.params]
    problems = [f"unknown argument '{k}' (arguments: {', '.join(names) or 'none'})" for k in args if k not in names]
    problems += [f"missing argument '{n}'" for n, _, has_default, _ in tpl.params if not has_default and n not in args]
    if tpl.fn is not None:
        sig = inspect.signature(tpl.fn)
        for k, v in args.items():
            if k in sig.parameters and not _type_ok(v, sig.parameters[k].annotation):
                problems.append(f"argument '{k}' must be {_annotation_text(sig.parameters[k].annotation)}")
    return problems


# ------------------------------------------------------------------ what template code receives
@dataclass
class Area:
    left: float = style.SAFE_LEFT
    right: float = style.SAFE_RIGHT
    bottom: float = style.SAFE_BOTTOM
    top: float = style.SAFE_TOP

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.top - self.bottom

    @property
    def center(self):
        return np.array([(self.left + self.right) / 2, (self.bottom + self.top) / 2, 0])


class Ctx:
    """What a template works with.

    ctx.scene, ctx.material         the Manim scene and the study material (material.page/figure)
    ctx.area                        the free area (below the title, if any): left, right, bottom, top,
                                    width, height, center
    ctx.place(mob, ...)             scale a mobject down to fit the area and position it
    ctx.title                       the title text of the block (None if none)
    """

    def __init__(self, scene, material):
        self.scene, self.material = scene, material
        self.heading, self.title, self.area = None, None, Area()

    def place(self, mob, width=None, height=None, at="center", buff=0.0, grow=1.35):
        """Fit `mob` in the area (at most width x height) and move it to `at`: "center", "top" (centered
        below the title), "left" or "right" (half of the area), or a point. Too large: scaled down; much
        smaller than the area: scaled up (at most `grow` times) so the space is used."""
        w = min(width or self.area.width, self.area.width) - 2 * buff
        h = min(height or self.area.height, self.area.height) - 2 * buff
        style.fit(mob, w, h)
        if grow and mob.width > 0 and mob.height > 0:
            factor = min(0.92 * w / mob.width, 0.85 * h / mob.height, grow)
            if factor > 1.05:
                mob.scale(factor)
        a = self.area
        if isinstance(at, str):
            if at == "top":
                mob.move_to([a.center[0], a.top - buff - mob.height / 2, 0])
            elif at == "left":
                mob.move_to([a.left + a.width / 4, a.center[1], 0])
            elif at == "right":
                mob.move_to([a.right - a.width / 4, a.center[1], 0])
            else:
                mob.move_to(a.center)
        else:
            mob.move_to(at)
        return mob


class BlockSteps:
    """The narration pieces of one block; the first call also plays the transition from the previous block."""

    def __init__(self, part, transition):
        self.part, self.transition, self.started = part, transition, False

    def __len__(self):
        return len(self.part)

    @property
    def left(self):
        return self.part.left

    def __call__(self):
        t = self.part()
        if not self.started:
            self.started = True
            self.transition(t)
        return t

    def take(self, n):
        if not self.started:
            raise RuntimeError("call steps() once before steps.take() in a template")
        return self.part.take(n)

    def finish(self):
        while self.part.left:
            self()


def run_blocks(scene, steps, material, blocks, on_block=None):
    """Play a segment made of template blocks (on_block(k) is called as block k starts)."""
    from manim import FadeIn, FadeOut
    ctx = Ctx(scene, material)
    for k, block in enumerate(blocks):
        if on_block:
            on_block(k)
        tpl = REGISTRY.get(block["template"])
        if tpl is None:
            raise ValueError(f"block {k}: unknown template '{block['template']}'")
        n = len(block["say"])
        title = (block.get("title") or "").strip() or None
        keep = bool(block.get("keep"))
        old_heading = ctx.heading
        outgoing = [] if keep else [m for m in scene.mobjects if m is not old_heading]
        new_heading = None
        if title != ctx.title:
            new_heading = style.heading(title) if title else None
            ctx.heading, ctx.title = new_heading, title
        ctx.area = Area(top=ctx.heading.get_bottom()[1] - 0.45) if ctx.heading is not None else Area()

        def transition(t, outgoing=outgoing, old=old_heading, new=new_heading, changed=new_heading is not None
                       or (title is None and old_heading is not None)):
            anims = [FadeOut(m) for m in outgoing]
            if changed and old is not None:
                anims.append(FadeOut(old))
            if new is not None:
                anims.append(FadeIn(new, shift=0.15 * np.array([0, -1, 0])))
            if anims:
                t.play(*anims, rt=0.5)
            for m in outgoing + ([old] if changed and old is not None else []):
                scene.remove(m)

        if title is None:
            ctx.heading = None
        part = BlockSteps(steps.take(n), transition)
        tpl.fn(ctx, part, **(block.get("args") or {}))
        part.finish()


# ------------------------------------------------------------------ the catalog the agent reads
def catalog(lesson=None, full=True):
    load_library()
    items = dict(REGISTRY)
    if lesson is not None:
        items.update({k: v for k, v in lesson_templates(lesson).items() if k not in items})
    out = []
    for cat, label in CATEGORIES.items():
        group = [t for t in items.values() if t.category == cat]
        if not group:
            continue
        out.append(f"## {label}")
        for t in group:
            args = ", ".join(f"{n}: {a}" + (f" = {d!r}" if has else "") if a else n + (f" = {d!r}" if has else "")
                             for n, a, has, d in t.params)
            src = "" if t.source == "built-in" else f"   [{t.source} template]"
            out.append(f"- {t.name}({args}){src}")
            if t.use_for:
                out.append(f"    use for: {t.use_for}")
            if full and t.doc:
                out.append("    " + t.doc.replace("\n", "\n    "))
            if full and t.example:
                import json
                ex = {"template": t.name, **{k: v for k, v in t.example.items() if k in ("title", "args")},
                      "say": [f"<{len(t.example.get('say', []))} pieces>"]}
                out.append("    example: " + json.dumps(ex, ensure_ascii=False))
    return "\n".join(out)
