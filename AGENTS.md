# AGENTS.md — developer guide

Guide for coding agents (and people) **developing** lezio. The program never reads this file at runtime:
LLM tasks get their instructions from `src/lezio/agent/prompts/`. Start from `docs/HANDOFF.md` (what
lezio is, decisions and constraints); how lezio came out of slide-reader: `docs/history.md`.

## What the program does

`./lezio make` turns study material (PDF, Markdown/text, DOCX, pictures; one or more files) into a narrated
video lesson. The program owns the whole process; an LLM is called only for narrow tasks, and only
through tools the program defines.

```
./lezio ─ app/cli.py ─ app/run.py (Run) ─┬─ material/             ingest sources → build/material/index.json, refs
                                         ├─ agent/tasks.py        plan · write segments · review (tools)
                                         │    agent/prompts/      role, tasks, rules (teaching...), depth.toml
                                         │    agent/backends/     LLM backends (Claude subscription, Anthropic
                                         │                        API, OpenAI API, local OpenAI-compatible server)
                                         ├─ validate.py           narration rules, scene code checks, script
                                         ├─ voice/client.py ─ voice/synthesize.py (in .venv-tts) ─ voice/engines/
                                         └─ video/render.py ─ manim ─ video/scene_runner.py ─ template blocks
                                                                        └─ lezio.scene (templates, helpers)
```

Flow of `./lezio make <files|lesson>`: resolve the per-video choices (wizard/options, saved choices) → summary
→ ingest new/changed sources → plan task (when there is no plan for the current sources/focus/depth)
→ write tasks (`tuning.segments_per_task` segments each; a segment is a list of template blocks, every
submission is checked and previewed) →
voice → render outdated segments → review task on the re-rendered segments → re-render fixed → join.
Every step is resumable. There are no styles: the agent decides how to teach each segment following the
teaching guidelines (`prompts/rules/teaching.md`, research in `docs/teaching-guidelines.md`); the user's
instructions override them. The look (colors, fonts, sizes) is the theme (`themes/*.toml`).

## Layout

```
lezio                      bash wrapper: python -m lezio in .venv (PYTHONPATH=src)
setup.sh                   installation (Homebrew libs, two venvs, TTS model download)
config.toml                configuration (TTS, language, LLM, video + theme, tuning) - also ./lezio config
themes/                    visual themes: colors, fonts, sizes (house style presets; users add their own)
templates/                 the user's own scene templates (optional; loaded with the library)
src/lezio/
  config.py                paths, CONFIG, environment for subprocesses
  lesson.py                Lesson (all paths of lessons/<id>/), slugify, listing
  settings.py              per-video choices (depth, instructions, focus) vs configuration; TTS options; theme
  script.py                script.json v2: load/save, narration pieces, audio keys
  validate.py              narration rules, scene code checks (AST allowlist), whole-script check
  material/                ingestion: pdf.py (pages, L-numbered text lines, figures, chrome removal),
                           text.py (.md/.txt sections), docx.py, image.py; __init__.py: index, refs, Material
  app/                     cli.py (COMMANDS: every command described once; help pages and parsers come from
                           it), run.py (make/redo: the workflow), commands.py (the other commands), ui.py
                           (rich: the only place output styles are defined), wizard.py (questionary),
                           configure.py (./lezio config, tomlkit)
  agent/
    tasks.py               the three tasks, their tools, the scene API reference given to the model
    prompts/               role.md, plan.md, write.md, review.md, rules/*.md (teaching, writing, narration
                           format, scene API), depth.toml (rules and target lengths)
    prompts.py             loads and composes prompt texts ($placeholders)
    backends/              base.py (Task, Tool, ToolResult, Image, Session: log/events/tool calls shared by
                           all backends), claude_subscription.py (Agent SDK), anthropic_api.py (Messages API),
                           openai_compatible.py (OpenAI Responses API; local servers via Chat Completions)
  voice/
    engines/               TTS engines (base.Engine with declared options): voxtral, edge
    synthesize.py          worker run in .venv-tts; prints JSON progress events
    client.py              runs the worker from .venv and relays its events
  video/
    scene_runner.py        Manim scene: one segment → runs scenes/<id>.py:build(scene, steps, material)
    manim_entry.py         file given to the manim CLI
    render.py              previews, final renders, step sheets, fingerprints, final join
    subtitles.py           subtitles from the narration timings: .srt, track in the MP4, or burned in
    theme_preview.py       still image of a theme (./lezio themes --preview)
    scene_runner.py        runs a segment: its template blocks (or, for older segments, scenes/<id>.py)
  scene/templates/         the template library: __init__.py (framework: @template, Ctx, run_blocks,
                           checks, catalog), kit.py (helpers for authors), one module per family
                           (text, diagrams, structures, compare, math, data, cs, material)
  scene/                   PUBLIC helper library of scene code (`from lezio.scene import *`):
                           sync.py (Steps/Timer), style.py (theme colors/fonts/sizes, T, heading, box...),
                           material.py (material.page/figure, page.mark), templates/ (above)
lessons/<id>/              lesson.json, script.json, templates/*.py (the agent's), build/ (cache); all of lessons/ is
                           gitignored: the user's lessons never go into the repository
lessons/_templates/        internal lesson used to render template examples (./lezio templates --demo)
archive/slide-reader/      old slide-reader lessons (local only, gitignored, not loaded)
input/  output/            material in, videos out (both gitignored)
```

