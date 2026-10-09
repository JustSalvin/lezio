ANIMATIONS
Use an animation when SEEING explains better than reading: processes, transformations, encodings,
architectures and data flows, comparisons, cause -> effect, a concrete example of an abstract rule.
Depth 1: about one every one or two content slides; depth 2: only for diagrams/processes; depth 3: rare;
depth 4: a few strong ones. Never just decoration. Prefer templates; templates spread their phases over
the steps, so give one step per phase (flow with four items -> four steps).

TEMPLATES (name(arguments) and what they do):
$templates

CUSTOM ANIMATIONS - only when no template fits. Submit them as `animation_code` (Python source) with
submit_script; every function name must start with the prefix "$prefix". Example:

from slidereader.video.anim_api import *   # Manim + house style + helpers

def ${prefix}segment_decay(scene, steps):        # used as {"anim": "${prefix}segment_decay", "steps": [s1, s2]}
    t = steps()                                    # step 1 starts: its audio plays now
    eight = T("8", 160, RED, bold=True)
    t.play(FadeIn(eight), rt=0.6)                  # rt = run time in seconds
    t.until(0.5)                                   # wait until half of this step's audio
    t.play(Indicate(eight), rt=0.8)
    t = steps()                                    # step 2
    t.play(Transform(eight, T("3", 160, RED, bold=True)), rt=0.8)

- Signature (scene, steps, **args); call steps() exactly once per step, in order; leftover time is waited
  automatically.
- Helpers: T(text, size, color, bold=False, font=FONT|MONO), box(text, w, h, size, color, fill),
  arrow(start, end, color, double=False), person(color), check(), cross(), wrap(text, width).
  Colors: BLUE, BLUE_LIGHT, ORANGE, ORANGE_LIGHT, GREEN, GREEN_LIGHT, YELLOW, YELLOW_LIGHT, RED, DARK, GREY;
  white background. All of Manim is available (VGroup, Arrow, Circle, FadeIn, Transform, LaggedStart, ...).
- Layout: frame x in [-7.1, 7.1], y in [-4, 4]; keep everything inside x in [-6.6, 6.6], y in [-3.6, 3.4].
  Sizes: titles 36-44, body 28-36, big symbols 90-160.
- Pitfalls: Text does not wrap (use wrap()); NO LaTeX (no MathTex/Tex); do not animate the same object twice
  in one t.play(...); on-screen texts are short labels; never FadeOut/remove scene.mobjects (it contains the
  slide) - fade out the groups you created.
