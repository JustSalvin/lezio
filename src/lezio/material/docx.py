# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""Word documents (.docx) with python-docx: sections by headings, paragraphs, lists, tables as text,
embedded pictures as figures of their section."""
import io

from ..config import CONFIG
from .common import save_preview, save_png, split_long

PAGE_IMAGE_WIDTH = CONFIG["tuning"]["page_image_width"]
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _heading_level(paragraph):
    name = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
    if name == "title":
        return 1
    for prefix in ("heading ", "titolo "):
        if name.startswith(prefix) and name[len(prefix):].strip().isdigit():
            return int(name[len(prefix):])
    return 0


def _is_list(paragraph):
    name = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
    return "list" in name or "elenco" in name or paragraph._p.find(f".//{{{NS_W}}}numPr") is not None


def _pictures(paragraph, doc):
    """Image blobs embedded in a paragraph, in order."""
    out = []
    for blip in paragraph._p.iter(f"{{{NS_A}}}blip"):
        rid = blip.get(f"{{{NS_R}}}embed")
        part = doc.part.related_parts.get(rid) if rid else None
        if part is not None and getattr(part, "blob", None):
            out.append(part.blob)
    return out


def ingest(path, source_id, out_dir, rel):
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    sections = [[None, 0, [], []]]               # heading, level, paragraphs, picture blobs
    for block in doc.element.body.iterchildren():
        tag = block.tag.split("}")[-1]
        if tag == "p":
            p = Paragraph(block, doc)
            level, text = _heading_level(p), p.text.strip()
            if level and text:
                sections.append([text, level, [], []])
                continue
            if text:
                sections[-1][2].append(("- " if _is_list(p) else "") + text)
            sections[-1][3] += _pictures(p, doc)
        elif tag == "tbl":
            rows = []
            for row in Table(block, doc).rows:
                cells = []
                for c in row.cells:
                    t = " ".join(c.text.split())
                    if not cells or cells[-1] != t:          # merged cells repeat their text
                        cells.append(t)
                rows.append(" | ".join(cells))
            sections[-1][2].append("Table:\n" + "\n".join(rows))

    items = []
    for heading, level, paras, blobs in sections:
        if not (heading or paras or blobs):
            continue
        parts = split_long(heading, paras)
        for n, (part_heading, part) in enumerate(parts):
            k = len(items) + 1
            ref = f"{source_id}#s{k}"
            figures = []
            for blob in (blobs if n == len(parts) - 1 else []):
                saved = save_png(io.BytesIO(blob), out_dir / f"s{k:03d}_f{len(figures) + 1}.png", PAGE_IMAGE_WIDTH)
                if saved:                                    # formats PIL cannot read (EMF, WMF) are skipped
                    png, size = saved
                    figures.append({"ref": f"{ref}.f{len(figures) + 1}", "size": list(size), "image": rel(png),
                                    "preview": rel(save_preview(png, png.with_suffix(".jpg"), 1024))})
            text = "\n".join(part)
            items.append({"ref": ref, "heading": part_heading, "level": level, "text": text,
                          "words": len(text.split()), "figures": figures})
    return {"type": "docx", "sections": len(items), "items": items}
