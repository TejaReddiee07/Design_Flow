"""Shared building blocks for every service layout."""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.agents.tools.design_engine import color as col
from app.agents.tools.design_engine.brand import Brand
from app.agents.tools.design_engine.canvas import Canvas, _n
from app.agents.tools.design_engine.icons import ICONS, draw_icon, rrect
from app.agents.tools.design_engine.marks import Scheme, icon_mark, lockup


@dataclass
class Art:
    """One output file of a design version."""
    name: str  # file name without extension, e.g. "Instagram post 1 - 1080x1350"
    svg: str
    w: int
    h: int
    label: str
    role: str = "variant"  # board | primary | variant | page
    group: str = ""  # folder inside the ZIP
    transparent: bool = False
    backdrop: Optional[str] = None  # thumbnail backdrop for transparent files
    pdf: Optional[str] = None  # name of the PDF this page belongs to
    export_width: Optional[int] = None
    svg_file: bool = True
    svg_role: Optional[str] = None  # role of the .svg copy (default "source": kept for the admin, not sent to the client)
    png: Optional[bytes] = None  # a finished raster (e.g. an AI-generated logo); used as-is instead of rendering svg


@dataclass
class Result:
    arts: List[Art] = field(default_factory=list)
    pdfs: Dict[str, int] = field(default_factory=dict)  # pdf name -> dpi
    texts: List[Tuple[str, str]] = field(default_factory=list)  # (file name, markdown text)
    summary: str = ""
    board: Optional[str] = None  # name of the art used as the preview board


# ---------------------------------------------------------------------------
# job: brief + copy helpers
# ---------------------------------------------------------------------------
_INSTRUCTION = re.compile(r"\b(i want|we want|we'd like|i'd like|should|please|make it|make sure|design|logo|colou?r|palette|style|feel|look|font|avoid|like the|vibe)\b", re.I)


def _clean(s: Any, limit: int = 160) -> str:
    t = re.sub(r"\s+", " ", str(s or "")).strip().strip('"').strip("'").strip()
    t = re.sub(r"^(headline|title|cta|body|hook)\s*[:\-]\s*", "", t, flags=re.I)
    return t[:limit].rstrip()


# Copy that talks about the design job instead of to customers ("Logo design brief", "inspired by your brand colours #6F4E37")
_META = re.compile(r"\b(logo|design brief|brief|design concepts?|concepts?|brand guide|brand colou?rs?|target audience|mood ?board|deliverables?|"
                   r"our design|we'?ve created|this design|the design|aesthetic)\b|#[0-9a-f]{3,6}\b", re.I)


def _text_of(x: Any) -> str:
    if isinstance(x, dict):  # some models return {"text": "...", "url": "#"}
        return str(x.get("text") or x.get("title") or x.get("label") or "")
    return str(x or "")


def _as_list(v: Any, *, customer_facing: bool = True) -> List[str]:
    if isinstance(v, list):
        items = [_clean(_text_of(x)) for x in v]
    elif isinstance(v, str) and v.strip():
        items = [_clean(x) for x in re.split(r"\n|;|•", v)]
    else:
        return []
    items = [x for x in items if x]
    if customer_facing:
        items = [x for x in items if not _META.search(x)]
    return items


