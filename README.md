# lezio

Turn **study material** — slide decks, notes, documents, pictures — into a **narrated video lesson**.
A synthetic voice explains the material like a teacher, while scenes written for the lesson (diagrams
that build up, animations, worked examples written step by step, clean slides, original figures) change
in sync with the voice. How to show each part is decided by the agent, following **teaching guidelines**
drawn from research on learning from video ([docs/teaching-guidelines.md](docs/teaching-guidelines.md)).

lezio is a **program**. It runs the whole process — reading the material, validation, speech synthesis,
rendering, editing — and calls an LLM only for the tasks that need judgment: planning the lesson, writing
the narration and the scene of each segment, and checking the rendered frames. In each task the model
works only through tools defined by the program (read the material, look at pages and figures, submit a
segment — checked and previewed on the spot —, ...): it has no files, shell or web.

```
./lezio make input/slides.pdf input/appunti.md
  ✓ Reading the material          2 sources · 31 pages/sections in scope
  ✓ Planning the lesson           9 segments · about 14 min                  agent
  ✓ Writing the lesson            9 segments · 84 narration pieces           agent
  ✓ Generating the voice          84 new pieces                              local TTS
  ✓ Rendering the video           9 segments
  ✓ Reviewing the video           no problems found                          agent
  ✓ Assembling the final video    13m 40s
```

## Requirements

