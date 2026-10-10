# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Registry of text-to-speech engines. To add one: subclass Engine in a new module and list it here."""
from .base import Engine, Option
from .edge import Edge
from .voxtral import Voxtral

ENGINES = {e.name: e for e in (Voxtral, Edge)}


def get_engine(name):
    if name not in ENGINES:
        raise SystemExit(f"unknown TTS engine '{name}' (available: {', '.join(ENGINES)})")
    return ENGINES[name]


def resolve(config_tts, lesson_tts=None, overrides=None):
    """Full option set of the chosen engine: engine defaults < config.toml [tts.<engine>] < lesson < overrides."""
    lesson_tts, overrides = lesson_tts or {}, overrides or {}
    name = overrides.get("engine") or lesson_tts.get("engine") or config_tts["engine"]
    engine = get_engine(name)
    opts = {k: o.default for k, o in engine.options.items()}
    opts.update(config_tts.get(name, {}))
    if lesson_tts.get("engine", name) == name:
        opts.update({k: v for k, v in lesson_tts.items() if k != "engine"})
    opts.update({k: v for k, v in overrides.items() if k != "engine"})
    return {"engine": name, **opts}


__all__ = ["ENGINES", "Engine", "Option", "get_engine", "resolve"]