## Concepts

- **Refs** address the material: `slides.pdf#p3` (page), `slides.pdf#p3-5`, `slides.pdf#p3.f1` (figure),
  `notes.md#s2` (section), `diagram.png` (picture source). Source ids are slugs of the file names.
- **Segments**: a lesson is an ordered list of segments (`s01`, `s02`, ...): plan data (title, goal,
  sources, minutes, visual idea) and **blocks**: `{"template", "title", "args", "say"}`. The narration
  pieces of all blocks (one audio file each, key `<segment>_<piece>`) are the segment's narration.
  (Segments written by older versions have `narration` + `scenes/<id>.py` instead; still rendered.)
- **Templates**: functions `(ctx, steps, **args)` registered with `@template(category, use_for, example)`.
  Three sources, one interface: the library (`scene/templates/`), the user's `templates/` folder, the
  agent's own per lesson (`lessons/<id>/templates/<name>.py`, written with the `define_template` tool,
  statically checked, executed only inside the render subprocess). The catalog the agent reads is
  generated from signatures, docstrings, `use_for` and `example`.
- **Blocks at run time** (`templates.run_blocks`): each block gets its narration pieces; at its first piece
  the previous block's content fades out (unless `keep`), the title changes only if it differs; the
  template lays out inside `ctx.area` (`ctx.place` fits and scales). The runner reports per piece:
  start/end times, texts cut off or overlapping, animations longer than the speech.
- **Step sheets** (`build/qa/preview_<id>.png`, `final_<id>.png`): for every piece, the frame in its
  middle and at its end. They are what the agent looks at when writing and reviewing (`view_frame` shows
  one frame at full size).
- **Themes**: `themes/<name>.toml` (colors by role, fonts, sizes). The runner applies the house theme
  (config.toml `[video] theme`; configuration only, the agent never chooses it) before the scene code runs (`style.apply_theme` rebinds the names in every `lezio.scene`
  module). Scene code uses role names (PRIMARY, HIGHLIGHT, ...), so a new theme re-skins existing lessons;
  the theme file is part of the fingerprint.
- **Visual language**: the plan states how key concepts look across the lesson (theme color roles,
  symbols, recurring diagrams); every write and review task receives it, so separately written segments
  read as one lesson.
- **Target length**: the program computes it from the depth (`depth.toml` seconds per unit) and the amount
  of material in scope (pages, pictures, 150-word blocks) and gives it to the plan.

## Conventions

- License: GNU AGPL v3 with additional terms (`LICENSE`, `NOTICE`). Every source file starts with the
  two-line copyright/SPDX header (copy it into new files); the attribution under `ui.banner()` must stay.
- Code, files, docs: English. Narration and on-screen texts: the lesson language (Italian by default);
  never hard-code them in the program.
