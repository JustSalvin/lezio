# lezio — handoff

What lezio is, how it works and what to keep in mind before changing it. For the details of each part
see `AGENTS.md` (developer guide), `README.md` (user guide), `docs/teaching-guidelines.md` (the research
behind the agent's teaching rules) and `docs/history.md` (how it came out of slide-reader).

The user writes in Italian: answer in Italian. Code, files and docs are in English. Narration and
on-screen texts of the videos are in the lesson language (Italian by default).

---

## 1. What it is

lezio turns **study material** (PDF slides or documents, Markdown/text, Word `.docx`, pictures; one or
more files of any kind) into a **narrated video lesson**: a synthetic voice explains the material while
scenes rendered with Manim (diagrams that build up, worked examples, tables, charts, clean slides,
original pages and figures, animations) change in sync with the voice.

It is a **program**, not an agent with free rein: the program runs the whole process (reading the
material, validation, speech synthesis, rendering, joining) and calls an LLM only for narrow tasks that
need judgment — planning the lesson, writing the narration and scenes of a few segments, reviewing the
final frames. In every task the model works only through tools the program defines (read the material,
look at pages, submit a segment — checked and previewed on the spot —, ...): it has no files, shell or web.

- Repository: `github.com/JustSalvin/lezio` (private). Local folder: `/Users/salvatore/Documents/Projects/slide-reader`
  (the folder kept its old name). Command: `./lezio` (bash wrapper → `.venv/bin/python -m lezio`, package in `src/lezio/`).
- Machine: macOS on Apple Silicon (M5, 24 GB). Python 3.14 via mise. Homebrew cairo/pkgconf. Two venvs:
  `.venv` (program, Manim 0.22, PyMuPDF, python-docx, Claude Agent SDK, rich, questionary, tomlkit) and
  `.venv-tts` (MLX, mlx-audio with Voxtral, edge-tts). `setup.sh` installs everything.
- LLM: Claude through the Claude Agent SDK with the user's Claude Code login (subscription, no API key).
  Default model Sonnet, effort high; per-task overrides possible.

## 2. How a lesson is made

```
./lezio make [files... | lesson]
  resolve choices (wizard or options) → summary + confirm
  → ingest material (new/changed files only)            program
  → plan                                                  agent task (1 session)
  → write segments, a few per session, with previews     agent tasks; voice generated in background
  → voice (what is still missing)                         local TTS (Voxtral) or online (edge)
  → render outdated segments (parallel)                   Manim
  → review final frames, fix segments                     agent tasks
  → re-render fixed → join (+ subtitles)                  ffmpeg → output/<lesson>.mp4 (+ .srt)
```

Everything is resumable: written segments, audio pieces and rendered segments are kept; changes are
detected with fingerprints, so only what changed is redone. Interrupting with Ctrl+C is safe.

### Per-video choices vs configuration (never mixed)
- **Per-video choices**, saved in the lesson (`script.json` settings): **depth** (1 extensive · 2 faithful
  [default] · 3 condensed · 4 short), **instructions** (free text: anything the user wants, with priority
  over the default rules, e.g. "show the original slides", "skip the live polls"), **focus** (page ranges
  of PDFs), and the files themselves (`lesson.json`).
- **Configuration**, only in `config.toml`, changed by hand or with `./lezio config` (menus, tomlkit keeps
  comments): voice/TTS engine, narration language and pause between pieces, agent backend/model/effort
  (+ per-task overrides), video theme/subtitles/resolution/fps, tuning. No CLI flags for configuration.
- There are **no visual styles** to choose: the agent decides how to teach each segment following the
  teaching guidelines. The **theme** (colors, fonts, sizes) is configuration only; the agent never
  chooses or changes it.

## 3. Concepts

**Material and refs.** Each source is read once into `build/material/<source id>/` and described in
`build/material/index.json`. PDF pages: page images (HD + preview), text lines with their bounding boxes
(L-numbers, used for highlights; repeated headers/footers removed), figures (raster images and vector
drawings detected, text frames excluded), superscripts kept as `2^k`. Text/Markdown: sections by
headings or paragraphs. DOCX: sections by headings, lists, tables as text, embedded pictures as figures.
Pictures: one item. Parts are addressed by **refs**: `slides.pdf#p3`, `slides.pdf#p3-5`,
`slides.pdf#p3.f1` (figure), `notes.md#s2`, `diagram.png`.

**Plan.** Title, outline, ordered **segments** (title, goal, sources, minutes, main visual idea), a
**visual language** for the whole lesson (which theme color/symbol each key concept gets, so separately
written segments read as one), and what is skipped and why. Every page/section in scope must be covered
or explicitly skipped. The program computes a **target length** from depth and amount of material
(`depth.toml` seconds per page or per 150 words, + half a minute for opening/recap) and rejects plans far
longer than it.

**Segments and blocks.** A segment's scene is a list of **blocks**:
`{"template": "bullets", "title": "...", "args": {...}, "say": ["piece", {"say": "...", "pause": 2}]}`.
Each narration piece is one audio file (key `<segment>_<piece>`), 8-60 words, written for the ear
(numbers in words, no symbols — digits and symbols are rejected). At run time the title stays while
consecutive blocks keep it, the previous content fades out, the template lays out inside the free area.

**Templates.** Data-driven scene blocks, functions `(ctx, steps, **args)` registered with
`@template(category, use_for, example)`. 36 in the library, in families: text (title card, question,
roadmap, bullets, definition, statement, recap quiz, predict), diagrams (flow, mapping, cards, diagram,
cycle, tree, layers, venn, timeline, concept map), comparing (compare, misconception, analogy,
example/non-example), math (number base, derivation, worked example, number line, table), data (function
plot with a safe expression evaluator, bar chart, line chart), computing (array with pointers, code with
highlighted lines, encode, translate), material (original page with highlights, figure with callouts).
Three sources, one interface: the library (`src/lezio/scene/templates/`), the user's own (`templates/` at
the project root), and the agent's own per lesson (`lessons/<id>/templates/<name>.py`, written with a
tool as a last resort, statically checked, executed only in the render subprocess). Every template's
`example` documents it for the agent and tests it: `./lezio templates --demo NAME|all`. The catalog the
agent reads is generated from signatures, docstrings, `use_for` and examples.

