# lezio

Turn **study material** — slide decks, notes, documents, pictures — into a **narrated video lesson**.
A synthetic voice explains the material like a teacher, while scenes written for the lesson (generated
slides, animations, a whiteboard) change in sync with the voice.

lezio is a **program**. It runs the whole process — reading the material, validation, speech synthesis,
rendering, editing — and calls an LLM only for the tasks that need judgment: planning the lesson, writing
the narration and the scene of each segment, and checking the rendered frames. In each task the model
works only through tools defined by the program (read the material, look at pages and figures, submit a
segment — checked and previewed on the spot —, ...): it has no files, shell or web.

```
./lezio input/slides.pdf input/appunti.md
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
./lezio                                        # wizard: arrow-key menus for files or lesson and options
./lezio input/slides.pdf                       # asks only what is missing
./lezio input/slides.pdf input/appunti.md input/schema.png   # several files, of any kind
./lezio input/slides.pdf --focus "slides.pdf:21-40" --style slides --depth 2 --yes   # no questions
./lezio my-lesson                              # continue / update an existing lesson
```

**Study material**: PDF (slides or documents), Markdown and plain text, Word (`.docx`), pictures (`.png`,
`.jpg`, `.webp`) — one or more files of any kind in the same lesson. Files outside `input/` are copied
there.

Before starting, a summary shows material, style, voice, agent model, instructions and the state of the
lesson; after planning, the list of segments is shown for confirmation. Each step runs with a live
progress line. Choices are saved in the lesson, so `./lezio <lesson>` later writes only what is missing and
rebuilds only what changed; it is resumable if interrupted.

On an existing lesson the wizard offers: update the video, change the study material (add/remove files,
page ranges), change style or depth (the lesson is planned and written again, the old one is backed up),
change the instructions, rewrite from scratch.

### Options (per-video choices, saved in the lesson)

| Option | Meaning |
|---|---|
| `--style STYLE` | `animated` · `slides` · `whiteboard` · `auto` (default) |
| `--depth N` | `1` extensive · `2` faithful (default) · `3` condensed · `4` short |
| `--instructions "..."` | instructions for the agent, e.g. `"Base the lesson only on the input slides, shown as they are."` |
| `--focus "FILE:PAGES"` | only some pages of a PDF, e.g. `--focus "slides.pdf:1-20"` (repeatable) |
| `--id NAME` | lesson name (default: from the first file); with files, adds them to that lesson |
| `--rewrite` | plan and write the lesson again from scratch (the old one is backed up) |
| `--no-review` | skip the final review of the frames |
| `-y`, `--yes` | no questions and no confirmation |

### Other commands

```bash
./lezio status <lesson>                                   # segments: written, voice, video up to date?
./lezio redo <lesson> --segments s03 --note "add an example"   # the agent rewrites segment s03
./lezio redo <lesson> --segments s03,s05 --part voice     # new voice takes   (--part video: re-render)
./lezio build <lesson>                                    # after editing the lesson by hand
./lezio config                                            # change the configuration with menus
./lezio tts                                               # TTS engines, options and voices
./lezio tts --try "Ciao a tutti." --voice it_male --play
./lezio help tools                                        # low-level commands
```

## Styles and depth

| Style | Result |
|---|---|
| `animated` | full animations: diagrams that build up, transformations, motion; no slide look |
| `slides` | clean generated slides revealed step by step with the voice (not copies of the input pages) |
| `whiteboard` | a board where everything is written and drawn by hand while the teacher talks |
| `auto` | the agent chooses animated, slides or whiteboard for each segment, switching along the video |

Using the original pages is not implied by any style: ask for it in the instructions (e.g. *"Show the
original slides and highlight the line being discussed"*).

| Depth | Narration |
|---|---|
| 1 — extensive | everything in the material, plus explanations, examples and connections |
| 2 — faithful | everything in the material, nothing added, nothing cut |
| 3 — condensed | the main points, lightly summarized |
| 4 — short | very concise, short-video style |

## Configuration — `config.toml`

Only stable configuration; per-video choices are never here. Edit it by hand or with `./lezio config`
(arrow-key menus, with a "try this voice" option; comments in the file are kept).

| Section | What |
|---|---|
| `[tts]`, `[tts.<engine>]` | speech engine (`voxtral` local, `edge` online) and its options: voice, expressiveness, model |
| `[narration]` | language of narration and on-screen texts, pause between pieces |
| `[agent]` | LLM backend, **model** (`opus`, `sonnet`, `haiku` or a full id) and **effort**; optional `[agent.plan]`, `[agent.write]`, `[agent.review]` overrides |
| `[video]` | resolution and frame rate |
| `[tuning]` | segments per agent task, previews per segment, render timeout, parallel renders, image sizes |

The summary shows the configured model; the final panel shows the model that actually answered.
Changing the voice regenerates the narration of a lesson the next time it is built (the summary says so).

## How a lesson is made

A lesson is an ordered list of **segments**. A segment has a narration (a list of short pieces, one audio
file each) and a **scene**: Python code written by the agent for that segment (`lessons/<id>/scenes/`),
rendered with Manim in sync with the narration. Scene code uses a small helper library (`lezio.scene`:
voice sync, house style and themes, access to pages and figures of the material, optional layouts) and
is checked before it runs (only safe imports, no files, a time limit).

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
config.toml                configuration
src/lezio/                 the program (see AGENTS.md)
```

## Notes

- The log of every LLM task (prompts, tool calls, results) is in `lessons/<lesson>/build/agent/log.jsonl`;
  the frames the agent looked at are in `lessons/<lesson>/build/qa/`.
- `AGENTS.md` is the developer guide; `docs/history.md` tells how lezio came out of slide-reader.
- The Voxtral weights are licensed CC BY-NC 4.0 (non-commercial). Make sure you may reuse the material.

## Roadmap

- PowerPoint (`.pptx`) material: text and pictures with python-pptx, page images through LibreOffice.
- `anthropic-api` backend and other LLMs behind the same interface (`src/lezio/agent/backends/`).
- More TTS engines (`src/lezio/voice/engines/`).
