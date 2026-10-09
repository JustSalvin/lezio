"""Interactive questions (arrow-key menus). Only used when the terminal is interactive."""
import sys

import questionary
from questionary import Choice, Separator, Style

from ..script import parse_pages
from ..settings import DEPTH_HELP, DEPTHS, VISUAL_MODES

STYLE = Style([("qmark", "fg:#00b8d4 bold"), ("question", "bold"), ("pointer", "fg:#00b8d4 bold"),
               ("highlighted", "fg:#00b8d4 bold"), ("answer", "fg:#2e9e44 bold"),
               ("instruction", "fg:#808080"), ("text", ""), ("disabled", "fg:#808080 italic")])


def interactive():
    return sys.stdin.isatty() and sys.stdout.isatty()


def _ask(question):
    answer = question.ask()
    if answer is None:                       # Ctrl+C
        print("Stopped, nothing changed.")
        sys.exit(130)
    return answer


def choose_target(lessons, pdfs):
    """lessons: [(id, description)], pdfs: [(path, name)] -> ("lesson", id) | ("pdf", path)"""
    choices = []
    if lessons:
        choices.append(Separator("── continue a lesson"))
        choices += [Choice(f"{lid}  ", value=("lesson", lid), description=desc) for lid, desc in lessons]
    if pdfs:
        choices.append(Separator("── new lesson from input/"))
        choices += [Choice(name, value=("pdf", path)) for path, name in pdfs]
    return _ask(questionary.select("What do you want to work on?", choices=choices, style=STYLE))


def lesson_name(default):
    return _ask(questionary.text("Lesson name", default=default, style=STYLE,
                                 validate=lambda t: bool(t.strip()) or "required"))


def existing_action(summary):
    return _ask(questionary.select(f"{summary}\n  What now?", style=STYLE, choices=[
        Choice("Update the video", "update", description="write what is missing, rebuild what changed"),
        Choice("Change the pages", "pages", description="slides already written are kept"),
        Choice("Change visual mode or depth", "style", description="rewrites the script (backed up)"),
        Choice("Change the instructions for the agent", "instructions"),
        Choice("Rewrite the script from scratch", "rewrite"),
    ]))


def pages(n_pages, default=""):
    def ok(text):
        try:
            return bool(parse_pages(text, range(1, n_pages + 1))) or f"pages between 1 and {n_pages}"
        except ValueError:
            return "e.g. 1-20 or 1,3,5-9 (empty = all)"
    return _ask(questionary.text(f"Pages to cover (1-{n_pages}, empty = all)", default=default, validate=ok,
                                 style=STYLE)).strip()


def visual(default):
    return _ask(questionary.select("Visual mode", default=default, style=STYLE, choices=[
        Choice(name, name, description=desc) for name, desc in VISUAL_MODES.items()]))


def depth(default):
    return _ask(questionary.select("Depth", default=default, style=STYLE, choices=[
        Choice(f"{n} · {DEPTHS[n]}", n, description=DEPTH_HELP[n]) for n in DEPTHS]))


def instructions(default=""):
    return _ask(questionary.text("Instructions for the agent (optional)", default=default, style=STYLE,
                                 instruction="e.g. Skip interactive slides such as live polls or quizzes.")).strip()


def confirm(message, default=True):
    return _ask(questionary.confirm(message, default=default, style=STYLE))
