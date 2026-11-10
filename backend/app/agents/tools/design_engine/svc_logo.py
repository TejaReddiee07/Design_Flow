"""Logo Design: exactly three logo directions, perfectly centred (AI-generated when an image model is configured)."""
from __future__ import annotations

from typing import List

from app.agents.tools.design_engine import color as col
from app.agents.tools.design_engine.canvas import Canvas
from app.agents.tools.design_engine.common import Art, Job, Result, art_panel, background, brand_badge, corner_marks, label, pill
from app.agents.tools.design_engine.icons import draw_icon, rrect
from app.agents.tools.design_engine.marks import Scheme, draw_logo, icon_mark, logo_dims, logo_svg

W, H = 1920, 1080
MOTIF_NOUN = {
    "bean": "coffee bean", "cup": "coffee cup", "wheat": "wheat sheaf", "cutlery": "knife and fork", "chef": "chef's hat", "bolt": "lightning bolt",
    "nodes": "connected node", "dumbbell": "dumbbell", "flame": "flame", "lotus": "lotus", "drop": "droplet", "flower": "flower", "gem": "gem",
    "home": "house", "key": "key", "plus": "cross", "heart": "heart", "tooth": "tooth", "chart": "rising chart", "shield": "shield", "book": "open book",
    "grad": "mortarboard", "plane": "plane", "mountain": "mountain", "compass": "compass", "note": "music note", "wave": "wave", "paw": "paw print",
    "gear": "gear", "scales": "scales", "columns": "columns", "camera": "camera", "leaf": "leaf", "sprout": "sprout", "spark": "spark", "star": "star",
    "scissors": "scissors", "car": "car", "globe": "globe", "bag": "shopping bag", "pen": "pen nib", "megaphone": "megaphone", "shirt": "shirt",
    "rocket": "rocket",
}


def _uses(industry: str) -> str:
    i = industry.lower()
    if any(k in i for k in ("coffee", "bakery", "food")):
        return "cups, stamps, packaging and signage"
    if any(k in i for k in ("tech", "launch", "creative", "energy")):
        return "stickers, event merch, app badges and social avatars"
    if any(k in i for k in ("fashion", "jewel", "beauty", "barber")):
        return "labels, swing tags, packaging and shop windows"
    return "stamps, packaging, merchandise and signage"


def concept_order(job: Job) -> List[str]:
    t = job.f("logo_type").lower()
    st = job.b.style
    if t.startswith("emblem"):
        order = ["emblem", "lockup", "monogram"]
    elif t.startswith("icon +"):
        order = ["lockup", "emblem", "monogram"]
    elif t.startswith("wordmark"):
        order = ["wordmark", "lockup", "monogram"]
    elif t.startswith("icon only"):
        order = ["monogram", "emblem", "lockup"]
    else:
        order = {"Vintage": ["emblem", "lockup", "monogram"], "Luxury": ["monogram", "wordmark", "emblem"], "Bold": ["wordmark", "lockup", "emblem"],
                 "Playful": ["lockup", "wordmark", "emblem"]}.get(st, ["lockup", "monogram", "emblem"])
    # a re-work promotes the next direction unless the client asked for a specific logo type
    shift = (job.version - 1) % 3 if not t or t.startswith("not sure") else 0
    return order[shift:] + order[:shift]


def describe(job: Job, kind: str) -> tuple:
    b = job.b
    noun = MOTIF_NOUN.get(b.motif, "brand mark")
    return {
        "emblem": ("Heritage emblem", f"A circular badge with the name set around the ring and a {noun} at its heart. Made for {_uses(b.industry)}."),
        "lockup": ("Icon + wordmark", f"A compact {noun} mark beside a clean {b.heading.family} wordmark. Reads instantly at small sizes and scales up to signage."),
        "monogram": ("Monogram", f"The initials {b.initials} in a {b.style.lower()} frame with a spaced wordmark. Ideal for labels, social avatars and favicons."),
        "wordmark": ("Signature wordmark", f"The name itself is the logo, set in {(b.display if b.style in ('Luxury', 'Vintage') else b.heading).family} with a signature detail."),
    }[kind]


