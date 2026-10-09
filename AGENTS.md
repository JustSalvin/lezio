# AGENTS.md — developer guide

Guide for coding agents (and people) **developing** slide-reader. The program never reads this file at
runtime: the LLM tasks get everything they need from `slidereader/tasks.py`.

## What the program does

`./sr` turns a PDF slide deck into a narrated video lecture. The program owns the whole process; an LLM
is called only for narrow tasks, and only through tools the program defines.

```
cli.py ── pipeline.py (Run) ──┬── pdf_extract.py      PDF -> slide images, text lines (L-numbers), images
                              ├── tasks.py ── llm/      LLM tasks: plan, write a group of slides, review
                              │                         (system prompt + message + program-defined tools)
                              ├── validate.py           script validation (used by tools, check, pipeline)
                              ├── tts.py ── tts_engines/  speech synthesis (runs in .venv-tts)
                              └── engine.py ── templates.py, anim_api.py, lessons/<id>/animations/*.py
                                                        Manim scene: one slide -> one video
```

Flow of `./sr <pdf|lesson>`: resolve settings (defaults < config.toml < lesson < CLI options) → summary
and confirmation → read PDF → **plan task** → **write tasks** (one per group of `group_size` slides) →
audio → render outdated slides → **review task** on re-rendered slides → join. Every step is resumable.

## Layout

```
sr                         bash wrapper: runs slidereader.cli in .venv
setup.sh                   installation (Homebrew libs, two venvs, TTS model download)
config.toml                user preferences
slidereader/
  cli.py                   argument parsing, low-level commands (init/check/audio/render/anim/join/status/tts)
  pipeline.py              the program: Run (resolve, summary, prepare, plan, write, build, review), redo
  tasks.py                 LLM tasks: knowledge (rules, script format, template reference), prompts, tools
  llm/                     LLM backends behind llm.base (Task, Tool, ToolResult, Image)
    claude_subscription.py Claude Agent SDK with the user's Claude Code login; isolated session
    anthropic_api.py       planned
  tts_engines/             TTS engines behind tts_engines.base.Engine (options declared by each engine)
  tts.py                   synthesis runner (runs in .venv-tts): lesson pieces, samples, model download
  pdf_extract.py           page analysis; header/footer detection; highlight resolution
  script_io.py             script loading, settings model, audio piece keys (no heavy imports)
  validate.py              script validation; custom animation loading
  engine.py                Manim scene (one slide); manim_entry.py is the file given to the manim CLI
  templates.py             animation templates (their docstrings are shown to the LLM)
  anim_api.py              Timer/Steps (sync with audio), house style, helpers
  ui.py                    wizard questions
lessons/<id>/              lesson.json (PDF), script.json, animations/, build/ (cache, gitignored)
input/  output/            PDFs in, videos out
```

## Conventions

- Code, files, docs: English. Narration and on-screen animation texts: the lesson language (Italian by
  default). Never hard-code Italian strings in the program; they come from scripts or task data.
- Two virtual environments: `.venv` (Manim, PyMuPDF, Claude Agent SDK) and `.venv-tts` (MLX, TTS engines).
  `script_io.py`, `config.py` and `tts_engines/*` are imported by both: keep their module level free of
  heavy imports (load libraries inside functions).
- The LLM has no files, shell or web. Anything it needs is in the task message or behind a tool; anything
  it produces goes through a tool that validates it. Do not give tasks file-system tools.
- A slide video is re-rendered when its fingerprint changes (script entry, audio durations, engine code,
  animation files): see `cli.fingerprint`. Audio is regenerated when text or TTS options change.
- User-facing choices must be persisted in `lessons/<id>/script.json` settings (`settings_to_save`).

## How to extend

**TTS engine** — add `slidereader/tts_engines/<name>.py` with a subclass of `Engine`: declare `options`
(`Option(default, help, choices, minimum, maximum)`), implement `prepare` (load models), `synthesize(text,
opts) -> (float32 array, sample_rate)` and optionally `download`. Register it in `tts_engines/__init__.py`,
add a `[tts.<name>]` section to `config.toml`, add its package to `requirements-tts.txt`.
`./sr tts` and validation pick it up automatically.

**LLM backend** — add `slidereader/llm/<name>.py` with a `Backend` subclass whose `run(task)` sends
`task.system` + `task.prompt`, exposes `task.tools` (name, description, JSON schema), executes their
handlers for every tool call (results are text and `Image` items), and stops when a result has
`done=True`. Register it in `llm/__init__.py`.

**Animation template** — add a function `(scene, steps, **args)` to `templates.py`, use `run_phases`, and
register it in `TEMPLATES`. Its signature and docstring are what the LLM reads: document arguments,
limits and phases precisely.

**Task behaviour** — prompts, rules and tools live in `tasks.py`; validation in `validate.py`; the order
of tasks and retries in `pipeline.py`.

## Testing

```bash
.venv/bin/python -m py_compile slidereader/*.py slidereader/llm/*.py slidereader/tts_engines/*.py
./sr check b1-rappresentazione-informazione          # example lessons must stay valid
./sr anim b1-rappresentazione-informazione --all      # templates + custom animations render; look at build/qa
./sr tts --try "Prova" --engine edge                  # TTS engines
./sr b1-test --no-review -y                           # resolve/summary/build path without LLM calls
```

LLM tasks use the user's Claude subscription: test them on a few pages (e.g. extend `b1-test` with
`--pages 21-26`) and read `lessons/<id>/build/agent/log.jsonl` (prompts, tool calls, tool results).

## Known pitfalls

- Manim loads scene files outside any package: `manim_entry.py` subclasses the scene so it is detected.
- Parallel renders need separate `--media_dir`s (otherwise partial files collide).
- Manim `Text` does not wrap; LaTeX is not installed (no `MathTex`).
- pydub/Manim need an `ffmpeg` on PATH: `setup.sh` links the imageio-ffmpeg binary into `.venv/bin`.
- The MLX speech model only runs in `.venv-tts`; the pipeline calls it as a subprocess.
- Claude Agent SDK isolation: `tools=[]`, `setting_sources=[]`, `strict_mcp_config=True`, and only the
  task's MCP tools in `allowed_tools`.
