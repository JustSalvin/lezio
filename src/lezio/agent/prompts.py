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


def style_rule(style):
    return text(f"styles/{style}")


def depth_rule(depth):
    d = DEPTH[str(depth)]
    return f"{d['rule']} Length: about {d['minutes']}."
