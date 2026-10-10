# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Interactive questions (arrow-key menus). Only used when the terminal is interactive."""
import sys

import questionary
from questionary import Choice, Separator, Style

from ..material import parse_range
from ..settings import DEPTH_HELP, DEPTHS

STYLE = Style([("qmark", "fg:#00b8d4 bold"), ("question", "bold"), ("pointer", "fg:#00b8d4 bold"),
               ("highlighted", "fg:#00b8d4 bold"), ("answer", "fg:#2e9e44 bold"), ("selected", "fg:#2e9e44"),
               ("instruction", "fg:#808080"), ("text", ""), ("disabled", "fg:#808080 italic")])


def interactive():
    return sys.stdin.isatty() and sys.stdout.isatty()


def ask(question):
    answer = question.ask()
    if answer is None:                       # Ctrl+C
        print("Stopped, nothing changed.")
        sys.exit(130)
    return answer


def choose_target(lessons, has_files):
    """lessons: [(id, description)] -> ("lesson", id) | ("new", None)"""
    choices = []
    if has_files:
        choices.append(Choice("New lesson from the files in input/", value=("new", None)))
    if lessons:
        choices.append(Separator("── continue a lesson"))
        choices += [Choice(f"{lid}  ", value=("lesson", lid), description=desc) for lid, desc in lessons]
    return ask(questionary.select("What do you want to work on?", choices=choices, style=STYLE))


def sources(files, checked=()):
    """files: [(path, label)] -> chosen paths (at least one)."""
    return ask(questionary.checkbox(
        "Study material for the lesson", style=STYLE, instruction="(space = select, enter = confirm)",
        choices=[Choice(label, value=path, checked=path in checked) for path, label in files],
        validate=lambda chosen: bool(chosen) or "choose at least one file"))


def lesson_name(default):
    return ask(questionary.text("Lesson name", default=default, style=STYLE,
                                validate=lambda t: bool(t.strip()) or "required"))


def existing_action(summary):
    return ask(questionary.select(f"{summary}\n  What now?", style=STYLE, choices=[
        Choice("Update the video", "update", description="write what is missing, rebuild what changed"),
        Choice("Change the study material", "sources", description="add or remove files, change page ranges "
               "(the lesson is planned again; the current one is backed up)"),
        Choice("Change the depth", "depth", description="rewrites the lesson (backed up)"),
        Choice("Change the instructions for the agent", "instructions"),
        Choice("Rewrite the lesson from scratch", "rewrite"),
    ]))


def focus(name, n_items, unit, default=""):
    def ok(text):
        try:
            return bool(parse_range(text, range(1, n_items + 1))) or f"{unit}s between 1 and {n_items}"
        except ValueError:
            return "e.g. 1-20 or 1,3,5-9 (empty = all)"
    return ask(questionary.text(f"{unit.capitalize()}s of {name} to use (1-{n_items}, empty = all)", default=default,
                                validate=ok, style=STYLE)).strip()


def depth(default):
    return ask(questionary.select("Depth", default=default, style=STYLE, choices=[
        Choice(f"{n} · {DEPTHS[n]}", n, description=DEPTH_HELP[n]) for n in DEPTHS]))


def instructions(default=""):
    return ask(questionary.text("Instructions for the agent (optional)", default=default, style=STYLE,
                                instruction="anything you want: e.g. \"Show the original slides\", \"A board "
                                            "drawn by hand\", \"Skip the live polls\".")).strip()


def confirm(message, default=True):
    return ask(questionary.confirm(message, default=default, style=STYLE))