**Scene runtime.** `lezio.scene` is the public API of template code: narration sync (`t = steps()` starts
the next piece; `t.play/wait/until`), house style (theme color roles PRIMARY, SECONDARY, HIGHLIGHT,
POSITIVE, NEGATIVE, MUTED, TEXT, *_SOFT; fonts FONT, TITLE_FONT, MONO, HAND; sizes; `T`, `MT` with Pango
markup for formulas — there is no LaTeX —, `heading`, `box`, `arrow`), material access (`page`,
`figure`, `page.mark(lines)`), helpers (`run_phases`, `text_box`/`text_lines`, `dim_to`, `frame`...).
Agent code passes an AST allowlist (imports: manim, numpy, math, random, itertools, colorsys,
lezio.scene; no files, no `config`, no ImageMobject/SVGMobject, no dunder attributes) and runs with a
timeout. The runner reports per piece: timing, texts cut off or overlapping, text too small, animations
longer than the speech.

**Step sheets.** For every narration piece, the frame in its middle and at its end, with the start of
the sentence. They are what the agent looks at when writing (low-res preview with estimated timing) and
reviewing (final render); a tool shows one frame at full size.

**Themes.** `themes/<name>.toml` (light [default], dark, chalkboard, whiteboard, paper; users add their
own): colors by role, fonts, sizes. Applied before scene code runs; scenes use role names, so changing
the theme re-renders lessons with the new look without rewriting them.

**Voice.** Engines with declared options (`voice/engines/`): **Voxtral 4B** local via MLX (6-bit;
20 preset voices, only `it_male`/`it_female` are Italian; options: voice, temperature, model weights) and
**edge** (Microsoft neural voices, online). One voice per lesson. The worker runs in `.venv-tts` and
generates only new or changed pieces; written segments are voiced in the background while the agent
writes the next ones.

**Subtitles.** From the narration, timed with each piece of the final render, two lines max:
`track` (a subtitle track in the MP4 that players turn on/off + `.srt` beside it; default), `burned`
(drawn into the picture; scenes keep the bottom band free) or `off`.

