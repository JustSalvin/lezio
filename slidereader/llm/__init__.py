"""LLM backends. The program describes tasks (llm.base.Task); a backend runs them on some model.

To add a backend: subclass Backend, implement run(task) (system prompt + user message + tool loop),
and register it here.
"""
from ..config import CONFIG
from .anthropic_api import AnthropicAPI
from .base import Backend, Image, Task, TaskOutcome, Tool, ToolResult
from .claude_subscription import ClaudeSubscription

BACKENDS = {b.name: b for b in (ClaudeSubscription, AnthropicAPI)}


def get_backend() -> Backend:
    name = CONFIG["agent"]["backend"]
    if name not in BACKENDS:
        raise SystemExit(f"Unknown agent backend '{name}' in config.toml (choose: {', '.join(BACKENDS)})")
    backend = BACKENDS[name](CONFIG["agent"].get("model", ""))
    backend.check()
    return backend


__all__ = ["BACKENDS", "Backend", "Image", "Task", "TaskOutcome", "Tool", "ToolResult", "get_backend"]