- Two kinds of settings, never mixed: per-video choices (depth, instructions, focus) come from the
  wizard/CLI and are saved in `lessons/<id>/script.json` (`settings.LESSON_CHOICES`); the sources are in
  `lesson.json`; configuration (TTS, language, LLM, video, `[tuning]`) lives only in `config.toml` and has
  no CLI flags (`./lezio config` edits the file).
- Two virtual environments: `.venv` (program, Manim, PyMuPDF, python-docx, Claude Agent SDK, anthropic,
  openai, rich, questionary, tomlkit) and `.venv-tts` (MLX, TTS engines). `config.py`, `lesson.py`, `settings.py`,
  `script.py` and `voice/engines/*` are imported by both: keep their module level free of heavy imports.
- The LLM has no files, shell or web. Anything it needs is in the task message or behind a tool; anything
  it produces goes through a tool that validates it. Prompt texts belong in `agent/prompts/`, not in code.
- Scene code is untrusted: `validate.check_scene_code` (imports allowlist, forbidden names/attributes)
  runs before every render, renders have a timeout, the runner's cwd is the render's media directory.
- Console output goes through `app/ui.py` (escape user text with `ui.escape`): `banner`, `section`,
  `table` for lists, `key_values` for summaries, `step` for work in progress, `done`/`warn`/`fail`, and
  `hint` for what to do next. Detailed output of subprocesses goes to `lessons/<id>/build/logs/`.
- Commands: one verb each (`make`, `redo`, `build`, `list`, `status`, `rename`, `copy`, `delete`,
  `config`, `voices`, `themes`, `templates`, `tools`, `help`); add one to `cli.COMMANDS`. Lesson commands work on
  lessons/<id>/ only: `delete` moves it to the macOS Trash; videos in output/ and files in input/ are never
  moved, renamed or deleted. Configuration changes only through `config` (or the file):
  the other commands show and preview.
- A segment video is re-rendered when its fingerprint changes (segment entry, audio durations, scene file,
  `lezio.scene` + runner code, material, video settings): `video/render.fingerprint`. Audio is regenerated
  when text or TTS options change.
- Temporary render files (`build/media/`) are deleted as soon as a render is copied out.
- Templates and older scene files import `from lezio.scene import *`: keep that API stable (it is also
  what `agent.tasks.scene_api()` shows the model for its own templates).
- Every template has an `example` that passes `./lezio templates --demo <name>`; run `--demo all` after
  changing the framework, the kit, the style or a theme.

## How to extend

**Material reader** — `material/<kind>.py` with `ingest(path, source_id, out_dir, rel) -> entry` (items
with `ref`, text, `image`/`preview` paths, `figures`); register the extensions in `material.KINDS` and the
reader in `material._reader`; bump `material.VERSION` when readers change (sources are read again).

**Theme** — a new `themes/<name>.toml` (copy `light.toml`); new color roles need a name in
`scene/style.COLOR_NAMES`, the list in `agent.tasks.scene_api()` and an entry in every preset.

**Teaching guidelines** — `agent/prompts/rules/teaching.md` (given to plan, write and review tasks); keep
`docs/teaching-guidelines.md` (sources) in sync.

**Template** — a function in a module of `scene/templates/` (or a file in `templates/` at the project
root for your own):

```python
from lezio.scene import *

@template(category="diagram", use_for="when the agent should pick it",
          example={"title": "...", "args": {"items": ["a", "b"]}, "say": ["...", "..."]})
def my_template(ctx, steps, items: list[str], note: str | None = None):
    """What it shows; the arguments; Phases: one per item."""
    group = VGroup(*[box(i) for i in items]).arrange(RIGHT)
    ctx.place(group)                                   # fit (and scale) inside the free area
    run_phases(steps, [(lambda m: lambda t: t.play(FadeIn(m), rt=0.6))(m) for m in group])
```

