# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Study material: ingestion of the lesson sources and the index the rest of the program works with.

Every source (PDF, text/Markdown, DOCX, picture) is read once into build/material/<source id>/ and
described in build/material/index.json. Its parts are addressed with refs:

    slides.pdf          the whole source               notes.md#s2       section 2
    slides.pdf#p3       page 3                         notes.md#s2-4     sections 2 to 4
    slides.pdf#p3-5     pages 3 to 5                   notes.md#s2.f1    figure 1 of section 2
    slides.pdf#p3.f1    figure 1 of page 3             diagram.png       a picture source

Refs are what the agent reads, looks at, cites in a segment's "sources" and uses in scene code.
Only material.<reader> modules import heavy libraries, and only while ingesting.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

from ..lesson import slugify
from .common import norm

VERSION = 4                     # bump when the readers change: sources are ingested again
KINDS = {".pdf": "pdf", ".md": "text", ".markdown": "text", ".txt": "text", ".docx": "docx",
         ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image"}
ITEM_LETTER = {"pdf": "p", "text": "s", "docx": "s"}
ITEM_NAME = {"pdf": "page", "text": "section", "docx": "section"}
REF = re.compile(r"^(?P<item>[ps])(?P<a>\d+)(?:-(?P<b>\d+))?(?:\.f(?P<fig>\d+))?$")


class RefError(ValueError):
    pass


def kind_of(path):
    return KINDS.get(Path(path).suffix.lower())


def supported(path):
    return kind_of(path) is not None


def _fingerprint(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:16]


def _reader(kind):
    from . import docx, image, pdf, text
    return {"pdf": pdf, "text": text, "docx": docx, "image": image}[kind]


def ingest(lesson, on_progress=None):
    """Read new or changed sources (others are kept). Returns the ids of the sources read now."""
    lesson.material.mkdir(parents=True, exist_ok=True)
    old = json.loads(lesson.index.read_text())["sources"] if lesson.index.exists() else []
    by_path = {s["path"]: s for s in old}
    taken = {s["id"] for s in old if s["path"] in lesson.source_names}
    entries, changed = [], []
    for stored, path in zip(lesson.source_names, lesson.sources):
        if not path.exists():
            raise SystemExit(f"source not found: {stored}")
        kind = kind_of(path)
        if kind is None:
            raise SystemExit(f"unsupported file type: {path.name} (supported: {', '.join(sorted(KINDS))})")
        fp = _fingerprint(path)
        prev = by_path.get(stored)
        if prev and prev["fingerprint"] == fp and prev.get("version") == VERSION and \
                (lesson.material / prev["id"]).is_dir():
            entries.append(prev)
            continue
        sid = prev["id"] if prev else None
        if sid is None:
            base = slugify(path.stem) + path.suffix.lower()
            sid, n = base, 2
            while sid in taken:
                sid = f"{slugify(path.stem)}-{n}{path.suffix.lower()}"
                n += 1
            taken.add(sid)
        if on_progress:
            on_progress(path.name)
        out_dir = lesson.material / sid
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True)
        entry = _reader(kind).ingest(path, sid, out_dir, lambda p: str(Path(p).relative_to(lesson.dir)))
        entries.append({"id": sid, "name": path.name, "path": stored, "fingerprint": fp, "version": VERSION,
                        **entry})
        changed.append(sid)
    for s in old:                                   # sources removed from the lesson
        if s["id"] not in {e["id"] for e in entries}:
            shutil.rmtree(lesson.material / s["id"], ignore_errors=True)
    lesson.index.write_text(json.dumps({"sources": entries}, ensure_ascii=False, indent=1))
    return changed


def parse_range(spec, available):
    """'1,3,5-8' -> [1,3,5,6,7,8] (only those present in `available`); empty = all."""
    if not spec:
        return list(available)
    wanted = set()
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            wanted.update(range(int(a), int(b) + 1))
        elif part:
            wanted.add(int(part))
    return [n for n in available if n in wanted]


