# Handoff — rebuild of slide-reader into **lezio**

This document is the complete brief for rebuilding the program. Read it fully before changing code.
It contains: what exists today, what the user wants, the decisions already taken, the target
architecture, the execution plan (phases with checks), and the practical knowledge gathered so far.

The user writes in Italian; answer in Italian. Code, files, docs: English. Narration and on-screen texts
of videos: the lesson language (Italian by default).

---

## 1. Where we are (current program: slide-reader)

Repository: `github.com/JustSalvin/slide-reader` (private), local folder
`/Users/salvatore/Documents/Projects/slide-reader`. macOS, Apple Silicon (M5, 24 GB). Python 3.14 via
mise (`mise.toml`). Two venvs: `.venv` (program, Manim 0.22, PyMuPDF, Claude Agent SDK, rich,
questionary) and `.venv-tts` (MLX, mlx-audio 0.5.8 with Voxtral, edge-tts). Homebrew: cairo, pkgconf.

Current behaviour: `./sr` takes a **PDF of slides** and produces a narrated video where the original
slides are shown with yellow highlights synced to the voice, plus optional full-screen animations.
Layout today (see `AGENTS.md` for details):

```
slidereader/
  config.py lesson.py settings.py script.py validate.py pdf.py
  app/        cli.py run.py commands.py ui.py (rich) wizard.py (questionary)
  agent/      tasks.py, prompts/*.md + modes.toml, backends/ (claude_subscription.py, anthropic_api.py stub)
  voice/      engines/ (voxtral, edge), synthesize.py (worker in .venv-tts), client.py
  video/      scene.py (Manim, one slide), templates.py (11 templates), anim_api.py, render.py
lessons/<id>/ lesson.json, script.json (slides → beats), animations/*.py, build/ (cache)
input/ output/ config.toml sr setup.sh
```

What works and must be **kept** (reuse the code):
- Wizard (questionary, arrow keys) + options; summary panel + confirmation; `-y`.
- Settings split: per-video choices from wizard/options saved in the lesson; configuration only in
  `config.toml` (TTS engine/voice, language, LLM backend/model/effort, video, `[tuning]`).
- Rich UI: live steps with spinner/progress bar collapsing to "✓ title  detail  time"; agent activity
  described in words; final panel with the model that actually answered; logs in `build/logs/`.
- LLM layer: `agent/backends/` — `Task(system, prompt, tools, model, effort, on_event)`; backend
  `claude-subscription` via Claude Agent SDK with the user's Claude Code login (no API key), isolated
  session; tools are program-defined Python functions returning text/images; `done=True` ends the task.
- TTS layer: `voice/engines/` with declared options; `voice/synthesize.py` worker emitting JSON events;
  only new/changed pieces regenerated (meta stores text + TTS options).
- Change detection with fingerprints; parallel renders; temporary Manim files deleted after each render.
- Depth levels 1-4 (extensive, faithful [default], condensed, short) — unchanged.
- Custom instructions from the user, with priority over default rules.
- Resumability: running again continues; nothing is redone without need.

## 2. What the user wants (their words, summarized)

1. The program must not be slide-centric. **Input = study material**: PDF, text, DOCX, images, etc.
   (one or more files). **Output = a video lesson.**
2. New name: **lezio** (command `./lezio`).
3. Video styles: animation, slides, mixed — plus **whiteboard (lavagna)**, **dialogue (dialogo)**,
   **review/quiz (ripasso)**. Any input can produce any style (text → slide video, slides → animation, ...).
4. Slides in → slides out does **not** mean reusing the input slides. Nothing special is implied; if the
   user wants that, they write it as a custom instruction (e.g. "base the lesson only on the input slides").
5. **Full freedom to the agent** for video generation: the program only says the style; the agent
   writes the scenes with the libraries. No predefined template workflow per mode.
6. **One workflow for all modes**: a mode is only a different prompt.
7. Depth stays as it is. Review must not be slide-centric.
8. Old lessons (slide format): **archive** them.
9. Plan here, execute in a new session (this document is the handoff).

## 3. Decisions taken

- **Name**: package `lezio/`, command `./lezio` (bash wrapper like `sr`), README/AGENTS updated.
  Rename the GitHub repo to `lezio` with `gh repo rename lezio` (ask the user before doing it).
  Do not rename the local folder (the user can do it).
- **One axis, just prompts**: `style` (visual): `animated` · `slides` · `whiteboard` · `auto` (files
  under `lezio/agent/prompts/styles/`). **`auto` (user decision during execution, first called `mixed`)** =
  the agent chooses
  among the other three for each segment and may use all of them, switching along the video: the plan
  gives every segment a `style`; the write task uses that style's rules; the scene's default theme
  follows it (scene code may still switch theme inside a segment). The program composes `role.md + styles/<style>.md + depth rule +
  user instructions`.
