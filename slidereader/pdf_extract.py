"""PDF analysis: slide images, highlightable text lines, images and an overview for the agent."""
import json
import re
import unicodedata
from collections import Counter

import pymupdf

from .config import CONFIG

SLIDE_IMAGE_WIDTH = CONFIG["video"]["slide_image_width"]
PREVIEW_IMAGE_WIDTH = CONFIG["video"]["preview_image_width"]

INTERACTIVE_WORDS = ("mentimeter", "kahoot", "wooclap", "slido", "socrative", "menti.com", "poll")


def norm(s: str) -> str:
    """Normalization used both when indexing lines and when matching highlight phrases."""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def _raw_lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            text = "".join(s["text"] for s in l["spans"]).strip()
            if text:
                out.append({"text": text, "bbox": [round(v, 2) for v in l["bbox"]]})
    out.sort(key=lambda r: (round(r["bbox"][1]), r["bbox"][0]))
    return out


def _chrome_key(text, bbox):
    """Same text (digits ignored) at the same place = repeated header/footer/navigation."""
    return (re.sub(r"\d+", "#", norm(text)), round(bbox[0] / 6), round(bbox[1] / 6))


def _img_key(bbox):
    return tuple(round(v / 6) for v in bbox)


def extract(lesson):
    doc = pymupdf.open(lesson.pdf)
    n_pages = doc.page_count
    w, h = doc[0].rect.width, doc[0].rect.height
    for d in (lesson.slides, lesson.preview):
        d.mkdir(parents=True, exist_ok=True)

    raw = [_raw_lines(p) for p in doc]
    imgs = [[[round(v, 2) for v in i["bbox"]] for i in p.get_image_info()] for p in doc]

    # repeated elements (on >= 40% of pages) are page chrome, not content
    threshold = max(3, int(0.4 * n_pages)) if n_pages >= 5 else n_pages + 1
    line_freq, text_freq = Counter(), Counter()
    for rl in raw:
        line_freq.update({_chrome_key(r["text"], r["bbox"]) for r in rl})
        text_freq.update({_chrome_key(r["text"], r["bbox"])[0] for r in rl})

    def is_chrome(r):
        """Repeated at the same place, or repeated anywhere inside the top/bottom bands of the page."""
        key = _chrome_key(r["text"], r["bbox"])
        in_band = r["bbox"][3] < 0.12 * h or r["bbox"][1] > 0.9 * h
        return line_freq[key] >= threshold or (in_band and text_freq[key[0]] >= threshold)

    img_freq = Counter()
    for il in imgs:
        img_freq.update({_img_key(b) for b in il})
    chrome_examples = sorted({re.sub(r"\d+", "#", r["text"]) for rl in raw for r in rl if is_chrome(r)})

    data = {"page_size": [w, h], "pages": n_pages, "slides": {}}
    md = [f"# Overview: {lesson.id}", "",
          f"- Pages: {n_pages}  |  page size: {w:.0f} x {h:.0f} pt  |  aspect {w / h:.2f}",
          f"- Previews (look at these): `build/{lesson.id}/preview/slide_NN.jpg`",
          "- Repeated header/footer/navigation text is excluded from the line lists below:"]
    md += [f"  - `{t}`" for t in chrome_examples[:12]] + [""]

    for i, page in enumerate(doc, start=1):
        zoom = SLIDE_IMAGE_WIDTH / w
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).save(lesson.slide_image(i))
        pz = PREVIEW_IMAGE_WIDTH / w
        page.get_pixmap(matrix=pymupdf.Matrix(pz, pz)).save(lesson.preview / f"slide_{i:02d}.jpg",
                                                              jpg_quality=85)

        lines = [r for r in raw[i - 1] if not is_chrome(r)]
        images = [b for b in imgs[i - 1]
                  if img_freq[_img_key(b)] < threshold and (b[2] - b[0]) * (b[3] - b[1]) > 0.01 * w * h]
        images.sort(key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
        data["slides"][str(i)] = {"lines": lines, "images": images}

        big = images and (images[0][2] - images[0][0]) * (images[0][3] - images[0][1]) / (w * h)
        all_text = " ".join(norm(r["text"]) for r in raw[i - 1])
        hints = []
        if any(word in all_text for word in INTERACTIVE_WORDS):
            hints.append("INTERACTIVE (live poll/quiz?) - usually skip")
        if len(lines) <= 2 and big and big > 0.5:
            hints.append("image slide (keyword/section divider) - describe image, use zoom")
        elif len(lines) == 0:
            hints.append("no text - look at the preview")
        md.append(f"## Slide {i}" + (f"  [{'; '.join(hints)}]" if hints else ""))
        md.append(f"Preview: `build/{lesson.id}/preview/slide_{i:02d}.jpg`")
        for k, r in enumerate(lines, start=1):
            md.append(f"- L{k}: {r['text']}")
        for k, b in enumerate(images, start=1):
            share = (b[2] - b[0]) * (b[3] - b[1]) / (w * h)
            md.append(f"- image #{k}: {share:.0%} of the slide")
        md.append("")

    lesson.lines.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    lesson.overview.write_text("\n".join(md))
    return n_pages


def load_lines(lesson):
    return json.loads(lesson.lines.read_text())


def resolve_highlight(slide_data, spec):
    """Bounding box (PDF points) for a highlight spec.

    spec: 3 | [3, 5] (line numbers, as listed in overview.md) | "phrase" | ["start phrase", "end phrase"]
    """
    lines = slide_data["lines"]
    if isinstance(spec, (int, str)):
        spec = [spec]
    if not isinstance(spec, list) or not 1 <= len(spec) <= 2:
        raise ValueError(f"bad highlight spec: {spec!r}")

    def find(item, start=0):
        if isinstance(item, int):
            if not 1 <= item <= len(lines):
                raise ValueError(f"line L{item} does not exist (slide has {len(lines)} lines)")
            return item - 1
        target = norm(item)
        for k in range(start, len(lines)):
            if target in norm(lines[k]["text"]):
                return k
        raise ValueError(f"phrase not found in a single line: {item!r}")

    i = find(spec[0])
    j = find(spec[-1], i)
    if j < i:
        raise ValueError(f"highlight end is before start: {spec!r}")
    boxes = [lines[k]["bbox"] for k in range(i, j + 1)]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def resolve_image(slide_data, spec):
    """spec: True (largest image) or 1-based image number as listed in overview.md."""
    images = slide_data["images"]
    if not images:
        raise ValueError("this slide has no images")
    k = 1 if spec is True else int(spec)
    if not 1 <= k <= len(images):
        raise ValueError(f"image #{k} does not exist (slide has {len(images)})")
    return images[k - 1]
