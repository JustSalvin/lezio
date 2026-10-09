"""Task prompts. Each task is self-contained: the program gives the inputs and names the only files the
agent may write. The agent never runs commands; the program validates and renders everything itself."""

HEADER = """You are a worker of the slide-reader program, called for ONE task.
Rules: read AGENTS.md (sections named below) before starting. Write only the files listed under
"Output". Do not run commands and do not touch any other file. When the output file is written, reply
with one short line and stop.

Lesson: {id}   Narration language: {language}
Visual mode: {visual} ({visual_rule})
Depth: {depth} - {depth_name} ({depth_rule})
"""

VISUAL_RULES = {
    "slides": "original slides with synced highlights; no animations",
    "mixed": "slides with highlights plus full-screen explanation animations where useful",
    "animated": "animations only; the slides are the source but are never shown; every beat is an anim",
}
DEPTH_RULES = {
    1: "say everything on each slide and go deeper with explanations, examples, connections; never summarize",
    2: "say everything on each slide, rephrased for speech; add nothing, cut nothing",
    3: "main points of each slide, lightly summarized",
    4: "very concise, short-video style, only key ideas",
}

PLAN = HEADER + """
TASK: plan the lesson.  AGENTS.md sections: 1, 2.

Inputs:
- Slide text, numbered lines and hints: {overview}
- Slide pictures (open EVERY one in scope): {preview_dir}/slide_NN.jpg
- Pages in scope: {pages}

Output: {output}  - JSON exactly in the "Plan file" format of AGENTS.md section 2, with one entry for
every page in scope, in order.
"""

WRITE = HEADER + """
TASK: write the narration script for slides {slide_list} (group {group} of {groups}).
AGENTS.md sections: 3, 4, 5.

Lesson outline: {outline}

Slides of this group (plan notes, text lines with their numbers, images, picture to open):
{slide_blocks}

Context:
- {before}
- {after}

Output:
- {output}: JSON {{"slides": [...]}} with exactly the slides {slide_list}, in this order, in the
  script format of AGENTS.md section 3.
- {anim_file}: ONLY if you need custom animations (no template fits). Function names must start with
  "{prefix}". Leave it uncreated otherwise.
"""

FIX = HEADER + """
TASK: fix the problems the program found in {target}.  AGENTS.md sections: 3, 4, 5.

Problems:
{problems}

Output: edit {target}{extra} so that every problem is solved. Change nothing else.
"""

JUDGE_ANIMATIONS = HEADER + """
TASK: judge the animations of slides {slide_list}.  AGENTS.md section 6.

The program rendered each animation alone. Open every contact sheet (frames in time order, left to right,
top to bottom):
{sheets}

If something is wrong, fix it in {group_file}{anim_file_note}.
Output: {output} - JSON {{"changed": true|false, "notes": "what you fixed, or why it is fine"}}.
"""

REVIEW = HEADER + """
TASK: review the final video of slides {slide_list}.  AGENTS.md section 7.

Contact sheets of the rendered slides (frames in time order):
{sheets}

The script of these slides is in {script} (do not touch other slides).
If something is wrong, fix it in {script}{anim_note}.
Output: {output} - JSON {{"changed": true|false, "notes": "what you fixed, or why it is fine"}}.
"""
