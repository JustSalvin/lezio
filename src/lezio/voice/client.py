"""Runs the speech worker (voice/synthesize.py) in the TTS environment and relays its progress events."""
import json
import subprocess

from ..config import ROOT, SUBPROCESS_ENV as ENV, VOICE_PY


class VoiceError(Exception):
    pass


def _run(args, on_event=None, log=None):
    proc = subprocess.Popen([str(VOICE_PY), "-m", "lezio.voice.synthesize", *args], cwd=ROOT, env=ENV,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    error, last = None, []
    with open(log, "a") if log else open("/dev/null", "w") as fh:
        for line in proc.stdout:
            fh.write(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                last = (last + [line.strip()])[-5:]
                continue
            if event.get("event") == "error":
                error = event["message"]
            elif on_event:
                on_event(event)
    if proc.wait() != 0:
        raise VoiceError(error or " | ".join(l for l in last if l) or "speech synthesis failed")


def synthesize_lesson(lesson, pages="", on_event=None):
    lesson.logs.mkdir(parents=True, exist_ok=True)
    _run(["lesson", lesson.id, "--pages", pages], on_event, lesson.logs / "voice.txt")


def sample(text, overrides, out, on_event=None):
    _run(["sample", text, "--out", str(out), "--set", json.dumps(overrides)], on_event)
