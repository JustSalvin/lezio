# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""./lezio config: change config.toml through arrow-key menus.

config.toml stays the only place of the configuration: this command edits it with tomlkit, so comments
and layout of the file are kept. Nothing is written until "Save and exit".
"""
import time

import questionary
import tomlkit
from questionary import Choice, Separator

from ..agent.backends import BACKENDS
from ..agent.backends.openai_compatible import LOCAL_URL
from ..config import CONFIG_FILE, ROOT
from ..voice import engines
from . import ui
from .wizard import STYLE, ask

EFFORTS = ["low", "medium", "high", "xhigh", "max"]
CLAUDE = [("sonnet", "fast and capable"), ("opus", "the most capable, slower"), ("haiku", "the fastest")]
MODELS = {"claude-subscription": CLAUDE,
          "anthropic-api": CLAUDE + [("fable", "Anthropic's most capable, the most expensive")],
          "openai-api": [("gpt-6.1-sol", "balanced"), ("gpt-6-astra", "the most capable"),
                         ("gpt-6-luna", "the fastest")]}    # local: the model's name on the server
TASKS = {"plan": "planning the lesson", "write": "writing narration and scenes", "review": "final review"}
RESOLUTIONS = [(1920, 1080), (1280, 720), (2560, 1440), (3840, 2160)]
FPS = [24, 25, 30, 60]
TUNING = {
    "segments_per_task": "segments written per agent task",
    "voice_while_writing": "generate the voice of written segments while the next ones are written",
    "preview_rounds": "submissions (previews) allowed per segment while writing",
    "render_timeout_seconds": "a scene render taking longer is stopped",
    "review_group_size": "segments per review task",
    "parallel_jobs": "segments rendered in parallel",
    "page_image_width": "pixel width of page images in the video",
    "preview_image_width": "pixel width of the pictures shown to the agent",
}
BACK = "__back__"


def select(message, choices, default=None):
    return ask(questionary.select(message, choices=choices, default=default, style=STYLE))


def text(message, default="", validate=None):
    return ask(questionary.text(message, default=str(default), validate=validate, style=STYLE)).strip()


def number(message, current, integer=True, minimum=None, maximum=None):
    def ok(value):
        try:
            v = int(value) if integer else float(value)
        except ValueError:
            return "a whole number" if integer else "a number"
        if minimum is not None and v < minimum:
            return f"at least {minimum}"
        if maximum is not None and v > maximum:
            return f"at most {maximum}"
        return True
    value = text(message, current, ok)
    return int(value) if integer else float(value)


def table(doc, *path):
    """The table at a path, created if missing."""
    t = doc
    for key in path:
        if key not in t:
            t[key] = tomlkit.table()
        t = t[key]
    return t


def flat(data, prefix=""):
    out = {}
    for k, v in data.items():
        if isinstance(v, dict):
            out.update(flat(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


# ------------------------------------------------------------------ sections
def voice_menu(doc):
    tts = table(doc, "tts")
    name = select("TTS engine", [Choice(f"{e.name:8} {e.description}", e.name) for e in engines.ENGINES.values()],
                  default=tts.get("engine"))
    tts["engine"] = name
    engine = engines.get_engine(name)
    section = table(doc, "tts", name)
    while True:
        values = {k: section.get(k, o.default) for k, o in engine.options.items()}
        choices = [Choice(f"{k:12} {values[k]}", k, description=o.help) for k, o in engine.options.items()]
        choices += [Separator(), Choice("Try this voice", "try"), Choice("Back", BACK)]
        key = select(f"Voice · {name}", choices)
        if key == BACK:
            return
        if key == "try":
            try_voice(name, values)
            continue
        o = engine.options[key]
        if o.choices:
            section[key] = select(key, [Choice(str(c), c) for c in o.choices], default=values[key])
        elif key == "voice" and getattr(engine, "suggested_voices", None):
            v = select(key, [Choice(c, c) for c in engine.suggested_voices] + [Choice("other…", BACK)],
                       default=values[key] if values[key] in engine.suggested_voices else None)
            section[key] = text("voice name", values[key]) if v == BACK else v
        elif isinstance(o.default, (int, float)) and not isinstance(o.default, bool):
            section[key] = number(f"{key} ({o.help})", values[key], isinstance(o.default, int), o.minimum, o.maximum)
        else:
            section[key] = text(f"{key} ({o.help})", values[key])


def try_voice(name, values):
    from ..voice import client
    phrase = text("Sentence to say", "Ciao a tutti, oggi parliamo di come un calcolatore rappresenta l'informazione.")
    out = ROOT / "voice-samples" / f"config_{name}_{time.strftime('%H%M%S')}.wav"
    with ui.step("Generating a sample") as st:
        try:
            client.sample(phrase, {"engine": name, **values}, out,
                          lambda e: st.status("loading the speech model") if e["event"] == "loading" else None)
        except client.VoiceError as e:
            st.done(f"[err]{ui.escape(str(e))}[/]")
            return
        st.done(f"{out.relative_to(ROOT)}  [muted](listen to it with any player)[/]")


def narration_menu(doc):
    n = table(doc, "narration")
    while True:
        key = select("Narration", [
            Choice(f"language     {n.get('language', 'Italian')}", "language",
                   description="language of narration and on-screen texts (should match the voice)"),
            Choice(f"piece_gap    {n.get('piece_gap', 0.35)} s", "piece_gap",
                   description="seconds of silence between two spoken pieces"),
            Choice("Back", BACK)])
        if key == BACK:
            return
        if key == "language":
            n["language"] = text("Language (in English, e.g. Italian, English, Spanish)", n.get("language", "Italian"))
        else:
            n["piece_gap"] = number("Seconds between pieces", n.get("piece_gap", 0.35), integer=False,
                                    minimum=0, maximum=3)


def model_choice(backend, message, current, allow_default=False):
    known = MODELS.get(backend, [])
    choices = ([Choice("same as the default", BACK)] if allow_default else [])
    choices += [Choice(f"{m:12} {d}", m) for m, d in known] + [Choice("other (model id)…" if known else "a model…",
                                                                       "other")]
    v = select(message, choices, default=current if current in [m for m, _ in known] else None)
    if v != "other":
        return v
    return text("Model id" + (" as the server names it (e.g. gemma4:12b)" if backend == "local" else ""), current or "")


def effort_choice(backend, message, current, allow_default=False):
    choices = ([Choice("same as the default", BACK)] if allow_default else []) + EFFORTS
    choices += [Choice("not sent (models that do not reason)", "")] if backend == "local" else []
    return select(message, choices, default=current if current in EFFORTS else None)


def agent_menu(doc):
    agent = table(doc, "agent")
    while True:
        name = agent.get("backend")
        b = table(doc, "agent", name)
        overrides = ", ".join(f"{t}: {b[t].get('model', '=')}/{b[t].get('effort', '=')}"
                              for t in TASKS if t in b) or "none"
        choices = [Choice(f"backend      {name}", "backend", description=getattr(BACKENDS.get(name), "summary", None)),
                   Choice(f"model        {b.get('model') or 'default'}", "model"),
                   Choice(f"effort       {b.get('effort') or 'not sent'}", "effort"),
                   Choice(f"per task     {overrides}", "tasks", description="a different model or effort for plan, "
                                                                            "write or review")]
        if name == "local":
            choices += [Choice(f"server       {b.get('url') or LOCAL_URL}", "url",
                               description="an OpenAI-compatible server: Ollama, LM Studio, llama.cpp..."),
                        Choice(f"vision       {'yes' if b.get('vision', True) else 'no'}", "vision",
                               description="whether the model can look at pages and frames")]
        key = select("Agent (LLM) · each backend keeps its own settings", choices + [Choice("Back", BACK)])
        if key == BACK:
            return
        if key == "backend":
            agent["backend"] = select("Backend", [Choice(f"{n:20} {cls.summary}", n) for n, cls in BACKENDS.items()],
                                      default=name if name in BACKENDS else None)
        elif key == "model":
            b["model"] = model_choice(name, "Model", b.get("model"))
        elif key == "effort":
            b["effort"] = effort_choice(name, "Reasoning effort", b.get("effort"))
        elif key == "url":
            b["url"] = text("Server address (ending in /v1)", b.get("url") or LOCAL_URL)
        elif key == "vision":
            b["vision"] = select("Can the model see images?", [Choice("yes", True), Choice("no", False)],
                                 default=b.get("vision", True))
        else:
            task = select("Which task?", [Choice(f"{t:7} {d}", t) for t, d in TASKS.items()] + [Choice("Back", BACK)])
            if task == BACK:
                continue
            current = b.get(task, {})
            m = model_choice(name, f"Model for {task}", current.get("model"), allow_default=True)
            e = effort_choice(name, f"Effort for {task}", current.get("effort"), allow_default=True)
            values = {k: v for k, v in (("model", m), ("effort", e)) if v != BACK}
            if values:
                t = tomlkit.table()
                t.update(values)
                t.add(tomlkit.nl())
                b[task] = t
            elif task in b:
                del b[task]


def video_menu(doc):
    import tomllib

    from ..config import THEMES
    v = table(doc, "video")
    while True:
        key = select("Video", [Choice(f"theme        {v.get('theme', 'light')}", "theme",
                                      description="the house visual style (themes/*.toml)"),
                               Choice(f"subtitles    {v.get('subtitles', 'track')}", "subtitles",
                                      description="from the narration: a track players turn on/off, drawn into "
                                                  "the picture, or none"),
                               Choice(f"resolution   {v.get('width')}x{v.get('height')}", "resolution"),
                               Choice(f"fps          {v.get('fps')}", "fps"), Choice("Back", BACK)])
        if key == BACK:
            return
        if key == "theme":
            themes = {p.stem: tomllib.loads(p.read_text()).get("description", "") for p in sorted(THEMES.glob("*.toml"))}
            while True:
                name = select("Theme (your own: copy themes/light.toml to themes/<name>.toml)",
                              [Choice(f"{n:12} {d}", n) for n, d in themes.items()], default=v.get("theme", "light"))
                if select(f"Theme {name}", [Choice("Use it", "use"), Choice("Make a preview picture first", "preview")]) == "use":
                    v["theme"] = name
                    break
                from .commands import preview_theme
                preview_theme(name)                   # prints where the picture is
        elif key == "subtitles":
            v["subtitles"] = select("Subtitles", [
                Choice("track    a subtitle track players turn on and off, plus a .srt file", "track"),
                Choice("burned   always visible, drawn into the picture", "burned"),
                Choice("off      no subtitles", "off")], default=v.get("subtitles", "track"))
        elif key == "resolution":
            w, h = select("Resolution", [Choice(f"{w}x{h}", (w, h)) for w, h in RESOLUTIONS],
                          default=(v.get("width"), v.get("height")) if (v.get("width"), v.get("height")) in RESOLUTIONS else None)
            v["width"], v["height"] = w, h
        else:
            v["fps"] = select("Frames per second", [Choice(str(f), f) for f in FPS],
                              default=v.get("fps") if v.get("fps") in FPS else None)


def tuning_menu(doc):
    t = table(doc, "tuning")
    while True:
        key = select("Tuning (normally untouched)", [Choice(f"{k:24} {t.get(k)}", k, description=d)
                                                     for k, d in TUNING.items()] + [Choice("Back", BACK)])
        if key == BACK:
            return
        if isinstance(t.get(key), bool):
            t[key] = select(key, [Choice("yes", True), Choice("no", False)], default=t.get(key))
        else:
            t[key] = number(f"{key} ({TUNING[key]})", t.get(key, 1), minimum=1)


# ------------------------------------------------------------------ main menu
def configure():
    doc = tomlkit.parse(CONFIG_FILE.read_text())
    before = flat(doc.unwrap())
    while True:
        d = doc.unwrap()
        tts = d.get("tts", {})
        eng = tts.get(tts.get("engine"), {})
        video = d.get("video", {})
        backend = d.get("agent", {}).get("backend")
        b = d.get("agent", {}).get(backend, {})
        changed = flat(d) != before
        key = select("config.toml · what do you want to change?" + ("  (unsaved changes)" if changed else ""), [
            Choice(f"Voice         {tts.get('engine')} · {eng.get('voice', '')}", "voice"),
            Choice(f"Narration     {d.get('narration', {}).get('language')}", "narration"),
            Choice(f"Agent         {backend} · {b.get('model') or 'default'}"
                   + (f" · effort {b['effort']}" if b.get("effort") else ""), "agent"),
            Choice(f"Video         theme {video.get('theme', 'light')} · subtitles {video.get('subtitles', 'track')} · "
                   f"{video.get('width')}x{video.get('height')} · {video.get('fps')} fps", "video"),
            Choice("Tuning", "tuning"),
            Separator(),
            Choice("Save and exit", "save"),
            Choice("Exit without saving", "quit")])
        if key == "quit":
            ui.info("Nothing saved.")
            return
        if key == "save":
            break
        {"voice": voice_menu, "narration": narration_menu, "agent": agent_menu, "video": video_menu,
         "tuning": tuning_menu}[key](doc)
    after = flat(doc.unwrap())
    diff = [(k, before.get(k, "—"), after.get(k, "—")) for k in sorted(set(before) | set(after))
            if before.get(k) != after.get(k)]
    if not diff:
        ui.info("No changes.")
        return
    CONFIG_FILE.write_text(tomlkit.dumps(doc))
    ui.key_values([(k, f"{ui.escape(str(a))} → [bold]{ui.escape(str(b))}[/]") for k, a, b in diff],
                  title="config.toml saved")
    if any(k.startswith("tts.") for k, _, _ in diff):
        ui.info("The voice changed: existing lessons get the new voice the next time they are built.")
