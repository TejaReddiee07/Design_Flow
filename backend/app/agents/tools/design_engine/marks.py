"""Logo constructions. Each draws onto a Canvas and returns its bounding box (x, y, w, h).

  emblem    circular badge: double ring, name set on an arc, motif in a disc, descriptor underneath
  lockup    icon mark + wordmark + tagline (horizontal), or stacked
  monogram  initials in a style-specific container (+ spaced wordmark when stacked)
  wordmark  the name alone, with a typographic detail (accent dot, bar, rules)
  icon      the square mark used for favicons, app icons and social avatars
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from app.agents.tools.design_engine import color as col
from app.agents.tools.design_engine.brand import Brand
from app.agents.tools.design_engine.canvas import Canvas, _n
from app.agents.tools.design_engine.icons import draw_icon, poly, rrect, star_points

Box = Tuple[float, float, float, float]


@dataclass
class Scheme:
    """Colours for one rendering of a logo (full colour, reversed, one-colour...)."""
    text: str  # wordmark
    sub: str  # tagline / descriptor
    mark_bg: str  # container fill
    mark_fg: str  # icon / initials inside the container
    line: str  # rings and rules
    accent: str

    @staticmethod
    def full(b: Brand, bg: str) -> "Scheme":
        dark_bg = col.luminance(bg) < 0.3
        if dark_bg:
            text = b.light if col.contrast(b.light, bg) > 4.5 else "#FFFFFF"
            mark_bg = b.accent if col.contrast(b.accent, bg) > 2.2 else b.light
            return Scheme(text, col.mix(text, bg, 0.3), mark_bg, col.readable_on(mark_bg, bg, b.dark, "#FFFFFF", minimum=3), text, b.accent)
        text = b.dark if col.contrast(b.dark, bg) > 4.5 else b.ink
        mark_bg = b.primary if col.contrast(b.primary, bg) > 2.2 else b.dark
        return Scheme(text, col.mix(b.primary, text, 0.35) if col.contrast(b.primary, bg) > 3 else col.mix(text, bg, 0.3), mark_bg,
                      col.readable_on(mark_bg, bg, b.light, "#FFFFFF", minimum=3), b.primary if col.contrast(b.primary, bg) > 3 else text, b.accent)

    @staticmethod
    def mono(c: str, bg: str) -> "Scheme":
        return Scheme(c, c, c, bg if bg != "none" else ("#FFFFFF" if col.luminance(c) < 0.5 else "#111111"), c, c)


# ---------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------
def _container(c: Canvas, b: Brand, x: float, y: float, s: float, sc: Scheme) -> None:
    st = b.style
    if st == "Playful":
        c.circle(x + s / 2, y + s / 2, s / 2, fill=sc.mark_bg)
    elif st == "Luxury":
        c.circle(x + s / 2, y + s / 2, s / 2 - s * 0.02, stroke=sc.line, sw=s * 0.03)
        c.circle(x + s / 2, y + s / 2, s / 2 - s * 0.09, stroke=sc.line, sw=s * 0.012)
    elif st == "Vintage":
        c.circle(x + s / 2, y + s / 2, s / 2, fill=sc.mark_bg)
        c.circle(x + s / 2, y + s / 2, s / 2 - s * 0.07, stroke=sc.mark_fg, sw=s * 0.018)
    elif st == "Bold":
        c.path(poly([(x + s / 2 + s / 2 * math.cos(math.radians(a)), y + s / 2 + s / 2 * math.sin(math.radians(a))) for a in range(-90, 270, 60)]), fill=sc.mark_bg)
    elif st == "Minimal":
        pass
    else:
        c.path(rrect(x, y, s, s, s * (0.28 if st == "Modern" else 0.18)), fill=sc.mark_bg)


def _inner_color(b: Brand, sc: Scheme, monogram: bool = False) -> str:
    base = sc.line if b.style in ("Luxury", "Minimal") else sc.mark_fg
    if monogram:
        return base
    # natural symbols take the client's green when they gave one ("a subtle leaf in soft green")
    if b.motif in ("leaf", "sprout", "lotus", "flower") and b.style in ("Luxury", "Minimal"):
        hue = col.hls(sc.accent)[0] * 360
        if 70 <= hue <= 170 and col.chroma(sc.accent) > 0.08 and sc.accent not in (sc.text, sc.line):
            return sc.accent
    return base


def icon_mark(c: Canvas, b: Brand, x: float, y: float, s: float, sc: Scheme, *, monogram: bool = False) -> Box:
    _container(c, b, x, y, s, sc)
    fg = _inner_color(b, sc, monogram)
    if monogram:
        fc = b.display if b.style in ("Luxury", "Vintage") else b.heading
        letters = b.initials
        cap_target = s * (0.40 if len(letters) > 1 else 0.48)
        size = cap_target / (fc.cap_height / fc.upem)
        w = fc.width(letters, size, -0.02)
        if w > s * 0.66:
            size *= s * 0.66 / w
        c.text(x + s / 2, y + s / 2 + fc.cap(size) / 2, letters, fc, size, fill=fg, anchor="middle", tracking=-0.02)
    else:
        k = 0.66 if b.style == "Minimal" else 0.52 if b.style in ("Luxury",) else 0.56
        draw_icon(c, b.motif, x + s * (1 - k) / 2, y + s * (1 - k) / 2, s * k, fg)
    return (x, y, s, s)


# ---------------------------------------------------------------------------
# wordmark helpers
# ---------------------------------------------------------------------------
def _name_lines(b: Brand, fc, cap: float, max_w: float, tracking: float) -> Tuple[list, float]:
    name = b.cased(b.name)
    size = cap / (fc.cap_height / fc.upem)
    full = fc.width(name, size, tracking)
    if full <= max_w:
        return [name], size
    words = name.split()
    if full * 0.72 <= max_w or len(words) < 2:  # a slightly smaller single line reads better than a forced break
        return [name], size * max_w / full
    if len(words) > 1:
        best = None
        for i in range(1, len(words)):
            l1, l2 = " ".join(words[:i]), " ".join(words[i:])
            w = max(fc.width(l1, size, tracking), fc.width(l2, size, tracking))
            if best is None or w < best[0]:
                best = (w, [l1, l2])
        lines = best[1]
        widest = best[0]
        if widest > max_w:
            size *= max_w / widest
        return lines, size
    return [name], size * max_w / fc.width(name, size, tracking)


def lockup(c: Canvas, b: Brand, x: float, y: float, h: float, sc: Scheme, *, tagline: Optional[str] = None, monogram: bool = False,
           max_w: Optional[float] = None) -> Box:
    """Mark on the left, name + tagline on the right; (x, y) is the top-left, h the mark height."""
    icon_mark(c, b, x, y, h, sc, monogram=monogram)
    tx = x + h * 1.26
    fc = b.heading
    tracking = 0.06 if b.case == "upper" and b.style not in ("Bold",) else -0.01
    tag = (tagline if tagline is not None else (b.tagline or b.descriptor)).strip()
    cap = h * (0.30 if tag else 0.40)
    lines, size = _name_lines(b, fc, cap, (max_w or h * 5.2) - h * 1.26, tracking)
    lh = size * 1.02
    block = fc.cap(size) + (len(lines) - 1) * lh
    tag_size = h * 0.105
    tag_gap = h * 0.13
    total = block + (tag_gap + b.label.cap(tag_size) if tag else 0)
    top = y + (h - total) / 2
    widths = []
    for i, ln in enumerate(lines):
        widths.append(c.text(tx, top + fc.cap(size) + i * lh, ln, fc, size, fill=sc.text, tracking=tracking))
    name_w = max(widths)
    if tag:
        tag_txt = tag.upper()
        ts = tag_size
        tw = b.label.width(tag_txt, ts, 0.22)
        if tw > name_w * 1.15:
            ts *= name_w * 1.15 / tw
        tw = c.text(tx, top + block + tag_gap + b.label.cap(ts), tag_txt, b.label, ts, fill=sc.sub, tracking=0.22)
        name_w = max(name_w, tw)
    return (x, y, tx - x + name_w, h)


def stacked(c: Canvas, b: Brand, cx: float, y: float, s: float, sc: Scheme, *, monogram: bool = True, tagline: Optional[str] = None,
            max_w: Optional[float] = None) -> Box:
    """Mark on top, spaced wordmark underneath, centred on cx."""
    icon_mark(c, b, cx - s / 2, y, s, sc, monogram=monogram)
    fc = b.heading if b.style not in ("Luxury",) else b.display
    tracking = 0.16 if b.case == "upper" else 0.0
    max_w = max_w or s * 3.4
    lines, size = _name_lines(b, fc, s * 0.2, max_w, tracking)
    yy = y + s + s * 0.24
    widths = []
    for i, ln in enumerate(lines):
        widths.append(c.text(cx, yy + fc.cap(size) + i * size * 1.05, ln, fc, size, fill=sc.text, anchor="middle", tracking=tracking))
    yy += fc.cap(size) + (len(lines) - 1) * size * 1.05
    w = max(widths + [s])
    tag = (tagline if tagline is not None else (b.tagline or b.descriptor)).strip()
    if tag:
        ts = s * 0.075
        tw = b.label.width(tag.upper(), ts, 0.28)
        if tw > w * 1.1:
            ts *= w * 1.1 / tw
            tw = w * 1.1
        ty = yy + s * 0.16 + b.label.cap(ts)
        c.text(cx, ty, tag, b.label, ts, fill=sc.sub, anchor="middle", tracking=0.28, upper=True)
        if b.style in ("Luxury", "Vintage", "Minimal"):
            gap = s * 0.08
            ll = s * 0.22
            c.line(cx - tw / 2 - gap - ll, ty - b.label.cap(ts) / 2, cx - tw / 2 - gap, ty - b.label.cap(ts) / 2, stroke=sc.line, sw=max(1, s * 0.008))
            c.line(cx + tw / 2 + gap, ty - b.label.cap(ts) / 2, cx + tw / 2 + gap + ll, ty - b.label.cap(ts) / 2, stroke=sc.line, sw=max(1, s * 0.008))
        yy = ty
        w = max(w, tw + 2 * (s * 0.3))
    return (cx - w / 2, y, w, yy - y + s * 0.04)


def wordmark(c: Canvas, b: Brand, x: float, y_top: float, cap: float, sc: Scheme, *, align: str = "left", max_w: Optional[float] = None,
             tagline: Optional[str] = None) -> Box:
    st = b.style
    fc = b.display if st in ("Luxury", "Vintage") else b.heading
    name = b.name
    if st in ("Modern", "Playful"):
        name = name.lower() if len(name) <= 18 else name
    elif b.case == "upper":
        name = name.upper()
    tracking = {"Luxury": 0.14, "Minimal": 0.08, "Corporate": 0.0, "Bold": -0.02, "Vintage": 0.02, "Modern": -0.03, "Playful": -0.02}[st]
    size = cap / (fc.cap_height / fc.upem)
    if max_w and fc.width(name, size, tracking) > max_w * 0.92:
        size *= max_w * 0.92 / fc.width(name, size, tracking)
    w = fc.width(name, size, tracking)
    x0 = x - w / 2 if align == "center" else x
    base = y_top + fc.cap(size)
    c.text(x0, base, name, fc, size, fill=sc.text, tracking=tracking)
    h = fc.cap(size)
    if st in ("Modern", "Playful"):
        r = size * 0.085
        c.circle(x0 + w + r * 1.6, base - r, r, fill=sc.accent if sc.accent != sc.text else sc.line)
        w += r * 3.2
    elif st == "Bold":
        c.rect(x0, base + size * 0.12, w * 0.34, size * 0.08, fill=sc.accent if sc.accent != sc.text else sc.line)
        h += size * 0.2
    tag = (tagline if tagline is not None else (b.tagline or b.descriptor)).strip()
    if tag:
        ts = max(size * 0.17, 6)
        tw = b.label.width(tag.upper(), ts, 0.3)
        if tw > w:
            ts *= w / tw
            tw = w
        ty = base + size * (0.42 if st == "Bold" else 0.34) + b.label.cap(ts)
        tx = x0 + w / 2 if align == "center" or st in ("Luxury", "Vintage") else x0
        anchor = "middle" if (align == "center" or st in ("Luxury", "Vintage")) else "start"
        c.text(tx, ty, tag, b.label, ts, fill=sc.sub, anchor=anchor, tracking=0.3, upper=True)
        if st in ("Luxury", "Vintage"):
            mid = ty - b.label.cap(ts) / 2
            gap = ts * 0.9
            c.line(x0, mid, x0 + w / 2 - tw / 2 - gap, mid, stroke=sc.line, sw=max(1, size * 0.012))
            c.line(x0 + w / 2 + tw / 2 + gap, mid, x0 + w, mid, stroke=sc.line, sw=max(1, size * 0.012))
        h = ty - y_top
    return (x0, y_top, w, h)


def emblem(c: Canvas, b: Brand, cx: float, cy: float, r: float, sc: Scheme, *, bottom: Optional[str] = None) -> Box:
    ring = r * 0.035
    c.circle(cx, cy, r - ring / 2, stroke=sc.line, sw=ring)
    c.circle(cx, cy, r * 0.885, stroke=sc.line, sw=r * 0.012)
    disc_r = r * 0.6
    if b.style in ("Luxury", "Minimal"):
        c.circle(cx, cy, disc_r, stroke=sc.line, sw=r * 0.012)
        icon_color = sc.line
    else:
        c.circle(cx, cy, disc_r, fill=sc.mark_bg)
        c.circle(cx, cy, disc_r * 0.9, stroke=sc.mark_fg, sw=r * 0.01, extra='stroke-dasharray="2 5"' if b.style == "Vintage" else "")
        icon_color = sc.mark_fg
    k = disc_r * 1.05
    draw_icon(c, b.motif, cx - k / 2, cy - k / 2, k, icon_color)

    band = r * 0.745
    fc = b.label if b.style not in ("Vintage", "Luxury") else b.heading
    top = b.name.upper()
    size = r * 0.15
    max_arc = band * math.radians(165)
    w = fc.width(top, size, 0.16)
    if w > max_arc:
        size *= max_arc / w
    c.arc_text(cx, cy, band, top, fc, size, fill=sc.text, position="top", tracking=0.16)
    bot = (bottom or b.location or b.descriptor or b.tagline or "").upper()
    if bot:
        bs = r * 0.095
        max_b = band * math.radians(110)
        wb = b.label.width(bot, bs, 0.24)
        if wb > max_b:
            bs *= max_b / wb
        c.arc_text(cx, cy, band, bot, b.label, bs, fill=sc.sub if sc.sub != sc.text else sc.text, position="bottom", tracking=0.24)
    for side in (-1, 1):
        a = math.radians(90 + 14) * side
        px, py = cx + band * math.sin(a), cy - band * math.cos(a)
        c.polygon(star_points(px, py, r * 0.045, r * 0.019), fill=sc.accent if col.contrast(sc.accent, sc.mark_fg) > 1.2 else sc.line)
    return (cx - r, cy - r, 2 * r, 2 * r)


# ---------------------------------------------------------------------------
# standalone logo files (transparent background)
# ---------------------------------------------------------------------------
LOGO_KINDS = ("emblem", "lockup", "monogram", "wordmark")


def draw_logo(c: Canvas, b: Brand, kind: str, x: float, y: float, w: float, h: float, sc: Scheme) -> None:
    """Fit a logo of the given kind into the box, centred."""
    cx, cy = x + w / 2, y + h / 2
    if kind == "emblem":
        r = min(w, h) / 2 * 0.96
        emblem(c, b, cx, cy, r, sc)
    elif kind == "monogram":
        s = min(h * 0.5, w * 0.34)
        probe = Canvas(10, 10)
        bx = stacked(probe, b, 0, 0, s, sc, max_w=w * 0.9)
        k = min(1.0, h * 0.94 / max(bx[3], 1), w * 0.94 / max(bx[2], 1))
        s *= k
        bx = stacked(Canvas(10, 10), b, 0, 0, s, sc, max_w=w * 0.9)
        stacked(c, b, cx, cy - bx[3] / 2, s, sc, max_w=w * 0.9)
    elif kind == "wordmark":
        probe = Canvas(10, 10)
        cap = h * 0.26
        bx = wordmark(probe, b, 0, 0, cap, sc, max_w=w * 0.9)
        k = min(w * 0.9 / max(bx[2], 1), h * 0.8 / max(bx[3], 1), 1.6)
        cap *= k
        bx = wordmark(Canvas(10, 10), b, 0, 0, cap, sc, max_w=w * 0.9)
        wordmark(c, b, cx - bx[2] / 2, cy - bx[3] / 2, cap, sc, max_w=w * 0.9)
    else:  # lockup
        mh = h * 0.42
        probe = Canvas(10, 10)
        bx = lockup(probe, b, 0, 0, mh, sc, max_w=w * 0.94)
        k = min(w * 0.92 / max(bx[2], 1), h * 0.9 / max(bx[3], 1), 1.4)
        mh *= k
        bx = lockup(Canvas(10, 10), b, 0, 0, mh, sc, max_w=w * 0.94)
        lockup(c, b, cx - bx[2] / 2, cy - mh / 2, mh, sc, max_w=w * 0.94)


def logo_svg(b: Brand, kind: str, sc: Scheme, *, width: float, height: float, background: Optional[str] = None, pad: float = 0.1) -> str:
    c = Canvas(width, height, background)
    draw_logo(c, b, kind, width * pad, height * pad, width * (1 - 2 * pad), height * (1 - 2 * pad), sc)
    return c.to_svg()


def logo_dims(kind: str) -> Tuple[int, int]:
    return {"emblem": (1200, 1200), "monogram": (1200, 1200), "wordmark": (2000, 800), "lockup": (2000, 800)}[kind]
