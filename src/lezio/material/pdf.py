# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""PDF sources: page images, text lines with their position (L-numbers), figures.

Repeated page chrome (headers, footers, navigation, logos) is removed from text lines and figures: an
element is chrome when it is repeated at the same place on >= 40% of the pages, or repeated anywhere
inside the top/bottom bands of the page.
"""
import re
from collections import Counter

import pymupdf

from ..config import CONFIG
from .common import INTERACTIVE_WORDS, norm, save_preview

PAGE_IMAGE_WIDTH = CONFIG["tuning"]["page_image_width"]
PREVIEW_IMAGE_WIDTH = CONFIG["tuning"]["preview_image_width"]


def _line_text(spans):
    """Text of a line; superscripts (exponents) stay readable: 2^k, 2^(k-1)."""
    out, sup = [], []
    for span in spans + [None]:
        if span is not None and span["flags"] & 1 and span["text"].strip():
            sup.append(span["text"])
            continue
        if sup:
            t = "".join(sup).strip()
            out.append("^" + (t if len(t) == 1 else f"({t})"))
            sup = []
        if span is not None:
            out.append(span["text"])
    return "".join(out).strip()


def _raw_lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            text = _line_text(line["spans"])
            if text:
                out.append({"text": text, "bbox": [round(v, 2) for v in line["bbox"]]})
    out.sort(key=lambda r: (round(r["bbox"][1]), r["bbox"][0]))
    return out


def _chrome_key(text, bbox):
    """Same text (digits ignored) at the same place = repeated header/footer/navigation."""
    return (re.sub(r"\d+", "#", norm(text)), round(bbox[0] / 6), round(bbox[1] / 6))


def _box_key(bbox):
    return tuple(round(v / 6) for v in bbox)


def _area(b):
    return max(b[2] - b[0], 0) * max(b[3] - b[1], 0)


def _near(a, b, gap):
    return not (a[2] + gap < b[0] or b[2] + gap < a[0] or a[3] + gap < b[1] or b[3] + gap < a[1])


def _merge(boxes, gap):
    """Merge boxes that overlap or almost touch (pieces of one diagram)."""
    boxes = [list(b) for b in boxes]
    merged = True
    while merged:
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if _near(boxes[i], boxes[j], gap):
                    a, b = boxes[i], boxes.pop(j)
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    merged = True
                    break
            if merged:
                break
    return boxes


def _text_frame(box, lines):
    """A box full of text, or holding sentences (not short labels), is a text frame, not a figure."""
    inside = [r for r in lines if box[0] <= (r["bbox"][0] + r["bbox"][2]) / 2 <= box[2]
              and box[1] <= (r["bbox"][1] + r["bbox"][3]) / 2 <= box[3]]
    share = sum(_area(r["bbox"]) for r in inside) / max(_area(box), 1e-6)
    return share >= 0.3 or (share >= 0.1 and any(len(r["text"]) >= 35 for r in inside))


def _candidates(page):
    """Picture-like regions of a page: raster images and clusters of vector drawings."""
    w, h = page.rect.width, page.rect.height
    out = [[round(v, 2) for v in i["bbox"]] for i in page.get_image_info()]
    try:
        clusters = page.cluster_drawings()
    except Exception:  # noqa: BLE001 - older PyMuPDF or odd drawings: images only
        clusters = []
    for r in clusters:
        share = r.width * r.height / (w * h)
        if 0.02 <= share <= 0.85:
            out.append([round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)])
    return out


def ingest(path, source_id, out_dir, rel):
    """Analyse a PDF; write images into out_dir. Returns the source entry of the material index."""
    doc = pymupdf.open(path)
    n_pages = doc.page_count
    raw = [_raw_lines(p) for p in doc]
    cands = [_candidates(p) for p in doc]

    threshold = max(3, int(0.4 * n_pages)) if n_pages >= 5 else n_pages + 1
    line_freq, text_freq, box_freq = Counter(), Counter(), Counter()
    for rl in raw:
        line_freq.update({_chrome_key(r["text"], r["bbox"]) for r in rl})
        text_freq.update({_chrome_key(r["text"], r["bbox"])[0] for r in rl})
    for cl in cands:
        box_freq.update({_box_key(b) for b in cl})

    items, chrome = [], set()
    for i, page in enumerate(doc, start=1):
        w, h = page.rect.width, page.rect.height

        def is_chrome(r):
            key = _chrome_key(r["text"], r["bbox"])
            in_band = r["bbox"][3] < 0.12 * h or r["bbox"][1] > 0.9 * h
            return line_freq[key] >= threshold or (in_band and text_freq[key[0]] >= threshold)

        lines = []
        for r in raw[i - 1]:
            if is_chrome(r):
                chrome.add(re.sub(r"\d+", "#", r["text"]))
            else:
                lines.append(r)

        zoom = PAGE_IMAGE_WIDTH / w
        image = out_dir / f"p{i:03d}.png"
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        pix.save(image)
        preview = save_preview(image, out_dir / f"p{i:03d}.jpg", PREVIEW_IMAGE_WIDTH)

        boxes = [b for b in cands[i - 1] if box_freq[_box_key(b)] < threshold and _area(b) > 0.002 * w * h]
        boxes = [b for b in _merge(boxes, gap=0.012 * w) if _area(b) > 0.015 * w * h
                 and not _text_frame(b, lines)
                 and b[3] - b[1] > 0.06 * h and b[2] - b[0] > 0.04 * w           # no strips or rules
                 and b[1] < 0.9 * h and b[3] > 0.1 * h]                           # not inside the bands
        boxes.sort(key=lambda b: -_area(b))
        figures = []
        if boxes:
            from PIL import Image as PILImage
            full = PILImage.open(image)
        for k, b in enumerate(boxes, start=1):
            pad = 0.01 * w
            crop = [max(b[0] - pad, 0), max(b[1] - pad, 0), min(b[2] + pad, w), min(b[3] + pad, h)]
            fig = out_dir / f"p{i:03d}_f{k}.png"
            full.crop(tuple(round(v * zoom) for v in crop)).save(fig)
            figures.append({"ref": f"{source_id}#p{i}.f{k}", "bbox": b, "share": round(_area(b) / (w * h), 3),
                            "image": rel(fig), "preview": rel(save_preview(fig, fig.with_suffix(".jpg"), 1024))})

        all_text = " ".join(norm(r["text"]) for r in raw[i - 1])
        hints = []
        if any(word in all_text for word in INTERACTIVE_WORDS):
            hints.append("interactive (live poll or quiz?)")
        if not lines:
            hints.append("no text: look at the picture")
        items.append({"ref": f"{source_id}#p{i}", "page": i, "size": [round(w, 2), round(h, 2)],
                      "text_lines": lines, "image": rel(image), "preview": rel(preview),
                      "figures": figures, "hints": hints})
    return {"type": "pdf", "pages": n_pages, "chrome": sorted(chrome)[:12], "items": items}