class Job:
    def __init__(self, ctx: Dict[str, Any], b: Brand) -> None:
        self.ctx = ctx
        self.b = b
        self.brief: Dict[str, Any] = ctx.get("brief") or {}
        self.content: Dict[str, Any] = ctx.get("content") or {}
        self.strategy: Dict[str, Any] = ctx.get("strategy") or {}
        self.concept: Dict[str, Any] = ctx.get("concept") or {}
        self.slug: str = ctx.get("service_slug") or ""
        self.service_name: str = ctx.get("service_name") or ""
        self.title: str = ctx.get("title") or ""
        self.version = int(ctx.get("version") or 1)
        self.request_id = int(ctx.get("request_id") or 0)
        self.rng = random.Random(f"{self.request_id}-{self.version}-{self.slug}")
        self.scale = float(ctx.get("scale") or 1.0)  # < 1 in the test-suite to keep renders fast

    # raw fields
    def f(self, *keys: str) -> str:
        for k in keys:
            v = self.brief.get(k)
            if isinstance(v, list):
                v = ", ".join(map(str, v))
            if v not in (None, ""):
                return str(v).strip()
        return ""

    def lines(self, *keys: str) -> List[str]:
        out: List[str] = []
        for k in keys:
            v = self.brief.get(k)
            if isinstance(v, list):
                out += [_clean(x) for x in v if _clean(x)]
            elif v:
                out += [_clean(x.lstrip("-*•0123456789.) ")) for x in str(v).splitlines() if _clean(x.lstrip("-*•0123456789.) "))]
        return out

    def number(self, key: str, default: int, lo: int, hi: int) -> int:
        m = re.search(r"\d+", str(self.brief.get(key) or ""))
        n = int(m.group(0)) if m else default
        return max(lo, min(hi, n))

    def multi(self, key: str) -> List[str]:
        v = self.brief.get(key)
        if isinstance(v, list):
            return [str(x) for x in v]
        return [x.strip() for x in str(v or "").split(",") if x.strip()]

    # copy
    def copy_parts(self) -> Tuple[str, str, str]:
        """(headline, body, cta) from the client's own 'Text / copy to include'."""
        raw = self.f("copy_text")
        if not raw:
            return "", "", ""
        cta = ""
        m = re.search(r"(?im)^\s*(?:cta|call to action)\s*[:\-]\s*(.+)$", raw)
        if m:
            cta = _clean(m.group(1), 40)
            raw = raw[: m.start()] + raw[m.end():]
        parts = [p for p in (x.strip() for x in raw.splitlines()) if p]
        if len(parts) == 1:
            sentences = re.split(r"(?<=[.!?])\s+", parts[0])
            head = sentences[0]
            body = " ".join(sentences[1:])
        else:
            head, body = parts[0], " ".join(parts[1:])
        return _clean(head, 90).rstrip("."), _clean(body, 260), cta

    def headlines(self) -> List[str]:
        out: List[str] = []
        head, _, _ = self.copy_parts()
        for v in [head, self.f("thumbnail_text"), self.f("topic")]:
            if v:
                out.append(_clean(v, 90).rstrip("."))
        offer_first = self.slug in ("ad-creative-design", "flyer-design", "product-advertisement-design")
        offer = self.f("event_or_offer", "offer", "product", "what")
        offer_line = _clean(re.split(r"(?<=[.!?\n])\s", offer)[0], 80).rstrip(".") if offer else ""
        if offer_first and offer_line and len(offer_line) <= 70:
            out.append(offer_line)
        out += [h.rstrip(".") for h in _as_list(self.content.get("headlines"))]
        if offer_line and offer_line not in out:
            out.append(offer_line)
        if not out:
            out = [f"Meet {self.b.name}", self.b.tagline or f"{self.b.descriptor}, done properly", "Made to be noticed"]
        seen, uniq = set(), []
        for h in out:
            k = h.lower()
            if h and k not in seen:
                seen.add(k)
                uniq.append(h)
        return uniq

    def headline(self, i: int = 0) -> str:
        hs = self.headlines()
        return hs[i % len(hs)]

    def subs(self) -> List[str]:
        out = _as_list(self.content.get("subheadlines"))
        if self.b.tagline:
            out.append(self.b.tagline)
        pos = _clean(self.strategy.get("positioning"), 140)
        pos = "" if _META.search(pos) else pos
        if pos:
            out.append(re.split(r"(?<=[.!?])\s", pos)[0])
        return out or [self.business_line() or f"{self.b.descriptor} by {self.b.name}"]

    def sub(self, i: int = 0) -> str:
        s = self.subs()
        return s[i % len(s)]

    def business_line(self) -> str:
        """First sentence of the client's description when it reads like marketing copy, not instructions."""
        about = self.f("about_and_wishes")
        for sent in re.split(r"(?<=[.!?])\s+", about)[:2]:
            s = _clean(sent, 140)
            if 12 <= len(s) and not _INSTRUCTION.search(s):
                return s.rstrip(".") + "."
        return ""

    def body(self) -> str:
        _, body, _ = self.copy_parts()
        copy = _clean(_text_of(self.content.get("body_copy")), 240)
        if copy and _META.search(copy):
            copy = ""
        return body or copy or self.business_line() or self.sub(0)

    def cta(self) -> str:
        _, _, cta = self.copy_parts()
        v = self.f("cta") or cta
        if v:
            return _clean(v, 32)
        opts = _as_list(self.content.get("cta_options"))
        if opts and len(opts[0]) <= 26:
            return opts[0].rstrip(".")
        return {"ad-creative-design": "Shop now", "website-banner-design": "Discover more", "flyer-design": "Find out more",
                "poster-design": "Find out more", "product-advertisement-design": "Shop now", "ecommerce-creative-design": "Add to basket"}.get(self.slug, "Learn more")

    def points(self, n: int = 4) -> List[str]:
        pts = self.lines("key_points", "usp")
        if len(pts) < 3:
            topics = self.f("topics")
            if topics:
                pts += [t for t in (_clean(x) for x in re.split(r"[\n,;]", topics)) if t]
        if not pts:
            prod = self.f("product")
            if prod:
                pts = [p for p in re.split(r"[\n,;]|\band\b", prod)[1:] if len(p.strip()) > 3]
        if len(pts) < 3:
            pts += _as_list(self.strategy.get("do")) + _as_list(self.strategy.get("audience_insights"))
        if len(pts) < 3:
            pts += _as_list(self.content.get("headlines"))[1:]
        if len(pts) < 3:
            pts += ["Designed around your customers", "Consistent on every channel", "Clear message, one action", "Built to last"]
        seen = set()
        pts = [p for p in pts if not (p.lower() in seen or seen.add(p.lower()))]
        return [p[:1].upper() + p[1:] for p in (_clean(x, 110).rstrip(".") for x in pts) if p][:n]

    def hashtags(self) -> List[str]:
        raw = self.f("hashtags")
        tags = re.findall(r"#\w+", raw) if raw else []
        tags += [t if t.startswith("#") else "#" + t for t in _as_list(self.content.get("hashtags")) if t]
        return list(dict.fromkeys(t.replace(" ", "") for t in tags))[:12]

    def captions(self) -> List[str]:
        return _as_list(self.content.get("captions"))