- **Update during execution (user decision)**: the `format` axis (`dialogue`, `review`) was dropped. A
  lesson is always a lecture with one voice: no speakers, no per-speaker voices, no countdown helpers.
- **Segments instead of slides.** A lesson is an ordered list of segments. A segment = narration
  pieces (one audio file each) + one scene (Python code written by the agent) that is rendered with the
  narration audio. Everything (plan, write, preview, review, redo, fingerprints) works per segment.
- **Agent freedom**: scenes are arbitrary Manim code written by the agent, with an optional helper
  library (`lezio.scene`) for: audio sync (required), access to the material (page images, figures,
  text-line coordinates for highlighting), house style, a few layout helpers. The 11 old templates may
  survive as optional helpers inside `lezio.scene` but are never imposed.
- **Safety of agent code**: scene code is statically checked before running (AST): allowed imports
  only (`manim`, `numpy`, `math`, `random`, `itertools`, `colorsys`, `lezio.scene`); forbidden names
  (`open`, `exec`, `eval`, `compile`, `__import__`, `globals`, `getattr` on modules, `os`, `sys`,
  `subprocess`, `socket`, `pathlib`, `shutil`, `importlib`); render subprocess with a timeout. Problems
  are returned to the agent like validation errors.
- **Old lessons**: move `lessons/*` to `archive/slide-reader/` (kept in git, not loaded by lezio).
  `output/*.mp4` stay. `voice-samples/` stays (gitignored).

## 4. Target architecture

```
lezio                        bash wrapper → .venv/bin/python -m lezio
lezio/
  config.py                  paths, CONFIG, SUBPROCESS_ENV
  lesson.py                  Lesson paths (lessons/<id>/...), slugify, listing
  settings.py                per-video choices (style, depth, instructions, focus) vs config; TTS options
  script.py                  script.json v2: load/save, narration pieces, keys
  validate.py                narration rules + scene code checks (AST allowlist) + structure
  material/                  ingestion of study material → build/material/ index
    __init__.py              ingest(lesson) dispatch by extension; Material index API
    pdf.py                   page images (HD + preview), text lines with bbox, figures (from old pdf.py)
    text.py                  .txt/.md: sections by headings/paragraphs
    docx.py                  python-docx: headings, paragraphs, tables as text, embedded images
    image.py                 png/jpg/webp: copies + preview
    (pptx.py later: python-pptx text + images; page images via LibreOffice if installed)
  app/                       cli.py, run.py (one workflow), commands.py, ui.py, wizard.py (reuse)
  agent/
    tasks.py                 plan / write segment(s) / review — tools defined here
    prompts/                 role.md, plan.md, write.md, review.md, rules/{writing.md,narration_format.md,scene_api.md},
                             styles/{animated,slides,whiteboard,auto}.md, depth.toml
    prompts.py               loader (string.Template, $placeholders)
    backends/                reuse as is
  voice/                     reuse
  video/
    scene_runner.py          Manim scene: loads lessons/<id>/scenes/<segment>.py, runs build(scene, steps, material)
    manim_entry.py
    render.py                render segments / previews, contact sheets, fingerprints, join (reuse)
  scene/                     public helper library for agent code: `from lezio.scene import *`
    __init__.py              re-exports Manim + helpers
    sync.py                  Steps/Timer (from old anim_api)
    style.py                 colors, fonts, T(), box(), arrow(), ... (from old anim_api)
    material.py              page(source, n) → ImageMobject; highlight(source, n, lines) → frame; figure(...)
    layouts.py               optional: title_slide, bullets_slide, two_columns, ... (from old templates)
lessons/<id>/
  lesson.json                {"sources": ["input/a.pdf", "input/notes.md"], "created": ...}
  script.json                settings + segments
  scenes/<segment>.py        scene code written by the agent
  build/                     material/, audio/, video/, qa/, agent/, logs/, media/ (temporary)
archive/slide-reader/        old lessons
```

### 4.1 script.json v2

```json
{
  "settings": {"style": "auto", "depth": 2, "instructions": "",
               "focus": {"input/slides.pdf": "1-20"}},
  "title": "Rappresentazione dell'informazione",
  "segments": [
    {"id": "s01", "title": "Introduzione",
     "sources": ["slides.pdf#p1-3"],
     "narration": ["Benvenuti...", {"say": "E voi cosa ne pensate?", "pause": 2},
                   "Perché proprio due simboli?"],
     "scene": "s01"}
  ]
}
```
- `narration`: one entry per spoken piece (string or object with `say` and optional `pause`).
- `scene`: file `scenes/<id>.py` defining `def build(scene, steps, material): ...`; it must call
  `steps()` once per narration piece, in order (exactly the old `Steps` contract).
