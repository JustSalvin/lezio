"""A lesson = one video project, stored in lessons/<id>/.

    lesson.json     the study material the lesson is made from: {"sources": [paths], "created": ...}
    script.json     per-video choices, plan and segments (template blocks with their narration)
    templates/      templates written by the agent for this lesson (templates/<name>.py)
    scenes/         scene code of segments written as code (older lessons)
    build/          regenerable cache (material, audio, renders, contact sheets, agent log, logs)

Pure Python (no heavy imports): used by both virtual environments.
"""
import json
import re
import time
import unicodedata
from pathlib import Path

from .config import LESSONS, OUTPUT, ROOT


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower() or "lesson"


def lesson_exists(lesson_id):
    return (LESSONS / lesson_id / "lesson.json").exists()


def all_lessons():
    """Lesson ids (folders starting with "_" are internal, e.g. the template demos)."""
    return sorted(p.parent.name for p in LESSONS.glob("*/lesson.json") if not p.parent.name.startswith("_"))


def stored_path(path: Path) -> str:
    """Paths inside the project are stored relative to it, others as absolute paths."""
    path = Path(path).expanduser().resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


class Lesson:
    def __init__(self, lesson_id: str):
        self.id = lesson_id
        self.dir = LESSONS / lesson_id
        if not lesson_exists(lesson_id):
            raise SystemExit(f"Unknown lesson '{lesson_id}'. Start one with: ./lezio input/<file>")
        self.info = json.loads((self.dir / "lesson.json").read_text())
        self.script = self.dir / "script.json"
        self.scenes = self.dir / "scenes"
        self.templates = self.dir / "templates"
        self.build = self.dir / "build"
        self.material = self.build / "material"      # ingested study material + index.json
        self.index = self.material / "index.json"
        self.audio = self.build / "audio"
        self.durations = self.audio / "durations.json"
        self.media = self.build / "media"            # Manim working files (deleted after each render)
        self.video = self.build / "video"            # one video per segment
        self.qa = self.build / "qa"                  # contact sheets and render reports
        self.agent = self.build / "agent"            # agent log, drafts, backups
        self.logs = self.build / "logs"
        self.output = OUTPUT / f"{lesson_id}.mp4"

    @property
    def source_names(self):
        """Source paths as stored in lesson.json (relative to the project when inside it)."""
        return list(self.info["sources"])

    @property
    def sources(self):
        return [ROOT / s for s in self.info["sources"]]

    @staticmethod
    def create(lesson_id: str, sources):
        d = LESSONS / lesson_id
        (d / "scenes").mkdir(parents=True, exist_ok=True)
        info = {"sources": [stored_path(p) for p in sources], "created": time.strftime("%Y-%m-%d %H:%M")}
        (d / "lesson.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
        return Lesson(lesson_id)

    def set_sources(self, sources):
        self.info["sources"] = [stored_path(p) for p in sources]
        (self.dir / "lesson.json").write_text(json.dumps(self.info, ensure_ascii=False, indent=2) + "\n")

    def scene_file(self, scene: str) -> Path:
        return self.scenes / f"{scene}.py"

    def segment_video(self, segment_id: str) -> Path:
        return self.video / f"{segment_id}.mp4"

    def durations_meta(self):
        return json.loads(self.durations.read_text()) if self.durations.exists() else {}
