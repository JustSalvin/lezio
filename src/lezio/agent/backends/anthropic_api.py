# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Backend: Claude through the Anthropic API (paid per token), with the official `anthropic` SDK.

A tool loop on the Messages API: the system prompt and the growing conversation are cached, thinking is
adaptive with the task's effort, answers are streamed (long ones do not time out). On the models that
support it, a request declined by the safety classifiers is retried server-side on the model Anthropic
recommends for that case (`fallbacks: "default"`). Credentials: ANTHROPIC_API_KEY (or `ant auth login`).
"""
import os
from pathlib import Path

from .base import Backend, Session, Task, TaskOutcome, ToolResult, error_message

ALIASES = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-4-5",
           "fable": "claude-fable-5-1"}
DEFAULT_MODEL = "claude-opus-5-5"
MAX_TOKENS = 64000
FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def model_options(model, effort):
    """Thinking and effort: adaptive thinking on current models; older ones (Haiku 4.x, Claude 3) get neither."""
    if model.startswith(("claude-haiku-4", "claude-3")):
        return {}
    options = {"thinking": {"type": "adaptive"}}
    if effort:
        options["output_config"] = {"effort": effort}
    return options


def result_blocks(result: ToolResult):
    blocks = [{"type": "text", "text": t} for t in result.texts()]
    blocks += [{"type": "image", "source": {"type": "base64", "media_type": i.mime, "data": i.b64()}}
               for i in result.images()]
    return blocks or [{"type": "text", "text": "(no output)"}]


def echo(content):
    """The assistant turn to send back. After a fallback in the middle of an answer, only the text written
    before the last `fallback` block is kept (the API's rule for echoing fallback turns)."""
    cut = max((i for i, b in enumerate(content) if b.type == "fallback"), default=-1)
    return [b for i, b in enumerate(content) if i >= cut or b.type == "text"]


class AnthropicAPI(Backend):
    name = "anthropic-api"
    summary = "Claude with an Anthropic API key (paid per token)"

    def check(self):
        try:
            import anthropic  # noqa: F401
        except ImportError:
            raise SystemExit("The anthropic package is not installed: run "
                             ".venv/bin/pip install -r requirements-video.txt")
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or (Path.home() / ".config" / "anthropic").is_dir()):
            raise SystemExit("No Anthropic API credentials: set the ANTHROPIC_API_KEY environment variable "
                             "(e.g. in ~/.zshrc) or log in with `ant auth login`")

    def run(self, task: Task) -> TaskOutcome:
        import anthropic

        s = Session(task)
        model = ALIASES.get(task.model, task.model) or DEFAULT_MODEL
        client = anthropic.Anthropic(max_retries=4)
        params = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            # the system prompt is the stable prefix; automatic caching follows the conversation as it grows
            "system": [{"type": "text", "text": task.system, "cache_control": {"type": "ephemeral"}}],
            "cache_control": {"type": "ephemeral"},
            "tools": [{"name": t.name, "description": t.description, "input_schema": t.schema} for t in task.tools],
            **model_options(model, task.effort),
        }
        if model.startswith(FALLBACK_MODELS):
            params |= {"betas": [FALLBACK_BETA], "extra_body": {"fallbacks": "default"}}
        messages = [{"role": "user", "content": task.prompt}]
        try:
            for turn in range(task.max_turns):
                with client.beta.messages.stream(messages=messages, **params) as stream:
                    response = stream.get_final_message()
                s.outcome.turns = turn + 1
                s.model(response.model)
                u = response.usage
                s.usage(input=u.input_tokens, cache_read=u.cache_read_input_tokens,
                        cache_write=u.cache_creation_input_tokens, output=u.output_tokens)
                for block in response.content:
                    if block.type == "text":
                        s.text(block.text)
                if response.stop_reason == "refusal":
                    details = getattr(response, "stop_details", None)
                    s.outcome.error = "the model declined the request" + (
                        f" ({details.category})" if details and details.category else "")
                    break
                calls = [b for b in response.content if b.type == "tool_use"]
                if not calls:
                    break                                    # the model stopped without finishing the task
                if response.stop_reason == "max_tokens":     # a cut tool input is not run
                    s.outcome.error = f"the answer reached the {MAX_TOKENS}-token limit"
                    break
                messages.append({"role": "assistant", "content": echo(response.content)})
                results = []
                for call in calls:
                    result = s.call(call.name, call.input)
                    results.append({"type": "tool_result", "tool_use_id": call.id, "content": result_blocks(result),
                                    "is_error": result.error})
                    if s.outcome.done:
                        break
                if s.outcome.done:
                    break
                messages.append({"role": "user", "content": results})
            else:
                s.outcome.error = f"stopped after {task.max_turns} turns"
        except anthropic.AuthenticationError:
            s.outcome.error = "Anthropic API: authentication failed (check ANTHROPIC_API_KEY)"
        except anthropic.APIStatusError as e:
            s.outcome.error = f"Anthropic API error {e.status_code}: {error_message(e)}"
        except anthropic.APIConnectionError as e:
            s.outcome.error = f"Anthropic API not reachable: {e}"
        return s.close()