STYLE_WORDS = {
    "Luxury": "elegant, premium and refined, with a high-contrast serif or finely spaced capitals",
    "Vintage": "handcrafted and classic, heritage feel, confident serif lettering",
    "Modern": "modern and geometric, clean sans-serif lettering",
    "Minimal": "minimal and calm, lots of white space, light confident lettering",
    "Bold": "bold and confident, heavy lettering, strong silhouette",
    "Playful": "friendly and approachable, rounded shapes and lettering",
    "Corporate": "trustworthy and professional, clean balanced lettering",
}
DIRECTION = {
    "emblem": "a circular badge emblem: the name set around the ring, the symbol in the centre",
    "lockup": "a horizontal lockup: a compact symbol on the left, the wordmark on the right, tagline underneath",
    "monogram": "a monogram of the initials {initials} inside an elegant frame, with the full name underneath",
    "wordmark": "a custom typographic wordmark of the full name with one distinctive, memorable detail",
}
LOGO_SIZE = 2048


def logo_prompt(job: Job, kind: str, letter: str) -> str:
    """A precise brief for the image model, built only from what the client wrote and the agents decided."""
    b = job.b
    where = f" in {b.location}" if b.location else ""
    noun = MOTIF_NOUN.get(b.motif, "simple abstract mark")
    colours = ", ".join(f"{nm.lower()} {hx}" for nm, hx in b.palette if nm != "Secondary")
    avoid = "; ".join(b.avoid_phrases) or ""
    about = (job.f("about_and_wishes") or "")[:420]
    tag = f' and the tagline "{b.tagline}" in small spaced capitals underneath' if b.tagline else ""
    parts = [
        f'Professional logo design for "{b.name}", a {b.descriptor.lower()}{where}. Concept {letter}: {DIRECTION[kind].format(initials=b.initials)}.',
        f"Style: {STYLE_WORDS.get(b.style, STYLE_WORDS['Modern'])}.",
        f'Text: write the brand name exactly as "{b.name}"{tag}. Spell every word exactly as given and add no other words.',
        f"Symbol: a {noun}, simplified and iconic." if kind != "wordmark" else "",
        f"Colours: use only {colours}. Background: plain flat {b.paper}.",
        f"What the client said: {about}" if about else "",
        f"The client asked to avoid: {avoid}." if avoid else "",
        "Requirements: flat vector-style artwork with crisp clean edges, perfectly centred and balanced, generous empty margin on every side, "
        "works small on a cup and large on a sign, no mockup, no photograph, no 3D, no drop shadows, no extra text or watermark.",
    ]
    return " ".join(p for p in parts if p)


def _wants(job: Job, pattern: str) -> bool:
    import re as _re

    return bool(_re.search(pattern, " ".join([job.f("notes", "formats", "about_and_wishes"), " ".join(job.b.tweaks.notes)]), _re.I))


