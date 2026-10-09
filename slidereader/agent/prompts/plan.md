TASK: plan the lesson.
Look at every slide in scope (view_slides), then call submit_plan once with:
- title: the lecture title;
- outline: 3-6 sentences on what the lecture is about, its parts and how they connect;
- slides: one entry per page in scope, in page order:
  {"slide": n, "kind": "title|agenda|divider|content|diagram|interactive|references|other",
   "skip": true|false, "summary": "one sentence on what the slide says",
   "visual_idea": "none" | "template <name>: <what it shows>" | "custom: <what it shows>"}
skip = true for interactive slides (live polls, quizzes or audience voting run with an external app), at
depth 4 for minor slides, and for whatever the user's instructions say to skip; otherwise false.
visual_idea: "none" in visual mode slides; never "none" in visual mode animated. Templates: title_card,
bullets, statement, flow, mapping, compare, cards, encode, translate, number_base, diagram.
The summaries are given to whoever writes the neighbouring slides, so make them informative.