- macOS on **Apple Silicon** (M1 or newer), ~6 GB of free disk space
- [Homebrew](https://brew.sh)
- Python 3.11+ (installed automatically if you use [mise](https://mise.jdx.dev))
- **[Claude Code](https://claude.com/claude-code)**, logged in once with `claude` using your Claude
  subscription: the program talks to Claude through the Claude Agent SDK with that login (no API key).

## Installation

```bash
./setup.sh
```

Installs `cairo`/`pkgconf` with Homebrew, creates two virtual environments inside the project (`.venv`
for the program and video, `.venv-tts` for speech) and downloads the speech model.

## Usage

```bash
./lezio                                        # the commands, at a glance
./lezio make                                   # wizard: arrow-key menus for files or lesson and options
./lezio make input/slides.pdf                  # asks only what is missing
./lezio make input/slides.pdf input/appunti.md input/schema.png   # several files, of any kind
./lezio make input/slides.pdf --focus "slides.pdf:21-40" --depth 2 --yes   # no questions
./lezio make input/slides.pdf --instructions "Mostra le slide originali ed evidenzia la riga di cui parli"
./lezio make my-lesson                         # continue / update an existing lesson
```

**Study material**: PDF (slides or documents), Markdown and plain text, Word (`.docx`), pictures (`.png`,
`.jpg`, `.webp`) — one or more files of any kind in the same lesson. Files outside `input/` are copied
there.

Before starting, a summary shows material, depth, theme, voice, agent model, instructions and the state of the
lesson; after planning, the list of segments is shown for confirmation. Each step runs with a live
progress line. Choices are saved in the lesson, so `./lezio make <lesson>` later writes only what is missing and
rebuilds only what changed; it is resumable if interrupted.

On an existing lesson the wizard offers: update the video, change the study material (add/remove files,
page ranges), change the depth (the lesson is planned and written again, the old one is backed up),
change the instructions, rewrite from scratch.

### Options (per-video choices, saved in the lesson)

| Option | Meaning |
|---|---|
| `--depth N` | `1` extensive · `2` faithful (default) · `3` condensed · `4` short |
| `--instructions "..."` | anything else you want from this lesson, e.g. `"Show the original slides"`, `"A board drawn by hand"`, `"Use the dark theme"`, `"Skip the live polls"` |
| `--focus "FILE:PAGES"` | only some pages of a PDF, e.g. `--focus "slides.pdf:1-20"` (repeatable) |
| `--id NAME` | lesson name (default: from the first file); with files, adds them to that lesson |
| `--rewrite` | plan and write the lesson again from scratch (the old one is backed up) |
| `--no-review` | skip the final review of the frames |
| `-y`, `--yes` | no questions and no confirmation |

### Other commands

```bash
./lezio list                                              # your lessons
./lezio status <lesson>                                   # segments: written, voice, video up to date?
./lezio rename <lesson> <new-name>                        # rename a lesson (output/ is not touched)
./lezio copy <lesson> <new-name>                          # duplicate it (e.g. to try other instructions)
./lezio delete <lesson>                                   # move it to the Trash (output/ and input/ are not touched)
./lezio redo <lesson> s03 --note "add an example"         # the agent rewrites segment s03
./lezio redo <lesson> s03,s05 --part voice                # new voice takes   (--part video: re-render)
./lezio build <lesson>                                    # after editing the lesson by hand
./lezio config                                            # change the configuration with menus (show: print it)
./lezio voices                                            # speech engines, options and voices
./lezio voices --try "Ciao a tutti." --voice it_male --play
./lezio themes                                            # visual themes;  --preview NAME to see one
./lezio templates                                         # scene templates;  --demo NAME --open to see one
./lezio tools                                             # low-level commands (check, ingest, audio, render, join)
./lezio help <command>                                    # the options of a command
```

## How a lesson looks

There are no fixed "styles": for every segment the agent chooses how to teach it — a diagram that builds
up, an animation of a process, a worked example written step by step, a comparison, a clean slide, an
original figure — following the teaching guidelines in [docs/teaching-guidelines.md](docs/teaching-guidelines.md)
(the agent's version is `src/lezio/agent/prompts/rules/teaching.md`). Anything specific you want goes in
the instructions; they take priority over the guidelines.

Scenes are built from **templates** filled with data (title cards, questions, bullets, definitions,
flows, cycles, trees, timelines, comparisons, analogies, misconceptions, derivations, worked examples,
tables, charts, function plots, arrays, code, original pages and figures, ...): `./lezio templates` lists
them, `./lezio templates --demo NAME --open` shows one. When none fits, the agent writes its own template
for the lesson. Your own templates go in `templates/` (see AGENTS.md): the agent sees them with the others.

The **visual style** (colors, fonts, sizes) is the house **theme**, a file in `themes/`: `light`
(default), `dark`, `chalkboard`, `whiteboard`, `paper`, or your own — copy `themes/light.toml` to
`themes/<name>.toml` and edit it. Choose the house theme in `config.toml` (`[video] theme`) or with
`./lezio config`; preview one with `./lezio themes --preview <name>`. Scenes use the theme's color names,
never fixed colors, so changing the theme re-renders existing lessons with the new look (no rewriting).
A lesson can ask for a different theme in its instructions (e.g. "use the chalkboard theme").

| Depth | Narration |
|---|---|
| 1 — extensive | everything in the material, plus explanations, examples and connections |
| 2 — faithful | everything in the material, nothing added, nothing cut |
| 3 — condensed | the main points, lightly summarized |
| 4 — short | very concise, short-video style |

## Subtitles

Subtitles come from the narration, timed with the voice (`config.toml [video] subtitles`, or
`./lezio config` → Video):

| Value | Result |
|---|---|
| `track` (default) | a subtitle track inside the MP4 that the player turns on and off (QuickTime: View → Subtitles; VLC: Subtitle menu; IINA, Windows players...), plus `output/<lesson>.srt` beside the video (YouTube, editors, players that load .srt files) |
| `burned` | always visible, drawn into the picture (for sites that ignore subtitle tracks); scenes keep the bottom band free |
| `off` | no subtitles |

## Configuration — `config.toml`

Only stable configuration; per-video choices are never here. It is the only place where configuration
lives: change it by hand or with `./lezio config` (`voices`, `themes` and `templates` only show and preview)
(arrow-key menus, with a "try this voice" option; comments in the file are kept).

| Section | What |
|---|---|
| `[tts]`, `[tts.<engine>]` | speech engine (`voxtral` local, `edge` online) and its options: voice, expressiveness, model |
| `[narration]` | language of narration and on-screen texts, pause between pieces |
| `[agent]` | LLM backend, **model** (`sonnet` by default, `opus`, `haiku` or a full id) and **effort**; optional `[agent.plan]`, `[agent.write]`, `[agent.review]` overrides |
| `[video]` | house **theme** (a file in `themes/`), **subtitles**, resolution and frame rate |
| `[tuning]` | segments per agent task, previews per segment, render timeout, parallel renders, image sizes |

The summary shows the configured model; the final panel shows the model that actually answered.
Changing the voice regenerates the narration of a lesson the next time it is built (the summary says so).

## How a lesson is made

A lesson is an ordered list of **segments**. A segment is a list of **blocks**: a template, its data, a
title and the narration pieces said meanwhile (one audio file each), rendered with Manim in sync with the
voice. Templates written by the agent for a lesson (`lessons/<id>/templates/`) are checked before they
run (only safe imports, no files, a time limit). The plan gives every segment a
goal, its sources, a length (from the depth and the amount of material) and its main visual idea, and
fixes a visual language for the whole lesson (the same concept always gets the same color and symbol).

## Folders

```
input/                     study material
output/                    finished videos
lessons/<lesson>/
    lesson.json            the files the lesson is made from
    script.json            per-video choices, plan, segments and narration (editable by hand)
    scenes/                scene code of each segment (editable by hand)
    build/                 cache: material, audio, renders, step sheets, agent log (deletable)
archive/slide-reader/      lessons of slide-reader, the previous version of the program (not used)
themes/                    visual themes (house style presets; add your own)
config.toml                configuration
src/lezio/                 the program (see AGENTS.md)
```

## Notes

- The log of every LLM task (prompts, tool calls, results) is in `lessons/<lesson>/build/agent/log.jsonl`;
  the frames the agent looked at are in `lessons/<lesson>/build/qa/`.
- `AGENTS.md` is the developer guide; `docs/history.md` tells how lezio came out of slide-reader;
  `docs/teaching-guidelines.md` is the research behind the teaching guidelines.
- The Voxtral weights are licensed CC BY-NC 4.0 (non-commercial). Make sure you may reuse the material.

## Roadmap

- PowerPoint (`.pptx`) material: text and pictures with python-pptx, page images through LibreOffice.
- `anthropic-api` backend and other LLMs behind the same interface (`src/lezio/agent/backends/`).
- More TTS engines (`src/lezio/voice/engines/`).
