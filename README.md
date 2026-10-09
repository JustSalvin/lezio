# slide-reader

Turn a PDF slide deck into a **narrated, animated video lecture** — like a teacher walking you through
the slides: every line is read and explained, the line being discussed is highlighted, and concepts get
full-screen explanation animations.

slide-reader is a **program**. It runs the whole process itself — PDF analysis, validation, speech
synthesis, rendering, editing — and calls an LLM only for the tasks that need judgment: planning the
lesson, writing the narration of a few slides at a time, and judging rendered frames.

Each LLM task is a system prompt, a message with the data and a few **tools defined by the program**
(e.g. `view_slides` returns slide pictures, `submit_script` validates the submitted script on the spot and
answers "accepted" or with the list of problems, `preview_animations` renders the animations and returns
their frames). The model has no files, shell or web: it works only through those tools, then the task ends.

```
./sr
  1. read the PDF                       program
  2. plan the lesson                    LLM task (tools: view_slides, submit_plan)
  3. write the script, group by group   LLM tasks (view_slides, submit_script, preview_animations, finish)
  4. narration audio                    program (TTS engine of your choice)
  5. render the video                   program
  6. review the final frames            LLM task (view_final, replace_slide, finish) -> program re-renders
  7. output/<lesson>.mp4                program
```

`sr` stands for **s**lide-**r**eader: a small script in the project folder that starts the program
inside its own Python environment.

## Requirements

- macOS on **Apple Silicon** (M1 or newer), ~6 GB of free disk space
- [Homebrew](https://brew.sh)
- Python 3.11+ (installed automatically if you use [mise](https://mise.jdx.dev))
- **[Claude Code](https://claude.com/claude-code)**, logged in once with `claude` using your Claude
  subscription. The program talks to Claude through the Claude Agent SDK with that login: no API key.
  Sessions are isolated (no built-in tools, no project settings): the model only has the task's tools.

## Installation

```bash
./setup.sh
```

It installs `cairo`/`pkgconf` with Homebrew, creates two virtual environments inside the project
(`.venv` for video, `.venv-tts` for speech) and downloads the speech model of the configured engine.

## Usage

```bash
./sr                                   # wizard: choose a PDF (or a lesson) and the options
./sr input/lesson.pdf                  # asks only what is missing
./sr input/lesson.pdf --pages 1-20 --visual mixed --depth 1 --yes     # no questions
```

Before starting, the program shows a summary (pages, modes, voice, agent instructions, estimated
length) and asks for confirmation. Every choice is saved in the lesson, so later you just run
`./sr <lesson>`: it writes what is missing and rebuilds only what changed. It is also resumable: if it is
interrupted, run it again.

On an existing lesson, the wizard offers: update the video, change the pages (slides already written
are kept), change visual mode or depth (rewrites the script, the old one is backed up), change the agent
instructions, rewrite from scratch.

### Options

| Option | Meaning |
|---|---|
| `--pages 1-20` | pages to cover (default: all) |
| `--visual MODE` | `slides` · `mixed` · `animated` |
| `--depth N` | `1` extensive · `2` faithful · `3` condensed · `4` short |
| `--instructions "..."` | instructions for the agent, saved in the lesson, e.g. `"Skip Mentimeter slides. Never read e-mail addresses aloud."` |
| `--engine NAME` / `--voice NAME` / `--tts KEY=VALUE` | TTS engine, voice and any engine option for this lesson |
| `--id NAME` | lesson name (default: from the PDF file name) |
| `--rewrite` | write the script again from scratch |
| `--no-review` | skip the final review of the frames |
| `-y`, `--yes` | no questions and no confirmation |

### Other commands

```bash
./sr status <lesson>                       # what is done, missing or outdated
./sr redo <lesson> --slides 7              # the agent rewrites slide 7
./sr redo <lesson> --slides 7 --note "add a concrete example"
./sr redo <lesson> --slides 3-5 --part voice     # new voice takes;  --part video: re-render
./sr build <lesson>                        # after editing lessons/<lesson>/script.json by hand
./sr tts                                   # TTS engines, options and voices
./sr help tools                            # low-level commands (debugging)
```

## Modes

**Visual mode**

| Mode | Result |
|---|---|
| `slides` | the original slides only, with a highlight following the voice |
| `mixed` | slides + full-screen explanation animations that are not in the slides (default) |
| `animated` | only animations; the slides are used as the source but never shown |

**Depth**

| Depth | Narration |
|---|---|
| 1 — extensive | everything on the slides, plus explanations, examples and connections (default) |
| 2 — faithful | everything on the slides, nothing added, nothing cut |
| 3 — condensed | the main points, lightly summarized |
| 4 — short | very concise, short-video style |

## Voice (TTS engines)

The program does not depend on a specific speech model: engines are plugins with their own options.

| Engine | Where | Notes |
|---|---|---|
| `voxtral` (default) | local, Apple Silicon | Voxtral 4B by Mistral; native Italian voices `it_male`, `it_female`; weights CC BY-NC (non-commercial) |
| `edge` | online | Microsoft neural voices, free and very fast; the text is sent to Microsoft |

```bash
./sr tts                                          # engines, options (with current values) and voices
./sr tts --engine edge                            # options of another engine
./sr tts --try "Ciao a tutti, iniziamo." --voice it_female --play       # listen before choosing
./sr tts --try "Ciao a tutti." --set temperature=0.6 --play
```

Defaults live in `config.toml` (`[tts]` and one `[tts.<engine>]` section per engine); one lesson can
use something else with `--engine`, `--voice`, `--tts key=value`. Changing the voice of a lesson
regenerates only the audio and re-renders the video; the script is untouched.
To add an engine, see `slidereader/tts_engines/` (one small class per engine).

## Folders

```
input/                     PDFs to turn into videos
output/                    finished videos (+ a lightweight 720p copy)
lessons/<lesson>/
    lesson.json            which PDF the lesson comes from
    script.json            the narration script and the lesson settings (editable by hand)
    animations/            custom animations written for the lesson
    build/                 regenerable cache: slide images, plan, audio, renders, contact sheets, agent log
config.toml                your preferences
slidereader/               the program
```

`build/` can be deleted at any time (it is regenerated; the audio takes the longest).

## Configuration

Precedence: built-in defaults < `config.toml` < settings saved in the lesson < command-line options.

`config.toml` holds stable preferences: TTS engine and options, narration language, default modes,
agent (backend, model, global instructions, slides per task, review) and video quality.

## Notes

- `AGENTS.md` is the developer guide (architecture, how to add TTS engines, LLM backends, animation
  templates). The program does not use it: task prompts and tools are in `slidereader/tasks.py`.
- The log of every LLM task (prompts, tool calls, results) is in `lessons/<lesson>/build/agent/log.jsonl`.
- Make sure you have the right to reuse the slides you convert.

## Roadmap

- `anthropic-api` backend (API key instead of the subscription) and other LLMs behind the same
  interface (`slidereader/llm/`): tasks and tools are model-independent.
- More TTS engines.
