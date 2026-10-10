# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""LLM backends. The program describes tasks (base.Task); a backend runs them on some model.

To add a backend: subclass Backend, implement run(task) (system prompt + user message + tool loop, report
events through task.on_event), and register it here.
"""
from ...config import CONFIG
from .anthropic_api import AnthropicAPI
from .base import Backend, Image, Task, TaskOutcome, Tool, ToolResult
from .claude_subscription import ClaudeSubscription

BACKENDS = {b.name: b for b in (ClaudeSubscription, AnthropicAPI)}


def get_backend() -> Backend:
    name = CONFIG["agent"]["backend"]
    if name not in BACKENDS:
        raise SystemExit(f"Unknown agent backend '{name}' in config.toml (choose: {', '.join(BACKENDS)})")
    backend = BACKENDS[name]()
    backend.check()
    return backend


def task_options(kind):
    """Model and effort for a kind of task (plan | write | review): [agent] overridden by [agent.<kind>]."""
    agent = CONFIG["agent"]
    specific = agent.get(kind, {})
    return {"model": specific.get("model", agent.get("model", "")),
            "effort": specific.get("effort", agent.get("effort", ""))}


__all__ = ["BACKENDS", "Backend", "Image", "Task", "TaskOutcome", "Tool", "ToolResult", "get_backend",
           "task_options"]