# ---------------------------------------------------------------------------
# visual components
# ---------------------------------------------------------------------------
def theme_colors(b: Brand, theme: str) -> Tuple[str, str, str]:
    """(background, text, soft text) for 'light' | 'dark' | 'brand'."""
    if theme == "dark":
        bg = b.dark
    elif theme == "brand":
        bg = b.primary
    else:
        bg = b.paper
    return bg, b.on(bg), b.soft_on(bg)


def background(c: Canvas, b: Brand, theme: str, *, grain: bool = True) -> Tuple[str, str, str]:
    bg, fg, soft = theme_colors(b, theme)
    c.rect(0, 0, c.w, c.h, fill=bg)
    if theme == "dark":
        c.rect(0, 0, c.w, c.h, fill=c.radial([(0, b.primary, 0.55), (1, b.primary, 0)], cx=0.92, cy=0.08, r=0.75))
        c.rect(0, 0, c.w, c.h, fill=c.radial([(0, b.accent, 0.18), (1, b.accent, 0)], cx=0.05, cy=1.0, r=0.6))
    elif theme == "brand":
        c.rect(0, 0, c.w, c.h, fill=c.linear([(0, col.lighten(b.primary, 0.08)), (1, col.darken(b.primary, 0.18))], angle=120))
    if grain:
        c.grain(0.05 if theme != "light" else 0.035)
    return bg, fg, soft


