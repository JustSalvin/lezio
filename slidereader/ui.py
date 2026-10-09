"""Interactive questions of the wizard."""
import sys


def ask(question, choices=None, default=None):
    """Ask on the terminal; returns the default when not interactive or on an empty answer."""
    if not sys.stdin.isatty():
        return default
    hint = f" [{'/'.join(map(str, choices))}]" if choices else ""
    hint += f" (default: {default})" if default not in (None, "") else ""
    while True:
        try:
            answer = input(f"{question}{hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nStopped, nothing changed.")
            sys.exit(130)
        if not answer:
            return default
        if not choices or answer in map(str, choices):
            return answer
        print(f"  choose one of: {', '.join(map(str, choices))}")
