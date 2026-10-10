"""Command line: ./lezio [files... | lesson] [options], plus a few other commands."""
import argparse
import sys

from ..settings import DEPTHS
from . import commands, ui

HELP = """[bold]lezio[/] [muted]· study material → narrated video lesson[/]

  [accent]./lezio[/]                                 wizard: choose files or a lesson, then the options
  [accent]./lezio[/] <files... | lesson> [...]        make or update a video (asks only what is missing)

  Files: PDF, Markdown, text, Word (.docx), pictures (.png .jpg .webp) - one or more, of any kind.

[bold]Options[/] [muted](per-video choices, saved in the lesson)[/]
  --depth N               1 extensive · 2 faithful · 3 condensed · 4 short
  --instructions "..."    anything you want from the lesson, e.g. "Show the original slides and highlight
                          the line being discussed", "A hand-drawn board", "Use the dark theme"
  --focus "FILE:PAGES"    use only some pages of a PDF, e.g. --focus "slides.pdf:1-20" (repeatable)
  --id NAME               lesson name (default: from the first file name); with files: add them to it
  --rewrite               plan and write the lesson again from scratch (the old one is backed up)
  --no-review             skip the final review of the frames
  -y, --yes               no questions, no confirmation

[bold]Other commands[/]
  ./lezio status <lesson>                          segments: what is done, missing or outdated
  ./lezio redo <lesson> --segments s03,s05 [--part script|voice|video] [--note "add an example"]
  ./lezio build <lesson>                           rebuild after editing the lesson by hand
  ./lezio config                                   change the configuration (voice, agent, video, theme...)
  ./lezio themes [--preview NAME]                  visual themes (house style presets) and their preview
  ./lezio templates [--demo NAME|all]              scene templates the agent uses; render their examples
  ./lezio tts                                      voices and TTS options;  --try "text" to listen
  ./lezio help tools                               low-level commands

[muted]Configuration (voice, language, agent model, video quality) is in config.toml: ./lezio config.[/]"""

TOOLS_HELP = """[bold]Low-level commands[/] [muted](the program runs them for you)[/]
  ./lezio check <lesson>                         validate script and scene code
  ./lezio ingest <lesson>                        read new or changed sources, list the material
  ./lezio audio <lesson>                         generate missing narration audio
  ./lezio render <lesson> [--segments s01,s02] [--preview]   render segments (step sheets in build/qa)
  ./lezio join <lesson>                          assemble output/<lesson>.mp4
  ./lezio scene-api                              the helper library available to scene code"""


def main_parser():
    p = argparse.ArgumentParser(prog="./lezio", add_help=False)
    p.add_argument("targets", nargs="*")
    p.add_argument("--depth", type=int, choices=sorted(DEPTHS))
    p.add_argument("--instructions")
    p.add_argument("--focus", action="append")
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
    add("redo", redo, lesson, (["--segments"], {"required": True}),
        (["--part"], {"choices": ("script", "voice", "video"), "default": "script"}),
        (["--note"], {}), (["--no-review"], {"action": "store_true"}), (["-y", "--yes"], {"action": "store_true"}))
    add("build", commands.build, lesson)
    add("config", commands.config)
    add("themes", commands.themes, (["--preview"], {}))
    add("templates", commands.templates, (["--demo"], {}), (["--open"], {"action": "store_true"}))
    add("tts", commands.tts, (["--engine"], {}), (["--try"], {"dest": "try_text"}), (["--voice"], {}),
        (["--set"], {"action": "append", "default": []}), (["--play"], {"action": "store_true"}))
    add("check", commands.check, lesson)
    add("ingest", commands.tool_ingest, lesson)
    add("audio", commands.tool_audio, lesson)
    add("render", commands.tool_render, lesson, (["--segments"], {"default": ""}),
        (["--preview"], {"action": "store_true"}))
    add("join", commands.tool_join, lesson)
    add("scene-api", commands.tool_scene_api)
    return ap


SUBCOMMANDS = {"status", "redo", "build", "config", "themes", "templates", "tts", "check", "ingest", "audio", "render", "join", "scene-api"}


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
            if not a.targets and not a.yes:
                ui.banner()
            make(a)
    except KeyboardInterrupt:
        ui.console.print("\n[muted]Stopped.[/]")
        sys.exit(130)
