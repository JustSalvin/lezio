"""Loads the prompt texts in agent/prompts/ (Markdown with $placeholders, and depth.toml)."""
import tomllib
from pathlib import Path
from string import Template

DIR = Path(__file__).parent / "prompts"
DEPTH = tomllib.loads((DIR / "depth.toml").read_text())


def text(name, **values):
    """agent/prompts/<name>.md (e.g. "plan", "rules/writing", "styles/slides") with $placeholders filled."""
    return Template((DIR / f"{name}.md").read_text().strip()).safe_substitute(**values)


def compose(*parts, **values):
    return "\n\n".join(text(p, **values) for p in parts)


def depth_rule(depth):
    d = DEPTH[str(depth)]
    return f"{d['rule']} Length: about {d['minutes']}."


def target_minutes(depth, units):
    """(low, high) minutes of the whole lesson for `units` pages / 150-word blocks of material
    (plus half a minute for the opening and the closing recap)."""
    lo, hi = DEPTH[str(depth)]["seconds"]
    return units * lo / 60 + 0.5, units * hi / 60 + 0.5