def render(job: Job) -> Result:
    """Exactly three logos (one per direction), each centred on a clean square canvas.
    AI-generated when an image model is configured, otherwise drawn by the vector engine.
    Extra formats only when the client asked for them (SVG, black-and-white)."""
    b = job.b
    res = Result()
    kinds = concept_order(job)
    ai = job.ctx.get("ai_image")
    made = []  # (kind, title, art)
    for i, kind in enumerate(kinds):
        letter = "ABC"[i]
        title, desc = describe(job, kind)
        label_txt = f"Logo {i + 1} - {title}"
        art = None
        if callable(ai):
            png = ai(logo_prompt(job, kind, letter))
            if png:
                from app.agents.tools.ai_images import recenter

                png, _ = recenter(png, canvas=LOGO_SIZE, fill=0.72, background=b.paper)
                art = Art(f"{b.name} - {label_txt}", "", LOGO_SIZE, LOGO_SIZE, label_txt, role="primary" if i == 0 else "variant",
                          group="Logos", png=png, svg_file=False)
        if art is None:
            c = Canvas(LOGO_SIZE, LOGO_SIZE, b.paper)
            pad = LOGO_SIZE * (0.2 if kind in ("emblem", "monogram") else 0.12)
            draw_logo(c, b, kind, pad, pad, LOGO_SIZE - 2 * pad, LOGO_SIZE - 2 * pad, Scheme.full(b, b.paper))
            art = Art(f"{b.name} - {label_txt}", c.to_svg(), LOGO_SIZE, LOGO_SIZE, label_txt, role="primary" if i == 0 else "variant", group="Logos",
                      svg_file=_wants(job, r"\bsvg\b|vector|\.ai\b|eps"), svg_role="variant")
        made.append((kind, title, desc, art))
        res.arts.append(art)

    if _wants(job, r"black[- ]and[- ]white|\bmono|one[- ]colou?r|b&w|greyscale|grayscale"):
        kind = kinds[0]
        c = Canvas(LOGO_SIZE, LOGO_SIZE, "#FFFFFF")
        pad = LOGO_SIZE * (0.2 if kind in ("emblem", "monogram") else 0.12)
        draw_logo(c, b, kind, pad, pad, LOGO_SIZE - 2 * pad, LOGO_SIZE - 2 * pad, Scheme.mono("#111111", "#FFFFFF"))
        res.arts.append(Art(f"{b.name} - Logo 1 - black and white", c.to_svg(), LOGO_SIZE, LOGO_SIZE, "Logo 1 - black and white", group="Logos",
                            svg_file=_wants(job, r"\bsvg\b|vector"), svg_role="variant"))

    # presentation board for the studio (not sent to the client): the three logos side by side, perfectly aligned
    from app.agents.tools.design_engine.svc_social import svg_href

    c = Canvas(W, H)
    background(c, b, "light")
    label(c, b, 96, 118, f"Three logo directions · {b.descriptor}", 18, b.primary if col.contrast(b.primary, b.paper) > 3 else b.ink)
    c.fit_text(96, 140, 1500, 86, b.name, b.heading, max_size=64, fill=b.ink, max_lines=1)
    gap, top = 40, 268
    cw = (W - 192 - 2 * gap) / 3
    for i, (kind, title, desc, art) in enumerate(made):
        x = 96 + i * (cw + gap)
        c.soft_shadow(x, top, cw, cw + 150, rx=22, dy=18, blur=40, color=b.dark, opacity=0.14)
        c.rect(x, top, cw, cw + 150, rx=22, fill="#FFFFFF")
        clip = c.clip_rect(x, top, cw, cw, 22)
        if art.png:
            import base64 as _b64

            c.image(x, top, cw, cw, "data:image/png;base64," + _b64.b64encode(art.png).decode(), clip=clip)
        else:
            c.image(x, top, cw, cw, svg_href(art.svg), clip=clip)
        c.text(x + 32, top + cw + 62, f"{i + 1}  ·  {title}", b.heading, 30, fill=b.ink)
        c.paragraph(x + 32, top + cw + 84, cw - 64, desc, b.body, 17, fill=b.muted, max_lines=2)
    res.arts.insert(0, Art(f"{b.name} - three logos", c.to_svg(), W, H, "Overview of the three logos", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    engine = "AI image model" if any(a.png for _, _, _, a in made) else "vector design engine"
    res.summary = (f"Three logo directions for {b.name}: {', '.join(t for _, t, _, _ in made)} (made with the {engine}), "
                   f"each a {LOGO_SIZE}x{LOGO_SIZE} PNG centred on {b.paper}.")
    return res


def guide_pages(job: Job, kind: str) -> List[tuple]:
    b = job.b
    pages = []
    on_paper = Scheme.full(b, b.paper)

    def header(c: Canvas, n: int, title: str, theme: str = "light") -> None:
        bg, fg, soft = background(c, b, theme)
        label(c, b, 96, 110, f"{n:02d}  ·  {title}", 18, b.primary if theme == "light" and col.contrast(b.primary, bg) > 3 else soft)
        c.text(W - 96, 110, f"{b.name} brand guidelines", b.label, 16, fill=soft, anchor="end", tracking=0.14, upper=True)

    # cover
    c = Canvas(W, H)
    background(c, b, "dark")
    rev = Scheme.full(b, b.dark)
    draw_logo(c, b, kind, 560, 250, 800, 440, rev)
    label(c, b, 96, 960, "Brand guidelines", 20, b.accent if col.contrast(b.accent, b.dark) > 3 else b.light)
    c.text(96, 1010, f"{b.name}  ·  version {job.version}", b.body, 22, fill=col.mix(b.light, b.dark, 0.3))
    pages.append(("Cover", c.to_svg()))

    # primary logo + rationale
    c = Canvas(W, H)
    header(c, 1, "Primary logo")
    c.rect(860, 170, 964, 760, rx=24, fill="#FFFFFF", filter=c.shadow(dy=14, blur=36, color=b.dark, opacity=0.1))
    draw_logo(c, b, kind, 940, 250, 804, 600, on_paper)
    title, desc = describe(job, kind)
    c.fit_text(96, 200, 680, 140, title, b.heading, max_size=64, fill=b.ink, max_lines=2)
    y = 380
    y += c.paragraph(96, y, 660, desc, b.body, 24, fill=b.muted, max_lines=5)
    why = job.concept.get("rationale") or job.business_line()
    if why:
        c.paragraph(96, y + 34, 660, str(why), b.body, 22, fill=b.muted, max_lines=6)
    pages.append(("Primary logo", c.to_svg()))

    # variations
    c = Canvas(W, H)
    header(c, 2, "Logo variations")
    tiles = [("Full colour", "#FFFFFF", Scheme.full(b, "#FFFFFF")), ("Reversed", b.dark, Scheme.full(b, b.dark)),
             ("One colour", b.light if col.luminance(b.light) > 0.6 else "#F2F2F2", Scheme.mono(b.dark, "none")),
             ("On brand colour", b.primary, Scheme(text=b.on(b.primary), sub=b.soft_on(b.primary), mark_bg=b.on(b.primary), mark_fg=b.primary, line=b.on(b.primary), accent=b.accent))]
    tw, th = (W - 192 - 32) / 2, 360
    for i, (nm, bg, sc) in enumerate(tiles):
        x = 96 + (i % 2) * (tw + 32)
        y = 170 + (i // 2) * (th + 52)
        c.rect(x, y, tw, th, rx=18, fill=bg, stroke=col.mix(b.ink, b.paper, 0.88) if bg == "#FFFFFF" else None, sw=1.5)
        draw_logo(c, b, kind, x + 70, y + 40, tw - 140, th - 80, sc)
        c.text(x, y + th + 34, nm, b.label, 16, fill=b.muted, tracking=0.14, upper=True)
    pages.append(("Logo variations", c.to_svg()))

    # clear space + minimum size
    c = Canvas(W, H)
    header(c, 3, "Clear space & minimum size")
    bx, by, bw, bh = 160, 230, 980, 620
    c.rect(bx, by, bw, bh, rx=18, fill="#FFFFFF")
    pad = 110
    c.rect(bx + pad, by + pad, bw - 2 * pad, bh - 2 * pad, stroke=b.primary, sw=2, extra='stroke-dasharray="10 10"')
    draw_logo(c, b, kind, bx + pad + 40, by + pad + 40, bw - 2 * pad - 80, bh - 2 * pad - 80, on_paper)
    for (x1, y1, x2, y2) in ((bx, by + bh / 2, bx + pad, by + bh / 2), (bx + bw - pad, by + bh / 2, bx + bw, by + bh / 2),
                             (bx + bw / 2, by, bx + bw / 2, by + pad), (bx + bw / 2, by + bh - pad, bx + bw / 2, by + bh)):
        c.line(x1, y1, x2, y2, stroke=b.accent, sw=3)
    c.text(bx + pad / 2, by + bh / 2 - 14, "x", b.heading, 30, fill=b.accent, anchor="middle")
    tx = 1240
    c.fit_text(tx, 240, 580, 120, "Give the logo room to breathe", b.heading, max_size=46, fill=b.ink, max_lines=2)
    c.paragraph(tx, 390, 560, "Keep a clear space of at least x around the logo on every side, where x equals the height of the icon. "
                "Never place text, edges or other graphics inside this area.", b.body, 22, fill=b.muted, max_lines=6)
    c.text(tx, 640, "Minimum size", b.label, 18, fill=b.ink, tracking=0.16, upper=True)
    c.paragraph(tx, 670, 560, "Print: 25 mm wide.  Screen: 120 px wide.  Below this size use the icon on its own.", b.body, 22, fill=b.muted, max_lines=3)
    pages.append(("Clear space", c.to_svg()))

    # colour palette
    c = Canvas(W, H)
    header(c, 4, "Colour palette")
    n = len(b.palette)
    sw_ = (W - 192 - 24 * (n - 1)) / n
    for i, (nm, hx) in enumerate(b.palette):
        x = 96 + i * (sw_ + 24)
        c.rect(x, 170, sw_, 560, rx=18, fill=hx, stroke=col.mix(b.ink, b.paper, 0.86) if col.luminance(hx) > 0.85 else None, sw=1.5)
        fg = col.readable_on(hx, "#FFFFFF", "#141414")
        c.text(x + 30, 230, nm, b.heading, 30, fill=fg)
        r, g, bl = col.rgb255(hx)
        cc, mm, yy, kk = col.cmyk(hx)
        rows = [("HEX", hx), ("RGB", f"{r} {g} {bl}"), ("CMYK", f"{cc} {mm} {yy} {kk}")]
        for j, (k, v) in enumerate(rows):
            c.text(x + 2, 790 + j * 52, k, b.label, 16, fill=b.muted, tracking=0.14)
            c.text(x + 92, 790 + j * 52, v, b.body_bold, 20, fill=b.ink)
    c.paragraph(96, 970, 1400, "Use the primary colour for the logo and key actions, the dark tone for text, the light tone for backgrounds and the accent sparingly to highlight.",
                b.body, 20, fill=b.muted, max_lines=2)
    pages.append(("Colour palette", c.to_svg()))

    # typography
    c = Canvas(W, H)
    header(c, 5, "Typography")
    hf, bf = b.display if b.style in ("Luxury", "Vintage") else b.heading, b.body
    c.text(96, 520, "Aa", hf, 330, fill=b.primary if col.contrast(b.primary, b.paper) > 2.5 else b.ink)
    c.text(96, 610, f"{hf.family}", b.heading, 40, fill=b.ink)
    c.text(96, 650, "Headings and display", b.label, 16, fill=b.muted, tracking=0.16, upper=True)
    c.text(96, 740, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", hf, 38, fill=b.ink, tracking=0.04)
    c.text(96, 800, "abcdefghijklmnopqrstuvwxyz 0123456789", hf, 38, fill=b.ink)
    x2 = 1040
    c.rect(x2 - 40, 170, 1, 760, fill=col.mix(b.ink, b.paper, 0.85))
    c.text(x2, 250, f"{bf.family}", b.heading, 40, fill=b.ink)
    c.text(x2, 290, "Body copy and interface", b.label, 16, fill=b.muted, tracking=0.16, upper=True)
    sample = job.business_line() or f"{b.name} brings {b.descriptor.lower()} to life with care, consistency and character."
    c.paragraph(x2, 350, 780, sample + " The quick brown fox jumps over the lazy dog.", bf, 30, fill=b.ink, line_height=1.5, max_lines=5)
    c.text(x2, 640, "Hierarchy", b.label, 16, fill=b.muted, tracking=0.16, upper=True)
    c.text(x2, 720, "Headline 64", hf, 64, fill=b.ink)
    c.text(x2, 790, "Subheading 34", b.body_bold, 34, fill=b.ink)
    c.text(x2, 840, "Body text 20 / 150% line height", bf, 20, fill=b.muted)
    pages.append(("Typography", c.to_svg()))

    # brand in use (mockups)
    c = Canvas(W, H)
    header(c, 6, "Brand in use", theme="light")
    # business cards
    cw, chh = 520, 316
    sh = c.shadow(dy=22, blur=40, color="#000000", opacity=0.22)
    c.rect(96, 190, 820, 700, rx=24, fill=col.mix(b.dark, b.primary, 0.25))
    c.grain(0.08, 96, 190, 820, 700)
    with c.group(transform="rotate(-6 380 420)"):
        c.rect(150, 300, cw, chh, rx=10, fill=b.primary, filter=sh)
        draw_logo(c, b, kind, 190, 330, cw - 80, chh - 60, Scheme(text=b.on(b.primary), sub=b.soft_on(b.primary), mark_bg=b.on(b.primary), mark_fg=b.primary,
                                                                  line=b.on(b.primary), accent=b.accent))
    with c.group(transform="rotate(4 620 650)"):
        c.rect(360, 520, cw, chh, rx=10, fill=b.paper, filter=sh)
        icon_mark(c, b, 400, 560, 70, on_paper, monogram=(kind == "monogram"))
        who = job.ctx.get("client") or {}
        c.text(400, 700, who.get("contact_name") or b.name, b.heading, 34, fill=b.ink)
        c.text(400, 734, "Founder" if who.get("contact_name") else b.descriptor, b.label, 16, fill=b.muted, tracking=0.16, upper=True)
        rows = [r for r in (("mail", who.get("email")), ("web", b.website), ("pin", b.location)) if r[1]][:2]
        for j, (ic, t) in enumerate(rows):
            draw_icon(c, ic, 400, 768 + j * 30 - 14, 18, b.primary)
            c.text(428, 768 + j * 30, t, b.body, 17, fill=b.ink)
    # social avatar + tote
    c.rect(960, 190, 864, 330, rx=24, fill="#FFFFFF")
    c.circle(1090, 355, 105, fill=b.primary)
    icon_mark(c, b, 1030, 295, 120, Scheme(text=b.light, sub=b.light, mark_bg=b.light, mark_fg=b.primary, line=b.light, accent=b.accent),
              monogram=(kind == "monogram"))
    c.text(1230, 330, b.name, b.heading, 34, fill=b.ink)
    c.text(1230, 372, b.handle or b.tagline or b.descriptor, b.body, 22, fill=b.muted)
    c.text(1230, 420, "Social profile", b.label, 15, fill=b.muted, tracking=0.16, upper=True)
    # sign
    c.rect(960, 560, 864, 330, rx=24, fill=col.mix(b.light, "#FFFFFF", 0.4))
    c.line(1240, 560, 1240, 600, stroke=b.dark, sw=4)
    c.line(1540, 560, 1540, 600, stroke=b.dark, sw=4)
    c.rect(1150, 600, 480, 250, rx=16, fill=b.dark, filter=c.shadow(dy=16, blur=30, color="#000", opacity=0.25))
    draw_logo(c, b, kind, 1180, 620, 420, 210, Scheme.full(b, b.dark))
    c.text(990, 870, "Signage", b.label, 15, fill=b.muted, tracking=0.16, upper=True)
    pages.append(("Brand in use", c.to_svg()))
    return pages
