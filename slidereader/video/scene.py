"""Manim scene that renders ONE slide of a lesson (chosen through environment variables).

Started by video/render.py through the manim command, which sets
SR_LESSON, SR_SLIDE and optionally SR_ONLY_BEAT (render a single animation beat) and
SR_FAKE_AUDIO (seconds per piece when audio has not been generated yet).
"""
import json
import os

import numpy as np
from manim import (ORIGIN, Create, FadeIn, FadeOut, ImageMobject, Rectangle, ReplacementTransform,
                   RoundedRectangle, Scene, config, linear)

from ..lesson import Lesson
from ..pdf import load_lines, resolve_highlight, resolve_image
from ..script import load_script, normalize_step, piece_key
from ..validate import find_animation, load_custom_animations
from .anim_api import BACKGROUND, YELLOW, Steps

config.background_color = BACKGROUND


class LessonScene(Scene):
    def construct(self):
        lesson = Lesson(os.environ["SR_LESSON"])
        n = int(os.environ["SR_SLIDE"])
        only_beat = os.environ.get("SR_ONLY_BEAT")
        fake = os.environ.get("SR_FAKE_AUDIO")
        settings, slides = load_script(lesson.script)
        slide = next(s for s in slides if s["slide"] == n)
        gap = settings["beat_gap"]
        durations = json.loads(lesson.durations.read_text()) if lesson.durations.exists() else {}
        custom = load_custom_animations(lesson)

        def piece(key):
            wav = lesson.audio / f"{key}.wav"
            if key in durations and wav.exists():
                return str(wav), durations[key]["duration"]
            if fake:
                return None, float(fake)
            raise SystemExit(f"Missing audio for {key}: run ./sr audio {lesson.id}")

        lines = load_lines(lesson)
        W, H = lines["page_size"]
        slide_data = lines["slides"][str(n)]

        img = ImageMobject(str(lesson.slide_image(n)))
        if W / H >= config.frame_width / config.frame_height:
            img.width = config.frame_width
        else:
            img.height = config.frame_height
        base_w, base_h = img.width, img.height

        def pdf_to_scene(x, y):
            return np.array([x / W * base_w - base_w / 2, base_h / 2 - y / H * base_h, 0])

        def frame_for(bbox):
            x0, y0, x1, y1 = bbox
            pad = 0.07
            a, b = pdf_to_scene(x0, y0), pdf_to_scene(x1, y1)
            r = RoundedRectangle(width=b[0] - a[0] + 2 * pad, height=a[1] - b[1] + 2 * pad, corner_radius=0.08,
                                 stroke_color=YELLOW, stroke_width=5, fill_color=YELLOW, fill_opacity=0.16)
            return r.move_to((a + b) / 2)

        if settings["visual"] != "animated":          # in "animated" mode the slide is never shown
            if only_beat is None:
                self.play(FadeIn(img), run_time=0.4)
            else:
                self.add(img)

        frame = None
        for k, beat in enumerate(slide["beats"]):
            if only_beat is not None and k != int(only_beat):
                continue

            if "anim" in beat:
                if frame is not None:
                    self.play(FadeOut(frame), run_time=0.3)
                    frame = None
                pieces = []
                for j, st in enumerate(beat["steps"]):
                    wav, d = piece(piece_key(n, k, j))
                    pieces.append((wav, d, normalize_step(st).get("pause", 0)))
                before = set(self.mobjects)
                cover = Rectangle(width=config.frame_width + 0.2, height=config.frame_height + 0.2, stroke_width=0,
                                  fill_color=BACKGROUND, fill_opacity=1)
                self.play(FadeIn(cover), run_time=0.35)
                steps = Steps(self, pieces, gap)
                find_animation(beat["anim"], custom)(self, steps, **beat.get("args", {}))
                steps.finish()
                if settings["visual"] != "animated" and img not in self.mobjects:
                    self.add(img)                        # an animation removed the slide: put it back
                    self.bring_to_back(img)
                new = [m for m in self.mobjects if m not in before]
                self.play(*[FadeOut(m) for m in new], run_time=0.4)
                self.remove(*new)
                continue

            wav, d = piece(piece_key(n, k))
            if wav:
                self.add_sound(wav)
            used = 0.0
            wants_frame = "highlight" in beat or "image" in beat
            if wants_frame and abs(img.width - base_w) > 1e-3:      # undo a previous zoom first
                self.play(img.animate.scale_to_fit_width(base_w).move_to(ORIGIN), run_time=0.5)
                used += 0.5
            if wants_frame:
                bbox = (resolve_highlight(slide_data, beat["highlight"]) if "highlight" in beat
                        else resolve_image(slide_data, beat["image"]))
                new_frame = frame_for(bbox)
                if frame is None:
                    self.play(Create(new_frame), run_time=0.5)
                else:
                    self.play(ReplacementTransform(frame, new_frame), run_time=0.5)
                frame, used = new_frame, used + 0.5
            elif frame is not None:
                self.play(FadeOut(frame), run_time=0.3)
                frame, used = None, used + 0.3
            if beat.get("zoom"):
                self.play(img.animate.scale(1 + 0.006 * d), run_time=max(d - used, 0.1), rate_func=linear)
            elif d - used > 0:
                self.wait(d - used)
            self.wait(gap + beat.get("pause", 0))
        self.wait(0.6)
