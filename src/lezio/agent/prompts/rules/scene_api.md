SCENE CODE
Every segment has a scene: Python code for Manim Community 0.22, submitted as `code`. Example:

from lezio.scene import *          # all of Manim + the helpers listed below

def build(scene, steps, material):
    t = steps()                                     # piece 0 starts: its audio plays now
    title = heading("Il sistema binario")
    t.play(Write(title), rt=1.0)                    # rt = run time in seconds
    t.until(0.5)                                    # wait until half of this piece's speech
    bits = VGroup(*[box(b, w=1.2, h=1.2, size=48) for b in "01"]).arrange(RIGHT, buff=0.6)
    t.play(FadeIn(bits, shift=UP * 0.3), rt=0.8)
    t = steps()                                     # piece 1
    t.play(Indicate(bits[1]), rt=0.8)

Contract:
- build is called once. Call steps() exactly once per narration piece, in order. The time between two
  steps() calls is the speech of one piece: spend it with t.play / t.wait / t.until; leftover time is
  waited automatically. Animations longer than the speech make the voice wait: keep them shorter.
- You own the whole screen: the scene starts empty, with the background of the lesson's theme. Add,
  transform and remove what you need; fade out what is no longer discussed (t.clear() fades out everything).
- House style: colors, fonts and sizes come from the theme by name (PRIMARY, HIGHLIGHT, TEXT, FONT, HAND,
  TEXT_SIZE, ...): never write fixed colors, so every lesson follows the theme. Screen titles with
  heading(...), so they look the same in every scene.
- Imports allowed: manim, numpy, math, random, itertools, colorsys, lezio.scene. No files, no `config`,
  no ImageMobject/SVGMobject (use material.page / material.figure), no add_sound.
Layout: the frame is x from -7.1 to 7.1, y from -4 to 4; keep everything inside x -6.6..6.6, y -3.6..3.4.
Use the space: content is large and spread over the frame (or centered), never a small cluster in a
corner. Font sizes: TITLE_SIZE for titles, TEXT_SIZE for text (never below SMALL_SIZE), big symbols 90-160. At most about 6 text
lines on screen at once: split long lists or tables, or show only the part being discussed. Something
relevant is on screen from the first second of every piece: never a title alone over an empty frame.
Pitfalls: Text does not wrap (use wrap(text, width)); there is NO LaTeX (MathTex and Tex fail): write
formulas with MT and <sup>/<sub> for exponents and indices - MT("2<sup>k-1</sup>") - and Unicode symbols
(×, ÷, ≤, ≥, ≠, √, π, →, ∑, ⌈ ⌉); never Unicode superscript or subscript letters (ᵏ ⁿ ⁻ ₖ): many fonts,
the handwriting one included, cannot draw them; do not animate the same mobject twice in one t.play; Transform keeps the first mobject on screen (use
ReplacementTransform or FadeOut what you replace); keep a reference to everything you add so you can
remove it.

HELPERS (from lezio.scene)
$api
