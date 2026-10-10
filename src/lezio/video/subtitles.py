# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Subtitles from the narration: the text of every piece, timed with the final render of each segment.

config.toml [video] subtitles:
    "track"   a subtitle track inside the MP4 that players can turn on and off (QuickTime, VLC, IINA,
              Windows players, ...), plus output/<lesson>.srt beside the video (YouTube, editors)
    "burned"  always visible, drawn into the picture (for places that ignore subtitle tracks)
    "off"     none
"""
import json
import re
import subprocess

from ..config import CONFIG, FFMPEG
from ..script import load_script

MAX_LINE = 42                 # characters per subtitle line (two lines per cue at most)
LANGUAGES = {"italian": "ita", "english": "eng", "spanish": "spa", "french": "fra", "german": "deu",
             "portuguese": "por", "dutch": "nld"}


def mode():
    m = str(CONFIG.get("video", {}).get("subtitles", "track")).lower()
    return m if m in ("track", "burned", "off") else "track"


def language_code():
    return LANGUAGES.get(CONFIG["narration"]["language"].strip().lower(), "und")


def _chunks(text):
    """Split a piece into cues of at most two lines. Words are packed greedily; when a cue is full it is cut
    at its last punctuation mark past 40% of its length (sentence end, comma...), else between words, so
    cues are neither too long nor too short ("Benvenuti!" joins what follows)."""
    limit = 2 * MAX_LINE
    out, cur = [], []
    for w in text.split():
        if cur and len(" ".join(cur + [w])) > limit:
            cut = len(cur)
            for i in range(len(cur) - 1, 0, -1):
                if re.search(r"[.!?…,;:]$", cur[i - 1]) and len(" ".join(cur[:i])) >= 0.4 * limit:
                    cut = i
                    break
            out.append(" ".join(cur[:cut]))
            cur = cur[cut:]
        cur.append(w)
        if re.search(r"[.!?…]$", w) and len(" ".join(cur)) >= 0.6 * limit:
            out.append(" ".join(cur))                    # a full sentence that fills a cue well
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def _two_lines(text):
    """Break a cue into two balanced lines when it is longer than one line."""
    if len(text) <= MAX_LINE:
        return text
    words = text.split()
    best, best_diff = text, None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if len(a) <= MAX_LINE + 4 and len(b) <= MAX_LINE + 4:
            diff = abs(len(a) - len(b))
            if best_diff is None or diff < best_diff:
                best, best_diff = f"{a}\n{b}", diff
    return best


def cues(lesson):
    """[(start, end, text)] over the whole final video (segments in script order)."""
    from .render import video_duration
    script = load_script(lesson.script)
    out, offset = [], 0.0
    for seg in script["segments"]:
        video = lesson.segment_video(seg["id"])
        report_path = lesson.qa / f"{seg['id']}.json"
        if not video.exists():
            continue
        report = json.loads(report_path.read_text()) if report_path.exists() else {}
        for p in report.get("pieces", []):
            if "end" not in p or not p.get("say", "").strip():
                continue
            parts = _chunks(p["say"])
            total = sum(len(x) for x in parts) or 1
            t, span = offset + p["start"], p["end"] - p["start"]
            for x in parts:
                d = span * len(x) / total
                out.append((t, t + d, _two_lines(x)))
                t += d
        offset += video_duration(video)
    return out


def _stamp(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(items, path):
    path.write_text("".join(f"{k}\n{_stamp(a)} --> {_stamp(b)}\n{text}\n\n"
                            for k, (a, b, text) in enumerate(items, 1)), encoding="utf-8")
    return path


def burn_filter(srt):
    """ffmpeg video filter drawing the subtitles: white text on a translucent dark band, the theme font."""
    from ..scene.style import load_theme
    from ..settings import house_theme
    font = load_theme(house_theme())["fonts"].get("text", "Avenir Next")
    # sizes are relative to a 288-pixel-high canvas (libass default for SRT): 15 is about 5% of the height
    style = (f"Fontname={font},Fontsize=17,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=4,"
             "Outline=0,Shadow=0,MarginV=8")
    path = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return f"subtitles='{path}':force_style='{style}'"


def probe_streams(path):
    out = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    return re.findall(r"Stream #\d+:\d+(?:\[\w+\])?(?:\((\w+)\))?: (\w+): (\w+)", out)
