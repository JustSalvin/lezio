SCRIPT FORMAT
A slide entry is {"slide": <page number>, "beats": [...]}. A beat is one spoken piece (one audio file)
plus what is shown meanwhile:
  {"say": "...", "highlight": X}   the slide, with a yellow frame around lines X
  {"say": "...", "image": true}    the slide, framing its largest image ("image": 2 = image #2)
  {"say": "...", "zoom": true}     the slide with a slow zoom (picture slides, section dividers)
  {"say": "..."}                   the slide, no frame
  {"anim": "<name>", "args": {...}, "steps": ["sentence", {"say": "sentence", "pause": 2}, ...]}
                                   a full-screen animation; EACH STEP is one spoken piece
Highlight X: a line number (3), a range ([3, 5]) - preferred -, exactly some lines ({"lines": [2, 4, 6]},
e.g. one column of a two-column table whose lines are listed interleaved), or a phrase contained in one
line ("Accordo sulla semantica") / ["start phrase", "end phrase"]. Line numbers are the L-numbers given
in the message. "pause": seconds of silence after a beat or step. No other keys are allowed.

Example (Italian lesson):
{"slide": 9, "beats": [
  {"say": "Il linguaggio di un calcolatore. Notate le virgolette attorno alla parola linguaggio.", "highlight": 1},
  {"say": "Un moderno calcolatore è un sistema elettronico, digitale, programmabile.", "highlight": [2, 4]},
  {"anim": "flow", "args": {"items": ["Programma", "Istruzioni", "Dati", "Memoria"], "title": "Dentro la macchina"},
   "steps": ["Il programma è fatto di istruzioni,", "che lavorano sui dati,", "e tutto finisce in memoria.",
             "Scritto con zeri e uni."]},
  {"say": "E qui nasce una domanda: come vengono codificate le istruzioni?", "highlight": 5}]}