**Agent tasks.** Plan (1 session), write (`segments_per_task` segments per session, each submission
checked and previewed, up to `preview_rounds` per segment), review (`review_group_size` segments per
session). Each session has a fresh context; continuity comes from what the program passes (plan, visual
language, last sentences of the previous segment, the lesson's own templates). Prompts live in
`src/lezio/agent/prompts/` (`role`, `plan`, `write`, `review`, `rules/teaching`, `rules/writing`,
`rules/narration_format`, `rules/scenes`, `depth.toml`). Log of every task: `lessons/<id>/build/agent/log.jsonl`.

## 4. Commands

| Command | |
|---|---|
| `./lezio` / `./lezio help [command]` | overview / options of a command |
| `make [files... \| lesson] [--depth N] [--instructions ...] [--focus FILE:PAGES] [--id] [--rewrite] [--no-review] [-y]` | new lesson or update (no args: wizard) |
| `redo <lesson> s03,s05 [--part script\|voice\|video] [--note ...]` | redo some segments |
| `build <lesson>` | voice + video + join without the agent |
| `list` · `status <lesson>` · `rename` · `copy` · `delete` | your lessons (work on `lessons/<id>/` only) |
| `config [show]` · `voices [--try ...]` · `themes [--preview]` · `templates [--demo]` | configuration (only `config` changes it) and previews |
| `tools check\|ingest\|audio\|render\|join\|scene-api` | low-level |

## 5. Files on disk

```
lezio  setup.sh  config.toml  mise.toml  requirements-*.txt
src/lezio/        the program (code map in AGENTS.md)
themes/           theme presets (versioned; users add their own)
templates/        the user's own templates (optional)
input/            study material (gitignored); files given from elsewhere are copied here
output/           finished videos + .srt (gitignored)
lessons/<id>/     lesson.json (sources), script.json (choices, plan, segments/blocks), templates/ (agent's),
                  build/ (cache: material, audio, video, qa step sheets, agent log, logs, joined.json)
lessons/_templates/   internal lesson for template demos and theme previews (gitignored)
archive/slide-reader/ lessons of the previous program (not loaded)
voice-samples/    voice tries (gitignored)
docs/             HANDOFF.md, history.md, teaching-guidelines.md
```

## 6. Decisions and constraints from the user (keep them)

- One workflow; no user-chosen visual styles; everything custom goes in the instructions, except depth
  (and which files/pages). Lessons are lectures with one voice (dialogue/review formats were dropped).
- The agent composes scenes from **library templates first**; its own templates only as a last resort.
- The **theme is configuration**: never chosen or changed by the agent or by instructions.
- Configuration changes only through `./lezio config` or the file; `voices`/`themes`/`templates` only show
  and preview.
- lezio works on the lesson, **not on `output/`**: lesson commands never move/rename/delete videos (it
  only writes the video when assembling); `delete` moves the lesson folder to the macOS Trash and never
  touches `input/`. Video state in `list`/`status` comes from the lesson (`build/joined.json`).
- **Never open other apps automatically** (no Preview/QuickTime/players): previews and samples are saved
  and their paths printed; audio is played only with an explicit `--play`.
- Consistent terminal UI: all output through `app/ui.py`; every command described once in `cli.COMMANDS`.
- Ask before outward-facing actions; the user tests lessons in parallel: check for running `lezio`/`manim`
  processes and do not touch their lessons; prompt files are read at every task, so editing them affects
  a running lesson.

## 7. Practical knowledge

- **Manim 0.22**: scene files load outside packages (`manim_entry.py` subclasses); parallel renders need
  separate `--media_dir`; `Text` does not wrap; no LaTeX (use `MT` with `<sup>/<sub>`; Unicode superscript
  letters are missing in many fonts; Charter/Palatino draw sub/sup badly, Baskerville is fine); drawing
  order = adding order, animated mobjects on top; `set_opacity` fills open curves (use `dim_to`);
  `Text.font_size` reflects scaling (used by the small-text check); creating Text in the project root
  leaves a `media/` folder (gitignored).
- **Claude Agent SDK**: isolation with `tools=[]`, `setting_sources=[]`, `strict_mcp_config=True`,
  `allowed_tools`; images in tool results compressed; raise `max_buffer_size`; `client.interrupt()` when a
  tool returns done; `AssistantMessage.model` tells the real model.
- **TTS**: Voxtral 6-bit ≈ 0.6-0.8× real time on the M5; always pass `max_tokens=4096`; keep pieces short;
  Voxtral via mlx-audio has no speed control and no voice cloning. `durations.json` is written atomically
  (renders read it while the voice is generated).
- **ffmpeg** (imageio-ffmpeg build, linked into `.venv/bin`): has libass (burned subtitles) and mov_text.
- **Rich**: escape user text (`ui.escape`); questionary returns None on Ctrl+C.

## 8. Performance and known limits

- Typical small test (6 slide pages, depth 2, ~7-8 min of video): plan ~0.5 min, writing ~5 min,
  voice ~5 min (now mostly overlapped with writing), render <1 min, review <1 min.
- A whole 61-page deck at depth 2 plans ~27 segments / ~80 min of video: writing ~35 min (sequential,
  ~1.2 min per segment), voice ~45-50 min with Voxtral. Writing sessions could run in parallel (each
  session is already independent apart from the previous segment's last sentences): not implemented yet.
- Templates the agent writes for itself are less polished than library ones (denser, smaller text).
- Open ideas: parallel write sessions; Opus for the plan and Sonnet for writing/review (per-task overrides
  exist); speech speed as a post-processing option; PowerPoint input (needs LibreOffice for page images);
  `anthropic-api` backend (stub); more TTS engines.

## 9. Checking that it works

```bash
.venv/bin/python -m py_compile $(find src -name "*.py")
./lezio templates --demo all          # every template renders its example (no LLM)
./lezio tools check <lesson>          # blocks, narration, templates, refs
./lezio build <lesson>                # voice, render, join without the agent
./lezio make input/x.pdf --focus "x.pdf:1-6" --depth 3 --yes   # end to end on small material (uses the subscription)
```
