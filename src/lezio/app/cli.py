"""Command line: ./lezio <command> [...]. Every command is described once, in COMMANDS: the help pages and
the argument parsers are made from that description."""
import argparse
import sys
from dataclasses import dataclass, field

from ..settings import DEPTHS
from . import commands, ui


@dataclass
class Command:
    name: str
    group: str
    summary: str
    usage: str = ""
    options: list = field(default_factory=list)      # (flags or "<arg>", help, argparse kwargs or None)
    examples: list = field(default_factory=list)
    run: object = None


def _run_make(a):
    from .run import make
    make(a)


def _run_redo(a):
    from .run import redo
    redo(a)


DEPTH_HELP = " · ".join(f"{n} {name}" for n, name in DEPTHS.items())
COMMANDS = [
    Command("make", "Make a lesson", "make a new lesson from files, or update a lesson",
            "[files... | lesson] [options]   (no arguments: wizard)",
            [("files... | lesson", "study material (PDF, Markdown, text, Word, pictures; one or more files) or the "
              "name of an existing lesson", None),
             ("--depth N", f"{DEPTH_HELP} (default 2)", {"type": int, "choices": sorted(DEPTHS)}),
             ("--instructions TEXT", "anything you want from this lesson, e.g. \"Show the original slides\", "
              "\"Use the dark theme\", \"Skip the live polls\"", {}),
             ("--focus FILE:PAGES", "use only some pages of a PDF, e.g. --focus \"slides.pdf:1-20\" (repeatable)",
              {"action": "append"}),
             ("--id NAME", "lesson name (default: from the first file); with files, adds them to that lesson", {}),
             ("--rewrite", "plan and write the lesson again from scratch (the old one is backed up)",
              {"action": "store_true"}),
             ("--no-review", "skip the final review of the frames", {"action": "store_true"}),
             ("-y, --yes", "no questions and no confirmation", {"action": "store_true"})],
            ["./lezio make", "./lezio make input/slides.pdf input/appunti.md",
             "./lezio make input/slides.pdf --focus \"slides.pdf:21-40\" --depth 3 --yes",
             "./lezio make my-lesson"], _run_make),
    Command("redo", "Make a lesson", "write, voice or render some segments again", "<lesson> <segments> [options]",
            [("<lesson>", "the lesson", None), ("<segments>", "segments, e.g. s03 or s03,s05", None),
             ("--part PART", "script (default: the agent writes them again) · voice · video",
              {"choices": ("script", "voice", "video"), "default": "script"}),
             ("--note TEXT", "what you want changed, for the agent", {}),
             ("--no-review", "skip the final review", {"action": "store_true"}),
             ("-y, --yes", "no confirmation", {"action": "store_true"})],
            ["./lezio redo my-lesson s03 --note \"add an example\"", "./lezio redo my-lesson s03,s05 --part voice"],
            _run_redo),
    Command("list", "Your lessons", "your lessons: title, how much is written, the video", "", [],
            ["./lezio list"], commands.lessons),
    Command("status", "Your lessons", "what is done in a lesson: segments, voice, video", "<lesson>",
            [("[lesson]", "a lesson (without it: the list of lessons)", {"nargs": "?"})],
            ["./lezio status my-lesson"], commands.status),
    Command("rename", "Your lessons", "rename a lesson (videos already in output/ are not touched)", "<lesson> <new-name>",
            [("<lesson>", "the lesson", None), ("<new-name>", "the new name", None)],
            ["./lezio rename my-lesson binario"], commands.rename),
    Command("copy", "Your lessons", "duplicate a lesson, e.g. to try other instructions or depth", "<lesson> <new-name>",
            [("<lesson>", "the lesson", None), ("<new-name>", "the name of the copy", None)],
            ["./lezio copy binario binario-breve", "./lezio make binario-breve --depth 4 --yes"], commands.copy),
    Command("delete", "Your lessons", "move a lesson to the Trash (output/ and input/ are not touched)",
            "<lesson> [--yes]", [("<lesson>", "the lesson", None),
                                 ("-y, --yes", "no confirmation", {"action": "store_true"})],
            ["./lezio delete binario-breve"], commands.delete),
    Command("build", "Make a lesson", "voice and video again without the agent (after editing by hand)", "<lesson>", [("<lesson>", "the lesson", None)], ["./lezio build my-lesson"],
            commands.build),
    Command("config", "Look and sound", "change the configuration: voice, theme, subtitles, agent, video",
            "[show]", [("[show]", "print the configuration instead of opening the menus",
                        {"nargs": "?", "choices": ("show",)})], ["./lezio config", "./lezio config show"],
            commands.config),
    Command("voices", "Look and sound", "the speech engines and their voices; listen to one", "[options]",
            [("--try TEXT", "say TEXT with the configured voice (or the one given)", {"dest": "try_text"}),
             ("--engine NAME", "another engine than the configured one", {}),
             ("--voice NAME", "another voice", {}),
             ("--set KEY=VALUE", "another value for an option of the engine (repeatable)",
              {"action": "append", "default": []}),
             ("--play", "also play the sample (otherwise it is only saved in voice-samples/)",
              {"action": "store_true"})],
            ["./lezio voices", "./lezio voices --try \"Ciao a tutti.\" --voice it_male --play"], commands.voices),
    Command("themes", "Look and sound", "the visual themes (colors, fonts, sizes); preview one", "[--preview NAME]",
            [("--preview NAME", "render a picture of a theme (output/theme_NAME.png)", {})],
            ["./lezio themes", "./lezio themes --preview chalkboard"], commands.themes),
    Command("templates", "Look and sound", "the scene templates lessons are built with; see examples",
            "[--demo NAME|all]",
            [("--demo NAMES", "render the example of some templates (comma separated) or all: the step sheets "
              "are written to lessons/_templates/build/qa/", {}),
             ],
            ["./lezio templates", "./lezio templates --demo flow", "./lezio templates --demo all"],
            commands.templates),
    Command("tools", "More", "low-level commands (the program runs them for you)", "<command> ...",
            [("check <lesson>", "validate the lesson: settings, blocks, narration, templates, refs", None),
             ("ingest <lesson>", "read new or changed sources and list the material", None),
             ("audio <lesson>", "generate the missing narration audio", None),
             ("render <lesson> [--segments s01,s02] [--preview]", "render segments (step sheets in build/qa)",
              None),
             ("join <lesson>", "assemble output/<lesson>.mp4 (and the subtitles)", None),
             ("scene-api", "the API the agent sees to write its own templates", None)],
            ["./lezio tools check my-lesson", "./lezio tools render my-lesson --segments s03 --preview"],
            commands.tools),
    Command("help", "More", "the options of a command", "[command]", [], ["./lezio help make"], None),
]
BY_NAME = {c.name: c for c in COMMANDS}
GROUPS = ["Make a lesson", "Your lessons", "Look and sound", "More"]


