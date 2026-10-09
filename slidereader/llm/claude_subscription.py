"""Backend: Claude through the Claude Agent SDK, authenticated with the user's Claude Code login
(Claude subscription, no API key).

The session is isolated: no built-in tools (no files, shell or web), no project or user settings,
no other MCP servers. The model only sees the task's system prompt, message and tools.
"""
import asyncio
import json
import logging
import shutil
import time

from .base import Backend, Task, TaskOutcome, ToolResult


logging.getLogger("claude_agent_sdk").setLevel(logging.ERROR)   # keep SDK info out of the console


class ClaudeSubscription(Backend):
    name = "claude-subscription"

    def __init__(self, model=""):
        self.model = model or None

    def check(self):
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError:
            raise SystemExit("claude-agent-sdk is not installed: run ./setup.sh")
        if shutil.which("claude") is None:
            print("note: Claude Code is not on PATH; the SDK's bundled copy is used "
                  "(log in once with `claude` so the subscription is available)")

    def run(self, task: Task) -> TaskOutcome:
        return asyncio.run(self._run(task))

    async def _run(self, task: Task) -> TaskOutcome:
        from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage,
                                      TextBlock, ToolUseBlock, create_sdk_mcp_server, tool)
        from claude_agent_sdk import ToolAnnotations

        state = {"done": False}
        log = open(task.log_path, "a") if task.log_path else None

        def write_log(kind, payload):
            if log:
                log.write(json.dumps({"t": round(time.time(), 1), "task": task.label, kind: payload},
                                     ensure_ascii=False, default=str) + "\n")
                log.flush()

        def wrap(t):
            @tool(t.name, t.description, t.schema, annotations=ToolAnnotations(maxResultSizeChars=4_000_000))
            async def handler(args):
                try:
                    result = t.handler(args)
                except Exception as e:  # noqa: BLE001 - report program errors to the model, keep going
                    result = ToolResult([f"Internal error while running {t.name}: {e!r}"], error=True)
                state["done"] = state["done"] or result.done
                write_log("tool_result", {"tool": t.name, "error": result.error, "done": result.done,
                                          "text": [c for c in result.content if isinstance(c, str)]})
                content = [{"type": "text", "text": c} if isinstance(c, str)
                           else {"type": "image", "data": c.b64(), "mimeType": c.mime} for c in result.content]
                return {"content": content, "is_error": result.error}
            return handler

        server = create_sdk_mcp_server(name="slidereader", version="1.0.0", tools=[wrap(t) for t in task.tools])
        names = [f"mcp__slidereader__{t.name}" for t in task.tools]
        options = ClaudeAgentOptions(
            system_prompt=task.system,
            tools=[],                         # no built-in tools at all
            mcp_servers={"slidereader": server},
            strict_mcp_config=True,
            allowed_tools=names,
            setting_sources=[],               # do not load CLAUDE.md, settings, hooks, skills
            max_turns=task.max_turns,
            model=self.model,
            max_buffer_size=64 * 1024 * 1024,     # tool results carry images
            stderr=lambda line: write_log("cli_stderr", line),
        )
        outcome = TaskOutcome(done=False)
        write_log("prompt", {"system": task.system, "user": task.prompt})
        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(task.prompt)
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock) and block.text.strip():
                                outcome.text = block.text.strip()
                                write_log("text", outcome.text)
                            elif isinstance(block, ToolUseBlock):
                                short = block.name.replace("mcp__slidereader__", "")
                                arg = {k: v for k, v in block.input.items() if k in ("slides", "numbers", "slide")}
                                hint = (f" {arg['numbers']}" if "numbers" in arg else
                                        f" slide {arg['slide']}" if "slide" in arg and isinstance(arg["slide"], int)
                                        else "")
                                print(f"      agent -> {short}{hint}", flush=True)
                                write_log("tool_use", {"tool": short, "input": block.input})
                    elif isinstance(message, ResultMessage):
                        outcome.turns = message.num_turns
                        if message.is_error:
                            outcome.error = str(message.subtype)
                    if state["done"]:
                        await client.interrupt()
                        break
        except Exception as e:  # noqa: BLE001
            outcome.error = repr(e)
        finally:
            if log:
                log.close()
        outcome.done = state["done"]
        return outcome