def line_box(item, spec):
    """Bounding box (PDF points) of some text lines of a PDF page.

    spec: 3 | [3, 5] (L-numbers, a range) | {"lines": [2, 4, 6]} (exactly these lines) | "phrase"
          | ["start phrase", "end phrase"] (phrases contained in a single line)
    """
    lines = item.get("text_lines")
    if lines is None:
        raise RefError(f"{item['ref']} has no text lines (only PDF pages have them)")
    if isinstance(spec, dict):
        picked = spec.get("lines")
        if not isinstance(picked, list) or not picked or not all(isinstance(k, int) for k in picked):
            raise RefError(f"bad lines spec: {spec!r} (expected {{\"lines\": [numbers]}})")
        bad = [k for k in picked if not 1 <= k <= len(lines)]
        if bad:
            raise RefError(f"lines {bad} do not exist ({item['ref']} has {len(lines)} lines)")
        boxes = [lines[k - 1]["bbox"] for k in picked]
    else:
        if isinstance(spec, (int, str)):
            spec = [spec]
        if not isinstance(spec, (list, tuple)) or not 1 <= len(spec) <= 2:
            raise RefError(f"bad lines spec: {spec!r}")

        def find(x, start=0):
            if isinstance(x, int):
                if not 1 <= x <= len(lines):
                    raise RefError(f"line L{x} does not exist ({item['ref']} has {len(lines)} lines)")
                return x - 1
            target = norm(str(x))
            for k in range(start, len(lines)):
                if target in norm(lines[k]["text"]):
                    return k
            raise RefError(f"phrase not found in a single line of {item['ref']}: {x!r}")

        i = find(spec[0])
        j = find(spec[-1], i)
        boxes = [lines[k]["bbox"] for k in range(i, j + 1)]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


