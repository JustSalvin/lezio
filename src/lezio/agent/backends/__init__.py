# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""LLM backends. The program describes tasks (base.Task); a backend runs them on some model.

config.toml: [agent] backend = "<name>" picks one; its settings are in [agent.<name>] (model, effort, and
what the backend needs, e.g. the server address), with optional per-task overrides in
[agent.<name>.<plan|write|review>]. Each backend keeps its own settings, so switching is one line.

To add a backend: subclass Backend, implement run(task) (system prompt + user message + tool loop through
base.Session, which logs, reports events and runs the tools), and register it here.
"""
from ...config import CONFIG
from .anthropic_api import AnthropicAPI
from .base import Backend, Image, Task, TaskOutcome, Tool, ToolResult
from .claude_subscription import ClaudeSubscription
from .openai_compatible import Local, OpenAIAPI

BACKENDS = {b.name: b for b in (ClaudeSubscription, AnthropicAPI, OpenAIAPI, Local)}


def backend_name():
    return CONFIG["agent"]["backend"]


def backend_settings(name=None):
    """The [agent.<backend>] table of config.toml."""
    return CONFIG["agent"].get(name or backend_name(), {})


def get_backend() -> Backend:
    name = backend_name()
    if name not in BACKENDS:
        raise SystemExit(f"Unknown agent backend '{name}' in config.toml (choose: {', '.join(BACKENDS)})")
    backend = BACKENDS[name](backend_settings(name))
    backend.check()
    return backend


def task_options(kind):
    """Model and effort for a kind of task (plan | write | review): [agent.<backend>] overridden by
    [agent.<backend>.<kind>]."""
    settings = backend_settings()
    specific = settings.get(kind, {})
    return {"model": specific.get("model", settings.get("model", "")),
            "effort": specific.get("effort", settings.get("effort", ""))}


__all__ = ["BACKENDS", "Backend", "Image", "Task", "TaskOutcome", "Tool", "ToolResult", "backend_name",
           "backend_settings", "get_backend", "task_options"]
