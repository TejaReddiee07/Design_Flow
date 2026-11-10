"""Exports: SVG -> PNG (resvg), thumbnails, multi-page PDF, ZIP packages."""
from __future__ import annotations

import io
import zipfile
from typing import Iterable, List, Optional, Tuple

import resvg_py
from PIL import Image


def png(svg: str, *, width: Optional[int] = None) -> bytes:
    out = resvg_py.svg_to_bytes(svg_string=svg, width=width) if width else resvg_py.svg_to_bytes(svg_string=svg)
    return bytes(out)


def thumb(png_bytes: bytes, *, max_side: int = 720, backdrop: Optional[str] = None) -> bytes:
    """Small JPEG preview for galleries. Transparent files are flattened onto a backdrop colour."""
    im = Image.open(io.BytesIO(png_bytes))
    im.draft("RGB", (max_side, max_side))
    im.thumbnail((max_side, max_side), Image.BILINEAR, reducing_gap=2.0)
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGBA", im.size, backdrop or "#FFFFFF")
        bg.alpha_composite(im.convert("RGBA"))
        im = bg
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=86, optimize=False, progressive=True)
    return buf.getvalue()


def pdf(pages: List[bytes], *, dpi: int = 150) -> bytes:
    """Multi-page PDF from PNG pages (flattened on white)."""
    images = []
    for p in pages:
        im = Image.open(io.BytesIO(p))
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, "#FFFFFF")
            im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        images.append(im.convert("RGB"))
    buf = io.BytesIO()
    images[0].save(buf, "PDF", resolution=float(dpi), save_all=True, append_images=images[1:])
    return buf.getvalue()


def zip_files(files: Iterable[Tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    seen = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files:
            n, i = name, 2
            while n in seen:
                stem, dot, ext = name.rpartition(".")
                n = f"{stem} ({i}).{ext}" if dot else f"{name} ({i})"
                i += 1
            seen.add(n)
            z.writestr(n, data)
    return buf.getvalue()


def size_of(png_bytes: bytes) -> Tuple[int, int]:
    return Image.open(io.BytesIO(png_bytes)).size
