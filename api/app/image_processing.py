"""
Server-side port of the resize/compress logic from the client-side PHOTO SPEC
tool. Kept in lockstep with the canvas-based `renderTo` / `exportImage`
functions in the original HTML:

  - cover_crop_resize()  mirrors renderTo()'s cover-fit draw (Math.max scale,
    centered — no pan/zoom offset since there's no interactive frame here).
  - compress_to_range()  mirrors exportImage()'s quality-stepping loop
    (same quality ladder, same "best in range, else closest-below-max,
    else last" fallback order).

DPI is embedded via Pillow's `save(..., dpi=(dpi, dpi))`, which writes a
genuine JFIF/EXIF resolution tag — no byte-patching hack needed server-side.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

# Same ladder as the `qualities` array in the HTML's exportImage(), just
# expressed as Pillow's 0-100 scale instead of canvas's 0-1 scale.
QUALITY_LADDER: list[int] = [95, 90, 85, 80, 75, 70, 65, 60, 50, 40, 30, 20, 12, 8]


@dataclass
class ResizeResult:
    data: bytes
    width_px: int
    height_px: int
    dpi: int
    result_kb: float
    min_kb: int
    max_kb: int
    in_range: bool
    message: str


def cover_crop_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Center-crop the source to the target aspect ratio, then resize exactly
    to (target_w, target_h) — equivalent to the HTML's cover-fit canvas draw
    with zoom=1, offX=0, offY=0."""
    src_w, src_h = img.size
    target_aspect = target_w / target_h
    src_aspect = src_w / src_h

    if src_aspect > target_aspect:
        # source is relatively wider than target -> crop the sides
        new_w = max(1, round(src_h * target_aspect))
        new_w = min(new_w, src_w)
        left = (src_w - new_w) // 2
        box = (left, 0, left + new_w, src_h)
    else:
        # source is relatively taller than target -> crop top/bottom
        new_h = max(1, round(src_w / target_aspect))
        new_h = min(new_h, src_h)
        top = (src_h - new_h) // 2
        box = (0, top, src_w, top + new_h)

    cropped = img.crop(box)
    return cropped.resize((target_w, target_h), Image.LANCZOS)


def _flatten_to_white(img: Image.Image) -> Image.Image:
    """Matches the HTML's `ctx.fillStyle = '#fff'; ctx.fillRect(...)` behind
    the drawn image — flattens any transparency onto a white background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


def compress_to_range(img: Image.Image, dpi: int, min_kb: int, max_kb: int) -> tuple[bytes, float, bool]:
    """Step JPEG quality down the same ladder used client-side until the
    encoded size lands in [min_kb, max_kb]. Mirrors exportImage()'s
    best / closest-below-max / last fallback order exactly."""
    best: tuple[bytes, float] | None = None
    closest_below_max: tuple[bytes, float] | None = None
    last: tuple[bytes, float] | None = None

    for q in QUALITY_LADDER:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=q, dpi=(dpi, dpi))
        data = buf.getvalue()
        kb = len(data) / 1024
        last = (data, kb)

        if kb <= max_kb and (closest_below_max is None or kb > closest_below_max[1]):
            closest_below_max = (data, kb)

        if min_kb <= kb <= max_kb:
            best = (data, kb)
            break

    result = best or closest_below_max or last
    assert result is not None
    data, kb = result
    in_range = min_kb <= kb <= max_kb
    return data, kb, in_range


def process_image(
    raw_bytes: bytes,
    width_px: int,
    height_px: int,
    dpi: int,
    min_kb: int,
    max_kb: int,
) -> ResizeResult:
    img = Image.open(io.BytesIO(raw_bytes))
    img.load()
    img = _flatten_to_white(img)

    resized = cover_crop_resize(img, width_px, height_px)
    data, kb, in_range = compress_to_range(resized, dpi, min_kb, max_kb)

    if in_range:
        message = f"Landed in range at {kb:.1f}KB."
    else:
        message = (
            f"Could not reach the [{min_kb}-{max_kb}]KB range at any quality step; "
            f"returning the closest result below the max ({kb:.1f}KB)."
        )

    return ResizeResult(
        data=data,
        width_px=width_px,
        height_px=height_px,
        dpi=dpi,
        result_kb=round(kb, 2),
        min_kb=min_kb,
        max_kb=max_kb,
        in_range=in_range,
        message=message,
    )