- Audio keys: `<segment>_<piece index>` (e.g. `s01_03`).

### 4.2 Material index (build/material/index.json)

```json
{"sources": [
  {"id": "slides.pdf", "type": "pdf", "path": "input/slides.pdf", "pages": 61,
   "items": [{"ref": "slides.pdf#p1", "text_lines": [{"text": "...", "bbox": [...]}],
              "image": "build/material/slides.pdf/p001.png", "preview": ".../p001.jpg", "figures": [...]}]},
  {"id": "notes.md", "type": "text", "items": [{"ref": "notes.md#2", "heading": "...", "text": "..."}]}
]}
```
Refs are what the agent cites in `sources` and passes to tools. Repeated headers/footers removed (reuse
`pdf.py` chrome detection).

### 4.3 Agent tasks (same for every style)

All tools return text/images; submissions are validated on the spot. The model has no files/shell/web.

| Task | Tools | Output |
|---|---|---|
| **plan** | `list_material()`, `read(ref)`, `view(refs)` (page/figure images), `submit_plan(plan)` | title, outline, ordered segments with id, title, goal, source refs, target length |
| **write** (1-3 segments per task) | `read`, `view`, `submit_segment(id, narration, code)` → checks narration rules + code (AST allowlist, compiles, has `build`, steps count) and **renders a low-res preview automatically**, returning contact-sheet frames; `finish(notes)` | narration + `scenes/<id>.py` |
| **review** | `view_final(segment)` (frames of the final render), `read`, `view`, `replace_segment(id, narration?, code?)` (validated + preview), `finish` | fixed segments |

Context given to every write task: style + depth rules, user instructions, lesson outline,
neighbouring segments' titles and the last sentences of the previous segment, the scene helper API
reference (generated from docstrings), the house style.

Narration: one voice, teacher tone (reuse old writing rules: write for the ear, numbers in words,
acronyms, phonetic foreign names, pieces of 8-60 words).

Default behaviour per **style** (prompt guidance only, agent is free):
- `animated`: full animations, no slide look; diagrams, transformations, motion.
- `slides`: clean generated slides (title + content), progressive reveal synced to the voice,
  highlight what is being said; may show original pages/figures when useful.
- `auto` (default): the agent picks `animated`, `slides` or `whiteboard` per segment (stored in the segment),
  using each where it explains best, and may alternate them along the video.
- `whiteboard`: white/dark board, content appears as if written/drawn by hand step by step (Manim
  `Write`/`Create`, handwriting-like font if available), arrows and annotations added while talking.

### 4.4 Program workflow (app/run.py) — one for all modes

```
resolve (wizard/options) → summary + confirm → ingest material (new sources only)
→ plan task (if no valid plan for current settings) → write tasks for segments without valid script/scene
→ voice (new/changed pieces) → render outdated segments → review task on re-rendered segments
→ re-render fixed → join → final panel
```
- Wizard for a new lesson: choose sources (multi-select files from `input/`, or paths given on the
  command line), optional page ranges for PDFs (`focus`), style, depth, instructions.
- Existing lesson menu: update · add/remove sources · change style/depth (rewrites, backup) ·
  change instructions · rewrite from scratch.
- `./lezio redo <lesson> --segments s03,s05 [--part script|voice|video] [--note "..."]`.
- `./lezio status <lesson>`: table of segments (pieces, voice, video state).
- Options: `--style`, `--depth`, `--instructions`, `--focus "file.pdf:1-20"`, `--id`,
  `--rewrite`, `--no-review`, `-y`. Sources are positional: `./lezio input/a.pdf input/notes.md`.

### 4.5 config.toml changes
- `[video]` unchanged; `[tuning]`: `segments_per_task` (replaces `group_size`), `preview_rounds`,
  `render_timeout_seconds`, `review_group_size`, `parallel_jobs`, image sizes.
- `[agent]` unchanged (backend, model, effort, per-task overrides `[agent.plan|write|review]`).

## 5. Execution plan (phases, each ends green before the next)

**Phase 0 — prepare**
- `git mv lessons archive/slide-reader` (create `lessons/` empty). Keep `output/`.
- Rename package `slidereader/` → `lezio/`, wrapper `sr` → `lezio`; fix imports; update `setup.sh`,
  requirements (add `python-docx`), `.gitignore`. Check: `./lezio --help` runs.

**Phase 1 — material ingestion**
- `lezio/material/` with pdf (move old `pdf.py` logic), text, docx, image; index.json; previews.
- Check: ingest the archived PDF + a small .md + a .docx + a .png into a test lesson; inspect index.

**Phase 2 — scene runtime**
- `lezio/scene/` (sync, style, material helpers, layouts from old templates), `video/scene_runner.py`
  executing `scenes/<id>.py:build(scene, steps, material)`; static code checks in `validate.py`;
  render with timeout; fingerprints per segment; join.