Rules: annotate the arguments (the program checks the agent's JSON against them); build first, animate
inside phases; only theme names for colors/fonts/sizes; `text_box` for text that must wrap; the example
narration in the lesson language without digits. Check it with `./lezio templates --demo my_template`
(step sheet in lessons/_templates/build/qa/). The module is discovered automatically; no registration list to edit.

**Scene helper** — a function in `lezio/scene/*.py` exported by `scene/__init__.py`, with a docstring
written for the model, and listed in `agent.tasks.scene_api()`.

**TTS engine** — `voice/engines/<name>.py`: subclass `Engine`, declare `options`
(`Option(default, help, choices, minimum, maximum)`), implement `prepare`, `synthesize(text, opts) ->
(float32 array, sample_rate)` and optionally `download`. Register in `voice/engines/__init__.py`, add
`[tts.<name>]` to `config.toml` and its package to `requirements-tts.txt`.

**LLM backend** — `agent/backends/<name>.py`: subclass `Backend` (its `[agent.<name>]` table of
`config.toml` is `self.settings`); `check()` fails early with a helpful message (missing package, key or
server); `run(task)` sends `task.system` + `task.prompt` with `task.model`/`task.effort`, exposes
`task.tools` and loops: every tool call goes through `Session.call` (logs, events, argument checks, the
handler; results are text and `Image`), the loop stops when `session.outcome.done` (a result with
`done=True`), when the model answers without tools or after `task.max_turns`; API errors go to
`outcome.error`. Register in `agent/backends/__init__.py`, add `[agent.<name>]` to `config.toml`, its
package to `requirements-video.txt` (imported inside `check`/`run`, so the others work without it) and its
models to `MODELS` in `app/configure.py`.

**Task behaviour** — texts in `agent/prompts/`, tools in `agent/tasks.py`, validation in `validate.py`,
order of tasks and retries in `app/run.py`.

## Testing

```bash
.venv/bin/python -m py_compile $(find src -name "*.py")
./lezio tools check <lesson>                             # blocks, narration, templates, refs
./lezio tools render <lesson> --segments s01 --preview   # step sheet in build/qa (estimated timing if no voice)
./lezio templates --demo all                             # every template renders its example (build/qa)
./lezio tools scene-api                                  # the API the model sees for its own templates
./lezio voices --try "Prova" --engine edge               # TTS engines
./lezio build <lesson>                                   # voice/render/join without LLM calls
.venv/bin/python tests/test_backends.py                  # LLM backends against fake servers (no model)
```

LLM tasks use the configured backend (by default the user's Claude subscription; the API backends cost
money): test them on small material first (e.g. a few PDF pages with `--focus`) and read
`lessons/<id>/build/agent/log.jsonl` (prompts, tool calls, tool results, token usage). The backends' tool
loops can be tested without any model against fake servers that speak each API (Anthropic SSE stream,
OpenAI Responses, Chat Completions + Ollama's `/api/ps`).

## Known pitfalls

- Manim loads scene files outside any package: `manim_entry.py` subclasses the scene so it is detected.
- Parallel renders need separate `--media_dir`s.
- Manim `Text` does not wrap; LaTeX is not installed (no `MathTex`): formulas with Unicode or MarkupText.
- pydub/Manim need `ffmpeg` on PATH: `setup.sh` links the imageio-ffmpeg binary into `.venv/bin`.
- Rich markup: escape user/config text containing `[...]` (`ui.escape`).
- Claude Agent SDK: isolation via `tools=[]`, `setting_sources=[]`, `strict_mcp_config=True`; images in
  tool results are compressed (`Image.from_file`) and `max_buffer_size` is raised.
- Anthropic API: streaming (`client.beta.messages.stream`), adaptive thinking + `output_config.effort`,
  `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) on Opus 5/5.5, Sonnet 5.5 and Fable 5.1;
  the assistant turn is sent back unchanged (thinking blocks included; after a mid-answer fallback only
  the text before the `fallback` block).
- OpenAI Responses API with `store: false`: reasoning items come back with `encrypted_content` and are
  passed back as they are; `function_call_output` can hold text and images.
- Local servers (Chat Completions): tool messages are text only, so pictures go in a user message after
  them; Ollama's default context (4096 on machines under 24 GB) silently cuts lezio's 15-25k-token prompts:
  the backend compares `GET /api/ps` `context_length` with what it sends.
- The package lives in `src/lezio/` because the wrapper `./lezio` and a `lezio/` folder cannot share a name.
