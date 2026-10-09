"""Project paths and configuration (config.toml).

Layout:
    input/                      PDFs to turn into videos
    output/                     finished videos
    lessons/<id>/lesson.json    which PDF the lesson comes from
    lessons/<id>/script.json    the narration script (the lesson's real work)
    lessons/<id>/animations/    custom animations written for the lesson
    lessons/<id>/build/         regenerable cache: slide images, plan, audio, renders, contact sheets
"""
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
LESSONS = ROOT / "lessons"

VIDEO_PY = ROOT / ".venv" / "bin" / "python"
TTS_PY = ROOT / ".venv-tts" / "bin" / "python"
FFMPEG = ROOT / ".venv" / "bin" / "ffmpeg"
MANIM = ROOT / ".venv" / "bin" / "manim"

CONFIG = tomllib.loads((ROOT / "config.toml").read_text())


def lesson_exists(lesson_id):
    return (LESSONS / lesson_id / "lesson.json").exists()


class Lesson:
    """Every path belonging to one lesson. The lesson id is derived from the PDF file name."""

    def __init__(self, lesson_id: str):
        self.id = lesson_id
        self.dir = LESSONS / lesson_id
        if not lesson_exists(lesson_id):
            raise SystemExit(f"Unknown lesson '{lesson_id}'. Start it with: ./sr input/<file>.pdf")
        self.pdf = ROOT / json.loads((self.dir / "lesson.json").read_text())["pdf"]
        self.script = self.dir / "script.json"
        self.animations_dir = self.dir / "animations"
        self.build = self.dir / "build"
        self.slides = self.build / "slides"
        self.preview = self.build / "preview"
        self.lines = self.build / "lines.json"
        self.overview = self.build / "overview.md"
        self.audio = self.build / "audio"
        self.durations = self.audio / "durations.json"
        self.media = self.build / "media"
        self.video = self.build / "video"
        self.qa = self.build / "qa"
        self.agent = self.build / "agent"
        self.output = OUTPUT / f"{lesson_id}.mp4"
        self.output_small = OUTPUT / f"{lesson_id}_{CONFIG['video']['small_height']}p.mp4"

    @staticmethod
    def create(lesson_id: str, pdf: Path):
        d = LESSONS / lesson_id
        (d / "animations").mkdir(parents=True, exist_ok=True)
        (d / "lesson.json").write_text(json.dumps({"pdf": str(pdf.resolve().relative_to(ROOT))}, indent=2) + "\n")
        return Lesson(lesson_id)

    def slide_image(self, n: int) -> Path:
        return self.slides / f"slide_{n:02d}.png"

    def slide_video(self, n: int) -> Path:
        return self.video / f"slide_{n:02d}.mp4"