# ------------------------------------------------------------------ help pages
def overview():
    ui.banner()
    rows = []
    for group in GROUPS:
        rows.append(["", ""])
        rows.append([f"[bold]{group}[/]", ""])
        rows += [[f"  [accent]{c.name}[/] {ui.escape(c.usage.split('   ')[0])}", c.summary]
                 for c in COMMANDS if c.group == group]
    ui.table(["", ""], rows[1:])
    ui.console.print()
    ui.hint("start:        ./lezio make")
    ui.hint("your lessons: ./lezio list")
    ui.hint("a command:    ./lezio help make")
    ui.info("Configuration (voice, theme, subtitles, agent model, video) is in config.toml: ./lezio config.")


def command_help(name):
    c = BY_NAME.get(name)
    if c is None:
        ui.fail(f"unknown command '{name}'", "./lezio help")
    ui.console.print(f"[bold accent]./lezio {c.name}[/] {ui.escape(c.usage)}\n[muted]{c.summary}[/]")
    if c.options:
        ui.section("Options" if c.name != "tools" else "Commands")
        ui.table(["", ""], [[f"[accent]{ui.escape(flags)}[/]", ui.escape(text)] for flags, text, _ in c.options])
    if c.examples:
        ui.section("Examples")
        for e in c.examples:
            ui.console.print(f"  {ui.escape(e)}")


# ------------------------------------------------------------------ parsing
class Parser(argparse.ArgumentParser):
    def error(self, message):
        ui.fail(message, f"./lezio help {self.prog.split()[-1]}")


def parser_for(c):
    p = Parser(prog=f"./lezio {c.name}", add_help=False)
    if c.name == "make":
        p.add_argument("targets", nargs="*")
    elif c.name == "redo":
        p.add_argument("lesson")
        p.add_argument("segments")
    elif c.name in ("build", "delete"):
        p.add_argument("lesson")
    elif c.name in ("rename", "copy"):
        p.add_argument("lesson")
        p.add_argument("name")
    for flags, _, kw in c.options:
        if kw is None:
            continue
        names = [f.split()[0] for f in flags.split(", ")]
        if names[0].startswith("["):                  # an optional positional
            p.add_argument(names[0].strip("[]"), **kw)
        else:
            p.add_argument(*names, **kw)
    return p


def tools_parser():
    p = Parser(prog="./lezio tools", add_help=False)
    sub = p.add_subparsers(dest="tool", required=True, parser_class=Parser)
    for name in ("check", "ingest", "audio", "join"):
        sub.add_parser(name, add_help=False).add_argument("lesson")
    r = sub.add_parser("render", add_help=False)
    r.add_argument("lesson")
    r.add_argument("--segments", default="")
    r.add_argument("--preview", action="store_true")
    sub.add_parser("scene-api", add_help=False)
    return p


def main():
    argv = sys.argv[1:]
    try:
        if not argv or argv[0] in ("-h", "--help"):
            overview()
            return
        name, rest = argv[0], argv[1:]
        if name == "help":
            command_help(rest[0]) if rest else overview()
            return
        if name not in BY_NAME:
            from pathlib import Path

            from ..lesson import lesson_exists
            looks_like_target = Path(name).exists() or lesson_exists(name)
            ui.fail(f"unknown command '{name}'", f"to make a lesson: ./lezio make {' '.join(argv)}"
                    if looks_like_target else "the commands: ./lezio help")
        if rest[:1] in (["-h"], ["--help"]):
            command_help(name)
            return
        c = BY_NAME[name]
        a = tools_parser().parse_args(rest) if name == "tools" else parser_for(c).parse_args(rest)
        c.run(a)
    except KeyboardInterrupt:
        ui.console.print("\n[muted]Stopped.[/]")
        sys.exit(130)
    except SystemExit as e:
        if isinstance(e.code, str):                   # errors raised as messages deeper in the program
            message, _, hint = e.code.partition(". Start one with: ")
            ui.fail(ui.escape(message), ui.escape(hint) if hint else None)
        raise
