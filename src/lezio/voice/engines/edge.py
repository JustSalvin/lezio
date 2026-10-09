"""Microsoft Edge neural voices through the edge-tts package (online, free, no account).

The narration text is sent to Microsoft's service. Useful as a light alternative or on machines
without Apple Silicon.
"""
import asyncio
import tempfile
from pathlib import Path

from .base import Engine, Option

ITALIAN = ["it-IT-DiegoNeural", "it-IT-IsabellaNeural", "it-IT-ElsaNeural", "it-IT-GiuseppeMultilingualNeural"]


class Edge(Engine):
    name = "edge"
    description = "Microsoft Edge neural voices (online: the text is sent to Microsoft). Free, very fast."
    runs = "online"
    options = {
        "voice": Option("it-IT-DiegoNeural", "voice name; Italian ones are listed, any edge-tts voice works "
                        "(full list: .venv-tts/bin/edge-tts --list-voices)"),
        "rate": Option("+0%", "speaking speed, e.g. -10% slower, +10% faster"),
        "pitch": Option("+0Hz", "voice pitch, e.g. -5Hz lower, +5Hz higher"),
    }
    suggested_voices = ITALIAN

    def prepare(self, opts):
        import edge_tts  # noqa: F401  (fail early if missing)

    def synthesize(self, text, opts):
        import edge_tts
        import soundfile as sf
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "piece.mp3"
            com = edge_tts.Communicate(text, opts["voice"], rate=opts["rate"], pitch=opts["pitch"])
            asyncio.run(com.save(str(mp3)))
            audio, sr = sf.read(mp3, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return audio, sr