def art_panel(c: Canvas, b: Brand, x: float, y: float, w: float, h: float, *, rx: float = 0, photo: int = -1, seed: int = 0,
              icon_scale: float = 0.5, dark: bool = False) -> None:
    """The hero visual: the client's photo if they uploaded one, otherwise a branded illustration."""
    clip = c.clip_rect(x, y, w, h, rx)
    if 0 <= photo < len(b.photos):
        with c.group(clip=clip):
            c.rect(x, y, w, h, fill=b.dark)
            c.image(x, y, w, h, b.photos[photo], fit="slice")
            c.rect(x, y, w, h, fill=c.linear([(0.55, b.dark, 0), (1, b.dark, 0.45)], angle=90))
        return
    base1 = b.dark if dark else b.primary
    base2 = col.mix(b.primary, b.accent, 0.45) if not dark else col.mix(b.dark, b.primary, 0.55)
    rnd = random.Random(seed)
    with c.group(clip=clip):
        c.rect(x, y, w, h, fill=c.linear([(0, base1), (1, base2)], angle=rnd.choice([35, 60, 120, 145])))
        m = min(w, h)
        ox, oy = x + w * rnd.uniform(0.62, 0.8), y + h * rnd.uniform(0.25, 0.45)
        for i, rr in enumerate((0.95, 0.72, 0.5)):
            c.circle(ox, oy, m * rr, stroke=b.light, sw=max(1.5, m * 0.004), opacity=0.16 - i * 0.03)
        c.circle(x + w * 0.12, y + h * 0.92, m * 0.42, fill=b.accent, opacity=0.9 if not dark else 0.65)
        c.circle(x + w * 0.12, y + h * 0.92, m * 0.24, fill=col.mix(b.accent, b.light, 0.35), opacity=0.55)
        _dots(c, x + w * 0.08, y + h * 0.1, 6, 5, m * 0.045, b.light, 0.35, r=max(1.5, m * 0.006))
        k = m * icon_scale
        ix, iy = x + (w - k) / 2 + w * 0.06, y + (h - k) / 2 - h * 0.02
        sh = c.shadow(dy=m * 0.025, blur=m * 0.05, color=col.darken(base1, 0.6), opacity=0.35)
        with c.group(filter=sh):
            draw_icon(c, b.motif, ix, iy, k, b.light)
        for sx, sy, sr in ((0.85, 0.18, 0.035), (0.22, 0.3, 0.022), (0.7, 0.78, 0.028)):
            _sparkle(c, x + w * sx, y + h * sy, m * sr, b.light, 0.85)
        c.grain(0.07, x, y, w, h)


def _dots(c: Canvas, x: float, y: float, cols: int, rows: int, gap: float, color: str, opacity: float, r: float = 3) -> None:
    parts = "".join(f'<circle cx="{_n(x + i * gap)}" cy="{_n(y + j * gap)}" r="{_n(r)}"/>' for i in range(cols) for j in range(rows))
    c.raw(f'<g fill="{color}" opacity="{_n(opacity)}">{parts}</g>')


def dots(c: Canvas, x: float, y: float, cols: int, rows: int, gap: float, color: str, opacity: float = 0.3, r: float = 3) -> None:
    _dots(c, x, y, cols, rows, gap, color, opacity, r)


def _sparkle(c: Canvas, x: float, y: float, r: float, color: str, opacity: float) -> None:
    c.path(f"M{_n(x)} {_n(y - r)}C{_n(x + r * 0.12)} {_n(y - r * 0.12)} {_n(x + r * 0.12)} {_n(y - r * 0.12)} {_n(x + r)} {_n(y)}"
           f"C{_n(x + r * 0.12)} {_n(y + r * 0.12)} {_n(x + r * 0.12)} {_n(y + r * 0.12)} {_n(x)} {_n(y + r)}"
           f"C{_n(x - r * 0.12)} {_n(y + r * 0.12)} {_n(x - r * 0.12)} {_n(y + r * 0.12)} {_n(x - r)} {_n(y)}"
           f"C{_n(x - r * 0.12)} {_n(y - r * 0.12)} {_n(x - r * 0.12)} {_n(y - r * 0.12)} {_n(x)} {_n(y - r)}Z", fill=color, opacity=opacity)


def sparkle(c: Canvas, x: float, y: float, r: float, color: str, opacity: float = 1.0) -> None:
    _sparkle(c, x, y, r, color, opacity)


def label(c: Canvas, b: Brand, x: float, y: float, text: str, size: float, color: str, *, anchor: str = "start", rule: bool = True,
          tracking: float = 0.22) -> float:
    """Small tracked caps with a short leading rule. y is the baseline."""
    text = text.upper()
    if rule and anchor == "start":
        rl = size * 2.2
        c.line(x, y - b.label.cap(size) / 2, x + rl, y - b.label.cap(size) / 2, stroke=color, sw=max(1.5, size * 0.12))
        return rl + size * 0.8 + c.text(x + rl + size * 0.8, y, text, b.label, size, fill=color, tracking=tracking)
    return c.text(x, y, text, b.label, size, fill=color, anchor=anchor, tracking=tracking)