class Material:
    """Read access to the ingested material of a lesson (build/material/index.json)."""

    def __init__(self, lesson):
        self.lesson = lesson
        data = json.loads(lesson.index.read_text()) if lesson.index.exists() else {"sources": []}
        self.sources = {s["id"]: s for s in data["sources"]}

    def path(self, rel) -> Path:
        return self.lesson.dir / rel

    # ------------------------------------------------------------------ refs
    def resolve(self, ref):
        """ref -> (source, [items], figure or None)."""
        if not isinstance(ref, str) or not ref.strip():
            raise RefError(f"bad ref {ref!r}")
        sid, _, frag = ref.strip().partition("#")
        source = self.sources.get(sid)
        if source is None:
            raise RefError(f"unknown source '{sid}' (sources: {', '.join(self.sources) or 'none'})")
        items = source["items"]
        if not frag:
            return source, items, None
        letter = ITEM_LETTER.get(source["type"])
        m = REF.match(frag)
        if letter is None or m is None or m["item"] != letter:
            example = f"{sid}#{letter}2" if letter else sid
            raise RefError(f"bad ref '{ref}': use e.g. {example}")
        a, b = int(m["a"]), int(m["b"] or m["a"])
        if not 1 <= a <= b <= len(items):
            raise RefError(f"'{ref}': {sid} has {ITEM_NAME[source['type']]}s 1-{len(items)}")
        if m["fig"]:
            if b != a:
                raise RefError(f"bad ref '{ref}': a figure belongs to one {ITEM_NAME[source['type']]}")
            figs = items[a - 1].get("figures", [])
            k = int(m["fig"])
            if not 1 <= k <= len(figs):
                raise RefError(f"'{ref}': {items[a - 1]['ref']} has {_count(figs, 'figure')}")
            return source, [items[a - 1]], figs[k - 1]
        return source, items[a - 1:b], None

    def item(self, ref):
        """The single item (page, section, picture) a ref points to."""
        source, items, fig = self.resolve(ref)
        if len(items) != 1 or fig is not None:
            raise RefError(f"'{ref}' must point to exactly one page, section or picture")
        return items[0]

    def figure(self, ref):
        """The picture a ref points to: a figure, a picture source or a PDF page (whole page)."""
        source, items, fig = self.resolve(ref)
        if fig is not None:
            return fig
        if len(items) == 1 and "image" in items[0]:
            return items[0]
        raise RefError(f"'{ref}' is not a picture (use a figure ref like ...#p3.f1, a page or a picture source)")

    def expand(self, refs):
        """Item refs covered by some refs (ranges and whole sources expanded, figures -> their item)."""
        out = []
        for ref in refs:
            _, items, _ = self.resolve(ref)
            out += [i["ref"] for i in items if i["ref"] not in out]
        return out

    # ------------------------------------------------------------------ scope
    def scope(self, focus=None):
        """Item refs in scope: all items, or for the sources in `focus` ({stored path: "1-20"}) only those."""
        focus = focus or {}
        out = []
        for s in self.sources.values():
            spec = focus.get(s["path"]) or focus.get(s["name"]) or focus.get(s["id"])
            numbers = parse_range(spec, range(1, len(s["items"]) + 1))
            out += [s["items"][n - 1]["ref"] for n in numbers]
        return out

    def size(self, focus=None):
        """Amount of material in scope: (units, description). A unit is a page, a picture or 150 words."""
        in_scope = set(self.scope(focus))
        pages = words = pictures = 0
        for s in self.sources.values():
            items = [i for i in s["items"] if i["ref"] in in_scope]
            if s["type"] == "pdf":
                pages += len(items)
            elif s["type"] == "image":
                pictures += len(items)
            else:
                words += sum(i["words"] for i in items)
        parts = [f"{pages} pages"] * bool(pages) + [f"{words} words of text"] * bool(words) + \
            [f"{pictures} pictures"] * bool(pictures)
        return pages + pictures + words / 150, ", ".join(parts)

    # ------------------------------------------------------------------ for the agent
    def overview(self, focus=None):
        """Listing of the material in scope: one line per page/section/picture."""
        in_scope = set(self.scope(focus))
        out = []
        for s in self.sources.values():
            items = [i for i in s["items"] if i["ref"] in in_scope]
            if not items:
                continue
            if s["type"] == "pdf":
                part = f"pages {_fmt_range([i['page'] for i in items])} of {s['pages']}"
                out.append(f"{s['id']} - PDF \"{s['name']}\", {part}")
                for i in items:
                    title = next((l["text"] for l in i["text_lines"]), "(no text)")
                    extra = [f"{len(i['text_lines'])} lines"]
                    if i["figures"]:
                        extra.append(_count(i["figures"], "figure"))
                    extra += i["hints"]
                    out.append(f"  {i['ref']}  {_short(title, 70)}  · {' · '.join(extra)}")
            elif s["type"] in ("text", "docx"):
                words = sum(i["words"] for i in items)
                out.append(f"{s['id']} - {'Word document' if s['type'] == 'docx' else 'text'} \"{s['name']}\", "
                           f"{len(items)} of {len(s['items'])} sections, {words} words")
                for i in items:
                    title = i["heading"] or _short(i["text"], 60)
                    extra = [f"{i['words']} words"] + ([_count(i["figures"], "figure")] if i["figures"] else [])
                    out.append(f"  {i['ref']}  {'  ' * max(i['level'] - 1, 0)}{_short(title, 70)}  · "
                               f"{' · '.join(extra)}")
            else:
                w, h = s["items"][0]["size"]
                out.append(f"{s['id']} - picture \"{s['name']}\", {w}x{h} px")
        return "\n".join(out)

    def read(self, ref, limit=30000):
        """Text of the items a ref points to, as shown to the agent."""
        source, items, fig = self.resolve(ref)
        if fig is not None:
            where = items[0]["ref"]
            share = f", {fig['share']:.0%} of the page" if "share" in fig else ""
            caption = f" \"{fig['caption']}\"" if fig.get("caption") else ""
            return f"{ref}: figure{caption} of {where}{share}. Use view to see it."
        blocks = []
        for i in items:
            if source["type"] == "pdf":
                rows = [f"{i['ref']} (page {i['page']})"]
                rows += [f"L{k}: {l['text']}" for k, l in enumerate(i["text_lines"], 1)] or ["(no text lines)"]
                rows += [f"figure {f['ref']} ({f['share']:.0%} of the page)" for f in i["figures"]]
                rows += [f"note: {h}" for h in i["hints"]]
            elif source["type"] in ("text", "docx"):
                head = f"{'#' * max(i['level'], 1)} {i['heading']}" if i["heading"] else "(no heading)"
                rows = [f"{i['ref']}  {head}", i["text"]]
                rows += [f"figure {f['ref']}" + (f" \"{f['caption']}\"" if f.get("caption") else "")
                         for f in i["figures"]]
            else:
                rows = [f"{i['ref']}: a picture, {i['size'][0]}x{i['size'][1]} px. Use view to see it."]
            blocks.append("\n".join(rows))
        text = "\n\n".join(blocks)
        if len(text) > limit:
            text = text[:limit] + f"\n[... truncated: read a smaller range than {ref}]"
        return text

    def pictures(self, ref):
        """[(label, preview path)] of what a ref shows: pages, figures, pictures."""
        source, items, fig = self.resolve(ref)
        if fig is not None:
            return [(fig["ref"], self.path(fig["preview"]))]
        out = []
        for i in items:
            if "preview" in i:
                out.append((i["ref"], self.path(i["preview"])))
            else:
                out += [(f["ref"], self.path(f["preview"])) for f in i.get("figures", [])]
        return out


def _count(things, word):
    return f"{len(things)} {word}" + ("" if len(things) == 1 else "s")


def _short(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1] + "…"


def _fmt_range(numbers):
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
