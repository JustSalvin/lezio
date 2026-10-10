"""Manim scene that renders ONE segment of a lesson: it runs scenes/<segment>.py:build(scene, steps, material).

Started by video/render.py through the manim command, with these environment variables:
    LEZIO_LESSON, LEZIO_SEGMENT   which segment
    LEZIO_DRAFT      optional JSON file {"segment": {...}, "code": "<path>"}: render a submission not saved yet
    LEZIO_ESTIMATE   "1": pieces without audio get an estimated duration (previews before the voice exists)
    LEZIO_REPORT     JSON file written at the end: error, timing of each piece, layout warnings

The scene code is checked (validate.check_scene_code) before it runs. While it runs, the end of every
narration piece is checked for texts cut off by the frame or overlapping each other. The house theme
(config.toml [video] theme) is applied before the scene code runs.
"""
import json
import os
import traceback
from pathlib import Path

from manim import MarkupText, Scene, Text

from ..lesson import Lesson
from ..scene.material import SceneMaterial
from ..scene import style
from ..scene.style import FRAME_HEIGHT, FRAME_WIDTH, apply_theme
from ..settings import house_theme
from ..scene.sync import Steps
from ..script import estimate_seconds, find_segment, load_script, narration, normalize_piece, piece_key, scene_name
from ..validate import check_scene_code

MIN_FONT_SIZE = 20          # smaller texts are hard to read in the video


class SceneError(Exception):
    pass


def _label(m):
    text = " ".join(str(getattr(m, "original_text", getattr(m, "text", ""))).split())
    return repr(text if len(text) <= 40 else text[:39] + "…")


def _visible(m):
    glyphs = m.family_members_with_points()
    return bool(glyphs) and max(g.get_fill_opacity() for g in glyphs) > 0.1


def _box(m):
    return m.get_left()[0], m.get_bottom()[1], m.get_right()[0], m.get_top()[1]


def layout_warnings(scene):
    """Texts on screen now that are too small, cut off by the frame or overlapping another text."""
    texts = []
    for top in scene.mobjects:
        for m in top.get_family():
            if isinstance(m, (Text, MarkupText)) and _visible(m) and all(m is not x for x in texts):
                texts.append(m)
    out = []
    fw, fh = FRAME_WIDTH / 2, FRAME_HEIGHT / 2
    small = [m for m in texts if getattr(m, "font_size", 99) < MIN_FONT_SIZE]
    if small:
        out.append(f"text {_label(small[0])} is too small to read (size {small[0].font_size:.0f}): shorten it, "
                   "split the content or use fewer elements" + (f" ({len(small)} small texts)" if len(small) > 1 else ""))
    for m in texts:
        x0, y0, x1, y1 = _box(m)
        outside = max(-fw - x0, x1 - fw, -fh - y0, y1 - fh)
        if outside > 0.05:
            out.append(f"text {_label(m)} is cut off by the edge of the frame")
    for i, a in enumerate(texts):
        ax0, ay0, ax1, ay1 = _box(a)
        for b in texts[i + 1:]:
            bx0, by0, bx1, by1 = _box(b)
            inter = max(min(ax1, bx1) - max(ax0, bx0), 0) * max(min(ay1, by1) - max(ay0, by0), 0)
            smaller = min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0))
            if smaller > 0 and inter > 0.2 * smaller:
                out.append(f"texts {_label(a)} and {_label(b)} overlap")
    return out[:5]


def scene_error(e, code_path):
    """A short error message pointing at the lines of the scene file."""
    frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == str(code_path)]
    where = "; ".join(f"line {f.lineno}: {(f.line or '').strip()}" for f in frames[-3:])
    return (f"{where} -> " if where else "") + f"{type(e).__name__}: {e}"


def template_error(e, block_index, name):
    """A short error message for a block, pointing at lines of the agent's template files if involved."""
    frames = [f for f in traceback.extract_tb(e.__traceback__) if "/templates/" in f.filename
              and "/src/lezio/" not in f.filename]
    where = "; ".join(f"{Path(f.filename).stem} line {f.lineno}: {(f.line or '').strip()}" for f in frames[-2:])
    return f"block {block_index} ({name}): " + (f"{where} -> " if where else "") + f"{type(e).__name__}: {e}"


