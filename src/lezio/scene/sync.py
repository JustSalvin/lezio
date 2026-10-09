"""Synchronizing a scene with its narration.

The narration of a segment is a list of pieces; each piece is one audio file. Calling `t = steps()`
starts the next piece (its audio plays from now) and returns a Timer holding that piece's duration.
Spend it with t.play(...), t.wait(...), t.until(...); whatever is left is waited automatically when
the next piece starts. Call steps() exactly once per piece, in order.
"""


class Timer:
    """The time of one narration piece.

    t.duration   seconds of speech of this piece          t.left     seconds of speech not yet used
    t.pause      seconds of silence after it (from the narration "pause")
    t.say        the text being spoken                     t.speaker  "teacher" or "student"
    t.index      0-based number of the piece in the segment
    """

    def __init__(self, scene, duration, pause=0, say="", speaker="teacher", index=0):
        self.scene, self.duration, self.left = scene, duration, duration
        self.pause, self.pause_left, self.say, self.speaker, self.index = pause, pause, say, speaker, index
        self.overrun = 0.0

    def play(self, *animations, rt=1.0, **kwargs):
        """Play animations together for rt seconds (Manim's run_time)."""
        self.scene.play(*animations, run_time=rt, **kwargs)
        self.left -= rt
        if self.left < 0:
            self.overrun = -self.left

    def wait(self, seconds):
        """Wait (within the speech of this piece)."""
        seconds = min(seconds, self.left)
        if seconds > 0.02:
            self.scene.wait(seconds)
            self.left -= seconds

    def until(self, fraction):
        """Wait until `fraction` (0..1) of this piece's speech has elapsed."""
        self.wait(self.duration * fraction - (self.duration - self.left))

    def finish(self):
        """Wait until the speech of this piece ends."""
        self.wait(self.left)

    def during_pause(self, *animations):
        """Wait for the end of the speech, then play animations over the silent pause after it
        (e.g. a countdown while the viewer thinks). Without animations, just waits the pause."""
        self.finish()
        if self.pause_left > 0.05:
            if animations:
                self.scene.play(*animations, run_time=self.pause_left)
            else:
                self.scene.wait(self.pause_left)
        self.pause_left = 0

    def clear(self, rt=0.5):
        """Fade out everything on screen."""
        mobs = list(self.scene.mobjects)
        if mobs:
            from manim import FadeOut
            self.play(*[FadeOut(m) for m in mobs], rt=rt)
            self.scene.remove(*mobs)


class Steps:
    """The narration pieces of a segment. len(steps) = number of pieces; steps.left = not started yet."""

    def __init__(self, scene, pieces, gap, on_start=None, on_end=None):
        """pieces: list of dicts {"wav", "duration", "pause", "say", "speaker"}."""
        self.scene, self.pieces, self.gap = scene, pieces, gap
        self.on_start, self.on_end = on_start, on_end
        self.i, self.current = 0, None

    def __len__(self):
        return len(self.pieces)

    @property
    def left(self):
        return len(self.pieces) - self.i

    def _close(self):
        if self.current is not None:
            t, self.current = self.current, None
            t.finish()
            if self.on_end:
                self.on_end(t)
            self.scene.wait(self.gap + t.pause_left)

    def __call__(self):
        self._close()
        if self.i >= len(self.pieces):
            raise RuntimeError(f"steps() called more times than there are narration pieces ({len(self.pieces)})")
        p = self.pieces[self.i]
        if p.get("wav"):
            self.scene.add_sound(p["wav"])
        self.current = Timer(self.scene, p["duration"], p.get("pause", 0), p.get("say", ""),
                             p.get("speaker", "teacher"), self.i)
        self.i += 1
        if self.on_start:
            self.on_start(self.current)
        return self.current

    def take(self, n):
        """A part of the remaining pieces (the next n), to give to a layout: bullets(scene, steps.take(3), ...)."""
        if not 1 <= n <= self.left:
            raise ValueError(f"steps.take({n}): only {self.left} narration pieces are left")
        return _Part(self, n)

    def finish(self):
        """Play the pieces not started yet (over the current screen) and close the last one."""
        while self.i < len(self.pieces):
            self()
        self._close()


class _Part:
    def __init__(self, parent, n):
        self.parent, self.n, self.i = parent, n, 0

    def __len__(self):
        return self.n

    @property
    def left(self):
        return self.n - self.i

    def __call__(self):
        if self.i >= self.n:
            raise RuntimeError(f"this part of the narration has only {self.n} pieces")
        self.i += 1
        return self.parent()

    def take(self, n):
        if not 1 <= n <= self.left:
            raise ValueError(f"take({n}): only {self.left} pieces are left in this part")
        return _Part(self, n)

    def finish(self):
        while self.i < self.n:
            self()
