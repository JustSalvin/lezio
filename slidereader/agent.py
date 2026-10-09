"""Agent backends: who does the creative steps (writing the script, reviewing frames).

The program prepares everything and runs every mechanical step itself; the agent only follows
AGENTS.md. Backends:
  claude-code    Claude Code CLI in headless mode (`claude -p`), authenticated with the user's own
                 Claude login, i.e. their subscription. No API key involved.
  anthropic-api  Planned: same prompts through the Anthropic API with a tool loop.
"""
import json
import shutil
import subprocess
import sys

from .config import CONFIG, ROOT

# The agent may read anything, but write only scripts and custom animations, and run only safe ./sr commands
ALLOWED_TOOLS = [
    "Read", "Glob", "Grep",
    "Write(scripts/**)", "Edit(scripts/**)", "Write(animations/**)", "Edit(animations/**)",
    "Bash(./sr check *)", "Bash(./sr anim *)", "Bash(./sr templates)", "Bash(./sr status *)",
]

WRITE_PROMPT = """You are the script-writing agent of slide-reader. Read AGENTS.md now and follow it exactly.

Lesson id: {id}
The settings are already in scripts/{id}.json (keep them unchanged):
  visual = {visual}, depth = {depth} ({depth_name}), pages = {pages}, language = {language}

Do the "Agent workflow" of AGENTS.md (understand the slides, write the script, custom animations if
needed, ./sr check, ./sr anim checks). Do NOT run ./sr audio, ./sr render, ./sr build or ./sr join:
the program runs them after you. Finish when `./sr check {id}` passes and every animation contact sheet
looks right, then reply with a short summary (slides covered, animations used, anything doubtful)."""

FIX_PROMPT = """You are the script-writing agent of slide-reader (instructions: AGENTS.md).
`./sr check {id}` reports errors in scripts/{id}.json. Fix them, run ./sr check {id} until it passes,
then reply with a one-line summary.

{report}"""

REVIEW_PROMPT = """You are the review agent of slide-reader. Read the "Review pass" section of AGENTS.md
and follow it for lesson {id}. The final renders are done; their contact sheets are
build/{id}/qa/final_slide_NN.png. Fix only real visual defects, re-check with ./sr check and ./sr anim,
and reply with a short list of what you changed (or "no changes")."""


class ClaudeCodeBackend:
    name = "claude-code"

    def check(self):
        if shutil.which("claude") is None:
            raise SystemExit("Claude Code is not installed (https://claude.com/claude-code). "
                             "Install it and log in once with `claude` (your Claude subscription).")

    def run(self, prompt, log_path):
        """Run one headless agent session; stream a readable progress log. Returns True on success."""
        cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "dontAsk"]
        if CONFIG["agent"]["model"]:
            cmd += ["--model", CONFIG["agent"]["model"]]
        cmd += ["--allowedTools", *ALLOWED_TOOLS]
        log_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        proc.stdin.write(prompt)
        proc.stdin.close()
        ok = False
        with open(log_path, "a") as log:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print(f"    {line.rstrip()}")
                    continue
                ok = _show(event) or ok
        return proc.wait() == 0 and ok


class AnthropicAPIBackend:
    name = "anthropic-api"

    def check(self):
        raise SystemExit("The anthropic-api backend is planned but not implemented yet. "
                         "Set [agent] backend = \"claude-code\" in config.toml.")

    def run(self, prompt, log_path):  # pragma: no cover - placeholder
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
    """Print a compact view of a stream-json event. Returns True for a successful final result."""
    kind = event.get("type")
    if kind == "assistant":
        for part in event.get("message", {}).get("content", []):
            if part.get("type") == "text" and part["text"].strip():
                first = part["text"].strip().splitlines()[0]
                print(f"  agent: {first[:150]}", flush=True)
            elif part.get("type") == "tool_use":
                inp = part.get("input", {})
                detail = inp.get("command") or inp.get("file_path") or inp.get("pattern") or ""
                print(f"    -> {part['name']}: {str(detail).replace(str(ROOT) + '/', '')[:140]}", flush=True)
    elif kind == "result":
        turns, cost = event.get("num_turns"), event.get("total_cost_usd")
        status = "done" if event.get("subtype") == "success" else f"stopped ({event.get('subtype')})"
        extra = f", {turns} turns" if turns else ""
        extra += f", ~${cost:.2f} of usage (covered by the subscription)" if cost else ""
        print(f"  agent {status}{extra}", flush=True)
        if event.get("result"):
            print("\n" + event["result"].strip() + "\n", flush=True)
        return event.get("subtype") == "success" and not event.get("is_error")
    return False


def ask(question, choices=None, default=None):
    """Tiny interactive prompt used by the ./sr make wizard."""
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