class SegmentScene(Scene):
    def construct(self):
        env = os.environ
        report = {"ok": False, "error": None, "warnings": [], "pieces": [], "steps_called": 0, "estimated": 0}
        try:
            self.run_segment(Lesson(env["LEZIO_LESSON"]), env, report)
            report["ok"] = True
        except Exception as e:
            report["error"] = report["error"] or f"{type(e).__name__}: {e}"
            raise
        finally:
            if env.get("LEZIO_REPORT"):
                Path(env["LEZIO_REPORT"]).write_text(json.dumps(report, ensure_ascii=False, indent=1))

    def run_blocks(self, lesson, blocks, steps, report):
        from ..scene import templates
        templates.load_library()
        try:
            templates.load_lesson_templates(lesson)
        except Exception as e:
            report["error"] = f"the lesson's templates cannot be loaded: {type(e).__name__}: {e}"
            raise
        material = SceneMaterial(lesson)
        index = {"k": 0}
        original = templates.REGISTRY.copy()
        try:
            templates.run_blocks(self, steps, material, blocks, on_block=lambda k: index.update(k=k))
        except Exception as e:
            report["error"] = template_error(e, index["k"], blocks[index["k"]].get("template"))
            raise
        finally:
            templates.REGISTRY.clear()
            templates.REGISTRY.update(original)

    def run_segment(self, lesson, env, report):
        script = load_script(lesson.script)
        settings = script["settings"]
        if env.get("LEZIO_DRAFT"):
            draft = json.loads(Path(env["LEZIO_DRAFT"]).read_text())
            segment = draft["segment"]
            code_path = Path(draft["code"]) if draft.get("code") else None
        else:
            segment = find_segment(script, env["LEZIO_SEGMENT"])
            if segment is None:
                raise SceneError(f"segment {env['LEZIO_SEGMENT']} is not in the script")
            code_path = None if segment.get("blocks") else lesson.scene_file(scene_name(segment))
        code = code_path.read_text() if code_path else None
        if code is not None:
            problems = check_scene_code(code)
            if problems:
                report["error"] = "scene code rejected: " + "; ".join(problems)
                raise SceneError(report["error"])

        meta = lesson.durations_meta()
        pieces = []
        for i, p in enumerate(normalize_piece(x) for x in narration(segment)):
            key = piece_key(segment["id"], i)
            wav, m = lesson.audio / f"{key}.wav", meta.get(key, {})
            if wav.exists() and m.get("text") == p["say"]:
                pieces.append({**p, "wav": str(wav), "duration": m["duration"]})
            elif env.get("LEZIO_ESTIMATE") == "1":
                pieces.append({**p, "wav": None, "duration": estimate_seconds(p["say"])})
                report["estimated"] += 1
            else:
                raise SceneError(f"missing audio for {key}: generate the voice first")

        def on_start(t):
            report["pieces"].append({"index": t.index, "start": round(self.renderer.time, 3), "say": t.say,
                                     "duration": round(t.duration, 2)})

        def on_end(t):
            info = report["pieces"][-1]
            info["end"] = round(self.renderer.time, 3)
            if t.overrun > (1.0 if report["estimated"] else 0.5):
                report["warnings"].append(f"piece {t.index}: the animations last {t.overrun:.1f} s longer than the "
                                          "speech (the voice waits for them)")
            report["warnings"] += [f"end of piece {t.index}: {w}" for w in layout_warnings(self)]

        report["theme"] = apply_theme(house_theme())     # before any scene or template code runs
        self.camera.background_color = style.BACKGROUND
        steps = Steps(self, pieces, settings["piece_gap"], on_start=on_start, on_end=on_end)
        if code is None:
            self.run_blocks(lesson, segment["blocks"], steps, report)
        else:
            namespace = {"__name__": f"lezio_scene_{segment['id']}", "__file__": str(code_path)}
            try:
                exec(compile(code, str(code_path), "exec"), namespace)      # noqa: S102 - checked scene code
                namespace["build"](self, steps, SceneMaterial(lesson))
            except Exception as e:
                report["error"] = scene_error(e, code_path)
                raise
        report["steps_called"] = steps.i
        if steps.i < len(pieces):
            report["warnings"].append(f"the scene used {steps.i} of {len(pieces)} narration pieces: "
                                      "the last pieces play over a still screen")
        steps.finish()
        self.wait(0.5)
