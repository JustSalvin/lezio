TASK: plan the lesson.
1. Read the material in scope (its listing is in the message; read gives the text of pages and sections)
   and look at it (view): many pages are pictures, diagrams or tables.
2. Decide how to teach it, following the teaching guidelines: the order of the topics, what goes
   together, what is left out, and for each segment how to show it.
3. Call submit_plan once with:
   - title: the lesson title;
   - outline: 3-6 sentences on what the lesson covers, its parts and how they connect;
   - visual_language: how the key concepts look in every segment, so the lesson reads as one: which theme
     color (by role name: PRIMARY, SECONDARY, HIGHLIGHT, POSITIVE, NEGATIVE, MUTED) and which symbol or
     recurring diagram each key concept gets (e.g. "bits: MONO digits in PRIMARY boxes; decimal values:
     SECONDARY; the current step: HIGHLIGHT"). The segments are written separately and follow it;
   - segments: the ordered segments of the lesson. A segment is one topic, shown by one scene with its
     narration: usually 0.5-3 minutes and 4-12 narration pieces. Each segment is
     {"title", "goal": what the viewer must understand by its end, "sources": refs of the material it
      covers (ranges allowed, e.g. "slides.pdf#p3-5"), "minutes": its length, "visual": how its scene
      teaches visually - the main representation (a diagram that builds up, an animation of a process, a
      worked example written step by step, a comparison, an original figure, ...), the templates that fit
      it, and why};
   - skipped: [{"ref", "reason"}] for the material in scope that no segment covers (live polls or quizzes,
     repeated or empty pages, minor details at depth 4, whatever the user's instructions exclude).
Every segment cites its sources (a recap cites what it sums up). Every page and section in scope must be
in the sources of some segment or in skipped. The first segment
opens the lesson (welcome, what it is about); the last one closes it with a short recap. Follow the depth
for the length. Titles, goals and visual ideas are given to whoever writes the segments: make them
specific.
