# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Model-independent description of an agent task.

A Task is a system prompt, a user message and a set of Tools. Tools are plain Python functions owned by
the program: the model can only act through them (it has no file system, shell or web access).
A backend runs the conversation until the model stops or a tool marks the task as done, and reports what
happens through task.on_event(kind, data):
    ("model", "<model id actually answering>"), ("tool", (name, input)), ("rejected", (name, first line))
Session does this bookkeeping (log, events, running the tools) the same way for every backend.
"""
import base64
import json
import time
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

    def data_url(self):
        return f"data:{self.mime};base64,{self.b64()}"


@dataclass
class ToolResult:
    content: list            # str and Image items, in order
    error: bool = False      # tell the model its call was rejected
    done: bool = False       # the task is complete: the backend stops the conversation

    def texts(self):
        return [c for c in self.content if isinstance(c, str) and c]

    def images(self):
        return [c for c in self.content if isinstance(c, Image)]


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
    model: str = ""          # "" = the backend's default
    effort: str = ""         # low | medium | high | xhigh | max ("" = default)
    max_turns: int = 40
    log_path: Path | None = None
    on_event: Callable[[str, object], None] | None = None


@dataclass
class TaskOutcome:
    done: bool               # a tool declared the task complete
    turns: int = 0
    text: str = ""           # last text the model wrote
    error: str = ""
    model: str = ""          # model that actually answered
    extra: dict = field(default_factory=dict)


class Session:
    """One run of a task: the log (lessons/<id>/build/agent/log.jsonl), the events, the tool calls."""

    def __init__(self, task: Task):
        self.task = task
        self.tools = {t.name: t for t in task.tools}
        self.notify = task.on_event or (lambda kind, data: None)
        self.outcome = TaskOutcome(done=False)
        self.file = open(task.log_path, "a") if task.log_path else None
        self.log("prompt", {"model": task.model, "effort": task.effort, "system": task.system, "user": task.prompt})

    def log(self, kind, payload):
        if self.file:
            self.file.write(json.dumps({"t": round(time.time(), 1), "task": self.task.label, kind: payload},
                                       ensure_ascii=False, default=str) + "\n")
            self.file.flush()

    def model(self, name):
        if name and name != self.outcome.model:
            self.outcome.model = name
            self.notify("model", name)

    def text(self, text):
        if text and text.strip():
            self.outcome.text = text.strip()
            self.log("text", self.outcome.text)

    def tool_use(self, name, args):
        self.log("tool_use", {"tool": name, "input": args})
        self.notify("tool", (name, args))

    def execute(self, name, args, problem="") -> ToolResult:
        """Run a tool for the model. Unknown tools, bad or missing arguments and program errors go back to the
        model as rejected calls; a result with done=True completes the task."""
        tool = self.tools.get(name)
        missing = ([k for k in tool.schema.get("required", []) if k not in args]
                   if tool and isinstance(args, dict) else [])
        if problem:
            result = ToolResult([problem], error=True)
        elif tool is None:
            result = ToolResult([f"Unknown tool {name}. The tools are: {', '.join(self.tools)}."], error=True)
        elif not isinstance(args, dict):
            result = ToolResult([f"The arguments of {name} must be a JSON object."], error=True)
        elif missing:
            result = ToolResult([f"Missing arguments for {name}: {', '.join(missing)}."], error=True)
        else:
            try:
                result = tool.handler(args)
            except Exception as e:  # noqa: BLE001 - report program errors to the model, keep going
                result = ToolResult([f"Internal error while running {name}: {e!r}"], error=True)
        self.outcome.done = self.outcome.done or result.done
        texts = result.texts()
        self.log("tool_result", {"tool": name, "error": result.error, "done": result.done, "text": texts})
        if result.error:
            self.notify("rejected", (name, texts[1] if len(texts) > 1 else (texts or [""])[0]))
        return result

    def call(self, name, args) -> ToolResult:
        """A tool call of the model: `args` is a dict, or a JSON string (OpenAI-style APIs)."""
        problem = ""
        if isinstance(args, str):
            raw = args
            args, problem = parse_arguments(raw)
            self.tool_use(name, raw if args is None else args)
        else:
            self.tool_use(name, args)
        return self.execute(name, args, problem)

    def usage(self, **tokens):
        """Token counts of one model call: logged and summed in outcome.extra["usage"]."""
        tokens = {k: v for k, v in tokens.items() if v}
        total = self.outcome.extra.setdefault("usage", {})
        for k, v in tokens.items():
            total[k] = total.get(k, 0) + v
        self.log("usage", tokens)

    def close(self) -> TaskOutcome:
        if self.file:
            self.file.close()
            self.file = None
        return self.outcome


def error_message(e):
    """The readable message of an API error (the `message` of its JSON body when there is one)."""
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        inner = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(inner.get("message"), str):
            return inner["message"]
    return getattr(e, "message", None) or str(e)


def parse_arguments(text):
    """Tool arguments sent as a JSON string (OpenAI-style APIs): a dict, or the error to give back."""
    try:
        args = json.loads(text or "{}")
    except json.JSONDecodeError as e:
        return None, f"Your arguments were not valid JSON ({e}). Call the tool again with a JSON object."
    return (args, "") if isinstance(args, dict) else (None, "The arguments must be a JSON object.")


class Backend:
    name = ""
    summary = ""             # one line for ./lezio config

    def __init__(self, settings: dict | None = None):
        self.settings = settings or {}     # the [agent.<name>] table of config.toml

    def check(self):
        """Raise SystemExit with a helpful message if the backend cannot be used."""

    def run(self, task: Task) -> TaskOutcome:
        raise NotImplementedError
