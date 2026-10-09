"""Backend (planned): the Anthropic API with an API key.

The same Task objects map directly onto the Messages API: `system` = task.system, first user message =
task.prompt, `tools` = [{"name", "description", "input_schema"}] from task.tools, then a loop that runs
tool handlers for every `tool_use` block and sends back `tool_result` blocks (text and base64 images)
until a handler returns done=True or the model stops calling tools.
"""
from .base import Backend, Task, TaskOutcome


class AnthropicAPI(Backend):
    name = "anthropic-api"

    def check(self):
        raise SystemExit("The anthropic-api backend is planned but not implemented yet. "
                         "Set [agent] backend = \"claude-subscription\" in config.toml.")

    def run(self, task: Task) -> TaskOutcome:  # pragma: no cover - placeholder
        raise NotImplementedError
