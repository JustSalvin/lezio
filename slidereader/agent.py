"""Agent backends. The program calls an agent for one narrow task at a time.

For each task the program decides which files the agent may write; the agent can read the project but
cannot run commands. Backends:
  claude-code    Claude Code CLI in headless mode (`claude -p`), authenticated with the user's own
                 Claude login, i.e. their subscription. No API key involved.
  anthropic-api  Planned: same tasks through the Anthropic API with a small tool loop.
"""
import json
import shutil
import subprocess
import sys

from .config import CONFIG, ROOT

READ_TOOLS = ["Read", "Glob", "Grep"]


class ClaudeCodeBackend:
    name = "claude-code"

    def check(self):
        if shutil.which("claude") is None:
            raise SystemExit("Claude Code is not installed (https://claude.com/claude-code). "
                             "Install it and log in once with `claude` (your Claude subscription).")

    def run(self, prompt, writable, log_path):
        """One headless session. `writable`: project-relative paths the agent may create or edit."""
        tools = READ_TOOLS + [f"{tool}({path})" for path in writable for tool in ("Write", "Edit")]
        cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "dontAsk"]
        if CONFIG["agent"]["model"]:
            cmd += ["--model", CONFIG["agent"]["model"]]
        cmd += ["--allowedTools", *tools]
        log_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        proc.stdin.write(prompt)
        proc.stdin.close()
        ok = False
        with open(log_path, "a") as log:
            log.write(json.dumps({"type": "task_prompt", "prompt": prompt, "writable": writable}) + "\n")
            for line in proc.stdout:
                log.write(line)
                log.flush()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ok = _show(event) or ok
        return proc.wait() == 0 and ok


class AnthropicAPIBackend:
    name = "anthropic-api"

    def check(self):
        raise SystemExit("The anthropic-api backend is planned but not implemented yet. "
                         "Set [agent] backend = \"claude-code\" in config.toml.")

    def run(self, prompt, writable, log_path):  # pragma: no cover - placeholder
        raise NotImplementedError


BACKENDS = {b.name: b for b in (ClaudeCodeBackend, AnthropicAPIBackend)}


def get_backend():
    name = CONFIG["agent"]["backend"]
    if name not in BACKENDS:
        raise SystemExit(f"Unknown agent backend '{name}' in config.toml (choose: {', '.join(BACKENDS)})")
    backend = BACKENDS[name]()
    backend.check()
    return backend


def _show(event):
    """Print a compact trace of what the agent does. Returns True for a successful final result."""
    kind = event.get("type")
    if kind == "assistant":
        for part in event.get("message", {}).get("content", []):
            if part.get("type") == "tool_use":
                inp = part.get("input", {})
                detail = inp.get("file_path") or inp.get("pattern") or ""
                print(f"      agent {part['name'].lower()}: {str(detail).replace(str(ROOT) + '/', '')[:110]}",
                      flush=True)
    elif kind == "result":
        ok = event.get("subtype") == "success" and not event.get("is_error")
        turns = event.get("num_turns")
        print(f"      agent {'finished' if ok else 'stopped: ' + str(event.get('subtype'))}"
              + (f" ({turns} turns)" if turns else ""), flush=True)
        return ok
    return False


def ask(question, choices=None, default=None):
    """Tiny interactive prompt used by the ./sr make wizard (returns the default when not interactive)."""
    if not sys.stdin.isatty():
        return default
    hint = f" [{'/'.join(map(str, choices))}]" if choices else ""
    hint += f" (default: {default})" if default not in (None, "") else ""
    while True:
        answer = input(f"{question}{hint}: ").strip()
        if not answer:
            return default
        if not choices or answer in map(str, choices):
            return answer
        print(f"  choose one of: {', '.join(map(str, choices))}")
