# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Backends with the official `openai` SDK: the OpenAI API, and local models behind an OpenAI-compatible server.

openai-api: OpenAI models through the Responses API (the API OpenAI recommends for tool calling with
reasoning). The model's reasoning goes back to it encrypted at every turn, so nothing is stored on
OpenAI's side (`store: false`). Credentials: OPENAI_API_KEY.

local: a model on this computer through Chat Completions, the API every local server implements:
Ollama (default address), LM Studio, llama.cpp, vLLM, mlx-lm... Pictures returned by tools go to the
model in a user message after the tool results (tool messages carry only text). A model without vision
gets a note instead (`vision = false`). Ollama cuts prompts longer than the model's context length without
saying so (and its default context is small): the context it reports (GET /api/ps) is compared with the
size of what lezio sends.
"""
import json
import os
import urllib.request

from .base import Backend, Session, Task, TaskOutcome, ToolResult, error_message

OPENAI_MODEL = "gpt-6.1-sol"
LOCAL_URL = "http://localhost:11434/v1"          # Ollama; LM Studio: http://localhost:1234/v1
LOCAL_MODEL = "gemma4:12b"
LOCAL_EFFORT = {"xhigh": "high", "max": "high"}  # local servers know low | medium | high


def require_openai():
    try:
        import openai  # noqa: F401
    except ImportError:
        raise SystemExit("The openai package is not installed: run .venv/bin/pip install -r requirements-video.txt")


# ======================================================================== OpenAI API (Responses)
def responses_output(result: ToolResult):
    """A tool result for function_call_output: plain text, or text and pictures as input parts."""
    texts, images = result.texts(), result.images()
    if not images:
        return "\n\n".join(texts) or "(no output)"
    return ([{"type": "input_text", "text": t} for t in texts]
            + [{"type": "input_image", "image_url": i.data_url(), "detail": "high"} for i in images])


class OpenAIAPI(Backend):
    name = "openai-api"
    summary = "OpenAI models with an OpenAI API key (paid per token)"

    def check(self):
        require_openai()
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("No OpenAI API key: set the OPENAI_API_KEY environment variable (e.g. in ~/.zshrc)")

    def run(self, task: Task) -> TaskOutcome:
        import openai

        s = Session(task)
        client = openai.OpenAI(max_retries=4, timeout=1800)
        params = {
            "model": task.model or OPENAI_MODEL,
            "instructions": task.system,
            "tools": [{"type": "function", "name": t.name, "description": t.description, "parameters": t.schema,
                       "strict": False} for t in task.tools],
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        if task.effort:
            params["reasoning"] = {"effort": task.effort}
        items = [{"role": "user", "content": task.prompt}]
        try:
            for turn in range(task.max_turns):
                response = client.responses.create(input=items, **params)
                s.outcome.turns = turn + 1
                s.model(response.model)
                if u := response.usage:
                    s.usage(input=u.input_tokens, cache_read=getattr(u.input_tokens_details, "cached_tokens", 0),
                            output=u.output_tokens)
                s.text(response.output_text)
                if response.status == "incomplete":
                    reason = getattr(response.incomplete_details, "reason", None) or "unknown reason"
                    s.outcome.error = f"the answer was cut ({reason})"
                    break
                calls = [item for item in response.output if item.type == "function_call"]
                if not calls:
                    break                                    # the model stopped without finishing the task
                items += response.output                     # reasoning and calls go back as they are
                for call in calls:
                    result = s.call(call.name, call.arguments)
                    items.append({"type": "function_call_output", "call_id": call.call_id,
                                  "output": responses_output(result)})
                    if s.outcome.done:
                        break
                if s.outcome.done:
                    break
            else:
                s.outcome.error = f"stopped after {task.max_turns} turns"
        except openai.AuthenticationError:
            s.outcome.error = "OpenAI API: authentication failed (check OPENAI_API_KEY)"
        except openai.APIStatusError as e:
            s.outcome.error = f"OpenAI API error {e.status_code}: {error_message(e)}"
        except openai.APIConnectionError as e:
            s.outcome.error = f"OpenAI API not reachable: {e}"
        return s.close()


# ======================================================================== local server (Chat Completions)
def sent_tokens(messages, tools):
    """About how many tokens of text are sent to the model (4 characters per token; pictures excluded)."""
    n = len(json.dumps(tools))
    for m in messages:
        content = m.get("content") or ""
        n += len(content) if isinstance(content, str) else sum(len(p.get("text", "")) for p in content)
        n += sum(len(c["function"]["arguments"] or "") for c in m.get("tool_calls", []))
    return n // 4


class Local(Backend):
    name = "local"
    summary = "a model on this computer (Ollama, LM Studio, llama.cpp... any OpenAI-compatible server)"

    @property
    def url(self):
        return self.settings.get("url") or LOCAL_URL

    def client(self, timeout=3600):
        import openai
        return openai.OpenAI(base_url=self.url, api_key="local", timeout=timeout, max_retries=1)

    def models(self):
        """The models named in [agent.local] (the default and the per-task ones)."""
        names = {self.settings.get("model") or LOCAL_MODEL}
        names |= {v["model"] for v in self.settings.values() if isinstance(v, dict) and v.get("model")}
        return names

    def context_length(self, model):
        """The context length a loaded model runs with, if the server is Ollama (GET /api/ps); else None."""
        base = self.url.rstrip("/").removesuffix("/v1")
        try:
            with urllib.request.urlopen(f"{base}/api/ps", timeout=5) as r:
                running = json.load(r).get("models", [])
        except (OSError, ValueError):
            return None
        names = {model, f"{model}:latest"}
        return next((m.get("context_length") for m in running if {m.get("name"), m.get("model")} & names), None)

    def check(self):
        require_openai()
        import openai
        try:
            available = {m.id for m in self.client(timeout=5).models.list()}
        except openai.APIConnectionError:
            raise SystemExit(f"No model server at {self.url}: start Ollama (the app, or `ollama serve`) or set "
                             "[agent.local] url in config.toml")
        except openai.APIError:
            return                                   # a server without a model list: try anyway
        for name in sorted(self.models()):
            if name not in available and f"{name}:latest" not in available:
                raise SystemExit(f"The server at {self.url} has no model '{name}': download it (Ollama: "
                                 f"`ollama pull {name}`) or change [agent.local] model in config.toml. "
                                 f"Models there: {', '.join(sorted(available)) or 'none'}")

    def run(self, task: Task) -> TaskOutcome:
        import openai

        s = Session(task)
        vision = self.settings.get("vision", True)
        tools = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                   "parameters": t.schema}} for t in task.tools]
        extra = {"reasoning_effort": LOCAL_EFFORT.get(task.effort, task.effort)} if task.effort else {}
        messages = [{"role": "system", "content": task.system}, {"role": "user", "content": task.prompt}]
        model = task.model or LOCAL_MODEL
        client = self.client()
        context = None
        try:
            for turn in range(task.max_turns):
                response = client.chat.completions.create(model=model, messages=messages, tools=tools, **extra)
                s.outcome.turns = turn + 1
                s.model(response.model)
                if u := response.usage:
                    s.usage(input=u.prompt_tokens, output=u.completion_tokens)
                context = context or self.context_length(model)    # known once the model is loaded
                if context and (sent := sent_tokens(messages, tools)) > context:
                    s.outcome.error = (f"{model} runs with a context of {context} tokens but lezio sent about {sent}: "
                                       "the model server cut it. Raise the context length to 32768 or more "
                                       "(Ollama: the app's settings, or OLLAMA_CONTEXT_LENGTH=32768 ollama serve)")
                    break
                choice = response.choices[0]
                s.text(choice.message.content)
                calls = choice.message.tool_calls or []
                if not calls:
                    if choice.finish_reason == "length":
                        s.outcome.error = "the answer was cut (output or context limit of the model server)"
                    break                                    # the model stopped without finishing the task
                ids = [c.id or f"call_{turn}_{k}" for k, c in enumerate(calls)]
                messages.append({"role": "assistant", "content": choice.message.content or "", "tool_calls": [
                    {"id": i, "type": "function", "function": {"name": c.function.name,
                                                               "arguments": c.function.arguments or "{}"}}
                    for i, c in zip(ids, calls)]})
                pictures = []
                for i, call in zip(ids, calls):
                    result = s.call(call.function.name, call.function.arguments or "{}")
                    text = "\n\n".join(result.texts()) or "(no output)"
                    if result.images() and not vision:
                        text += f"\n\n[{len(result.images())} picture(s) not shown: this model cannot see images]"
                    messages.append({"role": "tool", "tool_call_id": i, "content": text})
                    pictures += result.images() if vision else []
                    if s.outcome.done:
                        break
                if s.outcome.done:
                    break
                if pictures:
                    messages.append({"role": "user", "content": [
                        {"type": "text", "text": "The pictures returned by the tools above, in order."}] + [
                        {"type": "image_url", "image_url": {"url": p.data_url()}} for p in pictures]})
            else:
                s.outcome.error = f"stopped after {task.max_turns} turns"
        except openai.APIStatusError as e:
            s.outcome.error = f"model server error {e.status_code}: {error_message(e)}"
        except openai.APIConnectionError as e:
            s.outcome.error = f"model server at {self.url} not reachable: {e}"
        return s.close()
