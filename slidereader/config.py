"""Project paths and configuration (config.toml)."""
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
SCRIPTS = ROOT / "scripts"
ANIMATIONS = ROOT / "animations"
OUTPUT = ROOT / "output"
BUILD = ROOT / "build"

VIDEO_PY = ROOT / ".venv" / "bin" / "python"
TTS_PY = ROOT / ".venv-tts" / "bin" / "python"
FFMPEG = ROOT / ".venv" / "bin" / "ffmpeg"
MANIM = ROOT / ".venv" / "bin" / "manim"

CONFIG = tomllib.loads((ROOT / "config.toml").read_text())


class Lesson:
    """Every path belonging to one lesson. The lesson id is derived from the PDF file name."""

    def __init__(self, lesson_id: str):
        self.id = lesson_id
        self.build = BUILD / lesson_id
        meta = self.build / "meta.json"
        if not meta.exists():
            raise SystemExit(f"Unknown lesson '{lesson_id}'. Run: ./sr init input/<file>.pdf")
        self.pdf = ROOT / json.loads(meta.read_text())["pdf"]
        self.script = SCRIPTS / f"{lesson_id}.json"
        self.animations = ANIMATIONS / f"{lesson_id}.py"
        self.animations_dir = ANIMATIONS / lesson_id
        self.output = OUTPUT / f"{lesson_id}.mp4"
        self.output_small = OUTPUT / f"{lesson_id}_{CONFIG['video']['small_height']}p.mp4"
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

    @staticmethod
    def create(lesson_id: str, pdf: Path):
        d = BUILD / lesson_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "meta.json").write_text(json.dumps({"pdf": str(pdf.resolve().relative_to(ROOT))}))
        return Lesson(lesson_id)

    def slide_image(self, n: int) -> Path:
        return self.slides / f"slide_{n:02d}.png"

    def slide_video(self, n: int) -> Path:
        return self.video / f"slide_{n:02d}.mp4"
