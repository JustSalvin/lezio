# slide-reader

Turn a PDF slide deck into a **narrated, animated video lecture** — like a teacher walking you through
the slides: every line is read and explained, the line being discussed is highlighted, and concepts get
full-screen explanation animations.

slide-reader is a program driven by an **AI agent** (e.g. Claude Code): the program does all the
mechanical work (PDF analysis, local text-to-speech, rendering, editing), the agent does the part that
needs understanding — writing the narration script and designing the animations — following
[`AGENTS.md`](AGENTS.md).

Everything runs **locally** on your Mac: the voice is generated on-device (Voxtral on Apple Silicon via
MLX), the video is drawn with Manim.

## Requirements

- macOS on **Apple Silicon** (M1 or newer), ~6 GB of free disk space
- [Homebrew](https://brew.sh)
- Python 3.11+ (installed automatically if you use [mise](https://mise.jdx.dev))
- An AI coding agent. The built-in program uses **[Claude Code](https://claude.com/claude-code)** in
  headless mode with **your Claude subscription** (log in once with `claude`). No API key needed.
  Any other agent that can read files and run shell commands can be used manually (see below).

## Installation

```bash
./setup.sh
```

It installs `cairo`/`pkgconf` with Homebrew, creates two virtual environments inside the project
(`.venv` for video, `.venv-tts` for speech) and downloads the speech model (~3.5 GB, once).

## Usage

### A. The program (recommended)

Put a PDF in `input/`, then:

```bash
./sr make
```

A short wizard asks which PDF, which pages, the visual mode and the depth. Then it runs everything:
it starts Claude Code to write the script, validates it, generates the voice, renders the video, lets the
agent review the frames, and writes `output/<lesson>.mp4`.

Non-interactive:

```bash
./sr make "input/lesson.pdf" --pages 1-20 --visual mixed --depth 1
```

### B. Any agent, manually

Open this folder in your coding agent (Claude Code, Codex, Cursor, ...) and write:

> **Read AGENTS.md** and make the video of `input/lesson.pdf`, pages 1–20.

The agent follows `AGENTS.md` and uses the `./sr` commands for every mechanical step.

## Modes

**Visual mode** (`--visual`)

| Mode | Result |
|---|---|
| `slides` | the original slides only, with a highlight following the voice |
| `mixed` | slides + full-screen explanation animations that are not in the slides (default) |
| `animated` | only animations; the slides are used as the source but never shown |

**Depth** (`--depth`)

| Depth | Narration |
|---|---|
| 1 — extensive | everything on the slides, plus explanations, examples and connections (default) |
| 2 — faithful | everything on the slides, nothing added, nothing cut |
| 3 — condensed | the main points, lightly summarized |
| 4 — short | very concise, short-video style |

## Folders

| Folder | Content |
|---|---|
| `input/` | PDFs to turn into videos |
| `scripts/` | narration scripts, one JSON per lesson (editable by hand) |
| `animations/` | optional custom animations, one Python file per lesson |
| `output/` | finished videos |
| `build/` | intermediate files (slide images, audio, renders, contact sheets) — safe to delete |
| `slidereader/` | the program |

## Configuration

`config.toml`: voice and expressiveness, narration language, default modes, resolution, parallelism,
agent backend and model. A lesson script can override voice and temperature in its `settings`.

Available Italian voices: `it_male`, `it_female` (other languages: see the comments in `config.toml`).

## Changing a video

Edit `scripts/<lesson>.json` (or ask the agent), then:

```bash
./sr build <lesson>
```

Only the changed audio pieces and the affected slides are regenerated.

## Commands

```text
./sr make [pdf] [--pages] [--visual] [--depth]   the full program
./sr init <pdf>                                  analyse a PDF (overview, previews, empty script)
./sr check <lesson>                              validate a script
./sr templates                                   list animation templates
./sr anim <lesson> --all                         render animations alone + contact sheets
./sr audio <lesson>                              generate the narration audio
./sr render <lesson> [--preview] [--outdated]    render slides + contact sheets
./sr join <lesson> [--small]                     assemble output/<lesson>.mp4
./sr build <lesson> [--small]                    audio + render + join
./sr status <lesson>                             what is done / missing / outdated
```

## Notes

- The Voxtral speech model weights are licensed **CC BY-NC 4.0** (non-commercial use).
- Make sure you have the right to reuse the slides you convert.

## Roadmap

- `anthropic-api` agent backend (Anthropic API key instead of the Claude Code subscription) — the
  interface is ready in `slidereader/agent.py`.