def pill(c: Canvas, b: Brand, x: float, y: float, text: str, size: float, bg: str, fg: str, *, anchor: str = "start", arrow: bool = True,
         outline: bool = False) -> Tuple[float, float]:
    """Call-to-action button; (x, y) is the top-left (or top-right / top-centre). Returns (w, h)."""
    fc = b.body_bold
    tw = fc.width(text, size, 0.01)
    padx, h = size * 1.15, size * 2.55
    aw = size * 1.35 if arrow else 0
    w = tw + padx * 2 + aw
    x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
    r = min(h / 2, b.radius * (h / 60) if b.radius < 30 else h / 2)
    r = h / 2 if b.style in ("Modern", "Playful", "Minimal") else max(r, h * 0.12)
    if outline:
        c.rect(x0, y, w, h, rx=r, stroke=bg, sw=max(2, size * 0.09))
    else:
        c.rect(x0, y, w, h, rx=r, fill=bg)
    c.text(x0 + padx, y + h / 2 + fc.cap(size) / 2, text, fc, size, fill=fg if not outline else bg, tracking=0.01)
    if arrow:
        ax, ay = x0 + padx + tw + size * 0.55, y + h / 2
        col_ = fg if not outline else bg
        c.path(f"M{_n(ax)} {_n(ay)}H{_n(ax + size * 0.8)}M{_n(ax + size * 0.45)} {_n(ay - size * 0.36)}L{_n(ax + size * 0.82)} {_n(ay)}L{_n(ax + size * 0.45)} {_n(ay + size * 0.36)}",
               stroke=col_, sw=max(2, size * 0.11))
    return w, h


def brand_badge(c: Canvas, b: Brand, x: float, y: float, h: float, bg: str, *, anchor: str = "start", name: bool = True) -> float:
    """Small logo for corners: the client's own logo if uploaded, otherwise mark + name."""
    if b.logo_href:
        w = h * 3.2
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        c.image(x0, y, w, h, b.logo_href, fit="meet")
        return w
    sc = Scheme.full(b, bg)
    if not name:
        icon_mark(c, b, x - h if anchor == "end" else x - h / 2 if anchor == "middle" else x, y, h, sc)
        return h
    probe = Canvas(10, 10)
    bx = lockup(probe, b, 0, 0, h, sc, tagline="", max_w=h * 9)
    w = bx[2]
    x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
    lockup(c, b, x0, y, h, sc, tagline="", max_w=h * 9)
    return w


def bullets(c: Canvas, b: Brand, x: float, y: float, w: float, items: Sequence[str], size: float, color: str, accent: str, *,
            gap: float = 1.1, numbered: bool = False, icon: str = "check", max_lines: int = 2, mark_fg: Optional[str] = None) -> float:
    """Aligned list; returns the height used."""
    yy = y
    badge = size * 1.7
    for i, item in enumerate(items):
        if numbered:
            c.circle(x + badge / 2, yy + badge / 2, badge / 2, fill=accent)
            c.text(x + badge / 2, yy + badge / 2 + b.body_bold.cap(size * 0.8) / 2, f"{i + 1}", b.body_bold, size * 0.8,
                   fill=mark_fg or col.readable_on(accent, "#FFFFFF", b.dark), anchor="middle")
        else:
            draw_icon(c, icon, x + badge * 0.1, yy + badge * 0.1, badge * 0.8, accent)
        hgt = c.paragraph(x + badge + size * 0.8, yy + (badge - b.body.cap(size)) / 2, w - badge - size * 0.8, item, b.body, size, fill=color,
                          line_height=1.32, max_lines=max_lines)
        yy += max(badge, hgt + (badge - b.body.cap(size)) / 2) + size * gap
    return yy - y


