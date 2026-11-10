"""A small SVG builder with real typography (text drawn as glyph outlines)."""
from __future__ import annotations

import math
import re
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from app.agents.tools.design_engine.fonts import Face, fit, wrap

_ID_RE = re.compile(r"[^A-Za-z0-9_-]")


def _n(v: float) -> str:
    """Compact number formatting for SVG attributes."""
    if isinstance(v, int):
        return str(v)
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


_NOISE: Optional[str] = None


def _noise_tile() -> str:
    """A 256x256 grey noise PNG as a data URI (generated once per process)."""
    global _NOISE
    if _NOISE is None:
        import base64
        import io
        import os as _os

        from PIL import Image

        im = Image.frombytes("L", (256, 256), _os.urandom(256 * 256))
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=False)
        _NOISE = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return _NOISE


class Canvas:
    def __init__(self, width: float, height: float, background: Optional[str] = None) -> None:
        self.w = width
        self.h = height
        self._defs: Dict[str, str] = {}
        self._body: List[str] = []
        self._uid = 0
        self._shadow_specs: Dict[str, dict] = {}
        if background:
            self.rect(0, 0, width, height, fill=background)

    # --- infrastructure ----------------------------------------------------
    def uid(self, prefix: str = "e") -> str:
        self._uid += 1
        return f"{prefix}{self._uid}"

    def add_def(self, id_: str, xml: str) -> str:
        if id_ not in self._defs:
            self._defs[id_] = xml
        return id_

    def raw(self, xml: str) -> None:
        self._body.append(xml)

    @contextmanager
    def group(self, *, transform: str = "", opacity: float = 1.0, clip: Optional[str] = None, filter: Optional[str] = None,
              fill: Optional[str] = None) -> Iterator["Canvas"]:
        attrs = []
        if transform:
            attrs.append(f'transform="{transform}"')
        if opacity < 1:
            attrs.append(f'opacity="{_n(opacity)}"')
        if clip:
            attrs.append(f'clip-path="url(#{clip})"')
        if filter:
            attrs.append(f'filter="url(#{filter})"')
        if fill:
            attrs.append(f'fill="{fill}"')
        self._body.append(f"<g {' '.join(attrs)}>")
        try:
            yield self
        finally:
            self._body.append("</g>")

    def to_svg(self, *, transparent: bool = True) -> str:
        defs = "".join(self._defs.values())
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{_n(self.w)}" height="{_n(self.h)}" '
            f'viewBox="0 0 {_n(self.w)} {_n(self.h)}">' + (f"<defs>{defs}</defs>" if defs else "") + "".join(self._body) + "</svg>"
        )

    # --- paint servers / effects ------------------------------------------------
    def linear(self, stops: Sequence[Tuple[float, str, float]] | Sequence[Tuple[float, str]], angle: float = 90) -> str:
        """angle in degrees, 0 = left->right, 90 = top->bottom. Returns a fill value url(#id)."""
        gid = self.uid("lg")
        rad = math.radians(angle)
        x1, y1 = 0.5 - math.cos(rad) / 2, 0.5 - math.sin(rad) / 2
        x2, y2 = 0.5 + math.cos(rad) / 2, 0.5 + math.sin(rad) / 2
        st = "".join(
            f'<stop offset="{_n(s[0])}" stop-color="{s[1]}"' + (f' stop-opacity="{_n(s[2])}"' if len(s) > 2 else "") + "/>" for s in stops  # type: ignore[misc]
        )
        self.add_def(gid, f'<linearGradient id="{gid}" x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}">{st}</linearGradient>')
        return f"url(#{gid})"

    def radial(self, stops: Sequence[Tuple[float, str, float]] | Sequence[Tuple[float, str]], cx: float = 0.5, cy: float = 0.5, r: float = 0.5) -> str:
        gid = self.uid("rg")
        st = "".join(
            f'<stop offset="{_n(s[0])}" stop-color="{s[1]}"' + (f' stop-opacity="{_n(s[2])}"' if len(s) > 2 else "") + "/>" for s in stops  # type: ignore[misc]
        )
        self.add_def(gid, f'<radialGradient id="{gid}" cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}">{st}</radialGradient>')
        return f"url(#{gid})"

    def shadow(self, dy: float = 12, blur: float = 24, color: str = "#000000", opacity: float = 0.18, dx: float = 0) -> str:
        fid = f"sh{_n(dx)}_{_n(dy)}_{_n(blur)}_{color.strip('#')}_{_n(opacity)}".replace(".", "p").replace("-", "m")
        self._shadow_specs[fid] = {"dy": dy, "blur": blur, "color": color, "opacity": opacity}
        self.add_def(
            fid,
            f'<filter id="{fid}" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="{_n(dx)}" dy="{_n(dy)}" stdDeviation="{_n(blur / 2)}" '
            f'flood-color="{color}" flood-opacity="{_n(opacity)}"/></filter>',
        )
        return fid

    def blur(self, amount: float) -> str:
        fid = f"bl{_n(amount)}".replace(".", "p")
        self.add_def(fid, f'<filter id="{fid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{_n(amount)}"/></filter>')
        return fid

    def grain(self, opacity: float = 0.06, x: float = 0, y: float = 0, w: Optional[float] = None, h: Optional[float] = None) -> None:
        """Subtle film grain over an area; gives flat colour a printed, premium feel.
        Uses a tiled noise image (cheap to render) instead of an feTurbulence filter."""
        tile = _noise_tile()
        size = max(160.0, min(self.w, self.h) / 6)
        self.add_def("grainpat", f'<pattern id="grainpat" patternUnits="userSpaceOnUse" width="{_n(size)}" height="{_n(size)}">'
                                 f'<image width="{_n(size)}" height="{_n(size)}" href="{tile}" xlink:href="{tile}"/></pattern>')
        self.raw(f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w or self.w)}" height="{_n(h or self.h)}" fill="url(#grainpat)" opacity="{_n(opacity * 1.6)}"/>')

    def soft_shadow(self, x: float, y: float, w: float, h: float, *, rx: float = 0, dy: float = 14, blur: float = 30, color: str = "#000000",
                    opacity: float = 0.16) -> None:
        """Soft drop shadow for rectangles built from stacked translucent shapes (fast; no blur filter)."""
        steps = 7
        parts = []
        for i in range(steps, 0, -1):
            s = blur * i / steps
            a = opacity * 2.2 / steps * (1 - (i - 1) / steps) ** 1.2
            parts.append(f'<rect x="{_n(x - s * 0.5)}" y="{_n(y + dy - s * 0.35)}" width="{_n(w + s)}" height="{_n(h + s * 0.7)}" rx="{_n(rx + s * 0.6)}" '
                         f'fill="{color}" opacity="{_n(a)}"/>')
        self.raw("".join(parts))

    def clip_rect(self, x: float, y: float, w: float, h: float, rx: float = 0) -> str:
        cid = self.uid("cp")
        self.add_def(cid, f'<clipPath id="{cid}"><rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" rx="{_n(rx)}"/></clipPath>')
        return cid

    def clip_circle(self, cx: float, cy: float, r: float) -> str:
        cid = self.uid("cp")
        self.add_def(cid, f'<clipPath id="{cid}"><circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}"/></clipPath>')
        return cid

    def clip_path(self, d: str) -> str:
        cid = self.uid("cp")
        self.add_def(cid, f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
        return cid

    # --- shapes ------------------------------------------------------------------
    @staticmethod
    def _paint(fill: Optional[str], stroke: Optional[str], sw: float, opacity: float, extra: str = "") -> str:
        a = [f'fill="{fill or "none"}"']
        if stroke:
            a.append(f'stroke="{stroke}" stroke-width="{_n(sw)}"')
        if opacity < 1:
            a.append(f'opacity="{_n(opacity)}"')
        if extra:
            a.append(extra)
        return " ".join(a)

    def rect(self, x: float, y: float, w: float, h: float, *, fill: Optional[str] = None, rx: float = 0, stroke: Optional[str] = None,
             sw: float = 1, opacity: float = 1.0, filter: Optional[str] = None, extra: str = "") -> None:
        if filter and filter.startswith("sh"):
            # drop shadows on rectangles are drawn with the fast soft_shadow instead of a blur filter
            spec = self._shadow_specs.get(filter)
            if spec:
                self.soft_shadow(x, y, w, h, rx=rx, **spec)
            filter = None
        f = f' filter="url(#{filter})"' if filter else ""
        self.raw(f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(max(0, w))}" height="{_n(max(0, h))}" rx="{_n(rx)}" {self._paint(fill, stroke, sw, opacity, extra)}{f}/>')

    def circle(self, cx: float, cy: float, r: float, *, fill: Optional[str] = None, stroke: Optional[str] = None, sw: float = 1,
               opacity: float = 1.0, filter: Optional[str] = None, extra: str = "") -> None:
        f = f' filter="url(#{filter})"' if filter else ""
        self.raw(f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(max(0, r))}" {self._paint(fill, stroke, sw, opacity, extra)}{f}/>')

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, *, fill: Optional[str] = None, opacity: float = 1.0, transform: str = "") -> None:
        t = f' transform="{transform}"' if transform else ""
        self.raw(f'<ellipse cx="{_n(cx)}" cy="{_n(cy)}" rx="{_n(rx)}" ry="{_n(ry)}" {self._paint(fill, None, 0, opacity)}{t}/>')

    def line(self, x1: float, y1: float, x2: float, y2: float, *, stroke: str, sw: float = 1, opacity: float = 1.0, dash: str = "",
             cap: str = "round") -> None:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' opacity="{_n(opacity)}"' if opacity < 1 else ""
        self.raw(f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" stroke="{stroke}" stroke-width="{_n(sw)}" stroke-linecap="{cap}"{d}{o}/>')

    def path(self, d: str, *, fill: Optional[str] = None, stroke: Optional[str] = None, sw: float = 1, opacity: float = 1.0,
             transform: str = "", evenodd: bool = False, cap: str = "round", join: str = "round", filter: Optional[str] = None) -> None:
        extra = []
        if transform:
            extra.append(f'transform="{transform}"')
        if evenodd:
            extra.append('fill-rule="evenodd"')
        if stroke:
            extra.append(f'stroke-linecap="{cap}" stroke-linejoin="{join}"')
        if filter:
            extra.append(f'filter="url(#{filter})"')
        self.raw(f'<path d="{d}" {self._paint(fill, stroke, sw, opacity, " ".join(extra))}/>')

    def polygon(self, pts: Sequence[Tuple[float, float]], *, fill: Optional[str] = None, opacity: float = 1.0, stroke: Optional[str] = None, sw: float = 1) -> None:
        p = " ".join(f"{_n(x)},{_n(y)}" for x, y in pts)
        self.raw(f'<polygon points="{p}" {self._paint(fill, stroke, sw, opacity)}/>')

    def image(self, x: float, y: float, w: float, h: float, href: str, *, fit: str = "slice", clip: Optional[str] = None, opacity: float = 1.0) -> None:
        par = "xMidYMid slice" if fit == "slice" else "xMidYMid meet"
        c = f' clip-path="url(#{clip})"' if clip else ""
        o = f' opacity="{_n(opacity)}"' if opacity < 1 else ""
        self.raw(f'<image x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" preserveAspectRatio="{par}" href="{href}" xlink:href="{href}"{c}{o}/>')

    # --- typography ----------------------------------------------------------------
    def _glyph_id(self, fc: Face, name: str) -> str:
        gid = "g" + fc.key + "_" + _ID_RE.sub("_", name)
        if gid not in self._defs:
            d = fc.glyph_path(name)
            self._defs[gid] = f'<path id="{gid}" d="{d}"/>' if d else f'<path id="{gid}" d=""/>'
        return gid

    def text(self, x: float, y: float, s: str, fc: Face, size: float, *, fill: str = "#111111", anchor: str = "start",
             tracking: float = 0.0, opacity: float = 1.0, upper: bool = False, rotate: float = 0.0) -> float:
        """Draw one line; (x, y) is the baseline origin. Returns the width in px."""
        s = str(s or "")
        if upper:
            s = s.upper()
        if not s.strip():
            return 0.0
        shaped = fc.shape(s, tracking)
        k = size / fc.upem
        width = shaped.advance * k
        x0 = x - width if anchor == "end" else x - width / 2 if anchor == "middle" else x
        uses = "".join(
            f'<use href="#{self._glyph_id(fc, name)}" x="{_n(gx)}" y="{_n(-gy)}"/>' for name, gx, gy in shaped.glyphs if name not in ("space", "nbspace", "uni00A0")
        )
        o = f' opacity="{_n(opacity)}"' if opacity < 1 else ""
        rot = f" rotate({_n(rotate)} {_n(x)} {_n(y)})" if rotate else ""
        self.raw(f'<g fill="{fill}"{o} transform="{rot.strip()} translate({_n(x0)} {_n(y)}) scale({k:.5f} {-k:.5f})">{uses}</g>')
        return width

    def lines(self, x: float, y_top: float, lines: Sequence[str], fc: Face, size: float, *, fill: str = "#111111", align: str = "left",
              line_height: float = 1.2, tracking: float = 0.0, width: float = 0.0, opacity: float = 1.0, upper: bool = False) -> float:
        """Draw pre-wrapped lines whose block top is y_top. Returns block height (top to last baseline + descent)."""
        anchor = {"left": "start", "center": "middle", "right": "end"}[align]
        ax = x + (width / 2 if align == "center" else width if align == "right" else 0)
        baseline = y_top + fc.cap(size)
        for i, ln in enumerate(lines):
            self.text(ax, baseline + i * size * line_height, ln, fc, size, fill=fill, anchor=anchor, tracking=tracking, opacity=opacity, upper=upper)
        if not lines:
            return 0.0
        return fc.cap(size) + (len(lines) - 1) * size * line_height + fc.desc(size) * 0.5

    def paragraph(self, x: float, y_top: float, w: float, s: str, fc: Face, size: float, *, fill: str = "#333333", align: str = "left",
                  line_height: float = 1.45, max_lines: int = 99, tracking: float = 0.0, opacity: float = 1.0, upper: bool = False) -> float:
        text = s.upper() if upper else s
        ls = wrap(text, fc, size, w, tracking)
        if len(ls) > max_lines:
            ls = ls[:max_lines]
            last = ls[-1]
            while last and fc.width(last + "…", size, tracking) > w:
                last = last[:-1].rstrip()
            ls[-1] = (last.rstrip(",.;:") + "…") if last else "…"
        return self.lines(x, y_top, ls, fc, size, fill=fill, align=align, line_height=line_height, tracking=tracking, width=w, opacity=opacity)

    def fit_text(self, x: float, y_top: float, w: float, h: float, s: str, fc: Face, *, max_size: float, min_size: float = 10,
                 fill: str = "#111111", align: str = "left", line_height: float = 1.05, max_lines: int = 4, tracking: float = 0.0,
                 upper: bool = False, valign: str = "top", opacity: float = 1.0) -> Tuple[float, float]:
        """Largest size that fits the box. Returns (font size, used height)."""
        text = (s or "").upper() if upper else (s or "")
        size, ls = fit(text, fc, w, h, max_size=max_size, min_size=min_size, line_height=line_height, max_lines=max_lines, tracking=tracking)
        block = fc.cap(size) + (len(ls) - 1) * size * line_height
        top = y_top + (h - block) / 2 if valign == "middle" else y_top + (h - block) if valign == "bottom" else y_top
        used = self.lines(x, top, ls, fc, size, fill=fill, align=align, line_height=line_height, tracking=tracking, width=w, opacity=opacity)
        return size, used

    def arc_text(self, cx: float, cy: float, r: float, s: str, fc: Face, size: float, *, fill: str, position: str = "top",
                 tracking: float = 0.12, upper: bool = True) -> None:
        """Text set on a circle (badges/emblems). 'top' reads clockwise over the top; 'bottom' reads left-to-right under it."""
        text = s.upper() if upper else s
        if not text.strip():
            return
        shaped = fc.shape(text, tracking)
        k = size / fc.upem
        total = shaped.advance * k
        cap = fc.cap(size)
        span = total / r  # radians; r is the centre line of the lettering band
        parts = []
        for i, (name, gx, _gy) in enumerate(shaped.glyphs):
            nxt = shaped.glyphs[i + 1][1] if i + 1 < len(shaped.glyphs) else shaped.advance
            adv = (nxt - gx) * k
            if name in ("space", "nbspace", "uni00A0"):
                continue
            theta = -span / 2 + (gx * k + adv / 2) / r
            if position == "top":  # tops point outwards
                rb = r - cap / 2
                px, py, deg = cx + rb * math.sin(theta), cy - rb * math.cos(theta), math.degrees(theta)
            else:  # tops point to the centre, reads left to right like a smile
                rb = r + cap / 2
                px, py, deg = cx + rb * math.sin(theta), cy + rb * math.cos(theta), -math.degrees(theta)
            parts.append(
                f'<use href="#{self._glyph_id(fc, name)}" transform="translate({_n(px)} {_n(py)}) rotate({_n(deg)}) translate({_n(-adv / 2)} 0) scale({k:.5f} {-k:.5f})"/>'
            )
        self.raw(f'<g fill="{fill}">{"".join(parts)}</g>')
