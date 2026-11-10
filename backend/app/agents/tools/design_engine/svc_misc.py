"""Website banners, e-commerce listing images, product advertisements and custom requests."""
from __future__ import annotations

import re
from typing import List, Tuple

from app.agents.tools.design_engine import color as col
from app.agents.tools.design_engine.canvas import Canvas, _n
from app.agents.tools.design_engine.common import Art, Job, Result, art_panel, background, brand_badge, bullets, dots, label, pill, sparkle
from app.agents.tools.design_engine.icons import ICONS, draw_icon, rrect
from app.agents.tools.design_engine.marks import Scheme, draw_logo, icon_mark
from app.agents.tools.design_engine.svc_social import _board, _number_in, _themes, ad_sizes, promo, svg_href

PLACEMENT_SIZES = {
    "Homepage hero": [(1920, 600), (1440, 560), (768, 900)], "Promo strip": [(1920, 120), (1200, 100), (728, 90)],
    "Category page": [(1600, 400), (1200, 300), (768, 400)], "Sidebar": [(300, 600), (300, 250), (160, 600)],
    "Pop-up": [(600, 600), (500, 700)], "Display ad network": [(728, 90), (300, 250), (160, 600), (970, 250), (320, 50)],
}


def _parse_dims(text: str) -> List[Tuple[int, int]]:
    out = []
    for a, b in re.findall(r"(\d{2,4})\s*[x×X*]\s*(\d{2,4})", text or ""):
        w, h = int(a), int(b)
        if 40 <= w <= 4000 and 30 <= h <= 4000 and (w, h) not in out:
            out.append((w, h))
    return out


