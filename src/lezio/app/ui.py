"""Terminal interface: colors, panels, live steps with progress bars.

A step shows a spinner (and a bar when the amount of work is known) with a live status line; when it ends
it collapses into one summary line, so temporary messages disappear by themselves.
"""
import sys
import time
from contextlib import contextmanager

from rich.console import Console
from rich.markup import escape  # noqa: F401  (ui.escape: text that may contain [...])
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn,
                           TimeElapsedColumn)
from rich.table import Table
from rich.theme import Theme

THEME = Theme({"accent": "cyan", "ok": "green", "warn": "yellow", "err": "bold red", "muted": "grey50",
               "key": "grey62"})
console = Console(theme=THEME, highlight=False)


def banner():
    """The program's header (help, wizard)."""
    console.print(Panel.fit("[bold accent]lezio[/]  [muted]study material → narrated video lesson[/]",
                            border_style="accent", padding=(0, 2)))


def section(text):
    """A heading inside a page of output (help groups, parts of a listing)."""
    console.print(f"\n[bold]{text}[/]")


def fail(message, hint=None):
    """An error: red panel with the problem and, muted, what to do. Exits."""
    body = f"[err]{message}[/]" + (f"\n[muted]{hint}[/]" if hint else "")
    console.print(Panel(body, title="error", title_align="left", border_style="red", padding=(0, 1)))
    sys.exit(1)


def info(message):
    """A side note (muted)."""
    console.print(f"[muted]{message}[/]")


def hint(message):
    """What the user can do next: "→ message"."""
    console.print(f"[muted]→ {message}[/]")


def done(message):
    """A one-line success."""
    console.print(f"[ok]✓[/] {message}")


def warn(message):
    console.print(f"[warn]![/] {message}")


def table(columns, rows, title=None, wrap_last=True):
    """A list (lessons, voices, themes, templates, segments) in the same style everywhere.
    columns: names (a name starting with ">" is right-aligned); rows: lists of rich-markup strings."""
    t = Table(box=None, padding=(0, 2), header_style="key", show_header=any(columns),
              title=f"[bold]{title}[/]" if title else None, title_justify="left")
    for k, c in enumerate(columns):
        right, last = c.startswith(">"), k == len(columns) - 1
        fold = last and wrap_last
        t.add_column(c.lstrip(">"), justify="right" if right else "left", no_wrap=not fold,
                     overflow="fold" if fold else "ellipsis", min_width=len(c.lstrip(">")) if not fold else None)
    for r in rows:
        t.add_row(*r)
    console.print(t)


def fmt_seconds(s):
    s = int(s)
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


def fmt_pages(numbers):
    """[1,2,3,5,7,8] -> '1-3, 5, 7-8'"""
    out, start, prev = [], None, None
    for n in sorted(numbers) + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = n
    return ", ".join(out)


def key_values(rows, title=None):
    """A two-column panel: [(key, value), ...]."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="key", no_wrap=True)
    table.add_column()
    for k, v in rows:
        table.add_row(k, v)
    console.print(Panel(table, title=title, title_align="left", border_style="accent", padding=(0, 1)))


class Step:
    def __init__(self, title, total=None):
        self.title, self.total, self.detail = title, total, ""
        columns = [SpinnerColumn(style="accent"), TextColumn("[bold]{task.fields[title]}")]
        if total is not None:
            columns += [BarColumn(bar_width=24, complete_style="accent", finished_style="ok"), MofNCompleteColumn()]
        columns += [TextColumn("[muted]{task.description}"), TimeElapsedColumn()]
        self.progress = Progress(*columns, console=console, transient=True)
        self.task = self.progress.add_task("", total=total, title=title)
        self.start = time.time()

    def status(self, text):
        self.progress.update(self.task, description=text)

    def set_total(self, total):
        self.total = total
        self.progress.update(self.task, total=total)

    def advance(self, n=1):
        self.progress.advance(self.task, n)

    def note(self, text):
        """A line that stays (printed above the live line)."""
        self.progress.console.print(f"   [muted]{text}[/]")

    def done(self, detail):
        self.detail = detail


@contextmanager
def step(title, total=None):
    s = Step(title, total)
    s.progress.start()
    try:
        yield s
    except BaseException:
        s.progress.stop()
        console.print(f"[err]✗[/] [bold]{title}[/]")
        raise
    s.progress.stop()
    elapsed = time.time() - s.start
    console.print(f"[ok]✓[/] [bold]{title}[/]  {s.detail}  [muted]{fmt_seconds(elapsed)}[/]")
