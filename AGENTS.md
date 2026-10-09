# AGENTS.md — developer guide

> **Rebuild in progress**: slide-reader is being rebuilt into **lezio** (study material → video lesson,
> any style, one workflow). Before any change, read `docs/HANDOFF.md` and follow its execution plan.

Guide for coding agents (and people) **developing** slide-reader. The program never reads this file at
runtime: LLM tasks get their instructions from `slidereader/agent/prompts/`.

## What the program does

`./sr` turns a PDF slide deck into a narrated video lecture. The program owns the whole process; an LLM
is called only for narrow tasks, and only through tools the program defines.

```
./sr ─ app/cli.py ─ app/run.py (Run) ─┬─ pdf.py                  slide images, text lines (L-numbers), images
                                      ├─ agent/tasks.py          plan · write a group of slides · review
                                      │    agent/prompts/*.md    the texts of the tasks
                                      │    agent/backends/       LLM backends (Claude subscription, API planned)
                                      ├─ validate.py             script validation (tools, check, run)
                                      ├─ voice/client.py ─ voice/synthesize.py (in .venv-tts) ─ voice/engines/
                                      └─ video/render.py ─ manim ─ video/scene.py, templates.py, anim_api.py
```

Flow of `./sr <pdf|lesson>`: resolve the per-video choices (wizard/options, saved choices) → summary →
read PDF → plan task → write tasks (groups of `tuning.group_size` slides) → voice → render outdated
slides → review task on the re-rendered slides → join. Every step is resumable.

## Layout

```
sr                         bash wrapper: python -m slidereader in .venv
setup.sh                   installation (Homebrew libs, two venvs, TTS model download)
config.toml                configuration (TTS, language, LLM, video, tuning)
slidereader/
  config.py                paths, CONFIG, environment for subprocesses
  lesson.py                Lesson (all paths of lessons/<id>/), slugify, listing
  settings.py              per-video choices vs configuration; TTS options
  script.py                script.json load/save, spoken pieces, page lists
  validate.py              script validation, custom animation loading
  pdf.py                   page analysis, header/footer detection, highlight resolution
  app/                     the program
    cli.py                 argument parsing and help
    run.py                 Run: resolve → summary → prepare → plan → write → build; redo
    commands.py            status, check, build, tts and the low-level tools
    ui.py                  rich: colors, panels, live steps with progress bars
    wizard.py              questionary: arrow-key menus
  agent/
    tasks.py               the three tasks: data given to the model and the tools it may call
    prompts/*.md           task texts ($placeholders), modes.toml (visual/depth rules)
    prompts.py             loads and composes prompt texts
    backends/              base.py (Task, Tool, ToolResult, Image), claude_subscription.py, anthropic_api.py
  voice/
    engines/               TTS engines (base.Engine with declared options): voxtral, edge
    synthesize.py          worker run in .venv-tts; prints JSON progress events
    client.py              runs the worker from .venv and relays its events
  video/
    scene.py               Manim scene: one slide → one video (started by render.py)
    manim_entry.py         file given to the manim CLI
    templates.py           animation templates (signature + docstring are shown to the LLM)
    anim_api.py            Timer/Steps (sync with audio), house style, helpers (public API of custom animations)
    render.py              render slides/previews, contact sheets, fingerprints, final join
lessons/<id>/              lesson.json, script.json, animations/*.py, build/ (cache, gitignored)
input/  output/            PDFs in, videos out
```

## Conventions

- Code, files, docs: English. Narration and on-screen animation texts: the lesson language (Italian by
  default); never hard-code them in the program.
- Two kinds of settings, never mixed: per-video choices (pages, visual, depth, instructions, skip) come
  from the wizard/CLI and are saved in `lessons/<id>/script.json` (`settings.LESSON_CHOICES`);
  configuration (TTS, language, LLM, video, `[tuning]`) lives only in `config.toml` and has no CLI flags.
- Two virtual environments: `.venv` (program, Manim, PyMuPDF, Claude Agent SDK, rich, questionary) and
  `.venv-tts` (MLX, TTS engines). `config.py`, `lesson.py`, `settings.py`, `script.py` and
  `voice/engines/*` are imported by both: keep their module level free of heavy imports.
- The LLM has no files, shell or web. Anything it needs is in the task message or behind a tool; anything
  it produces goes through a tool that validates it. Prompt texts belong in `agent/prompts/`, not in code.
- Console output goes through `app/ui.py`; detailed output of subprocesses goes to `lessons/<id>/build/logs/`.
- A slide video is re-rendered when its fingerprint changes (script entry, audio durations, video code,
  animation files): `video/render.fingerprint`. Audio is regenerated when text or TTS options change.
- Temporary render files (`build/media/`) are deleted as soon as a render is copied out.
- Custom animations import `from slidereader.video.anim_api import *`: keep that module's API stable.

## How to extend

**TTS engine** — `voice/engines/<name>.py`: subclass `Engine`, declare `options`
(`Option(default, help, choices, minimum, maximum)`), implement `prepare`, `synthesize(text, opts) ->
(float32 array, sample_rate)` and optionally `download`. Register in `voice/engines/__init__.py`, add
`[tts.<name>]` to `config.toml` and its package to `requirements-tts.txt`.

**LLM backend** — `agent/backends/<name>.py`: subclass `Backend`; `run(task)` sends `task.system` +
`task.prompt` with `task.model`/`task.effort`, exposes `task.tools`, runs their handlers for every tool
call (results: text and `Image`), stops when a result has `done=True`, reports through
`task.on_event`. Register in `agent/backends/__init__.py`.

**Animation template** — function `(scene, steps, **args)` in `video/templates.py`, using `run_phases`;
register in `TEMPLATES`. Its signature and docstring are what the LLM reads.

**Task behaviour** — texts in `agent/prompts/`, tools in `agent/tasks.py`, validation in `validate.py`,
order of tasks and retries in `app/run.py`.

## Testing

```bash
.venv/bin/python -m py_compile $(find slidereader -name "*.py")
./sr check b1-rappresentazione-informazione          # example lessons must stay valid
./sr anim b1-rappresentazione-informazione --all      # templates + custom animations render (build/qa)
./sr tts --try "Prova" --engine edge                  # TTS engines
./sr build b1-test                                    # voice/render/join without LLM calls
```

LLM tasks use the user's Claude subscription: test them on a few slides (`./sr redo b1-test --slides 26`)
and read `lessons/<id>/build/agent/log.jsonl` (prompts, tool calls, tool results).

## Known pitfalls

- Manim loads scene files outside any package: `manim_entry.py` subclasses the scene so it is detected.
- Parallel renders need separate `--media_dir`s.
- Manim `Text` does not wrap; LaTeX is not installed (no `MathTex`).
- pydub/Manim need `ffmpeg` on PATH: `setup.sh` links the imageio-ffmpeg binary into `.venv/bin`.
- Rich markup: escape user/config text containing `[...]` (`rich.markup.escape`).
- Claude Agent SDK: isolation via `tools=[]`, `setting_sources=[]`, `strict_mcp_config=True`; images in
  tool results are compressed (`Image.from_file`) and `max_buffer_size` is raised.
