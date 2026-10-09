"""A lesson = one video project, stored in lessons/<id>/.

    lesson.json     which PDF the lesson comes from
    script.json     the narration script and the per-video choices
    animations/     custom animations written for the lesson
    build/          regenerable cache (slide images, plan, audio, renders, contact sheets, logs)
"""
import json
import re
import unicodedata
from pathlib import Path

from .config import LESSONS, OUTPUT, ROOT


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "lesson"


def lesson_exists(lesson_id):
    return (LESSONS / lesson_id / "lesson.json").exists()


def all_lessons():
    return sorted(p.parent.name for p in LESSONS.glob("*/lesson.json"))


class Lesson:
    def __init__(self, lesson_id: str):
        self.id = lesson_id
        self.dir = LESSONS / lesson_id
        if not lesson_exists(lesson_id):
            raise SystemExit(f"Unknown lesson '{lesson_id}'. Start it with: ./sr input/<file>.pdf")
        self.pdf = ROOT / json.loads((self.dir / "lesson.json").read_text())["pdf"]
        self.script = self.dir / "script.json"
        self.animations_dir = self.dir / "animations"
        self.build = self.dir / "build"
        self.slides = self.build / "slides"          # high-resolution slide images (video)
        self.preview = self.build / "preview"        # smaller slide images (shown to the agent)
        self.lines = self.build / "lines.json"
        self.overview = self.build / "overview.md"
        self.audio = self.build / "audio"
        self.durations = self.audio / "durations.json"
        self.media = self.build / "media"            # Manim working files (deleted after each render)
        self.video = self.build / "video"
        self.qa = self.build / "qa"                  # contact sheets
        self.agent = self.build / "agent"            # plan, group results, agent log
        self.logs = self.build / "logs"
        self.output = OUTPUT / f"{lesson_id}.mp4"

    @staticmethod
    def create(lesson_id: str, pdf: Path):
        d = LESSONS / lesson_id
        (d / "animations").mkdir(parents=True, exist_ok=True)
        (d / "lesson.json").write_text(json.dumps({"pdf": str(pdf.resolve().relative_to(ROOT))}, indent=2) + "\n")
        if not (d / "script.json").exists():
            (d / "script.json").write_text(json.dumps({"settings": {}, "slides": []}, indent=2) + "\n")
        return Lesson(lesson_id)

    def slide_image(self, n: int) -> Path:
        return self.slides / f"slide_{n:02d}.png"

    def slide_video(self, n: int) -> Path:
        return self.video / f"slide_{n:02d}.mp4"

    def durations_meta(self):
        return json.loads(self.durations.read_text()) if self.durations.exists() else {}
