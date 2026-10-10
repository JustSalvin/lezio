# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Plain text and Markdown sources: sections by headings (Markdown) or by paragraphs (plain text).

Markdown images that point to local files become figures of their section.
"""
import re
from pathlib import Path

from ..config import CONFIG
from .common import save_preview, save_png, split_long

PAGE_IMAGE_WIDTH = CONFIG["tuning"]["page_image_width"]
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
TXT_SECTION_WORDS = 350


def _paragraphs(lines):
    text = "\n".join(lines).strip()
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def ingest(path, source_id, out_dir, rel):
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    markdown = Path(path).suffix.lower() in (".md", ".markdown")
    sections = []                       # (heading, level, [paragraphs])
    if markdown:
        heading, level, lines, in_code = None, 0, [], False
        for line in raw.splitlines():
            if line.strip().startswith("```"):
                in_code = not in_code
            m = None if in_code else HEADING.match(line)
            if m:
                if lines and any(l.strip() for l in lines) or heading:
                    sections.append((heading, level, _paragraphs(lines)))
                heading, level, lines = m[2], len(m[1]), []
            else:
                lines.append(line)
        sections.append((heading, level, _paragraphs(lines)))
    else:
        paras, cur, words = _paragraphs(raw.splitlines()), [], 0
        for p in paras:
            cur.append(p)
            words += len(p.split())
            if words >= TXT_SECTION_WORDS:
                sections.append((None, 0, cur))
                cur, words = [], 0
        if cur:
            sections.append((None, 0, cur))

    items, n_fig = [], 0
    for heading, level, paras in sections:
        for part_heading, part in split_long(heading, paras):
            k = len(items) + 1
            ref = f"{source_id}#s{k}"
            figures = []
            for para in part:
                for alt, target in IMAGE.findall(para):
                    src = (Path(path).parent / target).resolve()
                    if target.startswith(("http://", "https://")) or not src.exists():
                        continue
                    n_fig += 1
                    saved = save_png(src, out_dir / f"s{k:03d}_f{len(figures) + 1}.png", PAGE_IMAGE_WIDTH)
                    if saved:
                        png, size = saved
                        figures.append({"ref": f"{ref}.f{len(figures) + 1}", "caption": alt, "size": list(size),
                                        "image": rel(png), "preview": rel(save_preview(png, png.with_suffix(".jpg"), 1024))})
            text = "\n\n".join(part)
            items.append({"ref": ref, "heading": part_heading, "level": level, "text": text,
                          "words": len(text.split()), "figures": figures})
    items = [i for i in items if i["text"] or i["heading"] or i["figures"]]
    for k, item in enumerate(items, start=1):          # renumber after dropping empty sections
        old = item["ref"]
        item["ref"] = f"{source_id}#s{k}"
        for f in item["figures"]:
            f["ref"] = f["ref"].replace(old, item["ref"], 1)
    return {"type": "text", "sections": len(items), "items": items}
