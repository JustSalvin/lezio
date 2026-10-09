"""Helpers shared by the material readers."""
import re
import unicodedata

INTERACTIVE_WORDS = ("mentimeter", "kahoot", "wooclap", "slido", "socrative", "menti.com", "poll")
MAX_SECTION_WORDS = 1200          # longer sections are split into parts


def norm(s: str) -> str:
    """Normalization used both when indexing text lines and when matching highlight phrases."""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def save_preview(src, dst, width):
    """JPEG copy of an image, at most `width` pixels wide (pictures shown to the agent)."""
    from PIL import Image
    im = Image.open(src)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.getchannel("A"))
        im = bg
    else:
        im = im.convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dst, "JPEG", quality=85)
    return dst


def save_png(src, dst, max_width):
    """PNG copy of any image PIL can read, at most `max_width` wide. Returns (dst, (w, h)) or None."""
    from PIL import Image, UnidentifiedImageError
    try:
        im = Image.open(src)
        im.load()
    except (UnidentifiedImageError, OSError):
        return None
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    im.save(dst, "PNG")
    return dst, im.size


def split_long(heading, paragraphs, max_words=MAX_SECTION_WORDS):
    """[(heading, [paragraphs])] with no part longer than max_words (long sections are split)."""
    parts, cur, words = [], [], 0
    for p in paragraphs:
        n = len(p.split())
        if cur and words + n > max_words:
            parts.append(cur)
            cur, words = [], 0
        cur.append(p)
        words += n
    parts.append(cur)
    if len(parts) == 1:
        return [(heading, parts[0])]
    return [(f"{heading} ({k}/{len(parts)})" if heading else None, p) for k, p in enumerate(parts, 1)]
