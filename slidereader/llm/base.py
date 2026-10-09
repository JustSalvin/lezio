"""Model-independent description of an agent task.

A Task is a system prompt, a user message and a set of Tools. Tools are plain Python functions owned by
the program: the model can only act through them (it has no file system, shell or web access).
A backend runs the conversation until the model stops or a tool marks the task as done.
"""
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Image:
    data: bytes
    mime: str = "image/jpeg"

    @staticmethod
    def from_file(path: Path, max_width: int = 1024, quality: int = 75):
        """Load an image for the model: downscaled and JPEG-compressed (readable, and small to transfer)."""
        import io
        from PIL import Image as PILImage
        im = PILImage.open(path).convert("RGB")
        if im.width > max_width:
            im = im.resize((max_width, round(im.height * max_width / im.width)), PILImage.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality)
        return Image(buf.getvalue(), "image/jpeg")

    def b64(self):
        return base64.b64encode(self.data).decode()


@dataclass
class ToolResult:
    content: list            # str and Image items, in order
    error: bool = False      # tell the model its call was rejected
    done: bool = False       # the task is complete: the backend stops the conversation


@dataclass
class Tool:
    name: str
    description: str
    schema: dict             # JSON schema of the input object
    handler: Callable[[dict], ToolResult]


@dataclass
class Task:
    label: str
    system: str
    prompt: str
    tools: list[Tool]
    max_turns: int = 40
    log_path: Path | None = None


@dataclass
class TaskOutcome:
    done: bool               # a tool declared the task complete
    turns: int = 0
    text: str = ""           # last text the model wrote
    error: str = ""
    extra: dict = field(default_factory=dict)


class Backend:
    name = ""

    def check(self):
        """Raise SystemExit with a helpful message if the backend cannot be used."""

    def run(self, task: Task) -> TaskOutcome:
        raise NotImplementedError
