# slide-reader

Turn a PDF slide deck into a **narrated, animated video lecture** — like a teacher walking you through
the slides: every line is read and explained, the line being discussed is highlighted, and concepts get
full-screen explanation animations.

slide-reader is a **program**. It runs the whole process itself — PDF analysis, validation, local
text-to-speech, rendering, editing — and uses an AI agent as a worker only for the tasks that need
judgment: planning the lesson, writing the narration of a few slides at a time, and judging rendered
frames. Every agent result is validated by the program; problems are sent back to the agent to fix.

```
./sr make
  1. read the PDF                       program
  2. plan the lesson                    agent task  -> validated by the program
  3. write the script, group by group   agent tasks -> validated; animations rendered and judged
  4. narration audio                    program (local voice)
  5. render the video                   program
  6. review the final frames            agent task  -> fixes re-rendered by the program
  7. output/<lesson>.mp4                program
```

Everything runs **locally** on your Mac except the agent: the voice is generated on-device (Voxtral on
Apple Silicon via MLX), the video is drawn with Manim.

## Requirements

- macOS on **Apple Silicon** (M1 or newer), ~6 GB of free disk space
- [Homebrew](https://brew.sh)
- Python 3.11+ (installed automatically if you use [mise](https://mise.jdx.dev))
- **[Claude Code](https://claude.com/claude-code)**, logged in once with `claude` using your Claude
  subscription. The program calls it in headless mode (`claude -p`); no API key is needed.
  The agent can only read the project and write the files of its current task; it cannot run commands.

## Installation

```bash
./setup.sh
```

It installs `cairo`/`pkgconf` with Homebrew, creates two virtual environments inside the project
(`.venv` for video, `.venv-tts` for speech) and downloads the speech model (~3.5 GB, once).

## Usage

Put a PDF in `input/`, then:

```bash
./sr make
```

A short wizard asks which PDF, which pages, the visual mode and the depth, shows the lesson plan for
confirmation, and then runs to the end. Non-interactive:

```bash
./sr make "input/lesson.pdf" --pages 1-20 --visual mixed --depth 1
```

`./sr make` is resumable: if it is interrupted, run it again and it continues where it stopped.
`--rewrite` starts the script from scratch, `--no-review` skips the final review.

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
| `animations/` | custom animations written for a lesson (Python) |
| `output/` | finished videos |
| `build/` | intermediate files (slide images, plan, audio, renders, contact sheets, agent log) |
| `slidereader/` | the program |

## Configuration

`config.toml`: voice and expressiveness, narration language, default modes, resolution, parallelism,
and the agent (backend, model, slides per task, review). A lesson script can override voice and
temperature in its `settings`.

Italian voices: `it_male`, `it_female` (other languages: see the comments in `config.toml`).

## Changing a video by hand

Edit `scripts/<lesson>.json`, then:

```bash
./sr check <lesson>     # validate
./sr build <lesson>     # regenerate only the changed audio and slides
```

## Commands

```text
./sr make [pdf] [--pages] [--visual] [--depth]   the program: PDF -> finished video
./sr init <pdf>                                  analyse a PDF (overview, previews, empty script)
./sr check <lesson>                              validate a script
./sr templates                                   list animation templates
./sr anim <lesson> --all                         render animations alone + contact sheets
./sr audio <lesson>                              generate the narration audio
./sr render <lesson> [--preview] [--outdated]    render slides + contact sheets in build/<lesson>/qa
./sr join <lesson> [--small]                     assemble output/<lesson>.mp4
./sr build <lesson> [--small]                    audio + render + join
./sr status <lesson>                             what is done / missing / outdated
```

`AGENTS.md` is the reference the agent reads during its tasks (script format, writing rules,
animations). You do not need to talk to the agent yourself.

## Notes

- The Voxtral speech model weights are licensed **CC BY-NC 4.0** (non-commercial use).
- Make sure you have the right to reuse the slides you convert.

## Roadmap

- `anthropic-api` agent backend (Anthropic API key instead of the Claude Code subscription) — the
  interface is in `slidereader/agent.py`.
