# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Data and charts: function_plot, bar_chart, line_chart."""
import ast
import math as pymath
import operator

import numpy as np
from manim import (DOWN, LEFT, RIGHT, UP, Axes, Create, DashedLine, Dot, FadeIn, GrowFromCenter, GrowFromEdge,
                   LaggedStart, Line, Rectangle, VGroup, VMobject)

from .. import style
from ..style import T
from . import template
from .kit import run_phases, text_box
from .math import decimals_for, family, fmt_number, formula, on_baseline, pace

SERIES = ("primary", "secondary", "positive", "negative", "neutral")      # fixed order of series colors


# ------------------------------------------------------------------ safe expressions of x
_FUNCS = {"sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "ln": np.log,
          "sqrt": np.sqrt, "abs": np.abs}
_CONSTS = {"pi": np.pi, "e": np.e}
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow}
_ALLOWED = "numbers, x, + - * / ** (or ^), parentheses, sin cos tan exp log sqrt abs, pi and e"


def parse_expr(expr):
    """The syntax tree of an expression of x, checked: only the allowed elements (never eval/exec)."""
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("empty expression")
    if len(expr) > 200:
        raise ValueError(f"expression too long ({len(expr)} characters, at most 200)")
    src = expr.replace("^", "**").replace("−", "-").replace("·", "*").replace("×", "*").replace("÷", "/")
    try:
        tree = ast.parse(src.strip(), mode="eval")
    except SyntaxError:
        raise ValueError(f"cannot read the expression {expr!r}: write it like 0.5*x**2 - 3*x + 1 "
                         f"(* for every product, . for decimals; allowed: {_ALLOWED})") from None

    def check(node):
        if isinstance(node, ast.Expression):
            return check(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError(f"{expr!r}: {node.value!r} is not a number")
            return
        if isinstance(node, ast.Name):
            if node.id != "x" and node.id not in _CONSTS:
                raise ValueError(f"{expr!r}: unknown name {node.id!r} (allowed: {_ALLOWED})")
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return check(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            check(node.left)
            return check(node.right)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS
                and len(node.args) == 1 and not node.keywords):
            return check(node.args[0])
        raise ValueError(f"{expr!r}: {ast.unparse(node)!r} is not allowed (allowed: {_ALLOWED})")

    check(tree)
    return tree


def compile_expr(expr):
    """A function f(x) (numpy arrays in, arrays out) of a checked expression. Invalid values become nan."""
    tree = parse_expr(expr)

    def build(node):
        if isinstance(node, ast.Expression):
            return build(node.body)
        if isinstance(node, ast.Constant):
            v = np.float64(node.value)
            return lambda x: v
        if isinstance(node, ast.Name):
            if node.id == "x":
                return lambda x: x
            v = np.float64(_CONSTS[node.id])
            return lambda x: v
        if isinstance(node, ast.UnaryOp):
            f = build(node.operand)
            return (lambda x: -f(x)) if isinstance(node.op, ast.USub) else f
        if isinstance(node, ast.BinOp):
            a, b, op = build(node.left), build(node.right), _OPS[type(node.op)]
            return lambda x: op(a(x), b(x))
        f, g = build(node.args[0]), _FUNCS[node.func.id]
        return lambda x: g(f(x))

    fn = build(tree)

    def evaluate(xs):
        xs = np.asarray(xs, dtype=float)
        with np.errstate(all="ignore"):
            ys = np.broadcast_to(np.asarray(fn(xs), dtype=float), xs.shape).copy()
        ys[~np.isfinite(ys)] = np.nan
        return ys

    return evaluate


def pretty_expr(expr):
    """An expression as Pango markup for a label: x**2 - 1 -> x<sup>2</sup> − 1, 2*x -> 2x, sqrt(x) -> √x."""
    def p(node):                                            # (markup, precedence)
        if isinstance(node, ast.Expression):
            return p(node.body)
        if isinstance(node, ast.Constant):
            return fmt_number(node.value), 5
        if isinstance(node, ast.Name):
            return {"x": "x", "pi": "π", "e": "e"}[node.id], 5
        if isinstance(node, ast.UnaryOp):
            m, k = p(node.operand)
            return ("−" if isinstance(node.op, ast.USub) else "") + (f"({m})" if k < 3 else m), 3
        if isinstance(node, ast.Call):
            m, k = p(node.args[0])
            name = node.func.id
            if name == "sqrt":
                return "√" + (m if k >= 5 else f"({m})"), 5
            if name == "abs":
                return f"|{m}|", 5
            if name == "exp":
                return f"e<sup>{m}</sup>", 4
            return f"{'ln' if name in ('log', 'ln') else name}({m})", 5
        a, ka = p(node.left)
        b, kb = p(node.right)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if isinstance(node.op, ast.Sub) and kb <= 1:
                b = f"({b})"
            return f"{a} {'+' if isinstance(node.op, ast.Add) else '−'} {b}", 1
        if isinstance(node.op, (ast.Mult, ast.Div)):
            a = f"({a})" if ka < 2 else a
            b = f"({b})" if kb < (3 if isinstance(node.op, ast.Div) else 2) else b
            if isinstance(node.op, ast.Mult):
                juxtapose = isinstance(node.left, ast.Constant) and not b[:1].isdigit() and not b.startswith("−")
                return (f"{a}{b}" if juxtapose else f"{a} · {b}"), 2
            return f"{a} / {b}", 2
        a = f"({a})" if ka < 5 else a                     # power
        return f"{a}<sup>{b}</sup>", 4

    return p(parse_expr(expr))[0]


# ------------------------------------------------------------------ helpers
def nice_ticks(lo, hi, target=5):
    """Round tick values covering [lo, hi] (about `target` intervals)."""
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / target
    mag = 10 ** pymath.floor(pymath.log10(raw))
    step = min((m * mag for m in (0.5, 1, 2, 5, 10)), key=lambda st: abs((hi - lo) / st - target))
    start, end = pymath.floor(lo / step + 1e-9) * step, pymath.ceil(hi / step - 1e-9) * step
    n = int(round((end - start) / step))
    return [round(start + k * step, 10) for k in range(n + 1)], step


def _overlaps(a, b, pad=0.08):
    """Boxes (x0, y0, x1, y1) overlap."""
    return a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad


def _box(m):
    return (m.get_left()[0], m.get_bottom()[1], m.get_right()[0], m.get_top()[1])


def _hits(box, pts, pad=0.06):
    """How many of the points (n x 2 array) fall inside the box."""
    if pts is None or not len(pts):
        return 0
    x0, y0, x1, y1 = box
    inside = (pts[:, 0] > x0 - pad) & (pts[:, 0] < x1 + pad) & (pts[:, 1] > y0 - pad) & (pts[:, 1] < y1 + pad)
    return int(np.sum(inside))


def _score(lab, window, taken, pts):
    """How badly a label sits: points of lines it covers; 1000 more if it leaves the window or covers a label."""
    b = _box(lab)
    outside = not (b[0] >= window[0] and b[2] <= window[2] and b[1] >= window[1] and b[3] <= window[3])
    return _hits(b, pts) + 1000 * outside + 1000 * sum(_overlaps(b, t) for t in taken)


AROUND = [(1, 1), (-1, 1), (1, -1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)]


def _place_label(lab, anchors, offsets, window, taken, pts):
    """Move `lab` next to the first anchor (and offset) where it stays in `window`, clear of the `taken` boxes and
    of the points `pts`; if there is no such place, where it covers least. Returns True if the place is free."""
    best = None
    for a in anchors:
        for far in (1.0, 1.8):
            for dx, dy in offsets:
                c = np.array([a[0] + dx * (lab.width / 2 + 0.18 * far), a[1] + dy * (lab.height / 2 + 0.16 * far), 0])
                score = _score(lab.move_to(c), window, taken, pts)
                if score == 0:
                    return True
                if best is None or score < best[0]:
                    best = (score, c)
    lab.move_to(best[1])
    return False


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and pymath.isfinite(v)


def _with_unit(text, unit):
    return text if not unit else text + ("" if unit in ("%", "‰", "°") else " ") + unit


def _runs(xs, ys, lo, hi):
    """Pieces of a sampled curve that lie in [lo, hi] (clipped at the edges, broken at gaps and jumps)."""
    runs, cur, span = [], [], hi - lo
    inside = np.isfinite(ys) & (ys >= lo) & (ys <= hi)
    for i in range(len(xs)):
        if i > 0:
            y0, y1 = ys[i - 1], ys[i]
            finite = np.isfinite(y0) and np.isfinite(y1)
            jump = finite and abs(y1 - y0) > 0.5 * span
            if finite and not jump and inside[i - 1] != inside[i]:        # crossing an edge: add the edge point
                edge = hi if max(y0, y1) > hi else lo
                t = (edge - y0) / (y1 - y0) if y1 != y0 else 0
                p = (xs[i - 1] + t * (xs[i] - xs[i - 1]), edge)
                if inside[i - 1]:
                    cur.append(p)
                else:
                    cur = [p]
            if jump and cur:
                runs.append(cur)
                cur = []
        if inside[i]:
            cur.append((xs[i], ys[i]))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [r for r in runs if len(r) > 1]


@template(category="data", use_for="the graph of one or more functions y = f(x): shape, zeros, intersections, growth, "
          "comparing functions; one curve per piece, then the notable points",
          example={"title": "Una parabola e una retta",
                   "args": {"functions": [{"expr": "x**2 - 1"}, {"expr": "2*x + 2"}], "x_range": [-3, 4],
                            "y_range": [-3, 10],
                            "points": [{"x": -1, "label": "(−1, 0)"}, {"x": 3, "label": "(3, 8)"}]},
                   "say": ["Ecco la parabola y uguale x al quadrato meno uno.", "E la retta y uguale due x più due.",
                           "Si incontrano in due punti: il primo ha x uguale a meno uno,",
                           "il secondo ha x uguale a tre."]})
def function_plot(ctx, steps, functions: list[dict], x_range: list[float], y_range: list[float] | None = None,
                  points: list[dict] | None = None, x_label: str = "x", y_label: str = "y"):
    """Cartesian axes with 1-4 function graphs and up to 6 marked points.
    functions: [{"expr": "x**2 - 1", "label": optional markup (default "y = x<sup>2</sup> − 1"), "color":
    optional primary|secondary|positive|negative|neutral}]; expr uses x, numbers (decimal point), + - * / **,
    parentheses, sin cos tan exp log (natural) sqrt abs, pi, e - write every product with * (2*x).
    x_range: [min, max] or [min, max, tick step]; y_range: the same, or null to fit the curves.
    points: [{"x": 3, "y": optional (default: on function "of", 0-based, default 0), "label": optional markup,
    "guides": true (dashed lines to the axes)}]. Each curve is labeled directly next to it.
    Phases: axes and the first curve, one per further curve, one per point."""
    if not 1 <= len(functions) <= 4:
        raise ValueError(f"function_plot: {len(functions)} functions (between 1 and 4)")
    if len(x_range) not in (2, 3) or not all(_number(v) for v in x_range) or not x_range[1] > x_range[0]:
        raise ValueError(f"function_plot: x_range must be [min, max] or [min, max, step] with min < max, not {x_range}")
    if y_range is not None and (len(y_range) not in (2, 3) or not all(_number(v) for v in y_range)
                                or not y_range[1] > y_range[0]):
        raise ValueError(f"function_plot: y_range must be [min, max] or [min, max, step] with min < max, not {y_range}")
    points = list(points or [])
    if len(points) > 6:
        raise ValueError(f"function_plot: {len(points)} points (at most 6)")
    fns = []
    for k, f in enumerate(functions):
        if not isinstance(f, dict) or not isinstance(f.get("expr"), str):
            raise ValueError(f"function_plot: function {k} must be {{\"expr\": \"x**2 - 1\", \"label\": ...}}")
        try:
            fns.append(compile_expr(f["expr"]))
        except ValueError as e:
            raise ValueError(f"function_plot: function {k}: {e}") from None
    xmin, xmax = float(x_range[0]), float(x_range[1])
    xs = np.linspace(xmin, xmax, 801)
    ys_all = [fn(xs) for fn in fns]
    finite = [y[np.isfinite(y)] for y in ys_all]
    if not any(len(v) for v in finite):
        raise ValueError(f"function_plot: no function has values for x between {xmin:g} and {xmax:g}")
    if y_range is not None:
        ymin, ymax = float(y_range[0]), float(y_range[1])
    else:
        vals = np.concatenate([v for v in finite if len(v)])
        lo, hi = float(vals.min()), float(vals.max())
        plo, phi = (float(v) for v in np.percentile(vals, [4, 96]))
        if hi - lo > 4 * max(phi - plo, 1e-9):             # vertical asymptotes: keep the bulk of the curve
            lo, hi = plo, phi
        if hi - lo < 1e-9:
            lo, hi = lo - 1, hi + 1
        pad = 0.06 * (hi - lo)
        lo = max(lo - pad, 0.0) if lo >= 0 else lo - pad            # do not invent negative values (or positive)
        hi = min(hi + pad, 0.0) if hi <= 0 else hi + pad
        ticks, _ = nice_ticks(lo, hi, 6)
        ymin, ymax = ticks[0], ticks[-1]
    x_step = float(x_range[2]) if len(x_range) == 3 and x_range[2] > 0 else nice_ticks(xmin, xmax, 8)[1]
    y_step = float(y_range[2]) if y_range is not None and len(y_range) == 3 and y_range[2] > 0 \
        else nice_ticks(ymin, ymax, 6)[1]

    def tick_values(lo, hi, step):
        k0, k1 = pymath.ceil(lo / step - 1e-9), pymath.floor(hi / step + 1e-9)
        if k1 - k0 > 60:
            raise ValueError(f"function_plot: a tick step of {step:g} gives too many ticks")
        return [round(k * step, 10) for k in range(k0, k1 + 1)]

    xt, yt = tick_values(xmin, xmax, x_step), tick_values(ymin, ymax, y_step)
    size = style.SMALL_SIZE + 2
    x_labs = {v: T(fmt_number(v), size, style.MUTED) for v in xt}
    y_labs = {v: T(fmt_number(v), size, style.MUTED) for v in yt}
    ax_x = formula(f"<i>{x_label}</i>", style.TEXT_SIZE - 4, style.TEXT)
    ax_y = formula(f"<i>{y_label}</i>", style.TEXT_SIZE - 4, style.TEXT)
    W, H, ext = ctx.area.width, ctx.area.height, 0.05
    # the axes cross at 0, or at the left / bottom edge when 0 is out of range
    fx = (0 - xmin) / (xmax - xmin) if xmin < 0 < xmax else 0.0
    fy = (0 - ymin) / (ymax - ymin) if ymin < 0 < ymax else 0.0
    ylw = max(m.width for m in y_labs.values())
    xlh = max(m.height for m in x_labs.values())
    margin_l = margin_b = 0.1
    for _ in range(3):                                      # tick labels must fit beside the axes
        Lx = (W - margin_l - ax_x.width - 0.35) / (1 + ext)
        Ly = (H - margin_b - ax_y.height - 0.3) / (1 + ext)
        margin_l = max(0.1, ylw + 0.3 - fx * Lx)
        margin_b = max(0.1, xlh + 0.3 - fy * Ly)
    axes = Axes(x_range=[xmin, xmax + ext * (xmax - xmin), xmax - xmin],
                y_range=[ymin, ymax + ext * (ymax - ymin), ymax - ymin],
                x_length=Lx * (1 + ext), y_length=Ly * (1 + ext), tips=True,
                axis_config={"color": style.MUTED, "stroke_width": 3, "include_ticks": False,
                             "include_numbers": False, "tip_width": 0.2, "tip_height": 0.2})
    axes.move_to([ctx.area.left + margin_l + Lx * (1 + ext) / 2,
                  ctx.area.bottom + margin_b + Ly * (1 + ext) / 2, 0])
    X0, Y0 = axes.c2p(xmin, ymin)[:2]
    X1, Y1 = axes.c2p(xmax, ymax)[:2]
    to_scene = lambda x, y: np.column_stack([X0 + (np.asarray(x) - xmin) / (xmax - xmin) * (X1 - X0),  # noqa: E731
                                             Y0 + (np.asarray(y) - ymin) / (ymax - ymin) * (Y1 - Y0)])
    window = (X0, Y0, X1, Y1)
    if xmax <= 0:                                          # Manim puts the axis at the right end: move it left
        axes.y_axis.shift(RIGHT * (X0 - axes.y_axis.get_center()[0]))
    if ymax <= 0:
        axes.x_axis.shift(UP * (Y0 - axes.x_axis.get_center()[1]))
    cross_x, cross_y = axes.y_axis.get_center()[0], axes.x_axis.get_center()[1]
    # ticks, tick labels (thinned when crowded; none where they would sit on the other axis), grid
    ticks, labels, grid = VGroup(), VGroup(), VGroup()
    y_axis_below, x_axis_beside = cross_y > Y0 + 0.01, cross_x > X0 + 0.01
    sx = (X1 - X0) / max(len(xt) - 1, 1)
    xlw = max(m.width for m in x_labs.values())
    every_x = next(k for k in (1, 2, 4, 5, 10, 20, 50) if xlw + 0.3 <= k * sx or k == 50)
    sy = (Y1 - Y0) / max(len(yt) - 1, 1)
    every_y = next(k for k in (1, 2, 4, 5, 10, 20, 50) if xlh + 0.2 <= k * sy or k == 50)
    for v in xt:
        x = to_scene([v], [ymin])[0][0]
        on_axis = abs(x - cross_x) < 1e-6
        if not on_axis:
            grid.add(Line([x, Y0, 0], [x, Y1, 0], color=style.MUTED, stroke_width=1.5, stroke_opacity=0.22))
            ticks.add(Line([x, cross_y - 0.08, 0], [x, cross_y + 0.08, 0], color=style.MUTED, stroke_width=2.5))
        if round(v / x_step) % every_x == 0 and not (on_axis and y_axis_below):
            labels.add(x_labs[v].move_to([x, cross_y - 0.18 - x_labs[v].height / 2, 0]))
    for v in yt:
        y = to_scene([xmin], [v])[0][1]
        on_axis = abs(y - cross_y) < 1e-6
        if not on_axis:
            grid.add(Line([X0, y, 0], [X1, y, 0], color=style.MUTED, stroke_width=1.5, stroke_opacity=0.22))
            ticks.add(Line([cross_x - 0.08, y, 0], [cross_x + 0.08, y, 0], color=style.MUTED, stroke_width=2.5))
        if round(v / y_step) % every_y == 0 and not (on_axis and x_axis_beside):
            labels.add(y_labs[v].move_to([cross_x - 0.18 - y_labs[v].width / 2, y, 0]))
    ax_x.next_to(axes.x_axis.get_right(), RIGHT, buff=0.15)
    ax_y.next_to(axes.y_axis.get_top(), UP, buff=0.1)
    frame_mobs = VGroup(grid, axes, ticks, labels, ax_x, ax_y)
    # the curves
    obstacles = [np.column_stack([np.linspace(X0, X1, 120), np.full(120, cross_y)]),
                 np.column_stack([np.full(120, cross_x), np.linspace(Y0, Y1, 120)])]
    curves, curve_pts = [], []
    for k, (f, ys) in enumerate(zip(functions, ys_all)):
        color = family(f.get("color"), SERIES[k])[0]
        runs = _runs(xs, ys, ymin, ymax)
        if not runs:
            raise ValueError(f"function_plot: function {k} ({f['expr']}) is outside the y range "
                             f"[{ymin:g}, {ymax:g}] for every x in [{xmin:g}, {xmax:g}]")
        group = VGroup()
        pts = []
        for r in runs:
            sc = to_scene([q[0] for q in r], [q[1] for q in r])
            pts.append(sc)
            group.add(VMobject().set_points_as_corners(np.column_stack([sc, np.zeros(len(sc))]))
                      .set_stroke(color, 6))
        curves.append(group.set_z_index(1))
        curve_pts.append(np.concatenate(pts))
    # the points and their guides (before the labels, which must avoid them)
    marks, centers = [], []
    for k, p in enumerate(points):
        if not isinstance(p, dict) or not _number(p.get("x")):
            raise ValueError(f"function_plot: point {k} must be {{\"x\": number, \"y\": optional, \"label\": ...}}")
        x = float(p["x"])
        if p.get("y") is not None:
            if not _number(p["y"]):
                raise ValueError(f"function_plot: point {k}: y must be a number")
            y = float(p["y"])
        else:
            of = p.get("of", 0)
            if not isinstance(of, int) or not 0 <= of < len(fns):
                raise ValueError(f"function_plot: point {k}: \"of\" must be a function index (0-{len(fns) - 1})")
            y = float(fns[of](np.array([x]))[0])
        if not (xmin <= x <= xmax and np.isfinite(y) and ymin <= y <= ymax):
            raise ValueError(f"function_plot: point {k} ({x:g}, {y:g}) is outside the plot")
        c = to_scene([x], [y])[0]
        centers.append(c)
        dot = Dot([c[0], c[1], 0], radius=0.12, color=style.TEXT).set_stroke(style.BACKGROUND, 3).set_z_index(4)
        guides = VGroup()
        if p.get("guides", True):
            if abs(c[1] - cross_y) > 0.2:
                guides.add(DashedLine([c[0], c[1], 0], [c[0], cross_y, 0], color=style.MUTED, stroke_width=2.5))
                obstacles.append(np.column_stack([np.full(40, c[0]), np.linspace(c[1], cross_y, 40)]))
            if abs(c[0] - cross_x) > 0.2:
                guides.add(DashedLine([c[0], c[1], 0], [cross_x, c[1], 0], color=style.MUTED, stroke_width=2.5))
                obstacles.append(np.column_stack([np.linspace(c[0], cross_x, 40), np.full(40, c[1])]))
        lab = formula(str(p["label"]), style.TEXT_SIZE - 4, style.TEXT, bold=True) \
            if str(p.get("label") or "").strip() else None
        marks.append([dot, guides, lab])
    dots = np.array(centers) if centers else np.zeros((0, 2))
    halo = lambda m: m.set_stroke(style.BACKGROUND, 8, background=True)         # noqa: E731 - readable over lines
    for m in labels:
        halo(m).set_z_index(2)
    taken = [_box(m) for m in labels] + [_box(ax_x), _box(ax_y)]
    # each curve labeled directly, near its right end if there is room
    curve_labels = []
    for k, f in enumerate(functions):
        color = family(f.get("color"), SERIES[k])[0]
        text = f.get("label") or f"{y_label} = {pretty_expr(f['expr'])}"
        lab = halo(formula(str(text), style.TEXT_SIZE - 2, color, bold=True)).set_z_index(3)
        pts = curve_pts[k]
        order = np.argsort(-pts[:, 0])                            # from the right end of the curve leftwards
        anchors = [pts[order[int(q * (len(order) - 1))]] for q in (0.03, 0.1, 0.2, 0.3, 0.42, 0.55, 0.7, 0.85)]
        avoid = np.concatenate(curve_pts + obstacles + [np.repeat(dots, 30, axis=0)])
        _place_label(lab, anchors, AROUND[:4], window, taken, avoid)
        taken.append(_box(lab))
        curve_labels.append(lab)
    avoid = np.concatenate(curve_pts + obstacles)
    for c, mark in zip(centers, marks):
        if mark[2] is not None:
            halo(mark[2]).set_z_index(3)
            _place_label(mark[2], [c], AROUND, window, taken, avoid)
            taken.append(_box(mark[2]))
    ctx.place(VGroup(frame_mobs, *curves, *curve_labels, *[VGroup(d, g, *([lb] if lb else [])) for d, g, lb in marks]),
              grow=1.0)

    def p_curve(k):
        def run(t):
            f = pace(t, 3.1 if k == 0 else 1.9)
            if k == 0:
                t.play(FadeIn(grid), Create(axes), FadeIn(ticks), rt=0.8 * f)
                t.play(FadeIn(labels), FadeIn(ax_x), FadeIn(ax_y), rt=0.4 * f)
            t.play(Create(curves[k], lag_ratio=1 if len(curves[k]) > 1 else 0), rt=1.5 * f)
            t.play(FadeIn(curve_labels[k], shift=UP * 0.1), rt=0.4 * f)
        return run

    def p_point(dot, guides, lab):
        def run(t):
            t.play(GrowFromCenter(dot), *[Create(g) for g in guides], rt=0.6)
            if lab is not None:
                t.play(FadeIn(lab, shift=UP * 0.1), rt=0.4)
        return run

    run_phases(steps, [p_curve(k) for k in range(len(curves))] + [p_point(*m) for m in marks])


@template(category="data", use_for="comparing amounts across a few categories (discrete values): bars growing one "
          "per piece or all together, values written on the bars, then one bar highlighted",
          example={"title": "Le città più popolose", "args": {
              "labels": ["Roma", "Milano", "Napoli", "Torino"], "values": [2.75, 1.37, 0.91, 0.84],
              "unit": "milioni di abitanti", "highlight": 0},
                   "say": ["Roma supera i due milioni e mezzo di abitanti.",
                           "Milano ne ha poco meno di un milione e mezzo.",
                           "Napoli poco più di novecentomila.", "Torino un po' meno.",
                           "Roma ha quasi il doppio degli abitanti di Milano."]})
def bar_chart(ctx, steps, labels: list[str], values: list[float], unit: str | None = None,
              highlight: int | None = None, together: bool = False):
    """Bars for 1-15 categories, with the value written on each bar (no axis needed). Few short labels: vertical
    bars; many or long labels: horizontal bars. Negative values grow the other way. unit: a short unit
    (%, °C, kg) is written after each value, a longer one ("milioni di abitanti") once above the chart.
    highlight: index (0-based) of a bar to bring out at the end, the others dimmed. together: all bars grow in
    one phase instead of one per phase.
    Phases: one per bar (or: all bars), then the highlight."""
    n = len(labels)
    if not 1 <= n <= 15:
        raise ValueError(f"bar_chart: {n} bars (between 1 and 15)")
    if len(values) != n or not all(_number(v) for v in values):
        raise ValueError(f"bar_chart: give one number per label ({n} labels, {len(values)} values)")
    if highlight is not None and not 0 <= highlight < n:
        raise ValueError(f"bar_chart: highlight must be a bar index from 0 to {n - 1}")
    unit = (unit or "").strip()
    short_unit = unit if len(unit) <= 3 else ""
    dec = decimals_for(values)
    W, H = ctx.area.width, ctx.area.height
    caption = text_box(unit, W * 0.8, style.SMALL_SIZE + 2, style.MUTED) if unit and not short_unit else None
    top_room = (caption.height + 0.3) if caption is not None else 0
    lab_size, val_size = style.SMALL_SIZE + 4, style.TEXT_SIZE - 2
    vals = [T(_with_unit(fmt_number(v, dec), short_unit), val_size, style.TEXT, bold=True) for v in values]
    lo, hi = min(0.0, min(values)), max(0.0, max(values))
    if hi == lo:
        hi = lo + 1
    slot = W / n
    names = [text_box(str(x), slot - 0.2, lab_size, style.TEXT, align="center") for x in labels]
    line_h = T("Ag", lab_size).height
    vertical = n <= 8 and all(m.height < 2.6 * line_h for m in names) and max(m.width for m in vals) < slot - 0.1
    bars, grow_dirs = [], []
    if vertical:
        name_h = max(m.height for m in names)
        val_room = vals[0].height + 0.25
        plot_h = H - top_room - name_h - 0.3 - val_room * ((hi > 0) + (lo < 0))
        scale = plot_h / (hi - lo)
        y_base = ctx.area.bottom + name_h + 0.3 + (val_room if lo < 0 else 0) + (0 - lo) * scale
        cap_h = T("H", lab_size).height
        bar_w = min(0.62 * slot, 1.8)
        for k, v in enumerate(values):
            x = ctx.area.left + slot * (k + 0.5)
            h = max(abs(v) * scale, 0.02)
            bar = Rectangle(width=bar_w, height=h, stroke_width=0, fill_color=style.PRIMARY, fill_opacity=1)
            bar.move_to([x, y_base + (h / 2 if v >= 0 else -h / 2), 0])
            bars.append(bar)
            grow_dirs.append(DOWN if v >= 0 else UP)
            vals[k].next_to(bar, UP if v >= 0 else DOWN, buff=0.15)
            names[k].set_x(x)
            on_baseline(names[k], str(labels[k]), ctx.area.bottom + name_h - cap_h, cap_h)
        base = Line([ctx.area.left, y_base, 0], [ctx.area.right, y_base, 0], color=style.MUTED, stroke_width=3)
    else:
        row = (H - top_room) / n
        for lab_size in (style.SMALL_SIZE + 4, style.SMALL_SIZE + 2, style.SMALL_SIZE):    # labels: as large as fit
            names = [text_box(str(x), W * 0.4, lab_size, style.TEXT) for x in labels]
            if max(m.height for m in names) + 0.06 <= row:
                break
        else:
            raise ValueError(f"bar_chart: {n} bars with these labels do not fit: shorten the labels or use fewer bars")
        if vals[0].height + 0.1 > row:
            vals = [T(_with_unit(fmt_number(v, dec), short_unit), lab_size, style.TEXT, bold=True) for v in values]
        name_w = max(m.width for m in names)
        val_w = max(m.width for m in vals) + 0.2
        plot_w = W - name_w - 0.35 - val_w * (2 if lo < 0 else 1)
        scale = plot_w / (hi - lo)
        x_base = ctx.area.left + name_w + 0.35 + (val_w if lo < 0 else 0) + (0 - lo) * scale
        bar_h = min(0.62 * row, 0.85)
        for k, v in enumerate(values):
            y = ctx.area.top - top_room - row * (k + 0.5)
            w = max(abs(v) * scale, 0.02)
            bar = Rectangle(width=w, height=bar_h, stroke_width=0, fill_color=style.PRIMARY, fill_opacity=1)
            bar.move_to([x_base + (w / 2 if v >= 0 else -w / 2), y, 0])
            bars.append(bar)
            grow_dirs.append(LEFT if v >= 0 else RIGHT)
            vals[k].next_to(bar, RIGHT if v >= 0 else LEFT, buff=0.15)
            names[k].move_to([ctx.area.left + name_w, y, 0], aligned_edge=RIGHT)
            on_baseline(names[k], str(labels[k]), y - T("H", lab_size).height / 2, T("H", lab_size).height)
        base = Line([x_base, ctx.area.top - top_room, 0], [x_base, ctx.area.bottom, 0], color=style.MUTED,
                    stroke_width=3)
    parts = [base, *bars, *vals, *names]
    if caption is not None:
        caption.move_to([ctx.area.left, ctx.area.top - caption.height / 2, 0], aligned_edge=LEFT)
        parts.append(caption)
    ctx.place(VGroup(*parts), grow=1.0)

    def p_bar(k):
        def run(t):
            f = pace(t, 1.1 + 0.5 * (k == 0))
            if k == 0:
                t.play(Create(base), *([FadeIn(caption)] if caption is not None else []), rt=0.5 * f)
            t.play(GrowFromEdge(bars[k], grow_dirs[k]), FadeIn(names[k]), rt=0.7 * f)
            t.play(FadeIn(vals[k], shift=-grow_dirs[k] * 0.1), rt=0.4 * f)
        return run

    def p_all(t):
        f = pace(t, 2.6)
        t.play(Create(base), *([FadeIn(caption)] if caption is not None else []), FadeIn(VGroup(*names)), rt=0.6 * f)
        t.play(LaggedStart(*[GrowFromEdge(b, d) for b, d in zip(bars, grow_dirs)], lag_ratio=0.12), rt=1.4 * f)
        t.play(LaggedStart(*[FadeIn(m) for m in vals], lag_ratio=0.1), rt=0.6 * f)

    def p_highlight(t):
        others = [k for k in range(n) if k != highlight]
        t.play(*[bars[k].animate.set_opacity(0.3) for k in others], *[vals[k].animate.set_opacity(0.4) for k in others],
               bars[highlight].animate.set_fill(style.SECONDARY, 1), rt=0.7)
        t.play(vals[highlight].animate.scale(1.15, about_edge=grow_dirs[highlight]), rt=0.4)

    phases = [p_all] if together else [p_bar(k) for k in range(n)]
    run_phases(steps, phases + ([p_highlight] if highlight is not None else []))


@template(category="data", use_for="trends over time or over an ordered quantity, one or more series compared; each "
          "line drawn on its piece and labeled at its end",
          example={"title": "Temperatura media mensile", "args": {
              "x": ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"],
              "series": [{"name": "Milano", "values": [2.5, 4.5, 9, 13, 17.5, 21.5, 24, 23.5, 19, 13.5, 7.5, 3.5]},
                         {"name": "Palermo", "values": [11.5, 11.5, 13, 15, 19, 23, 26, 26.5, 23.5, 20, 16, 13]}],
              "unit": "°C"},
                   "say": ["Ecco la temperatura media di Milano, mese per mese: d'inverno si sta vicino allo zero.",
                           "Palermo, sul mare, ha inverni molto più miti e un'estate appena più calda."]})
def line_chart(ctx, steps, x: list, series: list[dict], unit: str | None = None):
    """Lines over an ordered x axis (2-40 points: years, months, steps), 1-5 series, each labeled at its end
    (no legend). x: the labels of the points (texts or numbers, evenly spaced). series: [{"name", "values": [one
    number or null per x], "color": optional primary|secondary|positive|negative|neutral}]. unit: of the
    values, written above the value axis.
    Phases: axes and the first series, one per further series."""
    n = len(x)
    if not 2 <= n <= 40:
        raise ValueError(f"line_chart: {n} x values (between 2 and 40)")
    if not 1 <= len(series) <= 5:
        raise ValueError(f"line_chart: {len(series)} series (between 1 and 5)")
    for k, s in enumerate(series):
        if not isinstance(s, dict) or not isinstance(s.get("values"), list) or len(s["values"]) != n:
            raise ValueError(f"line_chart: series {k} must be {{\"name\", \"values\"}} with {n} values (one per x)")
        if not all(v is None or _number(v) for v in s["values"]) or not any(_number(v) for v in s["values"]):
            raise ValueError(f"line_chart: series {k}: values must be numbers (or null for a missing value)")
    allv = [float(v) for s in series for v in s["values"] if v is not None]
    lo, hi = min(allv), max(allv)
    if lo >= 0 and lo <= 0.3 * hi:
        lo = 0.0
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    yt, _ = nice_ticks(lo, hi, 5)
    ymin, ymax = yt[0], yt[-1]
    dec = decimals_for(yt)
    W, H = ctx.area.width, ctx.area.height
    size = style.SMALL_SIZE + 2
    y_labs = [T(fmt_number(v, dec), size, style.MUTED) for v in yt]
    x_text = [fmt_number(v) if _number(v) and not float(v).is_integer() else str(int(v)) if _number(v) else str(v)
              for v in x]
    x_labs = [T(t, size, style.MUTED) for t in x_text]
    names, colors = [], []
    for k, s in enumerate(series):
        colors.append(family(s.get("color"), SERIES[k])[0])
        names.append(text_box(str(s.get("name") or ""), W * 0.22, style.SMALL_SIZE + 4, colors[-1], bold=True)
                     if str(s.get("name") or "").strip() else None)
    cap = T(unit, size, style.MUTED) if unit else None
    left = max(m.width for m in y_labs) + 0.3
    right = max([m.width for m in names if m is not None] + [0]) + 0.35
    bottom = max(m.height for m in x_labs) + 0.45
    top = (cap.height + 0.3) if cap is not None else 0.2
    X0, X1 = ctx.area.left + left, ctx.area.right - right
    Y0, Y1 = ctx.area.bottom + bottom, ctx.area.top - top
    X = lambda i: X0 + i * (X1 - X0) / (n - 1)                                  # noqa: E731
    Y = lambda v: Y0 + (v - ymin) / (ymax - ymin) * (Y1 - Y0)                  # noqa: E731
    grid = VGroup()
    for v, m in zip(yt, y_labs):
        grid.add(Line([X0, Y(v), 0], [X1, Y(v), 0], color=style.MUTED, stroke_width=3 if v == ymin else 1.5,
                      stroke_opacity=1 if v == ymin else 0.25))
        m.move_to([X0 - 0.2, Y(v), 0], aligned_edge=RIGHT)
    step = (X1 - X0) / (n - 1)

    def fits(labs, idx):
        return all(step * (b - a) >= (labs[a].width + labs[b].width) / 2 + 0.2 for a, b in zip(idx, idx[1:]))

    if not fits(x_labs, list(range(n))):                         # crowded: a little smaller, then thinned
        x_labs = [T(t, style.SMALL_SIZE, style.MUTED) for t in x_text]
    keep = next((idx for k in (1, 2, 3, 4, 5, 6, 10, 12, 20, 40) for idx in [list(range(0, n, k))]
                 if fits(x_labs, idx)), [0])
    if keep[-1] != n - 1 and fits(x_labs, [keep[-1], n - 1]):
        keep.append(n - 1)
    shown, ticks = VGroup(), VGroup()
    for i in keep:
        m = x_labs[i].move_to([X(i), 0, 0])
        on_baseline(m, x_text[i], Y0 - 0.28 - T("H", style.SMALL_SIZE).height, T("H", style.SMALL_SIZE).height)
        shown.add(m)
        ticks.add(Line([X(i), Y0, 0], [X(i), Y0 - 0.1, 0], color=style.MUTED, stroke_width=2.5))
    if cap is not None:
        cap.move_to([ctx.area.left, ctx.area.top - cap.height / 2, 0], aligned_edge=LEFT)
    frame_mobs = VGroup(grid, VGroup(*y_labs), shown, ticks, *([cap] if cap is not None else []))
    lines, ends = [], []
    for k, s in enumerate(series):
        segs, cur = VGroup(), []
        for i, v in enumerate(s["values"] + [None]):
            if v is not None:
                cur.append([X(i), Y(float(v)), 0])
            elif cur:
                if len(cur) > 1:
                    segs.add(VMobject().set_points_as_corners(cur).set_stroke(colors[k], 6))
                else:
                    segs.add(Dot(cur[0], radius=0.07, color=colors[k]))
                cur = []
        last = max(i for i, v in enumerate(s["values"]) if v is not None)
        end = Dot([X(last), Y(float(s["values"][last])), 0], radius=0.1, color=colors[k])
        lines.append(VGroup(segs, end))
        ends.append(end.get_center())
    # end labels, nudged apart vertically when two lines end close together
    order = sorted([k for k in range(len(series)) if names[k] is not None], key=lambda k: ends[k][1])
    ys = []
    for k in order:
        y = ends[k][1]
        if ys and y - ys[-1][1] < (names[k].height + ys[-1][2]) / 2 + 0.1:
            y = ys[-1][1] + (names[k].height + ys[-1][2]) / 2 + 0.1
        ys.append((k, y, names[k].height))
    over = max([y + h / 2 - ctx.area.top for _, y, h in ys] + [0])
    for k, y, h in ys:
        names[k].move_to([ends[k][0] + 0.25, y - over, 0], aligned_edge=LEFT)
    ctx.place(VGroup(frame_mobs, *lines, *[m for m in names if m is not None]), grow=1.0)

    def p_series(k):
        def run(t):
            f = pace(t, 2.1 + 0.8 * (k == 0))
            if k == 0:
                t.play(FadeIn(grid), FadeIn(VGroup(*y_labs)), FadeIn(shown), FadeIn(ticks),
                       *([FadeIn(cap)] if cap is not None else []), rt=0.8 * f)
            t.play(Create(lines[k][0], lag_ratio=1 if len(lines[k][0]) > 1 else 0), rt=1.6 * f)
            t.play(GrowFromCenter(lines[k][1]), *([FadeIn(names[k], shift=LEFT * 0.15)] if names[k] is not None
                                                  else []), rt=0.5 * f)
        return run

    run_phases(steps, [p_series(k) for k in range(len(series))])
