"""./lezio config: change config.toml through arrow-key menus.

config.toml stays the only place of the configuration: this command edits it with tomlkit, so comments
and layout of the file are kept. Nothing is written until "Save and exit".
"""
import subprocess
import time

import questionary
import tomlkit
from questionary import Choice, Separator

from ..agent.backends import BACKENDS
from ..config import CONFIG_FILE, ROOT
from ..voice import engines
from . import ui
from .wizard import STYLE, ask

EFFORTS = ["low", "medium", "high", "xhigh", "max"]
MODELS = [("opus", "the most capable"), ("sonnet", "faster, lighter on usage"), ("haiku", "the fastest")]
TASKS = {"plan": "planning the lesson", "write": "writing narration and scenes", "review": "final review"}
RESOLUTIONS = [(1920, 1080), (1280, 720), (2560, 1440), (3840, 2160)]
FPS = [24, 25, 30, 60]
TUNING = {
    "segments_per_task": "segments written per agent task",
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
        st.done(str(out.relative_to(ROOT)))
    subprocess.run(["afplay", str(out)])


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


def model_choice(message, current, allow_default=False):
    choices = ([Choice("same as the default", BACK)] if allow_default else [])
    choices += [Choice(f"{m:8} {d}", m) for m, d in MODELS] + [Choice("other (full model id)…", "other")]
    known = [m for m, _ in MODELS]
    v = select(message, choices, default=current if current in known else None)
    return text("Model id (e.g. claude-opus-5-5)", current or "") if v == "other" else v


def agent_menu(doc):
    agent = table(doc, "agent")
    while True:
        overrides = ", ".join(f"{t}: {agent[t].get('model', '=')}/{agent[t].get('effort', '=')}"
                              for t in TASKS if t in agent) or "none"
        key = select("Agent (LLM)", [
            Choice(f"backend      {agent.get('backend')}", "backend"),
            Choice(f"model        {agent.get('model')}", "model"),
            Choice(f"effort       {agent.get('effort')}", "effort"),
            Choice(f"per task     {overrides}", "tasks", description="a different model or effort for plan, write "
                                                                     "or review"),
            Choice("Back", BACK)])
        if key == BACK:
            return
        if key == "backend":
            agent["backend"] = select("Backend", [Choice(b + ("  (planned, not implemented yet)"
                                                              if b == "anthropic-api" else ""), b) for b in BACKENDS],
                                      default=agent.get("backend"))
        elif key == "model":
            agent["model"] = model_choice("Model", agent.get("model"))
        elif key == "effort":
            agent["effort"] = select("Reasoning effort", EFFORTS, default=agent.get("effort"))
        else:
            task = select("Which task?", [Choice(f"{t:7} {d}", t) for t, d in TASKS.items()] + [Choice("Back", BACK)])
            if task == BACK:
                continue
            current = agent.get(task, {})
            m = model_choice(f"Model for {task}", current.get("model"), allow_default=True)
            e = select(f"Effort for {task}", [Choice("same as the default", BACK)] + EFFORTS,
                       default=current.get("effort"))
            values = {k: v for k, v in (("model", m), ("effort", e)) if v != BACK}
            if values:
                t = tomlkit.table()
                t.update(values)
                t.add(tomlkit.nl())
                agent[task] = t
            elif task in agent:
                del agent[task]


def video_menu(doc):
    import tomllib

    from ..config import THEMES
    v = table(doc, "video")
    while True:
        key = select("Video", [Choice(f"theme        {v.get('theme', 'light')}", "theme",
                                      description="the house visual style (themes/*.toml)"),
                               Choice(f"resolution   {v.get('width')}x{v.get('height')}", "resolution"),
                               Choice(f"fps          {v.get('fps')}", "fps"), Choice("Back", BACK)])
        if key == BACK:
            return
        if key == "theme":
            themes = {p.stem: tomllib.loads(p.read_text()).get("description", "") for p in sorted(THEMES.glob("*.toml"))}
            while True:
                name = select("Theme (your own: copy themes/light.toml to themes/<name>.toml)",
                              [Choice(f"{n:12} {d}", n) for n, d in themes.items()], default=v.get("theme", "light"))
                if select(f"Theme {name}", [Choice("Use it", "use"), Choice("See a preview first", "preview")]) == "use":
                    v["theme"] = name
                    break
                from .commands import preview_theme
                subprocess.run(["open", str(preview_theme(name))])
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
        t[key] = number(f"{key} ({TUNING[key]})", t.get(key, 1), minimum=1)


# ------------------------------------------------------------------ main menu
def configure():
    doc = tomlkit.parse(CONFIG_FILE.read_text())
    before = flat(doc.unwrap())
    while True:
        d = doc.unwrap()
        tts = d.get("tts", {})
        eng = tts.get(tts.get("engine"), {})
        agent, video = d.get("agent", {}), d.get("video", {})
        changed = flat(d) != before
        key = select("config.toml · what do you want to change?" + ("  (unsaved changes)" if changed else ""), [
            Choice(f"Voice         {tts.get('engine')} · {eng.get('voice', '')}", "voice"),
            Choice(f"Narration     {d.get('narration', {}).get('language')}", "narration"),
            Choice(f"Agent         {agent.get('backend')} · {agent.get('model')} · effort {agent.get('effort')}",
                   "agent"),
            Choice(f"Video         theme {video.get('theme', 'light')} · {video.get('width')}x{video.get('height')} · "
                   f"{video.get('fps')} fps", "video"),
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
