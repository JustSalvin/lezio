"""Voxtral 4B TTS (Mistral) running locally on Apple Silicon through mlx-audio."""
import numpy as np

from .base import Engine, Option

VOICES = ["it_male", "it_female", "fr_male", "fr_female", "es_male", "es_female", "de_male", "de_female",
          "pt_male", "pt_female", "nl_male", "nl_female", "ar_male", "hi_male", "hi_female",
          "casual_male", "casual_female", "cheerful_female", "neutral_male", "neutral_female"]


class Voxtral(Engine):
    name = "voxtral"
    description = "Voxtral 4B TTS by Mistral, local on Apple Silicon (MLX). Weights CC BY-NC (non-commercial)."
    runs = "local"
    options = {
        "model": Option("mlx-community/Voxtral-4B-TTS-2603-mlx-6bit",
                        "model weights; 6bit = best speed/quality, bf16 = original (about 4x slower), 4bit = smaller",
                        ["mlx-community/Voxtral-4B-TTS-2603-mlx-6bit", "mlx-community/Voxtral-4B-TTS-2603-mlx-4bit",
                         "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16"]),
        "voice": Option("it_male", "preset voice (it_* = native Italian; casual/cheerful/neutral = English)", VOICES),
        "temperature": Option(0.8, "expressiveness: lower = steadier and flatter, higher = livelier but more variable",
                              minimum=0.1, maximum=1.5),
    }

    def prepare(self, opts):
        from mlx_audio.tts.utils import load_model
        self.model = load_model(opts["model"])

    def synthesize(self, text, opts):
        parts, sr = [], None
        for r in self.model.generate(text=text, voice=opts["voice"], temperature=opts["temperature"], max_tokens=4096):
            parts.append(np.array(r.audio, dtype=np.float32))
            sr = r.sample_rate
        return np.concatenate(parts), sr

    def download(self, opts):
        from huggingface_hub import snapshot_download
        snapshot_download(opts["model"])
