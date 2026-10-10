# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Backend: Claude through the Claude Agent SDK, authenticated with the user's Claude Code login
(Claude subscription, no API key).

The session is isolated: no built-in tools (no files, shell or web), no project or user settings,
no other MCP servers. The model only sees the task's system prompt, message and tools.
"""
import asyncio
import logging

from .base import Backend, Session, Task, TaskOutcome

logging.getLogger("claude_agent_sdk").setLevel(logging.ERROR)   # keep SDK info out of the console


class ClaudeSubscription(Backend):
    name = "claude-subscription"
    summary = "Claude with your Claude Code login (subscription, no API key)"

    def check(self):
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError:
            raise SystemExit("claude-agent-sdk is not installed: run ./setup.sh")

    def run(self, task: Task) -> TaskOutcome:
        return asyncio.run(self._run(task))

    async def _run(self, task: Task) -> TaskOutcome:
        from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage,
                                      TextBlock, ToolAnnotations, ToolUseBlock, create_sdk_mcp_server, tool)

        s = Session(task)

        def wrap(t):
            @tool(t.name, t.description, t.schema, annotations=ToolAnnotations(maxResultSizeChars=4_000_000))
            async def handler(args):
                result = s.execute(t.name, args)
                content = [{"type": "text", "text": c} if isinstance(c, str)
                           else {"type": "image", "data": c.b64(), "mimeType": c.mime} for c in result.content]
                return {"content": content, "is_error": result.error}
            return handler

        server = create_sdk_mcp_server(name="lezio", version="1.0.0", tools=[wrap(t) for t in task.tools])
        options = ClaudeAgentOptions(
            system_prompt=task.system,
            tools=[],                         # no built-in tools at all
            mcp_servers={"lezio": server},
            strict_mcp_config=True,
            allowed_tools=[f"mcp__lezio__{t.name}" for t in task.tools],
            setting_sources=[],               # do not load CLAUDE.md/AGENTS.md, settings, hooks, skills
            max_turns=task.max_turns,
            model=task.model or None,
            effort=task.effort or None,
            max_buffer_size=64 * 1024 * 1024,  # tool results carry images
            stderr=lambda line: s.log("cli_stderr", line),
        )
        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(task.prompt)
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        s.model(message.model)
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                s.text(block.text)
                            elif isinstance(block, ToolUseBlock):
                                s.tool_use(block.name.replace("mcp__lezio__", ""), block.input)
                    elif isinstance(message, ResultMessage):
                        s.outcome.turns = message.num_turns
                        if message.is_error:
                            s.outcome.error = str(message.subtype)
                    if s.outcome.done:
                        await client.interrupt()
                        break
        except Exception as e:  # noqa: BLE001
            s.outcome.error = repr(e)
        return s.close()
