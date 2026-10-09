# slide-reader

Turn a PDF slide deck into a **narrated, animated video lecture** — like a teacher walking you through
the slides: every line is read and explained, the line being discussed is highlighted, and concepts get
full-screen explanation animations.

slide-reader is a **program**. It runs the whole process — PDF analysis, validation, speech synthesis,
rendering, editing — and calls an LLM only for the tasks that need judgment: planning the lesson,
writing the narration a few slides at a time, and checking the rendered frames. In each task the model
works only through tools defined by the program (look at slides, submit the script — validated on the
spot —, preview animations, ...): it has no files, shell or web.

```
./sr
  ✓ Reading the PDF              61 pages
  ✓ Planning the lesson          20 pages · skipping 14          agent
  ✓ Writing the script           19 slides · 15 animations       agent
  ✓ Generating the voice         118 new pieces                  local TTS
  ✓ Rendering the video          19 slides
  ✓ Reviewing the video          no problems found               agent
  ✓ Assembling the final video   19m 10s
```

`sr` stands for **s**lide-**r**eader.

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
./sr                                   # wizard: arrow-key menus to choose a PDF or a lesson and the options
./sr input/lesson.pdf                  # asks only what is missing
./sr input/lesson.pdf --pages 1-20 --visual mixed --depth 2 --yes      # no questions
./sr my-lesson                         # continue / update an existing lesson
```

Before starting, a summary shows pages, mode, voice, agent model, instructions and the estimated length.
Then each step runs with a live progress line. Choices are saved in the lesson, so `./sr <lesson>` later
writes only what is missing and rebuilds only what changed; it is resumable if interrupted.

On an existing lesson the wizard offers: update the video, change the pages (slides already written are
kept), change visual mode or depth (rewrites the script, the old one is backed up), change the
instructions, rewrite from scratch.

### Options (per-video choices, saved in the lesson)

| Option | Meaning |
|---|---|
| `--pages 1-20` | pages to cover (default: all) |
| `--visual MODE` | `slides` · `mixed` (default) · `animated` |
| `--depth N` | `1` extensive · `2` faithful (default) · `3` condensed · `4` short |
| `--instructions "..."` | instructions for the agent, e.g. `"Skip interactive slides such as live polls or quizzes."` |
| `--id NAME` | lesson name (default: from the PDF file name) |
| `--rewrite` | write the script again from scratch |
| `--no-review` | skip the final review of the frames |
| `-y`, `--yes` | no questions and no confirmation |

### Other commands

```bash
./sr status <lesson>                                  # what is done, missing or outdated
./sr redo <lesson> --slides 7 --note "add an example" # the agent rewrites slide 7
./sr redo <lesson> --slides 3-5 --part voice          # new voice takes   (--part video: re-render)
./sr build <lesson>                                   # after editing lessons/<lesson>/script.json by hand
./sr tts                                              # TTS engines, options and voices
./sr tts --try "Ciao a tutti." --voice it_female --play
./sr help tools                                       # low-level commands
```

## Modes

| Visual mode | Result |
|---|---|
| `slides` | the original slides only, with a highlight following the voice |
| `mixed` | slides + full-screen explanation animations that are not in the slides |
| `animated` | only animations; the slides are used as the source but never shown |

| Depth | Narration |
|---|---|
| 1 — extensive | everything on the slides, plus explanations, examples and connections |
| 2 — faithful | everything on the slides, nothing added, nothing cut |
| 3 — condensed | the main points, lightly summarized |
| 4 — short | very concise, short-video style |

## Configuration — `config.toml`

Only stable configuration; per-video choices are never here.

| Section | What |
|---|---|
| `[tts]`, `[tts.<engine>]` | speech engine (`voxtral` local, `edge` online) and its options: voice, expressiveness, model |
| `[narration]` | language of narration and on-screen texts, pause between pieces |
| `[agent]` | LLM backend, **model** (`opus`, `sonnet`, `haiku` or a full id) and **effort**; optional `[agent.plan]`, `[agent.write]`, `[agent.review]` overrides |
| `[video]` | resolution and frame rate |
| `[tuning]` | slides per agent task, animation previews, parallel renders, image sizes — normally untouched |

The summary shows the configured model; the final panel shows the model that actually answered.
Changing the voice regenerates the narration of a lesson the next time it is built (the summary says so).

## Folders

```
input/                     PDFs to turn into videos
output/                    finished videos
lessons/<lesson>/
    lesson.json            which PDF the lesson comes from
    script.json            the narration script and the per-video choices (editable by hand)
    animations/            custom animations written for the lesson
    build/                 cache: slide images, plan, audio, renders, contact sheets, logs (deletable)
config.toml                configuration
slidereader/               the program (see AGENTS.md)
```

## Notes

- The log of every LLM task (prompts, tool calls, results) is in `lessons/<lesson>/build/agent/log.jsonl`.
- `AGENTS.md` is the developer guide.
- The Voxtral weights are licensed CC BY-NC 4.0 (non-commercial). Make sure you may reuse the slides.

## Roadmap

- `anthropic-api` backend and other LLMs behind the same interface (`slidereader/agent/backends/`).
- More TTS engines (`slidereader/voice/engines/`).
