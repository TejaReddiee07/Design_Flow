"""Print services: flyers, posters, brochures, infographics, business cards and company profiles.

Print pieces are laid out at 150 dpi with 3 mm bleed and exported at 300 dpi for the print PDF.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.agents.tools.design_engine import color as col
from app.agents.tools.design_engine.canvas import Canvas, _n
from app.agents.tools.design_engine.common import (Art, Job, Result, art_panel, background, bar_chart, brand_badge, bullets, corner_marks, dots,
                                                   initials_avatar, label, pill, ring_stat, sparkle, theme_colors)
from app.agents.tools.design_engine.icons import draw_icon
from app.agents.tools.design_engine.marks import Scheme, draw_logo, icon_mark
from app.agents.tools.design_engine.svc_social import _board, _number_in, lay_hero, promo

DPI = 150
BLEED = round(3 / 25.4 * DPI)  # 3 mm


def mm(v: float) -> int:
    return round(v / 25.4 * DPI)


SIZES_MM = {"A4": (210, 297), "A5": (148, 210), "A3": (297, 420), "A2": (420, 594), "A1": (594, 841), "US Letter": (216, 279), "DL": (99, 210),
            "24x36 in": (610, 914)}


def _page(w_mm: float, h_mm: float) -> Tuple[int, int]:
    return mm(w_mm) + 2 * BLEED, mm(h_mm) + 2 * BLEED


def _sections(job: Job) -> List[Dict[str, Any]]:
    raw = job.content.get("sections") or job.content.get("slides") or []
    out = []
    if isinstance(raw, list):
        for s in raw:
            if isinstance(s, dict) and s.get("title"):
                bl = s.get("bullets") or s.get("points") or []
                out.append({"title": str(s["title"])[:80], "body": str(s.get("body") or "")[:600],
                            "bullets": [str(x)[:120] for x in bl if x][:6] if isinstance(bl, list) else []})
    return out


def _details(text: str) -> List[Tuple[str, str]]:
    """Pull date / time / place lines out of free text for event flyers."""
    out = []
    t = text or ""
    d = re.search(r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?|(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\s+\w+)", t, re.I)
    if d:
        out.append(("calendar" if False else "clock", d.group(0)))
    tm = re.search(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)(?:\s?[-–to]+\s?\d{1,2}(?::\d{2})?\s?(?:am|pm))?", t, re.I)
    if tm:
        out.append(("clock", tm.group(0)))
    pl = re.search(r"\b(?:at|@|venue[:\s])\s+([A-Z][\w'&]+(?:\s+[A-Z][\w'&]+){0,4})", t)
    if pl:
        out.append(("pin", pl.group(1)))
    return out


# ---------------------------------------------------------------------------
# Flyer
# ---------------------------------------------------------------------------
def render_flyer(job: Job) -> Result:
    b = job.b
    res = Result()
    size = job.f("size") or "A4"
    w_mm, h_mm = SIZES_MM.get(size, SIZES_MM["A4"])
    W, H = _page(w_mm, h_mm)
    what = job.f("event_or_offer")
    head = job.headline(0)
    pages = []
    c = Canvas(W, H)
    theme = b.tweaks.theme or ("dark" if b.style in ("Bold", "Luxury") else "light")
    bg, fg, soft = background(c, b, theme)
    u = W / 1240
    m = BLEED + 80 * u
    ah = H * 0.5
    art_panel(c, b, 0, 0, W, ah, photo=0, seed=job.request_id, icon_scale=0.42)
    c.path(f"M0 {_n(ah - 4)}Q{_n(W * 0.5)} {_n(ah - 150 * u)} {_n(W)} {_n(ah - 4)}V{_n(ah + 6)}H0Z", fill=bg)
    brand_badge(c, b, m, BLEED + 70 * u, 64 * u, b.primary)
    big = _number_in(what, job.f("copy_text"))
    acc = b.accent if col.contrast(b.accent, bg) > 2 else b.primary
    if big:
        r = 150 * u
        c.circle(W - m - r, ah - 30 * u, r, fill=acc)
        c.fit_text(W - m - 1.8 * r, ah - 30 * u - r * 0.45, 1.6 * r, r * 0.9, big, b.heading, max_size=110 * u, min_size=28, fill=col.readable_on(acc, "#FFFFFF", b.dark),
                   align="center", max_lines=2, valign="middle")
    y = ah + 70 * u
    label(c, b, m, y, b.descriptor, 26 * u, acc)
    used = c.fit_text(m, y + 40 * u, W - 2 * m - (300 * u if big else 0), 330 * u, head, b.heading, max_size=128 * u * b.tweaks.headline_scale,
                      min_size=50 * u, fill=fg, max_lines=3, line_height=1.03)[1]
    y += 40 * u + used + 50 * u
    body = job.body() if not what or job.body() != what else ""
    if body and not b.tweaks.minimal:
        y += c.paragraph(m, y, W - 2 * m, body, b.body, 34 * u, fill=soft, max_lines=3) + 40 * u
    det = _details(" ".join([what, job.f("copy_text")]))
    for icon, txt in det[:3]:
        draw_icon(c, icon, m, y - 4 * u, 40 * u, acc)
        c.text(m + 64 * u, y + 28 * u, txt, b.body_bold, 32 * u, fill=fg)
        y += 64 * u
    by = H - BLEED - 150 * u
    c.rect(0, by - 30 * u, W, H - by + 30 * u, fill=b.dark if theme == "light" else b.primary)
    fb = b.dark if theme == "light" else b.primary
    pill(c, b, m, by + 6 * u, job.cta(), 30 * u, b.accent if col.contrast(b.accent, fb) > 2 else b.light, col.readable_on(b.accent, "#FFFFFF", b.dark))
    tail = b.website or b.handle or b.location
    if tail:
        c.text(W - m, by + 62 * u, tail, b.label, 28 * u, fill=b.on(fb), anchor="end", tracking=0.1)
    pages.append(("Front", c.to_svg()))

    if "double" in job.f("sides").lower():
        c = Canvas(W, H)
        bg, fg, soft = background(c, b, "light")
        brand_badge(c, b, m, BLEED + 80 * u, 64 * u, bg)
        c.fit_text(m, BLEED + 230 * u, W - 2 * m, 220 * u, job.headline(1) if len(job.headlines()) > 1 else "Good to know", b.heading, max_size=96 * u,
                   min_size=40 * u, fill=fg, max_lines=2)
        bullets(c, b, m, BLEED + 520 * u, W - 2 * m, job.points(5), 34 * u, fg, acc, icon="check", gap=1.4, max_lines=2)
        art_panel(c, b, m, H - BLEED - 640 * u, W - 2 * m, 420 * u, rx=max(8, b.radius) * u * 1.4, photo=1, seed=job.request_id + 1, icon_scale=0.5)
        c.text(m, H - BLEED - 120 * u, " · ".join(x for x in (b.website, b.location) if x) or b.name, b.label, 28 * u, fill=soft, tracking=0.1)
        pages.append(("Back", c.to_svg()))

    pdf = f"{b.name} - flyer print ({size}, 3mm bleed)"
    for nm, svg in pages:
        res.arts.append(Art(f"Flyer {size} - {nm.lower()}", svg, W, H, f"Flyer {size} {nm.lower()} (with bleed)", role="primary" if nm == "Front" else "page",
                            group="Print", pdf=pdf, export_width=W * 2))
    res.pdfs[pdf] = DPI * 2
    sc = Canvas(1080, 1350)
    lay_hero(sc, job, 0, theme)
    res.arts.append(Art("Flyer - social 1080x1350", sc.to_svg(), 1080, 1350, "Digital / social version (1080x1350)", group="Digital"))
    res.arts.insert(0, Art(f"{b.name} - flyer", _board(job, f"Flyer: {head}", [(svg, W, H) for _, svg in pages] + [(sc.to_svg(), 1080, 1350)],
                                                    sub=f"{size} {job.f('sides') or 'single-sided'} · print PDF at 300 dpi with 3 mm bleed + social version"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{size} flyer for {b.name} ({len(pages)} side{'s' if len(pages) > 1 else ''}), print-ready PDF with bleed and a social version."
    return res


# ---------------------------------------------------------------------------
# Poster
# ---------------------------------------------------------------------------
def render_poster(job: Job) -> Result:
    b = job.b
    res = Result()
    size = job.f("size") or "A3"
    digital_only = size == "Digital screen"
    w_mm, h_mm = SIZES_MM.get(size, SIZES_MM["A3"])
    W, H = (1080, 1920) if digital_only else _page(w_mm, h_mm)
    c = Canvas(W, H)
    _poster(c, job, bleed=0 if digital_only else BLEED)
    svg = c.to_svg()
    pdf = f"{b.name} - poster print ({size})"
    if digital_only:
        res.arts.append(Art("Poster - digital screen 1080x1920", svg, W, H, "Poster for digital screens (1080x1920)", role="primary", group="Digital"))
    else:
        res.arts.append(Art(f"Poster {size} - print", svg, W, H, f"Poster {size} print (3 mm bleed)", role="primary", group="Print", pdf=pdf, export_width=W * 2))
        res.pdfs[pdf] = DPI * 2
    d = Canvas(1080, 1920)
    _poster(d, job, bleed=0)
    res.arts.append(Art("Poster - digital 1080x1920", d.to_svg(), 1080, 1920, "Digital screen version (1080x1920)", group="Digital"))
    res.arts.insert(0, Art(f"{b.name} - poster", _board(job, f"Poster: {job.headline(0)}", [(svg, W, H), (d.to_svg(), 1080, 1920)],
                                                     sub=f"{job.f('purpose') or 'Campaign'} poster · {size} print + digital screen version"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{size} poster for {b.name} with a print-ready PDF and a digital screen version."
    return res


def _poster(c: Canvas, job: Job, bleed: float) -> None:
    b = job.b
    W, H = c.w, c.h
    u = W / 1240
    m = bleed + 90 * u
    style = b.style
    kind = {"Bold": "bold", "Playful": "bold", "Luxury": "classic", "Vintage": "classic"}.get(style, "swiss")
    kind = ["swiss", "bold", "classic"][(["swiss", "bold", "classic"].index(kind) + job.version - 1) % 3]
    head = job.headline(0)
    det = _details(" ".join([job.f("copy_text"), job.f("about_and_wishes")]))
    if kind == "bold":
        bg, fg, soft = background(c, b, "brand")
        acc = b.accent if col.contrast(b.accent, bg) > 1.5 else b.light
        c.circle(W * 0.85, H * 0.18, W * 0.42, fill=acc, opacity=0.9)
        c.circle(W * 0.1, H * 0.86, W * 0.3, fill=b.dark, opacity=0.35)
        draw_icon(c, b.motif, W * 0.6, H * 0.06, W * 0.36, col.readable_on(acc, b.dark, "#FFFFFF"))
        words = head.upper().split()
        fc = b.heading if b.style != "Playful" else b.heading
        c.fit_text(m, H * 0.36, W - 2 * m, H * 0.4, " ".join(words), fc, max_size=300 * u * b.tweaks.headline_scale, min_size=60 * u, fill=fg, max_lines=4,
                   line_height=0.96)
        c.paragraph(m, H * 0.79, W * 0.7, job.sub(0), b.body_bold, 40 * u, fill=fg, max_lines=2)
        brand_badge(c, b, m, H - bleed - 150 * u, 70 * u, bg)
        if b.website:
            c.text(W - m, H - bleed - 100 * u, b.website, b.label, 30 * u, fill=fg, anchor="end", tracking=0.1)
    elif kind == "classic":
        bg, fg, soft = background(c, b, "dark" if b.theme == "dark" else "light")
        acc = b.accent if col.contrast(b.accent, bg) > 2 else b.primary
        inset = bleed + 60 * u
        c.rect(inset, inset, W - 2 * inset, H - 2 * inset, stroke=acc, sw=5 * u)
        c.rect(inset + 20 * u, inset + 20 * u, W - 2 * inset - 40 * u, H - 2 * inset - 40 * u, stroke=acc, sw=1.5 * u)
        fc = b.display if b.display.family != "Pacifico" else b.heading
        y = inset + 150 * u
        em = min(520 * u, H * 0.24)
        draw_logo(c, b, "emblem", W / 2 - em / 2, y, em, em, Scheme.full(b, bg))
        y += em + 80 * u
        label(c, b, W / 2, y, job.f("purpose") or b.descriptor, 30 * u, acc, anchor="middle", rule=False)
        y += 50 * u
        size, used = c.fit_text(inset + 100 * u, y, W - 2 * inset - 200 * u, H * 0.3, head, fc, max_size=230 * u * b.tweaks.headline_scale, min_size=60 * u,
                                fill=fg, align="center", max_lines=3, line_height=1.0)
        y += used + 70 * u
        c.line(W / 2 - 120 * u, y, W / 2 + 120 * u, y, stroke=acc, sw=3 * u)
        y += 60 * u
        sub = job.copy_parts()[1] or job.sub(0)
        y += c.paragraph(inset + 160 * u, y, W - 2 * inset - 320 * u, sub, b.body, 44 * u, fill=soft, align="center", max_lines=3) + 90 * u
        info = "  ·  ".join(t for _, t in det[:3]) or (b.website or b.location)
        if info:
            c.text(W / 2, max(y, H - inset - 160 * u), info, b.label, 32 * u, fill=fg, anchor="middle", tracking=0.14, upper=True)
    else:  # swiss grid
        bg, fg, soft = background(c, b, b.theme if b.theme in ("light", "dark") else "light")
        acc = b.primary if col.contrast(b.primary, bg) > 2 else b.accent
        cols = 6
        gw = (W - 2 * m) / cols
        for i in range(cols + 1):
            c.line(m + i * gw, bleed, m + i * gw, H - bleed, stroke=soft, sw=1, opacity=0.18)
        c.circle(m + gw * 4, H * 0.3, gw * 2.1, fill=acc)
        c.circle(m + gw * 5.2, H * 0.42, gw * 0.9, fill=b.accent if acc != b.accent else b.secondary, opacity=0.95)
        draw_icon(c, b.motif, m + gw * 3, H * 0.3 - gw, gw * 2, b.on(acc))
        c.text(m, bleed + 140 * u, b.descriptor.upper(), b.label, 30 * u, fill=soft, tracking=0.2)
        c.fit_text(m, H * 0.55, W - 2 * m, H * 0.26, head, b.heading, max_size=210 * u * b.tweaks.headline_scale, min_size=60 * u, fill=fg, max_lines=4,
                   line_height=0.98)
        c.paragraph(m, H * 0.83, gw * 3.6, job.sub(0), b.body, 34 * u, fill=soft, max_lines=3)
        yy = H * 0.83
        for icon, t in det[:3]:
            c.text(m + gw * 4, yy + 30 * u, t, b.body_bold, 32 * u, fill=fg)
            yy += 56 * u
        brand_badge(c, b, m, H - bleed - 130 * u, 60 * u, bg)


# ---------------------------------------------------------------------------
# Business card
# ---------------------------------------------------------------------------
def _contact(job: Job) -> Dict[str, str]:
    text = job.f("details")
    client = job.ctx.get("client") or {}
    out: Dict[str, str] = {}
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    out["email"] = m.group(0) if m else (client.get("email") or "")
    m = re.search(r"(\+?\d[\d\s()-]{7,}\d)", text)
    out["phone"] = m.group(1).strip() if m else ""
    m = re.search(r"\b(?:https?://)?(?:www\.)?[a-z0-9-]+\.(?:co\.uk|com|uk|io|co|org|net|studio|design|shop)(?:/\S*)?\b", text, re.I)
    out["web"] = (m.group(0) if m and "@" not in m.group(0) else "") or job.b.website
    lines = [l.strip(" ,") for l in text.splitlines() if l.strip()]
    rest = [l for l in lines if not re.search(r"@|\d{5,}|\+\d|www\.|\.co|\.com", l)]
    out["name"] = rest[0] if rest else (client.get("contact_name") or "")
    out["title"] = rest[1] if len(rest) > 1 and len(rest[1]) < 48 else ""
    addr = [l for l in rest[2:] if re.search(r"\d|street|st\b|road|rd\b|lane|avenue|ave\b|[A-Z]{1,2}\d", l, re.I)]
    out["address"] = addr[0] if addr else ""
    return out


def render_business_card(job: Job) -> Result:
    b = job.b
    res = Result()
    size = job.f("size")
    dpi = 300
    if size.startswith("Standard"):
        tw, th = 3.5 * 25.4, 2 * 25.4
    elif size.startswith("Square"):
        tw, th = 65, 65
    else:
        tw, th = 85, 55
    W, H = round((tw + 6) / 25.4 * dpi), round((th + 6) / 25.4 * dpi)
    bl = round(3 / 25.4 * dpi)
    info = _contact(job)
    acc = b.accent

    front = Canvas(W, H)
    face_bg = b.primary if b.style not in ("Luxury",) else b.dark
    front.rect(0, 0, W, H, fill=face_bg)
    front.rect(0, 0, W, H, fill=front.linear([(0, col.lighten(face_bg, 0.06)), (1, col.darken(face_bg, 0.12))], angle=130))
    front.grain(0.05)
    sc = Scheme(text=b.on(face_bg), sub=b.soft_on(face_bg), mark_bg=b.on(face_bg), mark_fg=face_bg, line=b.on(face_bg), accent=acc)
    if b.style == "Luxury":
        sc = Scheme(text=b.primary, sub=col.mix(b.primary, face_bg, 0.3), mark_bg=b.primary, mark_fg=face_bg, line=b.primary, accent=b.primary)
    kind = "emblem" if b.style == "Vintage" else "monogram" if b.style == "Luxury" else "lockup"
    if b.logo_href:
        front.image(bl + W * 0.15, bl + H * 0.2, W - 2 * bl - W * 0.3, H - 2 * bl - H * 0.4, b.logo_href, fit="meet")
    else:
        pad = 0.2 if kind == "lockup" else 0.16
        draw_logo(front, b, kind, bl + (W - 2 * bl) * pad, bl + (H - 2 * bl) * 0.16, (W - 2 * bl) * (1 - 2 * pad), (H - 2 * bl) * 0.68, sc)

    back = Canvas(W, H)
    back.rect(0, 0, W, H, fill=b.paper)
    back.rect(0, 0, bl + 22, H, fill=b.primary)
    s = (H - 2 * bl) / 640
    x = bl + 70 * s
    icon_mark(back, b, W - bl - 70 * s - 90 * s, bl + 60 * s, 90 * s, Scheme.full(b, b.paper), monogram=(kind == "monogram"))
    name_y = bl + 120 * s
    back.fit_text(x, name_y, W - 2 * bl - 280 * s, 70 * s, info["name"] or b.name, b.heading, max_size=64 * s, min_size=24 * s, fill=b.ink, max_lines=1)
    if info["title"]:
        back.text(x, name_y + 115 * s, info["title"], b.label, 24 * s, fill=b.primary if col.contrast(b.primary, b.paper) > 3 else b.muted, tracking=0.18,
                  upper=True)
    back.line(x, name_y + 165 * s, x + 90 * s, name_y + 165 * s, stroke=acc, sw=5 * s)
    rows = [(k, v) for k, v in (("phone", info["phone"]), ("mail", info["email"]), ("web", info["web"]), ("pin", info["address"])) if v]
    yy = name_y + 230 * s
    for icon, v in rows[:4]:
        draw_icon(back, icon, x, yy - 4 * s, 30 * s, b.primary if col.contrast(b.primary, b.paper) > 2.5 else b.ink)
        back.fit_text(x + 52 * s, yy, W - 2 * bl - 200 * s, 30 * s, v, b.body, max_size=27 * s, min_size=14 * s, fill=b.ink, max_lines=1)
        yy += 56 * s

    pdf = f"{b.name} - business cards print ({'US' if size.startswith('Standard') else '85x55mm' if not size.startswith('Square') else '65x65mm'})"
    res.arts.append(Art("Business card - front", front.to_svg(), W, H, "Business card front (300 dpi, 3 mm bleed)", role="primary", group="Print", pdf=pdf))
    res.arts.append(Art("Business card - back", back.to_svg(), W, H, "Business card back (300 dpi, 3 mm bleed)", group="Print", pdf=pdf))
    res.pdfs[pdf] = 300

    # mockup board
    mock = Canvas(1920, 1080)
    bg, fg, soft = background(mock, b, "dark")
    mock.grain(0.08)
    label(mock, b, 96, 112, "Business card · front and back", 18, soft)
    mock.fit_text(96, 134, 1300, 70, info["name"] or b.name, b.heading, max_size=52, fill=fg, max_lines=1)
    cw = 760
    ch = cw * H / W
    from app.agents.tools.design_engine.svc_social import svg_href

    for i, (svg, rot, x, y) in enumerate(((front.to_svg(), -5, 200, 320), (back.to_svg(), 4, 980, 380))):
        with mock.group(transform=f"rotate({rot} {x + cw / 2} {y + ch / 2})"):
            mock.soft_shadow(x, y, cw, ch, rx=14, dy=28, blur=46, opacity=0.45)
            mock.image(x, y, cw, ch, svg_href(svg), clip=mock.clip_rect(x, y, cw, ch, 14))
    finish = job.f("finish") or "Matte"
    rec = {"Matte": "Uncoated 400gsm matte board for a soft, premium feel.", "Gloss": "Silk 400gsm with gloss laminate for vivid colour.",
           "Spot UV": "Matte laminate with spot UV on the logo for contrast you can feel.", "Foil": "Uncoated 450gsm with foil-blocked logo (gold or copper).",
           "Not sure": "Uncoated 400gsm matte board, optional spot UV on the logo."}.get(finish, "Uncoated 400gsm matte board.")
    mock.text(96, 960, f"Recommended finish: {finish}", b.body_bold, 24, fill=fg)
    mock.text(96, 1000, rec, b.body, 22, fill=soft)
    res.arts.insert(0, Art(f"{b.name} - business card mockup", mock.to_svg(), 1920, 1080, "Mockup board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    digital = Canvas(1600, 900)
    bg, fg, soft = background(digital, b, "light")
    for i, svg in enumerate((front.to_svg(), back.to_svg())):
        x = 80 + i * 760
        dw, dh = 680, 680 * H / W
        digital.soft_shadow(x, 450 - dh / 2, dw, dh, rx=12, dy=16, blur=30, opacity=0.2)
        digital.image(x, 450 - dh / 2, dw, dh, svg_href(svg), clip=digital.clip_rect(x, 450 - dh / 2, dw, dh, 12))
    res.arts.append(Art("Digital business card - 1600x900", digital.to_svg(), 1600, 900, "Digital card for email and LinkedIn (1600x900)", group="Digital"))
    res.texts.append(("Finish recommendations.md", f"# Print and finish\n\nSize: {size or 'EU 85x55 mm'} with 3 mm bleed, 300 dpi.\n\n"
                      f"**Recommended:** {rec}\n\nKeep text 4 mm inside the trim edge. Colours are RGB; ask your printer for a CMYK proof before a large run.\n"))
    res.summary = f"Business card for {info['name'] or b.name}: front and back at 300 dpi with bleed, print PDF, mockup and digital card."
    return res


# ---------------------------------------------------------------------------
# Infographic
# ---------------------------------------------------------------------------
def _parse_data(text: str) -> Tuple[List[Tuple[str, str, float]], List[str]]:
    stats, facts = [], []
    for raw in re.split(r"\n|;", text or ""):
        line = raw.strip(" -•*\t")
        if not line:
            continue
        m = re.search(r"(£|\$|€|₹)?\s?(\d+(?:[.,]\d+)?)\s?(%|x\b|k\b|m\b|bn\b|million|\+)?", line, re.I)
        is_year = bool(m and re.fullmatch(r"(19|20)\d\d", m.group(2) or "") and not (m.group(1) or m.group(3)))
        if m and m.group(2) and not is_year:
            val = m.group(0).strip()
            lab = (line[: m.start()] + line[m.end():]).strip(" :-,.")
            lab = re.sub(r"\s{2,}", " ", lab)
            try:
                num = float(m.group(2).replace(",", ""))
            except ValueError:
                num = 0.0
            stats.append((val, lab if re.match(r"(of|in|per|a|an|the|to|for)\b", lab, re.I) else (lab[:1].upper() + lab[1:]), num))
        else:
            facts.append(line[:1].upper() + line[1:])
    return stats, facts


def render_infographic(job: Job) -> Result:
    b = job.b
    res = Result()
    stats, facts = _parse_data(job.f("data"))
    if not facts:
        facts = job.points(4)
    title = job.headline(0) if job.content.get("headlines") else (job.title or f"{b.name} in numbers")
    orient = job.f("orientation") or "Vertical (blog/Pinterest)"
    if orient.startswith("Horizontal"):
        W, H = 1920, 1080
    elif orient.startswith("Square"):
        W, H = 1080, 1080
    else:
        # height follows the content: header, stat rows, optional chart, facts, footer
        rows = (min(6, len(stats)) + 2) // 3
        chart = len([s for s in stats if "%" in s[0]]) >= 3
        H = int(520 + 70 + rows * 340 + (40 if rows else 0) + (620 if chart else 0) + 50 + min(len(facts), 8) * 180 + 260)
        W, H = 1080, max(1350, min(4000, H))
    c = Canvas(W, H)
    _infographic(c, job, title, stats, facts)
    main = c.to_svg()
    pdf = f"{b.name} - infographic"
    res.arts.append(Art(f"Infographic - {W}x{H}", main, W, H, f"Infographic ({W}x{H})", role="primary", group="Infographic", pdf=pdf))
    res.pdfs[pdf] = 150
    crops = []
    if H > W:
        n = 2 if H > 2200 else 1
        for k in range(n):
            y0 = k * (H - 1350) / max(1, n - 1) if n > 1 else 0
            crop = main.replace(f'width="{W}" height="{H}" viewBox="0 0 {W} {H}"', f'width="1080" height="1350" viewBox="0 {_n(y0)} 1080 1350"', 1)
            crops.append(crop)
            res.arts.append(Art(f"Social crop {k + 1} - 1080x1350", crop, 1080, 1350, f"Social crop {k + 1} (1080x1350)", group="Social crops"))
    res.arts.insert(0, Art(f"{b.name} - infographic", _board(job, f"Infographic: {title}", [(main, W, H)] + [(x, 1080, 1350) for x in crops],
                                                          sub=f"{len(stats)} data points · {len(facts)} key facts · PNG, PDF and social crops"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{orient.split(' ')[0]} infographic for {b.name} with {len(stats)} data points and {len(facts)} key facts, plus social crops."
    return res


def _infographic(c: Canvas, job: Job, title: str, stats, facts) -> None:
    b = job.b
    W, H = c.w, c.h
    land = W > H
    u = (W if not land else H) / 1080
    m = 80 * u
    bg, fg, soft = background(c, b, "light")
    acc = b.primary if col.contrast(b.primary, bg) > 2.4 else b.accent
    # header band
    hh = (520 if not land else 300) * u
    c.rect(0, 0, W, hh, fill=b.dark)
    c.rect(0, 0, W, hh, fill=c.radial([(0, b.primary, 0.6), (1, b.primary, 0)], cx=0.9, cy=0.1, r=0.8))
    dots(c, W - m - 8 * 36 * u, m, 8, 4, 36 * u, b.light, 0.25, r=4 * u)
    brand_badge(c, b, m, m - 10 * u, 50 * u, b.dark)
    c.fit_text(m, (190 if not land else 120) * u, W - 2 * m - (0 if not land else W * 0.3), (230 if not land else 120) * u, title, b.heading,
               max_size=96 * u, min_size=36 * u, fill=b.light, max_lines=3, line_height=1.04)
    c.paragraph(m, hh - 90 * u, W - 2 * m, job.sub(0), b.body, 28 * u, fill=col.mix(b.light, b.dark, 0.3), max_lines=1)
    y = hh + 70 * u
    # big stats: up to six cards, three per row
    pct = [s for s in stats if "%" in s[0]]
    top = stats[: (3 if land else 6)]
    per_row = min(3, max(1, len(top)))
    cw = (W - 2 * m - (per_row - 1) * 30 * u) / per_row
    for row in range(0, len(top), 3):
        chunk = top[row: row + 3]
        for i, (val, lab, _) in enumerate(chunk):
            x = m + i * (cw + 30 * u)
            c.rect(x, y, cw, 300 * u, rx=max(8, b.radius) * u * 1.4, fill="#FFFFFF", filter=c.shadow(dy=10 * u, blur=24 * u, color=b.dark, opacity=0.08))
            c.fit_text(x + 30 * u, y + 50 * u, cw - 60 * u, 110 * u, val, b.heading, max_size=110 * u, min_size=36 * u, fill=acc, max_lines=1)
            c.paragraph(x + 30 * u, y + 185 * u, cw - 60 * u, lab, b.body, 24 * u, fill=fg, max_lines=3)
        y += 300 * u + 40 * u
    if top:
        y += 40 * u
    # chart only when the values are comparable (all percentages)
    numeric = pct
    if len(numeric) >= 3 and not land:
        label(c, b, m, y, "By the numbers", 24 * u, acc)
        vals = [s[2] for s in numeric[:6]]
        labs = [(s[1][:24] or s[0]) for s in numeric[:6]]
        unit = "%" if all("%" in s[0] for s in numeric[:6]) else ""
        bar_chart(c, b, m, y + 40 * u, W - 2 * m, 520 * u, vals, labs, color=col.mix(acc, bg, 0.35), text=fg, grid=col.mix(fg, bg, 0.8),
                  highlight=vals.index(max(vals)), accent=acc, unit=unit)
        y += 620 * u
    # steps / facts
    if facts:
        label(c, b, m, y, "Key facts", 24 * u, acc)
        y += 50 * u
        icons = ["target", "users", "chart", "star", "clock", "shield", "heart", "globe"]
        if land:
            k = min(4, len(facts))
            cw = (W - 2 * m - (k - 1) * 30 * u) / k
            for i, fct in enumerate(facts[:k]):
                x = m + i * (cw + 30 * u)
                c.circle(x + 50 * u, y + 50 * u, 50 * u, fill=acc)
                draw_icon(c, icons[i % len(icons)], x + 22 * u, y + 22 * u, 56 * u, b.on(acc))
                c.paragraph(x, y + 130 * u, cw, fct, b.body, 24 * u, fill=fg, max_lines=4)
        else:
            avail = H - y - 220 * u
            k = min(len(facts), max(2, int(avail // (190 * u))))
            for i, fct in enumerate(facts[:k]):
                yy = y + i * 180 * u
                c.circle(m + 50 * u, yy + 50 * u, 50 * u, fill=acc)
                draw_icon(c, icons[i % len(icons)], m + 22 * u, yy + 22 * u, 56 * u, b.on(acc))
                if i < k - 1:
                    c.line(m + 50 * u, yy + 110 * u, m + 50 * u, yy + 170 * u, stroke=acc, sw=3 * u, dash="4 8")
                c.paragraph(m + 140 * u, yy + 20 * u, W - 2 * m - 140 * u, fct, b.body, 30 * u, fill=fg, max_lines=3)
    # footer
    c.rect(0, H - 130 * u, W, 130 * u, fill=b.dark)
    brand_badge(c, b, m, H - 95 * u, 50 * u, b.dark)
    if b.website:
        c.text(W - m, H - 58 * u, b.website, b.label, 24 * u, fill=b.light, anchor="end", tracking=0.1)


# ---------------------------------------------------------------------------
# Brochure and company profile (shared page builders)
# ---------------------------------------------------------------------------
def _default_sections(job: Job) -> List[Dict[str, Any]]:
    b = job.b
    about = job.business_line() or f"{b.name} is a {b.descriptor.lower()} business that puts its customers first."
    return [
        {"title": f"About {b.name}", "body": about + " " + (job.sub(0) if job.sub(0) not in about else ""), "bullets": []},
        {"title": "What we offer", "body": job.body(), "bullets": job.points(4)},
        {"title": "How we work", "body": "", "bullets": ["Listen and understand", "Plan the right approach", "Deliver with care", "Support you afterwards"]},
        {"title": "Why choose us", "body": job.sub(1) if len(job.subs()) > 1 else "", "bullets": job.points(3)},
    ]


def _content_page(c: Canvas, job: Job, sec: Dict[str, Any], x: float, y: float, w: float, h: float, u: float, fg: str, soft: str, acc: str, n: int) -> None:
    b = job.b
    c.text(x, y + 48 * u, f"{n:02d}", b.heading, 48 * u, fill=acc)
    used = c.fit_text(x, y + 84 * u, w, 200 * u, sec["title"], b.heading, max_size=84 * u, min_size=34 * u, fill=fg, max_lines=2)[1]
    yy = y + 84 * u + used + 46 * u
    if sec.get("body"):
        yy += c.paragraph(x, yy, w, sec["body"], b.body, 31 * u, fill=soft, max_lines=8, line_height=1.5) + 46 * u
    if sec.get("bullets"):
        bullets(c, b, x, yy, w, sec["bullets"][:5], 30 * u, fg, acc, icon="check", gap=1.2, max_lines=3)


def render_brochure(job: Job) -> Result:
    b = job.b
    res = Result()
    fold = job.f("fold") or "Tri-fold"
    secs = _sections(job) or _default_sections(job)
    if fold.startswith("Booklet") or fold.startswith("Single"):
        return render_company_profile(job, pages=8 if fold.startswith("Booklet") else 1, doc_name="brochure")
    W, H = _page(297, 210)  # A4 landscape flat sheet
    u = (H - 2 * BLEED) / 1240
    panels = 3 if fold in ("Tri-fold", "Z-fold") else 2
    pw = (W - 2 * BLEED) / panels
    acc = b.primary if col.contrast(b.primary, b.paper) > 2.4 else b.accent

    outside = Canvas(W, H)
    bg, fg, soft = background(outside, b, "light")
    fx = BLEED + pw * (panels - 1)  # front cover is the right-hand panel
    outside.rect(fx, 0, W - fx, H, fill=b.dark)
    art_panel(outside, b, fx, 0, W - fx, H * 0.55, seed=job.request_id, icon_scale=0.4)
    if b.logo_href:
        outside.image(fx + 60 * u, H * 0.6, pw - 120 * u, 160 * u, b.logo_href, fit="meet")
    else:
        draw_logo(outside, b, "lockup", fx + 60 * u, H * 0.58, pw - 120 * u, 140 * u, Scheme.full(b, b.dark))
    outside.fit_text(fx + 70 * u, H * 0.74, pw - 140 * u, 220 * u, job.headline(0), b.heading, max_size=72 * u, min_size=30 * u, fill=b.light, max_lines=3)
    # back panel (middle on tri-fold, left on bi-fold)
    bx = BLEED + pw * (panels - 2)
    outside.fit_text(bx + 70 * u, BLEED + 140 * u, pw - 140 * u, 120 * u, "Get in touch", b.heading, max_size=56 * u, min_size=28 * u, fill=fg, max_lines=1)
    contact = job.ctx.get("client") or {}
    rows = [(i, v) for i, v in (("mail", contact.get("email")), ("web", b.website), ("pin", b.location)) if v]
    yy = BLEED + 320 * u
    for ic, v in rows:
        draw_icon(outside, ic, bx + 70 * u, yy - 4 * u, 40 * u, acc)
        outside.text(bx + 130 * u, yy + 28 * u, v, b.body, 28 * u, fill=fg)
        yy += 80 * u
    brand_badge(outside, b, bx + 70 * u, H - BLEED - 160 * u, 60 * u, bg)
    if panels == 3:  # inside flap (left)
        s = secs[-1]
        _content_page(outside, job, s, BLEED + 70 * u, BLEED + 100 * u, pw - 140 * u, H, u, fg, soft, acc, len(secs))
    for i in range(1, panels):
        outside.line(BLEED + pw * i, BLEED, BLEED + pw * i, H - BLEED, stroke=soft, sw=1, opacity=0.15, dash="6 10")

    inside = Canvas(W, H)
    bg, fg, soft = background(inside, b, "light")
    for i in range(panels):
        x = BLEED + pw * i
        s = secs[i % len(secs)]
        if i == panels - 1:
            inside.rect(x, 0, W - x, H, fill=col.mix(b.primary, b.paper, 0.9))
            art_panel(inside, b, x + 60 * u, H - BLEED - 520 * u, pw - 120 * u, 420 * u, rx=max(8, b.radius) * u * 1.5, photo=0, seed=job.request_id + i, icon_scale=0.45)
            _content_page(inside, job, s, x + 70 * u, BLEED + 60 * u, pw - 140 * u, H, u, fg, soft, acc, i + 1)
        else:
            _content_page(inside, job, s, x + 70 * u, BLEED + 100 * u, pw - 140 * u, H, u, fg, soft, acc, i + 1)
        if i:
            inside.line(x, BLEED, x, H - BLEED, stroke=soft, sw=1, opacity=0.15, dash="6 10")

    pdf = f"{b.name} - {fold.lower()} brochure print (A4, 3mm bleed)"
    for nm, cv in (("outside", outside), ("inside", inside)):
        res.arts.append(Art(f"Brochure {fold} - {nm}", cv.to_svg(), W, H, f"{fold} brochure - {nm} spread (with bleed)", role="primary" if nm == "outside" else "page",
                            group="Print", pdf=pdf, export_width=W * 2))
    res.pdfs[pdf] = DPI * 2
    res.arts.insert(0, Art(f"{b.name} - brochure", _board(job, f"{fold} brochure for {b.name}", [(outside.to_svg(), W, H), (inside.to_svg(), W, H)], cols=1,
                                                       sub="Outside and inside spreads · A4 · print PDF at 300 dpi with 3 mm bleed"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{fold} A4 brochure for {b.name}: outside and inside spreads, print-ready PDF with bleed."
    return res


def render_company_profile(job: Job, pages: Optional[int] = None, doc_name: str = "company profile") -> Result:
    b = job.b
    res = Result()
    secs = _sections(job) or _default_sections(job)
    wanted = [s.lower() for s in job.multi("sections")]
    n = pages or job.number("pages", 8, 4, 12)
    W, H = _page(210, 297)
    u = (W - 2 * BLEED) / 1240
    m = BLEED + 100 * u
    acc = b.primary if col.contrast(b.primary, b.paper) > 2.4 else b.accent
    contact = job.ctx.get("client") or {}
    built: List[Tuple[str, str]] = []

    c = Canvas(W, H)
    bg, fg, soft = background(c, b, "dark")
    art_panel(c, b, 0, 0, W, H * 0.58, seed=job.request_id, icon_scale=0.34, dark=True)
    c.path(f"M0 {_n(H * 0.58 - 2)}L{_n(W)} {_n(H * 0.5)}V{_n(H * 0.58 + 4)}H0Z", fill=bg)
    if b.logo_href:
        c.image(m, H * 0.64, W * 0.5, 160 * u, b.logo_href, fit="meet")
    else:
        draw_logo(c, b, "lockup", m - 20 * u, H * 0.62, W * 0.62, 170 * u, Scheme.full(b, bg))
    c.fit_text(m, H * 0.76, W - 2 * m, 260 * u, "Company profile" if doc_name == "company profile" else job.headline(0), b.heading, max_size=110 * u,
               min_size=40 * u, fill=fg, max_lines=2)
    c.text(m, H - BLEED - 110 * u, str(__import__("datetime").datetime.utcnow().year), b.label, 30 * u, fill=soft, tracking=0.2)
    built.append(("Cover", c.to_svg()))

    order: List[Dict[str, Any]] = list(secs)
    if "team" in wanted or not wanted:
        order.append({"title": "Our team", "kind": "team"})
    if "contact" in wanted or not wanted or True:
        pass
    for i, s in enumerate(order):
        if len(built) >= n - 1:
            break
        c = Canvas(W, H)
        bg, fg, soft = background(c, b, "light")
        num = len(built)
        c.text(W - m, BLEED + 90 * u, f"{num:02d}", b.label, 26 * u, fill=soft, anchor="end", tracking=0.16)
        c.text(m, BLEED + 90 * u, b.name.upper(), b.label, 22 * u, fill=soft, tracking=0.2)
        if s.get("kind") == "team":
            c.fit_text(m, BLEED + 200 * u, W - 2 * m, 140 * u, "Our team", b.heading, max_size=96 * u, min_size=40 * u, fill=fg, max_lines=1)
            people = [(contact.get("contact_name") or b.name, "Founder")] + [("Key hire", r) for r in ("Operations", "Client success")]
            cw = (W - 2 * m - 2 * 40 * u) / 3
            for k, (nm, role) in enumerate(people):
                x = m + k * (cw + 40 * u)
                initials_avatar(c, b, x + cw / 2, BLEED + 620 * u, 120 * u, nm if k == 0 else role, b.primary if k == 0 else col.mix(b.primary, b.paper, 0.45))
                c.fit_text(x, BLEED + 800 * u, cw, 50 * u, nm if k == 0 else role, b.body_bold, max_size=34 * u, min_size=18 * u, fill=fg, align="center", max_lines=1)
                c.text(x + cw / 2, BLEED + 900 * u, role if k == 0 else "Hiring", b.label, 22 * u, fill=soft, anchor="middle", tracking=0.16, upper=True)
            art_panel(c, b, m, H - BLEED - 720 * u, W - 2 * m, 560 * u, rx=max(8, b.radius) * u * 1.5, photo=0, seed=job.request_id + 9, icon_scale=0.4)
            built.append(("Team", c.to_svg()))
            continue
        top_art = i % 2 == 0
        if top_art:
            art_panel(c, b, m, BLEED + 160 * u, W - 2 * m, 640 * u, rx=max(8, b.radius) * u * 1.5, photo=i, seed=job.request_id + i, icon_scale=0.38)
            _content_page(c, job, s, m, BLEED + 860 * u, W - 2 * m, H, u, fg, soft, acc, num)
        else:
            _content_page(c, job, s, m, BLEED + 160 * u, W - 2 * m, H, u, fg, soft, acc, num)
            c.rect(0, H - BLEED - 520 * u, W, 520 * u + BLEED, fill=b.dark)
            k = 3
            cw = (W - 2 * m - 2 * 40 * u) / k
            for j, p in enumerate((s.get("bullets") or job.points(3))[:3]):
                x = m + j * (cw + 40 * u)
                draw_icon(c, ["star", "shield", "heart"][j], x, H - BLEED - 430 * u, 70 * u, b.accent if col.contrast(b.accent, b.dark) > 2 else b.light)
                c.paragraph(x, H - BLEED - 320 * u, cw, p, b.body_bold, 28 * u, fill=b.light, max_lines=4)
        built.append((s["title"], c.to_svg()))

    c = Canvas(W, H)
    bg, fg, soft = background(c, b, "brand")
    draw_logo(c, b, "lockup", m, H * 0.3, W - 2 * m, 260 * u,
              Scheme(text=b.on(b.primary), sub=b.soft_on(b.primary), mark_bg=b.on(b.primary), mark_fg=b.primary, line=b.on(b.primary), accent=b.accent))
    c.fit_text(m, H * 0.55, W - 2 * m, 140 * u, "Let's work together", b.heading, max_size=86 * u, min_size=40 * u, fill=fg, align="center", max_lines=2)
    info = [v for v in (contact.get("email"), b.website, b.location) if v]
    for k, v in enumerate(info):
        c.text(W / 2, H * 0.68 + k * 60 * u, v, b.body, 32 * u, fill=fg, anchor="middle")
    built.append(("Contact", c.to_svg()))

    pdf = f"{b.name} - {doc_name} (A4)"
    for i, (nm, svg) in enumerate(built, 1):
        res.arts.append(Art(f"Page {i:02d} - {nm}", svg, W, H, f"Page {i}: {nm}", role="primary" if i == 1 else "page", group="Pages", pdf=pdf, export_width=round(W * 1.4)))
    res.pdfs[pdf] = round(DPI * 1.4)
    res.arts.insert(0, Art(f"{b.name} - {doc_name} overview", _board(job, f"{doc_name.capitalize()}: {b.name}", [(svg, W, H) for _, svg in built[:8]], cols=4,
                                                                  sub=f"{len(built)} A4 pages · interactive and print PDF"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{len(built)}-page A4 {doc_name} for {b.name} (PDF + page PNGs)."
    return res