def render_banners(job: Job) -> Result:
    b = job.b
    res = Result()
    sizes = _parse_dims(job.f("dimensions")) or PLACEMENT_SIZES.get(job.f("placement"), [(1920, 600), (1200, 300), (728, 90), (300, 250)])
    head = job.headline(0)
    sub = job.body()
    board = []
    theme = _themes(job, 1)[0]
    for i, (w, h) in enumerate(sizes[:6]):
        c = Canvas(w, h)
        promo(c, job, headline=head, sub=sub, cta=job.cta(), theme=theme, idx=0, badge=_number_in(job.f("copy_text")))
        svg = c.to_svg()
        res.arts.append(Art(f"Banner {w}x{h}", svg, w, h, f"Banner {w}x{h}", role="primary" if i == 0 else "variant", group="Banners"))
        res.arts.append(Art(f"Banner {w}x{h} @2x", svg, w, h, f"Banner {w}x{h} retina @2x ({w * 2}x{h * 2})", group="Banners/Retina @2x",
                            export_width=w * 2, svg_file=False))
        board.append((svg, w, h))
    res.arts.insert(0, Art(f"{b.name} - banner set", _board(job, f"Banners for {job.f('site_url') or b.name}", board,
                                                         sub=f"{job.f('placement') or 'Website'} · {len(sizes[:6])} sizes, each also exported at 2x for retina screens",
                                                         cols=2 if len(board) > 1 else 1),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{len(sizes[:6])} website banners for {b.name} ({', '.join(f'{w}x{h}' for w, h in sizes[:6])}) with retina @2x exports."
    return res


def _benefits(job: Job, n: int = 5) -> List[str]:
    prod = job.f("product", "usp")
    lines = [l for l in re.split(r"\n|;|•|, (?=[A-Z])", prod) if l.strip()]
    if len(lines) > 1:
        return [l.strip(" -.") for l in lines[1: n + 1]] or job.points(n)
    parts = [p.strip(" -.") for p in re.split(r",|\band\b", prod) if len(p.strip()) > 3]
    return (parts[1: n + 1] if len(parts) > 2 else []) or job.points(n)


def _product_name(job: Job) -> str:
    p = job.f("product")
    first = re.split(r"[\n,.:;–-]", p)[0].strip() if p else ""
    return first[:60] or job.headline(0)


def _product_stage(c: Canvas, job: Job, x: float, y: float, w: float, h: float, idx: int = 0, *, dark: bool = False) -> None:
    """The product shot: the client's photo, or a studio-style plinth with the brand mark."""
    b = job.b
    if idx < len(b.photos):
        c.rect(x, y, w, h, fill="#FFFFFF")
        c.image(x + w * 0.06, y + h * 0.06, w * 0.88, h * 0.88, b.photos[idx], fit="meet")
        return
    base = b.dark if dark else col.mix(b.light, "#FFFFFF", 0.4)
    c.rect(x, y, w, h, fill=c.radial([(0, col.lighten(base, 0.12)), (1, col.darken(base, 0.06))], cx=0.5, cy=0.4, r=0.8))
    cx = x + w / 2
    py = y + h * 0.74
    c.ellipse(cx, py + h * 0.02, w * 0.3, h * 0.035, fill="#000000", opacity=0.18)
    c.rect(cx - w * 0.26, py - h * 0.05, w * 0.52, h * 0.09, rx=h * 0.02, fill=col.mix(b.primary, base, 0.55))
    c.ellipse(cx, py - h * 0.05, w * 0.26, h * 0.03, fill=col.mix(b.primary, "#FFFFFF", 0.35))
    s = min(w, h) * 0.42
    bx, by = cx - s / 2, py - h * 0.05 - s - h * 0.02
    c.soft_shadow(bx, by, s, s, rx=s * 0.12, dy=s * 0.06, blur=s * 0.2, color="#000000", opacity=0.22)
    c.rect(bx, by, s, s, rx=s * 0.12, fill=c.linear([(0, col.lighten(b.primary, 0.1)), (1, col.darken(b.primary, 0.15))], angle=120))
    icon_mark(c, b, bx + s * 0.18, by + s * 0.18, s * 0.64, Scheme(text=b.light, sub=b.light, mark_bg=b.light, mark_fg=b.primary, line=b.light, accent=b.accent))
    for sx, sy in ((0.2, 0.2), (0.82, 0.3), (0.74, 0.12)):
        sparkle(c, x + w * sx, y + h * sy, min(w, h) * 0.025, b.accent if not dark else b.light, 0.8)


def render_ecommerce(job: Job) -> Result:
    b = job.b
    res = Result()
    n = job.number("image_count", 5, 3, 7)
    name = _product_name(job)
    bens = _benefits(job, 5)
    S = 2000
    imgs = []

    # 1 main image (white background, marketplace compliant)
    c = Canvas(S, S, "#FFFFFF")
    _product_stage(c, job, 0, 0, S, S, 0)
    imgs.append(("Main image (white background)", c.to_svg()))

    # 2 benefits infographic
    c = Canvas(S, S)
    bg, fg, soft = background(c, b, "light")
    _product_stage(c, job, S * 0.5, 0, S * 0.5, S, 1)
    label(c, b, 140, 260, "Why you'll love it", 34, b.primary if col.contrast(b.primary, bg) > 3 else soft)
    c.fit_text(140, 300, S * 0.5 - 220, 300, name, b.heading, max_size=120, min_size=60, fill=fg, max_lines=3)
    acc = b.primary if col.contrast(b.primary, bg) > 2.5 else b.accent
    icons = ["check", "star", "shield", "heart", "bolt", "leaf"]
    yy = 720
    for i, ben in enumerate(bens[:4]):
        c.circle(200, yy + 50, 60, fill=acc)
        draw_icon(c, icons[i % len(icons)], 160, yy + 10, 80, b.on(acc))
        c.paragraph(300, yy + 20, S * 0.5 - 360, ben, b.body_bold, 46, fill=fg, max_lines=2, line_height=1.25)
        yy += 260
    imgs.append(("Key benefits", c.to_svg()))

    # 3 feature callouts around the product
    c = Canvas(S, S)
    bg, fg, soft = background(c, b, "dark")
    _product_stage(c, job, S * 0.2, S * 0.2, S * 0.6, S * 0.6, 2, dark=True)
    c.fit_text(140, 110, S - 280, 160, name, b.heading, max_size=100, min_size=50, fill=fg, align="center", max_lines=1)
    spots = [(0.06, 0.32, 0.3, 0.42), (0.64, 0.3, 0.7, 0.42), (0.06, 0.7, 0.3, 0.62), (0.64, 0.72, 0.7, 0.64)]
    for i, (tx, ty, px, py) in enumerate(spots[: len(bens)]):
        x, y = S * tx, S * ty
        c.line(S * px, S * py, x + (S * 0.3 if tx < 0.5 else 0), y, stroke=b.accent, sw=4)
        c.circle(S * px, S * py, 14, fill=b.accent)
        c.rect(x, y - 70, S * 0.3, 160, rx=20, fill="#FFFFFF", opacity=0.08)
        c.paragraph(x + 30, y - 40, S * 0.3 - 60, bens[i], b.body_bold, 40, fill=fg, max_lines=2, line_height=1.2)
    imgs.append(("Feature callouts", c.to_svg()))

    # 4 comparison chart
    c = Canvas(S, S)
    bg, fg, soft = background(c, b, "light")
    c.fit_text(140, 180, S - 280, 200, f"Why {b.name}?", b.heading, max_size=130, min_size=60, fill=fg, align="center", max_lines=1)
    tx, tw = 200, S - 400
    c.rect(tx, 480, tw, 1300, rx=40, fill="#FFFFFF", filter=c.shadow(dy=20, blur=50, color=b.dark, opacity=0.12))
    cols = [tx + tw * 0.56, tx + tw * 0.82]
    c.rect(cols[0] - 140, 480, 280, 1300, fill=col.mix(b.primary, "#FFFFFF", 0.88))
    c.text(cols[0], 600, b.name, b.body_bold, 40, fill=b.primary if col.contrast(b.primary, "#FFFFFF") > 3 else fg, anchor="middle")
    c.text(cols[1], 600, "Others", b.body_bold, 40, fill=soft, anchor="middle")
    for i, ben in enumerate(bens[:5]):
        y = 720 + i * 210
        c.line(tx + 60, y - 70, tx + tw - 60, y - 70, stroke=col.mix(fg, "#FFFFFF", 0.9), sw=2)
        c.paragraph(tx + 70, y - 30, tw * 0.42, ben, b.body, 38, fill=fg, max_lines=2)
        draw_icon(c, "check", cols[0] - 40, y - 40, 80, b.primary if col.contrast(b.primary, "#FFFFFF") > 2.5 else b.accent)
        c.circle(cols[1], y, 36, stroke=col.mix(fg, "#FFFFFF", 0.7), sw=5)
        c.line(cols[1] - 14, y - 14, cols[1] + 14, y + 14, stroke=col.mix(fg, "#FFFFFF", 0.6), sw=5)
        c.line(cols[1] + 14, y - 14, cols[1] - 14, y + 14, stroke=col.mix(fg, "#FFFFFF", 0.6), sw=5)
    imgs.append(("Comparison", c.to_svg()))

    # 5 lifestyle / brand story
    c = Canvas(S, S)
    art_panel(c, b, 0, 0, S, S, photo=3, seed=job.request_id, icon_scale=0.36)
    c.rect(0, S * 0.62, S, S * 0.38, fill=c.linear([(0, b.dark, 0), (0.35, b.dark, 0.85), (1, b.dark, 0.95)], angle=90))
    c.fit_text(140, S * 0.7, S - 280, 280, job.sub(0), b.heading, max_size=110, min_size=56, fill=b.light, max_lines=3)
    brand_badge(c, b, 140, S - 200, 80, b.dark)
    imgs.append(("Brand story", c.to_svg()))

    # 6 promo
    c = Canvas(S, S)
    promo(c, job, headline=job.headline(0), sub=name, cta=job.cta(), theme="brand", idx=4, badge=_number_in(job.f("product", "copy_text")) or "New")
    imgs.append(("Promo graphic", c.to_svg()))

    # 7 what's included / specs
    c = Canvas(S, S)
    bg, fg, soft = background(c, b, "light")
    c.fit_text(140, 200, S - 280, 160, "At a glance", b.heading, max_size=120, min_size=60, fill=fg, max_lines=1)
    bullets(c, b, 160, 480, S - 320, bens[:5], 50, fg, b.primary if col.contrast(b.primary, bg) > 2.5 else b.accent, icon="check", gap=1.6)
    brand_badge(c, b, 160, S - 220, 90, bg)
    imgs.append(("At a glance", c.to_svg()))

    picked = imgs[:n]
    for i, (lab, svg) in enumerate(picked):
        res.arts.append(Art(f"Listing image {i + 1} - {lab}", svg, S, S, f"Listing image {i + 1}: {lab} (2000x2000)", role="primary" if i == 0 else "variant",
                            group="Listing images 2000x2000"))
    # A+ modules
    for k in range(2):
        w, h = 970, 600
        c = Canvas(w, h)
        if k == 0:
            bg, fg, soft = background(c, b, "light")
            _product_stage(c, job, w * 0.5, 0, w * 0.5, h, 0)
            c.fit_text(50, 120, w * 0.42, 220, name, b.heading, max_size=56, min_size=26, fill=fg, max_lines=3)
            c.paragraph(50, 360, w * 0.42, job.sub(0), b.body, 22, fill=soft, max_lines=4)
        else:
            bg, fg, soft = background(c, b, "dark")
            cw = (w - 100 - 40) / 3
            for i, ben in enumerate(bens[:3]):
                x = 50 + i * (cw + 20)
                c.rect(x, 140, cw, 380, rx=18, fill="#FFFFFF", opacity=0.06)
                draw_icon(c, ["star", "shield", "heart"][i], x + cw / 2 - 40, 180, 80, b.accent)
                c.paragraph(x + 20, 300, cw - 40, ben, b.body_bold, 24, fill=fg, align="center", max_lines=4)
            c.fit_text(50, 50, w - 100, 60, f"The {b.name} difference", b.heading, max_size=40, min_size=20, fill=fg, align="center", max_lines=1)
        res.arts.append(Art(f"A+ module {k + 1} - 970x600", c.to_svg(), w, h, f"A+ / EBC module {k + 1} (970x600)", group="A+ content"))
    res.arts.insert(0, Art(f"{b.name} - listing images", _board(job, f"Listing images: {name}", [(s, S, S) for _, s in picked], cols=min(4, len(picked)) if len(picked) <= 4 else 4,
                                                             sub=f"{len(picked)} images at 2000x2000 for {', '.join(job.multi('marketplace')) or 'your store'} + 2 A+ modules"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"{len(picked)} marketplace listing images (2000x2000) for {name} plus 2 A+ content modules."
    return res


def render_product_ad(job: Job) -> Result:
    b = job.b
    res = Result()
    name = job.f("product") or job.headline(0)
    usps = job.lines("usp") or _benefits(job, 4)
    mood_theme = {"Premium": "dark", "Tech": "dark", "Energetic": "brand", "Natural": "light", "Playful": "brand"}.get(job.f("mood"), b.theme)
    if b.tweaks.theme:
        mood_theme = b.tweaks.theme
    # hero 1080x1350
    c = Canvas(1080, 1350)
    bg, fg, soft = background(c, b, mood_theme)
    _product_stage(c, job, 0, 120, 1080, 760, 0, dark=mood_theme == "dark")
    brand_badge(c, b, 84, 74, 52, bg)
    label(c, b, 84, 940, job.f("mood") or "Introducing", 24, b.accent if col.contrast(b.accent, bg) > 2.4 else soft)
    used = c.fit_text(84, 980, 912, 170, name, b.heading, max_size=110 * b.tweaks.headline_scale, min_size=44, fill=fg, max_lines=2)[1]
    c.paragraph(84, 980 + used + 24, 700, job.sub(0), b.body, 30, fill=soft, max_lines=2)
    acc = b.accent if col.contrast(b.accent, bg) > 2 else b.primary
    pill(c, b, 84, 1230, job.cta(), 28, acc, col.readable_on(acc, "#FFFFFF", b.dark))
    hero = c.to_svg()
    res.arts.append(Art("Hero creative - 1080x1350", hero, 1080, 1350, "Hero creative (1080x1350)", role="primary", group="Hero"))
    # feature callouts 1080x1080
    c = Canvas(1080, 1080)
    bg, fg, soft = background(c, b, "light" if mood_theme == "dark" else "dark")
    _product_stage(c, job, 290, 250, 500, 520, 1, dark=(mood_theme != "dark"))
    c.fit_text(84, 84, 912, 110, name, b.heading, max_size=70, min_size=34, fill=fg, align="center", max_lines=1)
    pos = [(84, 300, 0), (796, 300, 1), (84, 700, 0), (796, 700, 1)]
    for i, (x, y, right) in enumerate(pos[: len(usps)]):
        c.circle(x + (200 if not right else 0), y + 20, 10, fill=b.accent)
        c.line(x + (200 if not right else 0), y + 20, 290 + (0 if not right else 500), y + 20 + (40 if i > 1 else -10), stroke=b.accent, sw=3)
        c.paragraph(x - (0 if not right else 0), y + 50, 200, usps[i], b.body_bold, 26, fill=fg, max_lines=4, align="left" if not right else "left")
    brand_badge(c, b, 540, 960, 50, bg, anchor="middle")
    res.arts.append(Art("Feature callouts - 1080x1080", c.to_svg(), 1080, 1080, "Feature callouts (1080x1080)", group="Feature callouts"))
    board = [(hero, 1080, 1350)]
    sizes = [s for s in ad_sizes(job) if s not in ((1080, 1350),)][:4] or [(1080, 1080), (1080, 1920), (1200, 628)]
    for (w, h) in sizes:
        c = Canvas(w, h)
        promo(c, job, headline=name, sub=usps[0] if usps else job.sub(0), cta=job.cta(), theme=mood_theme, idx=0, badge=_number_in(job.f("usp", "product")))
        svg = c.to_svg()
        res.arts.append(Art(f"Adaptation - {w}x{h}", svg, w, h, f"Adaptation {w}x{h}", group="Adaptations"))
        board.append((svg, w, h))
    res.arts.insert(0, Art(f"{b.name} - product campaign", _board(job, f"Launch creatives: {name}", board[:5], sub=f"{job.f('mood') or b.style} mood · hero, callouts and {len(sizes)} adaptations"),
                           1920, 1080, "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"Product campaign for {name}: hero creative, feature callouts and {len(sizes)} size adaptations."
    return res


def render_custom(job: Job) -> Result:
    """Scoped by what the client asked for: packaging/labels, merch, icon sets, email headers or a general key visual."""
    b = job.b
    what = (job.f("what") + " " + job.title).lower()
    res = Result()
    if re.search(r"icon", what):
        icons = [k for k in ("home", "chart", "users", "mail", "phone", "pin", "shield", "star", "heart", "clock", "target", "globe") if k in ICONS]
        sheet = Canvas(1920, 1080)
        bg, fg, soft = background(sheet, b, "light")
        label(sheet, b, 96, 112, "Custom icon set", 18, soft)
        sheet.fit_text(96, 134, 1500, 70, f"{b.name} icon set", b.heading, max_size=52, fill=fg, max_lines=1)
        for i, nm in enumerate(icons):
            x, y = 96 + (i % 6) * 292, 290 + (i // 6) * 360
            sheet.rect(x, y, 260, 300, rx=28, fill="#FFFFFF")
            sheet.rect(x + 60, y + 50, 140, 140, rx=40, fill=col.mix(b.primary, "#FFFFFF", 0.86))
            draw_icon(sheet, nm, x + 85, y + 75, 90, b.primary)
            sheet.text(x + 130, y + 250, nm.title(), b.label, 20, fill=soft, anchor="middle", tracking=0.12, upper=True)
            ic = Canvas(512, 512)
            draw_icon(ic, nm, 56, 56, 400, b.primary)
            res.arts.append(Art(f"Icon - {nm}", ic.to_svg(), 512, 512, f"Icon: {nm}", group="Icons", transparent=True, backdrop="#FFFFFF"))
        res.arts.insert(0, Art(f"{b.name} - icon set", sheet.to_svg(), 1920, 1080, "Icon set sheet", role="board", group="Presentation"))
        res.board = res.arts[0].name
        res.summary = f"Custom icon set ({len(icons)} icons) in {b.name}'s colours, as SVG and PNG."
        return res
    if re.search(r"t-?shirt|tee|hoodie|merch|tote|mug|cap|apparel", what):
        c = Canvas(1920, 1080)
        bg, fg, soft = background(c, b, "light")
        for k, (x, shirt) in enumerate(((180, b.dark), (1020, "#FFFFFF"))):
            with c.group(transform=f"translate({x} 120) scale(7.2)"):
                c.path("M31 10L12 22L21 40L30 35V90H70V35L79 40L88 22L69 10C65 19 58 23 50 23C42 23 35 19 31 10Z", fill=shirt,
                       stroke=col.mix(b.ink, "#FFFFFF", 0.8), sw=0.4)
            sc = Scheme.full(b, shirt)
            draw_logo(c, b, "lockup" if k == 0 else "emblem", x + 250, 420, 220, 220, sc)
        c.fit_text(96, 960, 1700, 60, f"{b.name} merch: front print on dark and light garments", b.heading, max_size=40, fill=fg, max_lines=1)
        res.arts.append(Art(f"{b.name} - merch mockup", c.to_svg(), 1920, 1080, "Merch mockup", role="board", group="Presentation"))
        art = Canvas(3000, 3000)
        draw_logo(art, b, "emblem", 300, 300, 2400, 2400, Scheme.full(b, "#FFFFFF"))
        res.arts.append(Art(f"{b.name} - print file 3000x3000", art.to_svg(), 3000, 3000, "Print artwork (transparent, 3000x3000)", role="primary",
                            group="Print files", transparent=True, backdrop=b.paper))
        res.board = res.arts[0].name
        res.summary = f"Merch design for {b.name}: print-ready transparent artwork and garment mockups."
        return res
    if re.search(r"packag|label|box|bottle|jar|pouch|can\b|sticker", what):
        w, h = 1800, 1200
        c = Canvas(w, h)
        bg, fg, soft = background(c, b, b.theme)
        c.rect(60, 60, w - 120, h - 120, rx=30, stroke=b.accent if col.contrast(b.accent, bg) > 1.8 else fg, sw=6)
        c.rect(84, 84, w - 168, h - 168, rx=22, stroke=b.accent if col.contrast(b.accent, bg) > 1.8 else fg, sw=2)
        draw_logo(c, b, "emblem", w / 2 - 300, 150, 600, 600, Scheme.full(b, bg))
        c.fit_text(200, 800, w - 400, 160, job.headline(0), b.heading, max_size=90, min_size=40, fill=fg, align="center", max_lines=2)
        c.paragraph(200, 980, w - 400, job.sub(0), b.body, 34, fill=soft, align="center", max_lines=2)
        label_svg = c.to_svg()
        res.arts.append(Art(f"{b.name} - label front", label_svg, w, h, "Label / packaging front", role="primary", group="Packaging"))
        res.arts.insert(0, Art(f"{b.name} - packaging", _board(job, f"Packaging label for {b.name}", [(label_svg, w, h)]), 1920, 1080, "Overview board", role="board",
                               group="Presentation", svg_file=False))
        res.board = res.arts[0].name
        res.summary = f"Packaging label design for {b.name}."
        return res
    # general key visual in the formats people use most
    sizes = [(1920, 1080), (1080, 1080), (1080, 1920)]
    board = []
    for i, (w, h) in enumerate(sizes):
        c = Canvas(w, h)
        promo(c, job, headline=job.headline(0), sub=job.body(), cta=job.cta(), theme=b.theme, idx=0)
        svg = c.to_svg()
        board.append((svg, w, h))
        res.arts.append(Art(f"Key visual - {w}x{h}", svg, w, h, f"Key visual {w}x{h}", role="primary" if i == 0 else "variant", group="Key visual"))
    res.arts.insert(0, Art(f"{b.name} - key visual", _board(job, job.title or f"Custom design for {b.name}", board, sub=job.f("what")[:120]), 1920, 1080,
                           "Overview board", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    res.summary = f"Custom key visual for {b.name} in landscape, square and story formats."
    return res
