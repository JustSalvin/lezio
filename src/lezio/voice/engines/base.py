# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Common interface of the text-to-speech engines.

An engine declares its own options (with defaults, allowed values and help), so the program can
validate them, show them (`./lezio voices`) and pass them back to the engine, without knowing anything
about the engine itself. Module-level code must stay light: heavy libraries are imported in prepare().
"""
from dataclasses import dataclass, field


@dataclass
class Option:
    default: object
    help: str
    choices: list = field(default_factory=list)   # allowed values (empty = free)
    minimum: float | None = None
    maximum: float | None = None

    def check(self, name, value):
        if self.choices and value not in self.choices:
            return f"{name} must be one of: {', '.join(map(str, self.choices))}"
        if isinstance(self.default, (int, float)) and not isinstance(self.default, bool):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return f"{name} must be a number"
            if self.minimum is not None and value < self.minimum:
                return f"{name} must be >= {self.minimum}"
            if self.maximum is not None and value > self.maximum:
                return f"{name} must be <= {self.maximum}"
        elif not isinstance(value, type(self.default)):
            return f"{name} must be a {type(self.default).__name__}"
        return None


class Engine:
    name = ""
    description = ""
    runs = "local"              # "local" or "online" (the text is sent to a service)
    options: dict[str, Option] = {}

    def prepare(self, opts):
        """Load models etc. once before a batch of syntheses."""

    def synthesize(self, text, opts):
        """Return (samples as float32 numpy array, sample_rate)."""
        raise NotImplementedError

    def download(self, opts):
        """Fetch what the engine needs (called by setup.sh)."""

    @classmethod
    def validate(cls, opts):
        problems = [f"unknown option '{k}' for engine {cls.name} (options: {', '.join(cls.options)})"
                    for k in opts if k not in cls.options]
        problems += [p for k, o in cls.options.items() if k in opts for p in [o.check(k, opts[k])] if p]
        return problems
