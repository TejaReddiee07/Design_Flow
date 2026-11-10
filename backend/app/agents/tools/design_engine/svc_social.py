"""Social media services: feed posts, carousels, Reels covers, YouTube thumbnails and ad sets."""
from __future__ import annotations

import base64
import re
from typing import Callable, List, Optional, Sequence, Tuple

from app.agents.tools.design_engine import color as col
from app.agents.tools.design_engine.brand import Brand
from app.agents.tools.design_engine.canvas import Canvas, _n
from app.agents.tools.design_engine.common import (Art, Job, Result, art_panel, background, brand_badge, bullets, dots, label, pill, sparkle,
                                                   theme_colors)
from app.agents.tools.design_engine.fonts import face
from app.agents.tools.design_engine.icons import draw_icon, rrect
from app.agents.tools.design_engine.marks import Scheme, draw_logo, lockup


def svg_href(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()


def _number_in(*texts: str) -> str:
    for t in texts:
        m = re.search(r"(£|\$|€|₹)?\s?\d+(?:[.,]\d+)?\s?(%|x\b|k\b|m\b|\+)?(?:\s?off)?", t or "", re.I)
        if m and (m.group(1) or m.group(2)):
            return m.group(0).strip().upper().replace(" OFF", " OFF")
    return ""


def _themes(job: Job, n: int) -> List[str]:
    b = job.b
    base = ["light", "brand", "dark"] if b.theme == "light" else ["dark", "brand", "light"]
    if b.tweaks.theme:
        base = [b.tweaks.theme, "brand", b.tweaks.theme]
    s = job.variant_shift = (job.version - 1) % 3
    order = base[s:] + base[:s]
    return [order[i % 3] for i in range(n)]


def _footer(c: Canvas, job: Job, w: float, h: float, u: float, bg: str, soft: str, *, show_cta: bool = True, cta: Optional[str] = None) -> None:
    b = job.b
    m = 84 * u
    by = h - m - 56 * u
    if show_cta:
        txt = cta or job.cta()
        pbg = b.accent if col.contrast(b.accent, bg) > 2.0 else (b.primary if col.contrast(b.primary, bg) > 2 else b.on(bg))
        pill(c, b, m, by - 4 * u, txt, 28 * u, pbg, col.readable_on(pbg, "#FFFFFF", b.dark, "#141414"))
    tail = b.website or b.handle
    if tail:
        c.text(w - m, by + 40 * u, tail, b.label, 24 * u, fill=soft, anchor="end", tracking=0.08)


def _header(c: Canvas, job: Job, w: float, u: float, bg: str, soft: str, right: str = "") -> None:
    b = job.b
    m = 84 * u
    brand_badge(c, b, m, m - 10 * u, 52 * u, bg)
    if right:
        c.text(w - m, m + 28 * u, right, b.label, 22 * u, fill=soft, anchor="end", tracking=0.18, upper=True)


# ---------------------------------------------------------------------------
# post layouts (all adapt to 1080x1350, 1080x1080 and 1080x1920)
# ---------------------------------------------------------------------------
def lay_hero(c: Canvas, job: Job, i: int, theme: str) -> None:
    b, w, h = job.b, c.w, c.h
    u = w / 1080
    bg, fg, soft = background(c, b, theme)
    m = 84 * u
    _header(c, job, w, u, bg, soft, right=b.descriptor if len(b.descriptor) < 26 else "")
    tall = h / w
    top = 190 * u if tall < 1.5 else 330 * u
    ah = h * (0.40 if tall >= 1.2 else 0.36)
    art_panel(c, b, m, top, w - 2 * m, ah, rx=max(0, b.radius) * 1.6 * u, photo=i, seed=job.request_id * 7 + i, dark=(theme == "brand"))
    y = top + ah + 70 * u
    lab = "New" if i == 0 else b.descriptor
    label(c, b, m, y, lab, 22 * u, b.accent if col.contrast(b.accent, bg) > 2.6 else soft)
    head_h = h - y - (290 * u if tall < 1.5 else 520 * u)
    size, used = c.fit_text(m, y + 36 * u, w - 2 * m, head_h, b.cased(job.headline(i)) if b.case == "upper" else job.headline(i), b.heading,
                            max_size=104 * u * b.tweaks.headline_scale, min_size=40 * u, fill=fg, max_lines=3, line_height=1.04)
    if not b.tweaks.minimal:
        own_body = job.copy_parts()[1] if i == 0 else ""
        c.paragraph(m, y + 36 * u + used + 30 * u, w - 2 * m, own_body or job.sub(i), b.body, 32 * u, fill=soft, max_lines=2)
    _footer(c, job, w, h, u, bg, soft)


def lay_quote(c: Canvas, job: Job, i: int, theme: str) -> None:
    b, w, h = job.b, c.w, c.h
    u = w / 1080
    bg, fg, soft = background(c, b, theme)
    m = 84 * u
    c.circle(w + 60 * u, h * 0.78, 360 * u, stroke=fg, sw=3 * u, opacity=0.14)
    c.circle(w + 60 * u, h * 0.78, 250 * u, stroke=fg, sw=3 * u, opacity=0.1)
    _header(c, job, w, u, bg, soft)
    qy = h * (0.2 if h / w < 1.5 else 0.26)
    draw_icon(c, "quote", m, qy, 110 * u, b.accent if col.contrast(b.accent, bg) > 1.8 else fg)
    text = job.business_line() if i % 2 == 0 and job.business_line() else job.sub(i)
    fc = b.display if b.style in ("Luxury", "Vintage", "Playful") and b.display.family != "Pacifico" else b.heading
    size, used = c.fit_text(m, qy + 170 * u, w - 2 * m, h * 0.42, text, fc, max_size=84 * u * b.tweaks.headline_scale, min_size=36 * u, fill=fg,
                            max_lines=6, line_height=1.14)
    yy = qy + 170 * u + used + 56 * u
    c.line(m, yy, m + 70 * u, yy, stroke=b.accent if col.contrast(b.accent, bg) > 1.8 else fg, sw=5 * u)
    c.text(m + 96 * u, yy + 10 * u, b.name, b.label, 26 * u, fill=soft, tracking=0.2, upper=True)
    _footer(c, job, w, h, u, bg, soft, show_cta=False)


def lay_list(c: Canvas, job: Job, i: int, theme: str) -> None:
    b, w, h = job.b, c.w, c.h
    u = w / 1080
    bg, fg, soft = background(c, b, theme)
    m = 84 * u
    _header(c, job, w, u, bg, soft, right=f"{len(job.points())} things to know")
    y = 210 * u if h / w < 1.5 else 360 * u
    title = job.headline(i)
    size, used = c.fit_text(m, y, w - 2 * m, 230 * u, title, b.heading, max_size=86 * u * b.tweaks.headline_scale, min_size=40 * u, fill=fg,
                            max_lines=3, line_height=1.05)
    y += used + 60 * u
    acc = b.accent if col.contrast(b.accent, bg) > 1.6 else b.primary
    pts = job.points(4 if h / w >= 1.2 else 3)
    room = h - y - 240 * u
    sz = max(30 * u, min(44 * u, room / (len(pts) * 3.0)))
    bullets(c, b, m, y, w - 2 * m, pts, sz, fg, acc, numbered=True, gap=1.5, max_lines=2, mark_fg=col.readable_on(acc, "#FFFFFF", b.dark))
    _footer(c, job, w, h, u, bg, soft)


def lay_offer(c: Canvas, job: Job, i: int, theme: str) -> None:
    b, w, h = job.b, c.w, c.h
    u = w / 1080
    bg, fg, soft = background(c, b, "light" if theme == "brand" else theme)
    m = 84 * u
    ph = h * 0.56
    art_panel(c, b, 0, 0, w, ph, photo=i, seed=job.request_id * 11 + i, icon_scale=0.42)
    big = _number_in(job.f("offer", "copy_text", "event_or_offer", "usp"))
    brand_badge(c, b, m, m - 10 * u, 52 * u, b.primary)
    if big:
        sticker_r = 150 * u
        cx, cy = w - m - sticker_r, ph - 40 * u
        c.circle(cx, cy, sticker_r, fill=b.accent)
        fs = c.fit_text(cx - sticker_r * 0.8, cy - sticker_r * 0.45, sticker_r * 1.6, sticker_r * 0.9, big, b.heading, max_size=110 * u, min_size=30 * u,
                        fill=col.readable_on(b.accent, "#FFFFFF", b.dark), align="center", max_lines=2, valign="middle")
    y = ph + 80 * u
    used = c.fit_text(m, y, w - 2 * m - (300 * u if big else 0), h - y - 300 * u, job.headline(i), b.heading, max_size=92 * u * b.tweaks.headline_scale,
                      min_size=38 * u, fill=fg, max_lines=3, line_height=1.05)[1]
    if not b.tweaks.minimal:
        c.paragraph(m, y + used + 26 * u, w - 2 * m, job.body(), b.body, 30 * u, fill=soft, max_lines=2)
    _footer(c, job, w, h, u, bg, soft)


def lay_stat(c: Canvas, job: Job, i: int, theme: str) -> None:
    b, w, h = job.b, c.w, c.h
    u = w / 1080
    num = _number_in(job.f("copy_text", "data", "offer", "usp", "key_points"), " ".join(job.points()))
    if not num:
        return lay_split(c, job, i, theme)
    bg, fg, soft = background(c, b, theme)
    m = 84 * u
    _header(c, job, w, u, bg, soft)
    acc = b.accent if col.contrast(b.accent, bg) > 2.2 else b.primary if col.contrast(b.primary, bg) > 2.2 else fg
    y = h * 0.24
    size, used = c.fit_text(m, y, w - 2 * m, h * 0.3, num, b.heading, max_size=360 * u, min_size=120 * u, fill=acc, max_lines=1)
    c.fit_text(m, y + used + 50 * u, w - 2 * m, h * 0.22, job.headline(i), b.heading, max_size=64 * u, min_size=32 * u, fill=fg, max_lines=3)
    dots(c, w - m - 5 * 30 * u, h * 0.12, 6, 4, 30 * u, acc, 0.35, r=4 * u)
    _footer(c, job, w, h, u, bg, soft)


def lay_split(c: Canvas, job: Job, i: int, theme: str) -> None:
    b, w, h = job.b, c.w, c.h
    u = w / 1080
    bg, fg, soft = background(c, b, theme)
    m = 84 * u
    pw = w * 0.44
    art_panel(c, b, w - pw, 0, pw, h, photo=i, seed=job.request_id * 13 + i, icon_scale=0.62)
    _header(c, job, w - pw, u, bg, soft)
    y = h * 0.3
    label(c, b, m, y, b.descriptor, 22 * u, b.accent if col.contrast(b.accent, bg) > 2.6 else soft)
    size, used = c.fit_text(m, y + 40 * u, w - pw - 2 * m + 20 * u, h * 0.36, job.headline(i), b.heading, max_size=88 * u * b.tweaks.headline_scale,
                            min_size=36 * u, fill=fg, max_lines=5, line_height=1.05)
    if not b.tweaks.minimal:
        c.paragraph(m, y + 40 * u + used + 30 * u, w - pw - 2 * m, job.sub(i), b.body, 28 * u, fill=soft, max_lines=3)
    _footer(c, job, w - pw + m, h, u, bg, soft)


def lay_cta(c: Canvas, job: Job, i: int, theme: str) -> None:
    b, w, h = job.b, c.w, c.h
    u = w / 1080
    bg, fg, soft = background(c, b, "dark" if theme != "brand" else "brand")
    m = 84 * u
    for k, rr in enumerate((520, 400, 280)):
        c.circle(w / 2, h * 0.36, rr * u, stroke=fg, sw=2.5 * u, opacity=0.08 + k * 0.03)
    sc = Scheme.full(b, bg)
    if b.logo_href:
        c.image(w / 2 - 260 * u, h * 0.24, 520 * u, 220 * u, b.logo_href, fit="meet")
    else:
        draw_logo(c, b, "lockup", m, h * 0.22, w - 2 * m, h * 0.24, sc)
    c.fit_text(m, h * 0.52, w - 2 * m, h * 0.16, job.headline(i), b.heading, max_size=78 * u, min_size=34 * u, fill=fg, align="center", max_lines=2)
    info = " · ".join(x for x in (b.location, b.website or b.handle) if x)
    if info:
        c.text(w / 2, h * 0.72, info, b.label, 26 * u, fill=soft, anchor="middle", tracking=0.16, upper=True)
    pbg = b.accent if col.contrast(b.accent, bg) > 2 else b.light
    pill(c, b, w / 2, h * 0.78, job.cta(), 30 * u, pbg, col.readable_on(pbg, "#FFFFFF", b.dark), anchor="middle")


LAYOUTS: dict = {"hero": lay_hero, "quote": lay_quote, "list": lay_list, "offer": lay_offer, "stat": lay_stat, "split": lay_split, "cta": lay_cta}


def _sequence(job: Job, n: int) -> List[str]:
    pt = job.f("post_type").lower()
    first = {"quote": "quote", "announcement": "hero", "product": "offer", "single image": "hero"}.get(pt, "hero")
    pool = ["hero", "list", "quote", "offer", "split", "stat", "cta"]
    seq = [first] + [p for p in pool if p != first]
    if job.f("offer", "event_or_offer") or pt == "product":
        seq.remove("offer")
        seq.insert(1, "offer")
    shift = (job.version - 1) % len(seq)
    seq = seq[shift:] + seq[:shift] if job.version > 1 else seq
    if n >= 4 and "cta" in seq[: n - 1]:
        seq.remove("cta")
        seq.insert(n - 1, "cta")
    return seq[:n]


def _post(job: Job, layout: str, i: int, theme: str, w: int, h: int) -> str:
    c = Canvas(w, h)
    LAYOUTS[layout](c, job, i, theme)
    return c.to_svg()


def _board(job: Job, title: str, items: Sequence[Tuple[str, int, int]], *, sub: str = "", cols: int = 0, theme: str = "light") -> str:
    """Presentation board: the actual deliverables laid out on a 1920x1080 canvas."""
    b = job.b
    c = Canvas(1920, 1080)
    bg, fg, soft = background(c, b, theme)
    label(c, b, 96, 112, f"{job.service_name or 'Design'} · version {job.version}", 18, b.primary if col.contrast(b.primary, bg) > 3 else soft)
    c.fit_text(96, 134, 1300, 70, title, b.heading, max_size=52, fill=fg, max_lines=1)
    if sub:
        c.paragraph(96, 222, 1500, sub, b.body, 22, fill=soft, max_lines=1)
    n = len(items)
    top, bottom = 290, 1000
    area_w, area_h = 1728, bottom - top
    if not cols:
        cols = n if n <= 4 else (3 if n <= 6 else 4)
    rows = (n + cols - 1) // cols
    gap = 36
    cell_w = (area_w - gap * (cols - 1)) / cols
    cell_h = (area_h - gap * (rows - 1)) / rows
    for k, (svg, w, h) in enumerate(items):
        r, cc = divmod(k, cols)
        scale = min(cell_w / w, cell_h / h)
        dw, dh = w * scale, h * scale
        x = 96 + cc * (cell_w + gap) + (cell_w - dw) / 2
        y = top + r * (cell_h + gap) + (cell_h - dh) / 2
        c.soft_shadow(x, y, dw, dh, rx=10, dy=14, blur=26, color=b.dark, opacity=0.18)
        clip = c.clip_rect(x, y, dw, dh, 10)
        c.image(x, y, dw, dh, svg_href(svg), clip=clip)
    return c.to_svg()


# ---------------------------------------------------------------------------
# services
# ---------------------------------------------------------------------------
def render_posts(job: Job) -> Result:
    b = job.b
    res = Result()
    insta = job.slug == "instagram-post-design"
    pt = job.f("post_type").lower()
    if "carousel" in pt:
        return render_carousel(job, square=False, social_name="Instagram carousel")
    n = job.number("quantity", 3 if insta else 4, 1, 6)
    seq = _sequence(job, n)
    themes = _themes(job, n)
    story = "story" in pt
    board_items = []
    for i, layout in enumerate(seq):
        if story:
            svg = _post(job, layout, i, themes[i], 1080, 1920)
            res.arts.append(Art(f"Story {i + 1} - 1080x1920", svg, 1080, 1920, f"Story {i + 1} (1080x1920)", role="primary" if i == 0 else "variant", group="Stories"))
            board_items.append((svg, 1080, 1920))
            continue
        svg = _post(job, layout, i, themes[i], 1080, 1350)
        res.arts.append(Art(f"Post {i + 1} - portrait 1080x1350", svg, 1080, 1350, f"Post {i + 1} - portrait (1080x1350)", role="primary" if i == 0 else "variant", group="Posts/Portrait 1080x1350"))
        board_items.append((svg, 1080, 1350))
        sq = _post(job, layout, i, themes[i], 1080, 1080)
        res.arts.append(Art(f"Post {i + 1} - square 1080x1080", sq, 1080, 1080, f"Post {i + 1} - square (1080x1080)", group="Posts/Square 1080x1080"))
    platforms = [p.lower() for p in job.multi("platforms")]
    if not story and (insta or any(p in ("instagram", "facebook", "tiktok") for p in platforms) or not platforms):
        st = _post(job, seq[0], 0, themes[0], 1080, 1920)
        res.arts.append(Art("Story - 1080x1920", st, 1080, 1920, "Story version (1080x1920)", group="Stories"))
    if any(p in ("linkedin", "x") for p in platforms):
        land = _post(job, "split", 0, themes[0], 1200, 628)
        res.arts.append(Art("Landscape - 1200x628", land, 1200, 628, "LinkedIn / X landscape (1200x628)", group="Posts/Landscape 1200x628"))
    title = f"{n} {'stories' if story else 'posts'} for {b.name}"
    res.arts.insert(0, Art(f"{b.name} - social set overview", _board(job, title, board_items, sub=f"{b.style} style · {', '.join(job.multi('platforms')) or 'Instagram'} · copy from your brief"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.texts.append(("Captions and hashtags.md", _captions_md(job, n)))
    res.summary = f"{n} on-brand {'stories' if story else 'posts'} for {b.name} in portrait and square, a story version, captions and hashtags."
    return res


def _captions_md(job: Job, n: int) -> str:
    caps = job.captions() or [job.sub(i) for i in range(n)]
    tags = " ".join(job.hashtags()) or f"#{re.sub(r'[^A-Za-z0-9]', '', job.b.name)}"
    lines = [f"# Captions - {job.b.name}", ""]
    for i in range(n):
        lines += [f"## Post {i + 1}", "", f"**{job.headline(i)}**", "", caps[i % len(caps)], "", tags, ""]
    return "\n".join(lines)


def render_carousel(job: Job, square: bool = False, social_name: str = "LinkedIn carousel") -> Result:
    b = job.b
    res = Result()
    w, h = (1080, 1080) if square else (1080, 1350)
    slide_titles = [str(s.get("title")) for s in (job.content.get("slides") or []) if isinstance(s, dict) and s.get("title")]
    pts = job.lines("key_points") or slide_titles or job.points(6)
    want = job.number("slides", min(10, len(pts) + 3), 4, 12)
    pts = pts[: max(1, want - 3)]
    topic = job.f("topic") or job.headline(0)
    total = len(pts) + 3
    slides: List[str] = []
    for k in range(total):
        c = Canvas(w, h)
        _carousel_slide(c, job, k, total, topic, pts)
        slides.append(c.to_svg())
    pdf_name = f"{b.name} - {social_name.lower()}"
    for k, svg in enumerate(slides):
        res.arts.append(Art(f"Slide {k + 1:02d}", svg, w, h, f"Slide {k + 1} of {total}", role="primary" if k == 0 else "page", group="Slides", pdf=pdf_name))
    res.pdfs[pdf_name] = 150
    res.arts.insert(0, Art(f"{b.name} - carousel overview", _board(job, f"{social_name}: {topic}", [(s, w, h) for s in slides[:8]], cols=4,
                                                                sub=f"{total} slides · hook, {len(pts)} value slides, summary and call to action"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    hook = topic
    res.texts.append(("Post copy.md", f"# {social_name} - {b.name}\n\n**Hook:** {hook}\n\n" + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(pts))
                      + f"\n\n**Call to action:** {job.cta()}\n\n{' '.join(job.hashtags())}\n"))
    res.summary = f"{total}-slide {social_name.lower()} on \"{topic}\" (PDF for upload plus PNG slides) with hook and CTA copy."
    return res


def _carousel_slide(c: Canvas, job: Job, k: int, total: int, topic: str, pts: List[str]) -> None:
    b, w, h = job.b, c.w, c.h
    u = w / 1080
    m = 84 * u
    first, last, summary = k == 0, k == total - 1, k == total - 2
    theme = "dark" if first or last else ("light" if b.theme == "light" else "dark")
    if b.tweaks.theme:
        theme = b.tweaks.theme
    bg, fg, soft = background(c, b, theme)
    acc = b.accent if col.contrast(b.accent, bg) > 2.2 else b.primary if col.contrast(b.primary, bg) > 2.2 else fg
    brand_badge(c, b, m, m - 10 * u, 48 * u, bg)
    c.text(w - m, m + 24 * u, f"{k + 1:02d}/{total:02d}", b.label, 22 * u, fill=soft, anchor="end", tracking=0.14)
    # progress bar
    by = h - 70 * u
    c.rect(m, by, w - 2 * m, 6 * u, rx=3 * u, fill=soft, opacity=0.25)
    c.rect(m, by, (w - 2 * m) * (k + 1) / total, 6 * u, rx=3 * u, fill=acc)
    if first:
        art_panel(c, b, w * 0.52, h * 0.1, w * 0.48 + 2, h * 0.36, rx=0, seed=job.request_id, icon_scale=0.55)
        label(c, b, m, h * 0.5, job.f("tone") or "Swipe to learn", 22 * u, acc)
        c.fit_text(m, h * 0.5 + 40 * u, w - 2 * m, h * 0.3, topic, b.heading, max_size=100 * u * b.tweaks.headline_scale, min_size=44 * u, fill=fg,
                   max_lines=4, line_height=1.03)
        pill(c, b, m, h - 200 * u, "Swipe", 28 * u, acc, col.readable_on(acc, "#FFFFFF", b.dark))
        return
    if last:
        c.fit_text(m, h * 0.3, w - 2 * m, h * 0.2, f"Found this useful?", b.heading, max_size=84 * u, min_size=40 * u, fill=fg, max_lines=2)
        c.paragraph(m, h * 0.5, w - 2 * m, f"Follow {b.name} for more, and repost to share it with your network.", b.body, 34 * u, fill=soft, max_lines=3)
        pill(c, b, m, h * 0.68, job.cta() if job.cta() not in ("Learn more",) else "Follow for more", 30 * u, acc, col.readable_on(acc, "#FFFFFF", b.dark))
        if b.website or b.handle:
            c.text(m, h - 120 * u, b.website or b.handle, b.label, 24 * u, fill=soft, tracking=0.1)
        return
    if summary:
        c.fit_text(m, h * 0.17, w - 2 * m, 140 * u, "In short", b.heading, max_size=80 * u, min_size=40 * u, fill=fg, max_lines=1)
        room = h * 0.62
        sz = min(34 * u, room / (len(pts) * 2.5))
        bullets(c, b, m, h * 0.17 + 150 * u, w - 2 * m, pts, sz, fg, acc, icon="check", max_lines=2)
        return
    idx = k - 1
    num = f"{idx + 1:02d}"
    detail = ""
    slides = job.content.get("slides") if isinstance(job.content.get("slides"), list) else []
    if idx < len(slides) and isinstance(slides[idx], dict):
        detail = str(slides[idx].get("body") or " ".join(map(str, slides[idx].get("bullets") or [])))[:220]
    c.text(m, h * 0.3, num, b.heading, 230 * u, fill=acc)
    c.line(m, h * 0.3 + 54 * u, m + 120 * u, h * 0.3 + 54 * u, stroke=acc, sw=6 * u)
    used = c.fit_text(m, h * 0.3 + 110 * u, w - 2 * m, h * (0.26 if detail else 0.38), pts[idx], b.heading, max_size=96 * u * b.tweaks.headline_scale,
                      min_size=40 * u, fill=fg, max_lines=4, line_height=1.06)[1]
    if detail:
        c.paragraph(m, h * 0.3 + 110 * u + used + 44 * u, w - 2 * m, detail, b.body, 34 * u, fill=soft, max_lines=5, line_height=1.45)
    draw_icon(c, b.motif, w - m - 170 * u, h - 380 * u, 170 * u, acc, opacity=0.12)
    # swipe arrow
    ax, ay = w - m - 40 * u, h - 150 * u
    c.circle(ax, ay, 40 * u, stroke=fg, sw=3 * u, opacity=0.5)
    c.path(f"M{_n(ax - 14 * u)} {_n(ay)}H{_n(ax + 14 * u)}M{_n(ax + 2 * u)} {_n(ay - 12 * u)}L{_n(ax + 14 * u)} {_n(ay)}L{_n(ax + 2 * u)} {_n(ay + 12 * u)}",
           stroke=fg, sw=3.5 * u)


def render_reels(job: Job) -> Result:
    b = job.b
    res = Result()
    titles = job.lines("titles") or job.headlines()
    n = job.number("quantity", len(titles) or 3, 1, 9)
    titles = (titles * ((n // max(1, len(titles))) + 1))[:n]
    covers = []
    for i, t in enumerate(titles):
        c = Canvas(1080, 1920)
        _reel_cover(c, job, i, t)
        svg = c.to_svg()
        covers.append(svg)
        res.arts.append(Art(f"Cover {i + 1:02d} - 1080x1920", svg, 1080, 1920, f"Reels cover {i + 1}: {t[:40]}", role="primary" if i == 0 else "variant", group="Covers 1080x1920"))
        crop = svg.replace('width="1080" height="1920" viewBox="0 0 1080 1920"', 'width="1080" height="1350" viewBox="0 285 1080 1350"', 1)
        res.arts.append(Art(f"Cover {i + 1:02d} - grid crop 1080x1350", crop, 1080, 1350, f"Grid-safe crop {i + 1}", group="Grid crops 1080x1350"))
    res.arts.insert(0, Art(f"{b.name} - reels covers overview", _board(job, f"{n} Reels covers for {b.name}", [(s, 1080, 1920) for s in covers[:6]],
                                                                    sub="Titles sit inside the 1080x1350 grid-safe zone so your profile grid stays tidy", cols=min(6, n)),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{n} Reels / TikTok covers (1080x1920) with grid-safe crops for {b.name}."
    return res


def _reel_cover(c: Canvas, job: Job, i: int, title: str) -> None:
    b = job.b
    w, h = c.w, c.h
    themes = ["brand", "dark", "light"] if b.theme == "light" else ["dark", "brand", "light"]
    theme = themes[(i + job.version - 1) % 3]
    bg, fg, soft = background(c, b, theme)
    m = 96
    art_panel(c, b, 0, 0, w, 560, photo=i, seed=job.request_id * 17 + i, icon_scale=0.45, dark=(theme == "dark"))
    c.rect(0, 540, w, 40, fill=bg)
    c.path(f"M0 560Q{w / 2} 470 {w} 560V600H0Z", fill=bg)
    acc = b.accent if col.contrast(b.accent, bg) > 2.2 else fg
    c.text(m, 760, f"#{i + 1:02d}", b.heading, 64, fill=acc)
    _, used = c.fit_text(m, 800, w - 2 * m, 600, title, b.heading, max_size=160 * b.tweaks.headline_scale, min_size=60, fill=fg, max_lines=5, line_height=1.02,
                         upper=b.case == "upper")
    pill(c, b, m, min(1380, 800 + used + 80), "Watch now", 30, acc, col.readable_on(acc, "#FFFFFF", b.dark))
    brand_badge(c, b, m, 1500, 64, bg)
    c.text(w - m, 1546, b.handle or b.website or "", b.label, 28, fill=soft, anchor="end", tracking=0.1)


def render_thumbnails(job: Job) -> Result:
    b = job.b
    res = Result()
    text = job.f("thumbnail_text") or " ".join(job.f("video_title").split()[:5]) or job.headline(0)
    variants = []
    for k, kind in enumerate(["impact", "bright", "split"][: 3 if job.version > 1 else 2] if True else []):
        c = Canvas(1280, 720)
        _thumbnail(c, job, kind, text, k)
        variants.append(c.to_svg())
        res.arts.append(Art(f"Thumbnail {'ABC'[k]} - 1280x720", variants[-1], 1280, 720, f"Thumbnail variant {'ABC'[k]} (1280x720)",
                            role="primary" if k == 0 else "variant", group="Thumbnails"))
    # YouTube-style preview board
    c = Canvas(1920, 1080)
    bg, fg, soft = background(c, b, "dark")
    label(c, b, 96, 112, "YouTube thumbnail · A/B test", 18, soft)
    c.fit_text(96, 134, 1500, 70, job.f("video_title") or text, b.heading, max_size=52, fill=fg, max_lines=1)
    for k, svg in enumerate(variants[:2]):
        x = 96 + k * 880
        c.soft_shadow(x, 280, 840, 472, rx=18, dy=16, blur=30, opacity=0.4)
        c.image(x, 280, 840, 472, svg_href(svg), clip=c.clip_rect(x, 280, 840, 472, 18))
        c.rect(x + 840 - 92, 280 + 472 - 46, 76, 32, rx=6, fill="#000000", opacity=0.8)
        c.text(x + 840 - 54, 280 + 472 - 23, "12:47", face("Inter", 600), 18, fill="#FFFFFF", anchor="middle")
        c.circle(x + 26, 800, 26, fill=b.primary)
        c.text(x + 26, 809, (job.f("channel_name") or b.name)[:1].upper(), b.heading, 26, fill=b.on(b.primary), anchor="middle")
        c.paragraph(x + 70, 784, 760, job.f("video_title") or text, face("Inter", 600), 26, fill=fg, max_lines=2, line_height=1.3)
        c.text(x + 70, 868, job.f("channel_name") or b.name, face("Inter", 400), 20, fill=soft)
        c.text(x, 940, f"Variant {'AB'[k]}", b.label, 18, fill=soft, tracking=0.18, upper=True)
    res.arts.insert(0, Art(f"{b.name} - thumbnail preview", c.to_svg(), 1920, 1080, "A/B preview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{len(variants)} high-contrast YouTube thumbnails (1280x720) for \"{job.f('video_title') or text}\" ready for A/B testing."
    return res


def _thumbnail(c: Canvas, job: Job, kind: str, text: str, k: int) -> None:
    b = job.b
    w, h = c.w, c.h
    big = face("Archivo Black", 400) if b.style in ("Bold", "Playful", "Modern") else face("Bebas Neue", 400) if b.style in ("Corporate",) else b.heading
    words = text.upper().split()
    hot = max(range(len(words)), key=lambda i: len(words[i])) if words else 0
    yellow = "#FFD400"
    if kind == "impact":
        c.rect(0, 0, w, h, fill=c.linear([(0, col.darken(b.primary, 0.55)), (1, col.darken(b.primary, 0.2))], angle=30))
        c.rect(0, 0, w, h, fill=c.radial([(0, b.accent, 0.45), (1, b.accent, 0)], cx=0.82, cy=0.4, r=0.6))
        right = 0.42
        if b.photos:
            r = 230
            c.circle(w * 0.77, h * 0.52, r + 14, fill="#FFFFFF")
            c.image(w * 0.77 - r, h * 0.52 - r, 2 * r, 2 * r, b.photos[0], clip=c.clip_circle(w * 0.77, h * 0.52, r))
        else:
            for rr, op in ((300, 0.12), (220, 0.18)):
                c.circle(w * 0.78, h * 0.5, rr, fill="#FFFFFF", opacity=op)
            draw_icon(c, b.motif, w * 0.78 - 150, h * 0.5 - 150, 300, "#FFFFFF")
        _thumb_words(c, big, words, hot, 60, 120, w * (1 - right) - 40, h - 220, "#FFFFFF", yellow, "#111111")
        c.path(f"M{w * 0.55} {h * 0.78}Q{w * 0.6} {h * 0.62} {w * 0.66} {h * 0.6}", stroke=yellow, sw=14)
        c.path(f"M{w * 0.655} {h * 0.56}L{w * 0.69} {h * 0.6}L{w * 0.65} {h * 0.645}Z", fill=yellow)
    elif kind == "bright":
        c.rect(0, 0, w, h, fill=yellow if b.style in ("Bold", "Playful") else b.accent)
        bgc = yellow if b.style in ("Bold", "Playful") else b.accent
        c.polygon([(w * 0.58, 0), (w, 0), (w, h), (w * 0.46, h)], fill=b.dark)
        if b.photos:
            c.image(w * 0.52, 0, w * 0.48, h, b.photos[0], clip=c.clip_path(f"M{w * 0.58} 0H{w}V{h}H{w * 0.46}Z"))
        else:
            draw_icon(c, b.motif, w * 0.66, h * 0.22, 380, b.accent if col.contrast(b.accent, b.dark) > 2 else "#FFFFFF")
        ink = col.readable_on(bgc, "#111111", "#FFFFFF")
        _thumb_words(c, big, words, hot, 56, 110, w * 0.5, h - 200, ink, "#E62117", "#FFFFFF")
        c.rect(56, h - 120, 210, 64, rx=10, fill="#E62117")
        c.text(161, h - 76, "NEW", big, 40, fill="#FFFFFF", anchor="middle")
    else:
        c.rect(0, 0, w, h, fill=b.paper)
        art_panel(c, b, w * 0.5, 0, w * 0.5, h, photo=0, seed=k, icon_scale=0.6)
        _thumb_words(c, big, words, hot, 56, 110, w * 0.44, h - 160, b.ink, b.primary, b.on(b.primary))


def _thumb_words(c: Canvas, fc, words: List[str], hot: int, x: float, y: float, w: float, h: float, ink: str, hot_bg: str, hot_ink: str) -> None:
    text = " ".join(words)
    size, lines = 0.0, []
    from app.agents.tools.design_engine.fonts import fit

    size, lines = fit(text, fc, w, h, max_size=170, min_size=60, line_height=1.0, max_lines=3)
    yy = y + fc.cap(size)
    hot_word = words[hot] if words else ""
    for ln in lines:
        xx = x
        for wd in ln.split():
            ww = fc.width(wd, size)
            if wd == hot_word:
                c.rect(xx - size * 0.08, yy - fc.cap(size) - size * 0.12, ww + size * 0.16, fc.cap(size) + size * 0.24, rx=size * 0.06, fill=hot_bg)
                c.text(xx, yy, wd, fc, size, fill=hot_ink)
            else:
                c.text(xx + size * 0.03, yy + size * 0.04, wd, fc, size, fill="#000000", opacity=0.35)
                c.text(xx, yy, wd, fc, size, fill=ink)
            xx += ww + fc.width(" ", size)
        yy += size * 1.0


# ---------------------------------------------------------------------------
# adaptive promo layout: ads, banners, product ads, digital flyers
# ---------------------------------------------------------------------------
def promo(c: Canvas, job: Job, *, headline: str, sub: str, cta: str, theme: str, idx: int = 0, badge: str = "") -> None:
    b, w, h = job.b, c.w, c.h
    ratio = w / h
    bg, fg, soft = background(c, b, theme)
    acc = b.accent if col.contrast(b.accent, bg) > 2.0 else b.primary if col.contrast(b.primary, bg) > 2 else b.on(bg)
    acc_fg = col.readable_on(acc, "#FFFFFF", b.dark, "#141414")
    if ratio >= 4:  # leaderboards / strips
        u = h / 90
        pad = 18 * u
        art_panel(c, b, w - h * 2.2, 0, h * 2.2, h, photo=idx, seed=idx, icon_scale=0.7)
        logo_w = brand_badge(c, b, pad, h * 0.3, h * 0.4, bg, name=w > 900)
        tx = pad + logo_w + pad * 1.5
        ps = h * 0.2
        probe = Canvas(10, 10)
        pw_, ph_ = pill(probe, b, 0, 0, cta, ps, acc, acc_fg, arrow=w > 600)
        pill(c, b, w - h * 2.2 - pad, h / 2 - ph_ / 2, cta, ps, acc, acc_fg, anchor="end", arrow=w > 600)
        bw = w - tx - h * 2.2 - pad * 2.5 - pw_
        c.fit_text(tx, h * 0.18, bw, h * 0.64, headline, b.heading, max_size=h * 0.34, min_size=8, fill=fg, max_lines=2, valign="middle")
        return
    if ratio <= 0.4:  # skyscraper 160x600
        u = w / 160
        art_panel(c, b, 0, 0, w, h * 0.38, photo=idx, seed=idx, icon_scale=0.6)
        brand_badge(c, b, w / 2, h * 0.42, 18 * u, bg, anchor="middle", name=False)
        c.fit_text(10 * u, h * 0.5, w - 20 * u, h * 0.28, headline, b.heading, max_size=26 * u, min_size=10, fill=fg, align="center", max_lines=5)
        pill(c, b, w / 2, h * 0.85, cta, 10 * u, acc, acc_fg, anchor="middle", arrow=False)
        return
    if ratio > 1.4:  # landscape: link ads, heros, 1200x628, 1920x600
        u = h / 628
        m = 64 * u
        pw = w * (0.42 if ratio < 2.4 else 0.36)
        art_panel(c, b, w - pw, 0, pw, h, photo=idx, seed=idx * 5 + job.request_id, icon_scale=0.55)
        brand_badge(c, b, m, m - 6 * u, 46 * u, bg)
        if badge:
            c.circle(w - pw, h * 0.5, 90 * u, fill=acc)
            c.fit_text(w - pw - 70 * u, h * 0.5 - 40 * u, 140 * u, 80 * u, badge, b.heading, max_size=56 * u, min_size=14, fill=acc_fg, align="center",
                       max_lines=2, valign="middle")
        tw = w - pw - 2 * m - (90 * u if badge else 0)
        top = h * 0.26
        size, used = c.fit_text(m, top, tw, h * 0.42, headline, b.heading, max_size=86 * u * b.tweaks.headline_scale, min_size=14, fill=fg, max_lines=3,
                                line_height=1.04)
        if sub and not b.tweaks.minimal and h >= 250:
            c.paragraph(m, top + used + 22 * u, tw, sub, b.body, 26 * u, fill=soft, max_lines=2)
        pill(c, b, m, h - m - 66 * u, cta, 26 * u, acc, acc_fg)
        return
    # square / portrait / story
    u = w / 1080
    m = 84 * u
    tall = h / w
    ah = h * (0.5 if tall > 1.5 else 0.48 if tall > 1.1 else 0.46)
    art_panel(c, b, 0, 0, w, ah, photo=idx, seed=idx * 3 + job.request_id, icon_scale=0.42)
    c.path(f"M0 {_n(ah - 2)}Q{_n(w * 0.5)} {_n(ah - 90 * u)} {_n(w)} {_n(ah - 2)}V{_n(ah + 4)}H0Z", fill=bg)
    brand_badge(c, b, m, m - 10 * u, 52 * u, b.primary)
    if badge:
        r = 128 * u
        c.circle(w - m - r, ah - 20 * u, r, fill=acc)
        c.fit_text(w - m - 1.8 * r, ah - 20 * u - r * 0.45, 1.6 * r, r * 0.9, badge, b.heading, max_size=96 * u, min_size=20, fill=acc_fg, align="center",
                   max_lines=2, valign="middle")
    y = ah + (60 if tall < 1.1 else 80) * u
    avail = h - y - 220 * u
    size, used = c.fit_text(m, y, w - 2 * m, avail * 0.62, headline, b.heading, max_size=104 * u * b.tweaks.headline_scale, min_size=36 * u, fill=fg,
                            max_lines=3, line_height=1.04)
    if sub and not b.tweaks.minimal:
        c.paragraph(m, y + used + 24 * u, w - 2 * m, sub, b.body, 32 * u, fill=soft, max_lines=2 if tall < 1.5 else 3)
    pill(c, b, m, h - m - 72 * u, cta, 30 * u, acc, acc_fg)
    if b.website and tall >= 1.0:
        c.text(w - m, h - m - 28 * u, b.website, b.label, 24 * u, fill=soft, anchor="end", tracking=0.08)


PLATFORM_SIZES = {
    "meta": [(1080, 1080), (1080, 1350), (1080, 1920)], "google": [(1200, 628), (300, 250), (728, 90), (160, 600)], "tiktok": [(1080, 1920)],
    "linkedin": [(1200, 627), (1080, 1080)], "x": [(1600, 900)],
}
SIZE_WORDS = {"1080x1080": (1080, 1080), "1080x1350": (1080, 1350), "1080x1920": (1080, 1920), "1920x1080": (1920, 1080)}


def ad_sizes(job: Job) -> List[Tuple[int, int]]:
    sizes: List[Tuple[int, int]] = []
    for s in job.multi("sizes"):
        k = s.split(" ")[0]
        if k in SIZE_WORDS:
            sizes.append(SIZE_WORDS[k])
    for p in job.multi("platform"):
        key = p.lower().split()[0].replace("(fb/ig)", "")
        sizes += PLATFORM_SIZES.get(key, [])
    if not sizes:
        sizes = PLATFORM_SIZES["meta"] + [(1200, 628)]
    out: List[Tuple[int, int]] = []
    for s in sizes:
        if s not in out:
            out.append(s)
    return out[:6]


def render_ads(job: Job) -> Result:
    b = job.b
    res = Result()
    sizes = ad_sizes(job)
    hooks = job.headlines()[:3]
    while len(hooks) < 3:
        hooks.append(job.sub(len(hooks)))
    offer = job.f("offer")
    badge = _number_in(offer, job.f("copy_text"))
    board = []
    themes = _themes(job, 3)
    for hi, hook in enumerate(hooks):
        for si, (w, h) in enumerate(sizes):
            c = Canvas(w, h)
            promo(c, job, headline=hook, sub=job.sub(hi) if hi else (job.business_line() or job.sub(0)), cta=job.cta(), theme=themes[hi], idx=hi, badge=badge)
            svg = c.to_svg()
            res.arts.append(Art(f"Hook {hi + 1} - {w}x{h}", svg, w, h, f"Hook {hi + 1} · {w}x{h}", role="primary" if hi == 0 and si == 0 else "variant",
                                group=f"Hook {hi + 1}"))
            if si == 0:
                board.append((svg, w, h))
    res.arts.insert(0, Art(f"{b.name} - ad set overview", _board(job, f"Ad set: {offer[:60] or b.name}", board,
                                                              sub=f"3 hook variants × {len(sizes)} placements · goal: {job.f('goal') or 'conversions'}"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.texts.append(("Copy angles.md", "# Copy angles\n\n" + "\n".join(f"{i + 1}. **{h}** - {job.sub(i)}" for i, h in enumerate(hooks))
                      + f"\n\nCall to action: {job.cta()}\n"))
    res.summary = f"Ad set for {b.name}: 3 hook variants in {len(sizes)} placements ({', '.join(f'{w}x{h}' for w, h in sizes)}), plus copy angles."
    return res
