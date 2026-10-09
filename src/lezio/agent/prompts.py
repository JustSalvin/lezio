"""Loads the prompt texts in agent/prompts/ (Markdown with $placeholders, and modes.toml)."""
import tomllib
from pathlib import Path
from string import Template

DIR = Path(__file__).parent / "prompts"
MODES = tomllib.loads((DIR / "modes.toml").read_text())


def text(name, **values):
    """agent/prompts/<name>.md with $placeholders filled."""
    return Template((DIR / f"{name}.md").read_text().strip()).safe_substitute(**values)


def compose(*parts, **values):
    return "\n\n".join(text(p, **values) for p in parts)


def visual_rule(mode):
    return MODES["visual"][mode]


def depth_rule(depth):
    return MODES["depth"][str(depth)]
