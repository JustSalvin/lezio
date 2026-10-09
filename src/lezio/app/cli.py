"""Command line: ./lezio [pdf | lesson] [options], plus a few other commands."""
import argparse
import sys

from ..settings import DEPTHS, VISUAL_MODES
from . import commands, ui

HELP = """[bold]lezio[/] [muted]· PDF slides → narrated, animated video lecture[/]

  [accent]./lezio[/]                             wizard: choose a PDF or a lesson, then the options
  [accent]./lezio[/] <file.pdf | lesson> [...]   make or update a video (asks only what is missing)

[bold]Options[/] [muted](per-video choices, saved in the lesson)[/]
  --pages 1-20          pages to cover (default: all)
  --visual MODE         slides | mixed | animated
  --depth N             1 extensive · 2 faithful · 3 condensed · 4 short
  --instructions "..."  instructions for the agent, e.g. "Skip interactive slides such as polls."
  --id NAME             lesson name (default: from the PDF file name)
  --rewrite             write the script again from scratch (the old one is backed up)
  --no-review           skip the final review of the frames
  -y, --yes             no questions, no confirmation

[bold]Other commands[/]
  ./lezio status <lesson>                          what is done, missing or outdated
  ./lezio redo <lesson> --slides 7 [--part script|voice|video] [--note "add an example"]
  ./lezio build <lesson>                           rebuild after editing lessons/<lesson>/script.json
  ./lezio tts                                      voices and TTS options;  --try "text" to listen
  ./lezio help tools                               low-level commands

[muted]Configuration (voice, language, agent model, video quality) is in config.toml.[/]"""

TOOLS_HELP = """[bold]Low-level commands[/] [muted](the program runs them for you)[/]
  ./lezio check <lesson>                       validate the script
  ./lezio init <pdf> [--id NAME]               analyse a PDF (slide images, text lines)
  ./lezio audio <lesson>                       generate missing narration audio
  ./lezio render <lesson> [--slides 3-5] [--preview]   render slides (contact sheets in build/qa)
  ./lezio anim <lesson> --all | --slide N [--beat K]   render animations alone + contact sheets
  ./lezio join <lesson>                        assemble output/<lesson>.mp4
  ./lezio templates                            animation templates and their arguments"""


def main_parser():
    p = argparse.ArgumentParser(prog="./lezio", add_help=False)
    p.add_argument("target", nargs="?")
    p.add_argument("--pages")
    p.add_argument("--visual", choices=list(VISUAL_MODES))
    p.add_argument("--depth", type=int, choices=sorted(DEPTHS))
    p.add_argument("--instructions")
    p.add_argument("--id")
    p.add_argument("--rewrite", action="store_true")
    p.add_argument("--no-review", action="store_true")
    p.add_argument("-y", "--yes", action="store_true")
    return p


def sub_parser():
    ap = argparse.ArgumentParser(prog="./lezio")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *args):
        p = sub.add_parser(name)
        for spec in args:
            p.add_argument(*spec[0], **spec[1])
        p.set_defaults(fn=fn)
        return p

    lesson = (["lesson"], {})
    add("status", commands.status, lesson)
    from .run import redo
    add("redo", redo, lesson, (["--slides"], {"required": True}),
        (["--part"], {"choices": ("script", "voice", "video"), "default": "script"}),
        (["--note"], {}), (["--no-review"], {"action": "store_true"}), (["-y", "--yes"], {"action": "store_true"}))
    add("build", commands.build, lesson)
    add("tts", commands.tts, (["--engine"], {}), (["--try"], {"dest": "try_text"}), (["--voice"], {}),
        (["--set"], {"action": "append", "default": []}), (["--play"], {"action": "store_true"}))
    add("check", commands.check, lesson)
    add("init", commands.tool_init, (["pdf"], {}), (["--id"], {}))
    add("audio", commands.tool_audio, lesson)
    add("render", commands.tool_render, lesson, (["--slides"], {"default": ""}), (["--preview"], {"action": "store_true"}))
    add("anim", commands.tool_anim, lesson, (["--slide"], {"type": int}), (["--beat"], {"type": int}),
        (["--all"], {"action": "store_true"}))
    add("join", commands.tool_join, lesson)
    add("templates", commands.tool_templates)
    return ap


SUBCOMMANDS = {"status", "redo", "build", "tts", "check", "init", "audio", "render", "anim", "join", "templates"}


def main():
    argv = sys.argv[1:]
    if argv[:1] in (["-h"], ["--help"], ["help"]):
        ui.console.print(TOOLS_HELP if argv[1:2] == ["tools"] else HELP)
        return
    try:
        if argv and argv[0] in SUBCOMMANDS:
            a = sub_parser().parse_args(argv)
            a.fn(a)
        else:
            from .run import make
            a = main_parser().parse_args(argv)
            if not a.target and not a.yes:
                ui.banner()
            make(a)
    except KeyboardInterrupt:
        ui.console.print("\n[muted]Stopped.[/]")
        sys.exit(130)
