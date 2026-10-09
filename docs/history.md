# History — from slide-reader to lezio

## slide-reader (until October 2026)

The first version, `./sr`, took **one PDF of slides** and produced a narrated video in which the original
slides were shown with yellow highlights synced to the voice, plus optional full-screen animations chosen
from 11 templates or written as custom functions. Visual modes: `slides`, `mixed`, `animated`; depth
levels 1-4. The script was a list of slides, each a list of "beats" (`say` + `highlight`/`image`/`zoom`, or
`anim` with `steps`).

What lezio kept from it: the program-driven design (the LLM only does narrow tasks through
program-defined tools, every submission validated on the spot), the Claude subscription backend through
the Claude Agent SDK, the TTS engines with declared options and the worker in a separate environment,
the wizard and the rich terminal UI, the split between per-video choices and configuration, change
detection with fingerprints, resumability, the depth levels, the writing rules for speech, PDF chrome
detection and text-line highlighting, the house style and the animation templates (now optional layouts).

The lessons made with slide-reader are kept in `archive/slide-reader/` (not loaded by lezio); their
videos stay in `output/`.

## The rebuild (October 2026)

What the user asked for:

1. Not slide-centric: the input is **study material** (PDF, text, DOCX, pictures; one or more files),
   the output is a video lesson.
2. A new name: **lezio** (`./lezio`).
3. Any input can produce any visual style; slides in does not mean the input slides are shown (that is
   a custom instruction when wanted).
4. Full freedom to the agent: the program says the style, the agent writes the scenes with the
   libraries; no predefined template workflow.
5. One workflow for all styles: a style is only a prompt.
6. Depth unchanged; the review is not slide-centric.

Decisions taken while planning: segments instead of slides (narration pieces + one scene of free Manim
code each, with an optional helper library `lezio.scene`); a material index with refs
(`slides.pdf#p3`, `notes.md#s2`, `...#p3.f1`); static checks of agent code (imports allowlist, no files)
and render timeouts; the program workflow plan → write (with automatic previews: step sheets) → voice →
render → review → join.

Changes decided by the user during the execution:

- The second axis `format` (`lecture`/`dialogue`/`review`, with a teacher and a student voice) was
  dropped: a lesson is always a lecture with one voice.
- Styles were first `animated`, `slides`, `whiteboard` and `auto` (the agent choosing per segment), then
  dropped altogether: the agent decides how to teach every segment following teaching guidelines drawn
  from research (`docs/teaching-guidelines.md`), and everything specific the user wants goes in the
  instructions. Only the depth remains a choice (plus which files and pages to use).
- The house visual style became themes: files in `themes/` with presets (light, dark, chalkboard,
  whiteboard, paper) that users can copy and edit; scenes use color roles, so a theme re-skins lessons.
- `./lezio config`: every configuration setting can be changed through the arrow-key menus;
  `config.toml` stays the only place of the configuration (edited with tomlkit, comments kept).

Implementation notes: the package lives in `src/lezio/` because the wrapper `./lezio` and a `lezio/`
folder cannot share a name. PowerPoint input is on the roadmap (it needs LibreOffice for page images).