def corner_marks(c: Canvas, x: float, y: float, w: float, h: float, color: str, length: float, sw: float = 2) -> None:
    for (px, py, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        c.path(f"M{_n(px)} {_n(py + dy * length)}V{_n(py)}H{_n(px + dx * length)}", stroke=color, sw=sw, cap="square", join="miter")


def page_number(c: Canvas, b: Brand, x: float, y: float, i: int, n: int, size: float, color: str, *, anchor: str = "end") -> None:
    c.text(x, y, f"{i:02d} / {n:02d}", b.label, size, fill=color, anchor=anchor, tracking=0.12)


def bar_chart(c: Canvas, b: Brand, x: float, y: float, w: float, h: float, values: Sequence[float], labels: Sequence[str], *,
              color: str, text: str, grid: str, highlight: Optional[int] = None, accent: Optional[str] = None, unit: str = "") -> None:
    n = max(1, len(values))
    vmax = max(values) if values else 1
    vmax = vmax if vmax > 0 else 1
    gap = w / n * 0.32
    bw = (w - gap * (n - 1)) / n
    lab = max(12, min(bw * 0.16, h * 0.06))
    for g in range(1, 4):
        gy = y + h - (h - lab * 3) * g / 3
        c.line(x, gy, x + w, gy, stroke=grid, sw=1.2, dash="4 6")
    base = y + h - lab * 2.2
    c.line(x, base, x + w, base, stroke=grid, sw=2)
    for i, (v, l) in enumerate(zip(values, labels)):
        bh = (base - y - lab * 2.4) * (v / vmax)
        bx = x + i * (bw + gap)
        fill = (accent or color) if highlight == i else color
        r = min(bw * 0.18, 12)
        c.path(f"M{_n(bx)} {_n(base)}V{_n(base - bh + r)}Q{_n(bx)} {_n(base - bh)} {_n(bx + r)} {_n(base - bh)}H{_n(bx + bw - r)}"
               f"Q{_n(bx + bw)} {_n(base - bh)} {_n(bx + bw)} {_n(base - bh + r)}V{_n(base)}Z", fill=fill)
        vtxt = (f"{v:g}{unit}" if isinstance(v, (int, float)) else str(v))
        c.text(bx + bw / 2, base - bh - lab * 0.6, vtxt, b.body_bold, lab * 1.1, fill=text, anchor="middle")
        c.paragraph(bx - gap / 2, base + lab * 0.7, bw + gap, l, b.body, lab, fill=col.mix(text, grid, 0.2), align="center", max_lines=2, line_height=1.2)


def ring_stat(c: Canvas, b: Brand, cx: float, cy: float, r: float, pct: float, *, track: str, color: str, text: str, label_text: str = "") -> None:
    sw = r * 0.18
    c.circle(cx, cy, r, stroke=track, sw=sw)
    a = max(0.001, min(0.999, pct / 100)) * 2 * math.pi
    ex, ey = cx + r * math.sin(a), cy - r * math.cos(a)
    large = 1 if a > math.pi else 0
    c.path(f"M{_n(cx)} {_n(cy - r)}A{_n(r)} {_n(r)} 0 {large} 1 {_n(ex)} {_n(ey)}", stroke=color, sw=sw)
    c.text(cx, cy + b.heading.cap(r * 0.5) / 2, f"{pct:g}%", b.heading, r * 0.5, fill=text, anchor="middle")
    if label_text:
        c.paragraph(cx - r * 1.4, cy + r + sw + r * 0.3, r * 2.8, label_text, b.body, r * 0.2, fill=text, align="center", max_lines=3)


def phone_frame(c: Canvas, x: float, y: float, w: float, h: float, screen_href: Optional[str], *, body: str = "#0E0F13") -> None:
    r = w * 0.13
    sh = c.shadow(dy=w * 0.05, blur=w * 0.12, opacity=0.28)
    c.rect(x, y, w, h, rx=r, fill=body, filter=sh)
    inset = w * 0.035
    clip = c.clip_rect(x + inset, y + inset, w - 2 * inset, h - 2 * inset, r - inset)
    if screen_href:
        c.image(x + inset, y + inset, w - 2 * inset, h - 2 * inset, screen_href, clip=clip)
    c.rect(x + w * 0.36, y + inset + w * 0.025, w * 0.28, w * 0.06, rx=w * 0.03, fill=body)


def initials_avatar(c: Canvas, b: Brand, cx: float, cy: float, r: float, text: str, bg: str) -> None:
    c.circle(cx, cy, r, fill=bg)
    t = "".join(w[0] for w in text.split()[:2]).upper() or "?"
    c.text(cx, cy + b.heading.cap(r * 0.7) / 2, t, b.heading, r * 0.7, fill=col.readable_on(bg, "#FFFFFF", b.dark), anchor="middle")


def data_uri(png_bytes: bytes) -> str:
    import base64

    return "data:image/png;base64," + base64.b64encode(png_bytes).decode()


def nice_size(w: int, h: int) -> str:
    return f"{w}x{h}"
