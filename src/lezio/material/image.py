"""Picture sources (.png, .jpg, .jpeg, .webp): one item, the picture itself."""
from ..config import CONFIG
from .common import save_preview, save_png

PAGE_IMAGE_WIDTH = CONFIG["tuning"]["page_image_width"]
PREVIEW_IMAGE_WIDTH = CONFIG["tuning"]["preview_image_width"]


def ingest(path, source_id, out_dir, rel):
    saved = save_png(path, out_dir / "image.png", PAGE_IMAGE_WIDTH)
    if not saved:
        raise ValueError(f"{path.name}: not a readable picture")
    png, size = saved
    preview = save_preview(png, out_dir / "image.jpg", PREVIEW_IMAGE_WIDTH)
    return {"type": "image", "items": [{"ref": source_id, "size": list(size), "image": rel(png),
                                         "preview": rel(preview), "figures": []}]}