- Check: hand-write 2 scenes (one slide-like using `material.page` + highlight, one animated), fake
  narration with placeholder timing → preview contact sheets → final render → join.

**Phase 3 — script v2 + voice**
- script.json v2; voice worker generates the pieces of the segments (one voice).
- Check: a segment with real voice generates and renders.

**Phase 4 — agent tasks + prompts**
- Prompts: role, plan, write, review, rules (writing/narration format/scene API), styles ×4, depth.toml. Tools as in 4.3; scene API reference generated from `lezio/scene` docstrings.
- Check: plan + write on a 3-5 minute test (PDF pages 21-26 of the archived deck) in `auto`;
  then the same material in `animated`, `slides`, `whiteboard`; read `build/agent/log.jsonl`.

**Phase 5 — program workflow + UI**
- `app/run.py` generic flow, wizard (sources multi-select, style, depth, instructions), summary,
  status table by segment, redo by segment, final panel. Reuse ui.py/wizard.py patterns.
- `./lezio config` (requested by the user during execution): edit every config.toml setting through the
  arrow-key menus; config.toml stays the only place of configuration (written with tomlkit, comments kept).
- Check: full `./lezio` runs: new lesson from a .md file → slides video; from the PDF → animated video;
  resume after interruption; change style → rewrite with backup; voice change in config → regenerate.

**Phase 6 — docs and release**
- README (user guide, Italian examples allowed in commands), AGENTS.md (developer guide, new layout),
  remove this handoff's "current program" parts or move to `docs/history.md`. Commit, push, ask the user
  about `gh repo rename lezio`.

## 6. Practical knowledge (do not rediscover)

- **Claude Agent SDK** (`claude-agent-sdk==0.2.165`, `ClaudeSDKClient`): isolation with `tools=[]`,
  `setting_sources=[]`, `strict_mcp_config=True`, `allowed_tools=[mcp__<server>__<tool>...]`; custom tools
  via `@tool(name, description, json_schema, annotations=ToolAnnotations(maxResultSizeChars=4_000_000))`
  and `create_sdk_mcp_server`; tool results `{"content": [{"type":"text"}|{"type":"image","data":b64,
  "mimeType"}], "is_error": bool}`; set `max_buffer_size` (default 1 MB breaks with images) and compress
  images (JPEG, ≤1024 px for pages, ≤1440 px for contact sheets); `model`, `effort` options;
  `AssistantMessage.model` tells the real model (seen: `claude-opus-5-5`); silence SDK logger
  (`logging.getLogger("claude_agent_sdk").setLevel(ERROR)`) because Manim's rich logging prints it;
  call `client.interrupt()` when a tool returns done.
- **Manim 0.22**: scene file is loaded outside any package → `manim_entry.py` subclasses the scene;
  parallel renders need separate `--media_dir`; `Text` does not wrap; no LaTeX installed; never remove
  `scene.mobjects` in agent code (the runner restores required background objects); `ImageMobject` scaling
  works on high-res PNGs (2700 px wide for slides); render previews with `-ql`; ffmpeg must be on PATH
  (`.venv/bin/ffmpeg` symlink to imageio-ffmpeg).
- **TTS**: Voxtral 6-bit (`mlx-community/Voxtral-4B-TTS-2603-mlx-6bit`) ≈ 0.8× real time on M5, needs
  `mistral-common[audio]`; voices `it_male` (good), `it_female` (strong accent, user dislikes it);
  bf16 is ~4× slower; mlx-audio CLI default `max_tokens=1200` truncates (~96 s) → always pass
  `max_tokens=4096` and keep pieces short. Edge-tts voices `it-IT-DiegoNeural` etc. (online). Qwen3-TTS
  was tested and rejected by the user (random pauses, odd accent on long text).
- **Writing for TTS**: numbers in words, phonetic foreign names ("von Noiman"), no parentheses/symbols;
  validation rejects digits and pieces > 70 words.
- **PDF**: chrome detection = text repeated on ≥40% of pages at the same place, or anywhere in the
  top/bottom 12% band; two-column tables produce interleaved lines → highlight `{"lines": [...]}`.
- **UI**: rich markup eats `[...]` → `rich.markup.escape`; questionary returns None on Ctrl+C.
- **git push**: if credentials fail, `gh auth setup-git` (already done by the user).
- The user tests the program themselves in parallel: before refactoring, check `ps` for running
  `lezio`/`manim` processes and do not break their lessons.
- Agent tasks cost subscription usage: test on small material first.

## 7. Open points to confirm with the user during execution
- `gh repo rename lezio` (outward-facing).
- Handwriting font for `whiteboard` (needs a font with a suitable licence; otherwise Manim default + `Write`).
- PPTX support priority (needs LibreOffice for page images).
