"""Pitch decks and presentations: 16:9 slides (PNG + SVG) and a PDF of the whole deck."""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.agents.tools.design_engine import color as col
from app.agents.tools.design_engine.canvas import Canvas, _n
from app.agents.tools.design_engine.common import (Art, Job, Result, art_panel, background, bar_chart, brand_badge, bullets, dots, initials_avatar,
                                                   label, pill, sparkle)
from app.agents.tools.design_engine.icons import draw_icon
from app.agents.tools.design_engine.marks import Scheme, draw_logo
from app.agents.tools.design_engine.svc_social import _board

W, H = 1920, 1080
M = 120


class Deck:
    def __init__(self, job: Job, title: str) -> None:
        self.job = job
        self.b = job.b
        self.title = title
        self.slides: List[Tuple[str, str]] = []
        self.total = 0

    # frame shared by content slides
    def frame(self, section: str, theme: str = "light") -> Tuple[Canvas, str, str, str]:
        c = Canvas(W, H)
        bg, fg, soft = background(c, self.b, theme)
        acc = self.acc(bg)
        label(c, self.b, M, 118, section, 20, acc)
        n = len(self.slides) + 1
        c.text(W - M, H - 64, f"{n:02d}", self.b.label, 20, fill=soft, anchor="end", tracking=0.14)
        brand_badge(c, self.b, M, H - 92, 40, bg)
        c.line(M, H - 120, W - M, H - 120, stroke=soft, sw=1, opacity=0.25)
        return c, bg, fg, soft

    def acc(self, bg: str) -> str:
        b = self.b
        return b.primary if col.contrast(b.primary, bg) > 2.6 else b.accent if col.contrast(b.accent, bg) > 2.6 else b.on(bg)

    def add(self, name: str, c: Canvas) -> None:
        self.slides.append((name, c.to_svg()))

    def heading(self, c: Canvas, text: str, fg: str, *, y: float = 150, w: float = W - 2 * M, max_size: float = 76) -> float:
        return c.fit_text(M, y, w, 190, text, self.b.heading, max_size=max_size * self.b.tweaks.headline_scale, min_size=36, fill=fg, max_lines=2,
                          line_height=1.04)[1]


def _slides_from_content(job: Job) -> List[Dict[str, Any]]:
    raw = job.content.get("slides") or []
    out = []
    if isinstance(raw, list):
        for s in raw:
            if isinstance(s, dict) and s.get("title"):
                bl = s.get("bullets") or s.get("points") or []
                out.append({"title": str(s["title"])[:90], "bullets": [str(x)[:140] for x in bl if x][:5] if isinstance(bl, list) else [],
                            "kind": str(s.get("kind") or s.get("type") or "").lower(), "body": str(s.get("body") or "")[:300]})
    return out


def _find(slides: List[Dict[str, Any]], *keys: str) -> Optional[Dict[str, Any]]:
    for s in slides:
        t = (s["title"] + " " + s.get("kind", "")).lower()
        if any(k in t for k in keys):
            return s
    return None


def _money(text: str) -> str:
    m = re.search(r"(£|\$|€|₹)\s?\d+(?:[.,]\d+)?\s?(k|m|bn|million|thousand)?", text or "", re.I)
    return m.group(0).replace(" ", "") if m else ""


def render_pitch(job: Job) -> Result:
    b = job.b
    d = Deck(job, f"{b.name} - pitch deck")
    content = _slides_from_content(job)
    n = job.number("slide_count", 10, 6, 14)
    stage = job.f("stage") or "Seed"
    about = job.business_line() or job.sub(0)
    contact = job.ctx.get("client") or {}

    # 1 cover
    c = Canvas(W, H)
    bg, fg, soft = background(c, b, "dark")
    art_panel(c, b, W * 0.56, 0, W * 0.44 + 2, H, seed=job.request_id, icon_scale=0.42)
    draw_logo(c, b, "lockup", M, 170, 760, 170, Scheme.full(b, bg))
    c.fit_text(M, 470, 900, 220, job.headline(0) if job.content.get("headlines") else (b.tagline or about), b.heading, max_size=84, min_size=40, fill=fg, max_lines=3)
    label(c, b, M, 820, f"{stage} · investor presentation", 22, b.accent if col.contrast(b.accent, bg) > 2.4 else soft)
    c.text(M, 870, datetime.utcnow().strftime("%B %Y"), b.body, 24, fill=soft)
    d.add("Cover", c)

    # 2 problem
    s = _find(content, "problem", "challenge", "pain")
    c, bg, fg, soft = d.frame("The problem")
    d.heading(c, s["title"] if s else "The problem we solve", fg)
    statement = (s or {}).get("body") or job.f("audience") or about
    c.paragraph(M, 330, 1100, statement, b.body, 34, fill=soft, max_lines=3, line_height=1.4)
    insights = [str(x) for x in (job.strategy.get("audience_insights") or []) if x] if isinstance(job.strategy.get("audience_insights"), list) else []
    pains = (s or {}).get("bullets") or insights[:3] or job.points(3)
    cw = (W - 2 * M - 2 * 40) / 3
    for i, p in enumerate(pains[:3]):
        x = M + i * (cw + 40)
        c.rect(x, 540, cw, 360, rx=max(8, b.radius), fill="#FFFFFF" if bg != "#FFFFFF" else col.mix(b.light, "#FFFFFF", 0.3),
               filter=c.shadow(dy=10, blur=28, color=b.dark, opacity=0.08))
        c.text(x + 44, 630, f"0{i + 1}", b.heading, 56, fill=d.acc(bg))
        c.paragraph(x + 44, 680, cw - 88, p, b.body, 32, fill=fg, max_lines=5, line_height=1.35)
    d.add("Problem", c)

    # 3 solution
    s = _find(content, "solution", "product", "what we do")
    c, bg, fg, soft = d.frame("Our solution")
    art_panel(c, b, W * 0.54, 170, W * 0.46 - M, 740, rx=max(10, b.radius * 1.5), photo=0, seed=job.request_id + 3, icon_scale=0.4)
    d.heading(c, s["title"] if s else f"Introducing {b.name}", fg, w=W * 0.5 - M)
    c.paragraph(M, 400, W * 0.46 - M, (s or {}).get("body") or job.body(), b.body, 30, fill=soft, max_lines=4, line_height=1.45)
    bullets(c, b, M, 600, W * 0.46 - M, (s or {}).get("bullets") or job.points(3), 26, fg, d.acc(bg), icon="check", max_lines=2)
    d.add("Solution", c)

    # 4 how it works
    s = _find(content, "how it works", "process", "how")
    c, bg, fg, soft = d.frame("How it works")
    d.heading(c, s["title"] if s else "How it works", fg)
    steps = (s or {}).get("bullets") or ["Tell us what you need", f"{b.name} gets to work", "You see the results"]
    k = min(4, len(steps))
    sw = (W - 2 * M - (k - 1) * 60) / k
    for i, st in enumerate(steps[:k]):
        x = M + i * (sw + 60)
        c.circle(x + 60, 470, 60, fill=d.acc(bg))
        c.text(x + 60, 470 + b.heading.cap(48) / 2, str(i + 1), b.heading, 48, fill=col.readable_on(d.acc(bg), "#FFFFFF", b.dark), anchor="middle")
        if i < k - 1:
            c.line(x + 140, 470, x + sw + 40, 470, stroke=soft, sw=3, dash="2 10")
        c.paragraph(x, 580, sw - 20, st, b.body_bold, 30, fill=fg, max_lines=3, line_height=1.3)
    d.add("How it works", c)

    # 5 market
    s = _find(content, "market", "opportunity", "audience")
    c, bg, fg, soft = d.frame("Market opportunity")
    d.heading(c, s["title"] if s else "A large, reachable market", fg, w=820)
    cx, cy = 1320, 560
    rings = [(330, "Total market", col.mix(b.primary, bg, 0.8)), (230, "Serviceable market", col.mix(b.primary, bg, 0.55)), (120, "Our 3-year target", b.primary)]
    vals = (s or {}).get("bullets") or []
    for i, (r, lab, fill) in enumerate(rings):
        c.circle(cx, cy - (330 - r) * 0.9 + 0, r, fill=fill)
    for i, (r, lab, fill) in enumerate(rings):
        ly = 420 + i * 150
        c.circle(M + 14, ly - 8, 14, fill=fill)
        c.text(M + 50, ly, lab, b.body_bold, 30, fill=fg)
        c.paragraph(M + 50, ly + 22, 760, vals[i] if i < len(vals) else ["Everyone who buys " + b.descriptor.lower(), f"Customers {b.name} can reach today", "Our focus segment"][i],
                    b.body, 24, fill=soft, max_lines=2)
    d.add("Market", c)

    # 6 business model
    s = _find(content, "business model", "revenue", "pricing", "model")
    c, bg, fg, soft = d.frame("Business model")
    d.heading(c, s["title"] if s else "How we make money", fg)
    streams = (s or {}).get("bullets") or ["Direct sales", "Repeat customers", "Partnerships"]
    cw = (W - 2 * M - 2 * 40) / 3
    for i, st in enumerate(streams[:3]):
        x = M + i * (cw + 40)
        hi = i == 1
        c.rect(x, 380 - (30 if hi else 0), cw, 480 + (30 if hi else 0), rx=max(10, b.radius * 1.2), fill=b.primary if hi else "#FFFFFF",
               filter=c.shadow(dy=12, blur=30, color=b.dark, opacity=0.1))
        tc = b.on(b.primary) if hi else fg
        draw_icon(c, ["bag", "repeat" if "repeat" in st.lower() else "users", "target"][i % 3] if False else ["bag", "users", "target"][i % 3], x + 44, 420, 70, tc)
        c.paragraph(x + 44, 540, cw - 88, st, b.body_bold, 32, fill=tc, max_lines=3)
    d.add("Business model", c)

    # 7 roadmap / traction
    s = _find(content, "traction", "roadmap", "milestone", "growth")
    c, bg, fg, soft = d.frame("Roadmap")
    d.heading(c, s["title"] if s else "Where we are going", fg)
    ms = (s or {}).get("bullets") or ["Launch and first customers", "Prove repeatable sales", "Expand the offer", "Scale nationally"]
    k = min(5, len(ms))
    c.line(M, 560, W - M, 560, stroke=soft, sw=3, opacity=0.4)
    seg = (W - 2 * M) / k
    for i, mtxt in enumerate(ms[:k]):
        x = M + seg * i + seg / 2
        done = i == 0
        c.circle(x, 560, 22, fill=d.acc(bg) if done else bg, stroke=d.acc(bg), sw=5)
        c.text(x, 480, f"Stage {i + 1}", b.label, 20, fill=d.acc(bg), anchor="middle", tracking=0.16, upper=True)
        c.paragraph(x - seg / 2 + 20, 620, seg - 40, mtxt, b.body_bold, 28, fill=fg, align="center", max_lines=3)
    d.add("Roadmap", c)

    # 8 competition matrix
    c, bg, fg, soft = d.frame("Competitive landscape")
    d.heading(c, "Why we win", fg, w=760)
    comp = job.strategy.get("competitor_notes")
    comp_txt = " ".join(map(str, comp))[:300] if isinstance(comp, list) and comp else (str(comp)[:300] if comp else job.sub(0))
    c.paragraph(M, 360, 700, comp_txt, b.body, 28, fill=soft, max_lines=6)
    bx, by, bw, bh = 1000, 190, 760, 720
    c.rect(bx, by, bw, bh, rx=16, fill="#FFFFFF" if col.luminance(bg) > 0.5 else col.lighten(bg, 0.06))
    c.line(bx + bw / 2, by + 40, bx + bw / 2, by + bh - 40, stroke=soft, sw=2, opacity=0.5)
    c.line(bx + 40, by + bh / 2, bx + bw - 40, by + bh / 2, stroke=soft, sw=2, opacity=0.5)
    c.text(bx + bw - 50, by + bh / 2 - 16, "More specialised", b.label, 16, fill=soft, anchor="end", tracking=0.1, upper=True)
    c.text(bx + bw / 2 + 14, by + 64, "Better experience", b.label, 16, fill=soft, tracking=0.1, upper=True)
    for (px, py, lab) in ((0.28, 0.7, "Large incumbents"), (0.32, 0.3, "DIY tools"), (0.7, 0.72, "Local agencies")):
        c.circle(bx + bw * px, by + bh * py, 16, fill=soft, opacity=0.6)
        c.text(bx + bw * px, by + bh * py + 46, lab, b.body, 20, fill=soft, anchor="middle")
    c.circle(bx + bw * 0.76, by + bh * 0.24, 34, fill=d.acc(bg))
    c.text(bx + bw * 0.76, by + bh * 0.24 + 74, b.name, b.body_bold, 24, fill=fg, anchor="middle")
    d.add("Competition", c)

    # 9 team
    c, bg, fg, soft = d.frame("Team")
    d.heading(c, "The team", fg)
    team = [(contact.get("contact_name") or "Founder", "Founder")] + [("Key hire", "Head of Product"), ("Key hire", "Head of Growth")]
    cw = (W - 2 * M - 2 * 40) / 3
    for i, (nm, role) in enumerate(team):
        x = M + i * (cw + 40)
        c.rect(x, 360, cw, 500, rx=max(10, b.radius), fill="#FFFFFF" if col.luminance(bg) > 0.5 else col.lighten(bg, 0.06))
        initials_avatar(c, b, x + cw / 2, 500, 90, nm if i == 0 else role, b.primary if i == 0 else col.mix(b.primary, bg, 0.5))
        c.text(x + cw / 2, 680, nm if i == 0 else role, b.body_bold, 32, fill=fg, anchor="middle")
        c.text(x + cw / 2, 724, role if i == 0 else "Hiring now", b.label, 18, fill=soft, anchor="middle", tracking=0.16, upper=True)
    d.add("Team", c)

    # 10 ask
    c, bg, fg, soft = d.frame("The ask", theme="brand")
    amount = _money(" ".join([job.f("about_and_wishes"), job.f("notes")]))
    c.fit_text(M, 220, W - 2 * M, 220, f"Raising {amount}" if amount else f"Our {stage.lower()} round", b.heading, max_size=130, min_size=60, fill=fg, max_lines=1)
    alloc = [("Product", 40), ("Growth", 35), ("Operations", 25)]
    x0, total_w = M, W - 2 * M
    xx = x0
    shades = [b.light, col.mix(b.light, b.primary, 0.4), col.mix(b.light, b.primary, 0.7)]
    for i, (lab, pct) in enumerate(alloc):
        ww = total_w * pct / 100
        c.rect(xx, 560, ww - 8, 70, rx=10, fill=shades[i])
        c.text(xx, 690, f"{pct}%", b.heading, 54, fill=fg)
        c.text(xx, 734, lab, b.label, 20, fill=soft, tracking=0.16, upper=True)
        xx += ww
    c.text(M, 840, "Proposed use of funds", b.body, 24, fill=soft)
    d.add("The ask", c)

    # 11 contact
    c = Canvas(W, H)
    bg, fg, soft = background(c, b, "dark")
    draw_logo(c, b, "lockup", 460, 300, 1000, 260, Scheme.full(b, bg))
    c.text(W / 2, 700, "Thank you", b.heading, 72, fill=fg, anchor="middle")
    info = " · ".join(x for x in (contact.get("email"), b.website) if x)
    if info:
        c.text(W / 2, 780, info, b.body, 28, fill=soft, anchor="middle")
    d.add("Thank you", c)

    order = ["Cover", "Problem", "Solution", "How it works", "Market", "Business model", "Roadmap", "Competition", "Team", "The ask", "Thank you"]
    keep = order if n >= len(order) else (order[: n - 1] + ["Thank you"])
    slides = [(nm, svg) for nm, svg in d.slides if nm in keep]
    return _deck_result(job, slides, f"{b.name} - pitch deck", f"{len(slides)}-slide {stage.lower()} pitch deck for {b.name}")


def render_presentation(job: Job) -> Result:
    b = job.b
    d = Deck(job, f"{b.name} - presentation")
    content = _slides_from_content(job)
    purpose = job.f("purpose") or "Presentation"
    title = job.title.replace("Presentation for", "").strip() or f"{b.name} {purpose.lower()}"
    agenda = [s["title"] for s in content[:5]] or job.points(4)

    c = Canvas(W, H)
    bg, fg, soft = background(c, b, "dark")
    art_panel(c, b, W * 0.6, 120, W * 0.4 - M, H - 240, rx=max(12, b.radius * 1.5), seed=job.request_id, icon_scale=0.4)
    brand_badge(c, b, M, 110, 56, bg)
    c.fit_text(M, 360, W * 0.5, 300, job.headline(0) if job.content.get("headlines") else title, b.heading, max_size=96, min_size=44, fill=fg, max_lines=3)
    label(c, b, M, 760, purpose, 22, b.accent if col.contrast(b.accent, bg) > 2.4 else soft)
    c.text(M, 810, datetime.utcnow().strftime("%d %B %Y"), b.body, 24, fill=soft)
    d.add("Title", c)

    c, bg, fg, soft = d.frame("Agenda")
    d.heading(c, "Agenda", fg)
    for i, a in enumerate(agenda[:5]):
        y = 360 + i * 110
        c.text(M, y + 34, f"{i + 1:02d}", b.heading, 44, fill=d.acc(bg))
        c.paragraph(M + 120, y, 1300, a, b.body_bold, 34, fill=fg, max_lines=1)
        c.line(M, y + 70, W - M, y + 70, stroke=soft, sw=1, opacity=0.3)
    d.add("Agenda", c)

    c = Canvas(W, H)
    bg, fg, soft = background(c, b, "brand")
    c.text(M, 520, "01", b.heading, 260, fill=fg, opacity=0.25)
    c.fit_text(M, 560, W - 2 * M, 220, agenda[0] if agenda else "Section title", b.heading, max_size=110, min_size=50, fill=fg, max_lines=2)
    d.add("Section divider", c)

    s = content[0] if content else None
    c, bg, fg, soft = d.frame(agenda[0] if agenda else "Overview")
    d.heading(c, s["title"] if s else job.headline(1 if len(job.headlines()) > 1 else 0), fg, w=W * 0.5)
    bullets(c, b, M, 400, W * 0.48, (s or {}).get("bullets") or job.points(4), 30, fg, d.acc(bg), icon="check", max_lines=2)
    art_panel(c, b, W * 0.56, 170, W * 0.44 - M, 740, rx=max(10, b.radius * 1.5), photo=0, seed=job.request_id + 5, icon_scale=0.4)
    d.add("Content", c)

    c, bg, fg, soft = d.frame("Comparison")
    d.heading(c, "Before and after", fg)
    cw = (W - 2 * M - 60) / 2
    for i, (head, items) in enumerate((("Today", job.points(3)), (f"With {b.name}", job.subs()[:3] or job.points(3)))):
        x = M + i * (cw + 60)
        hi = i == 1
        c.rect(x, 330, cw, 560, rx=max(10, b.radius), fill=b.primary if hi else ("#FFFFFF" if col.luminance(bg) > 0.5 else col.lighten(bg, 0.06)))
        tc = b.on(b.primary) if hi else fg
        c.text(x + 50, 410, head, b.heading, 40, fill=tc)
        bullets(c, b, x + 50, 470, cw - 100, items, 26, tc, b.accent if hi else d.acc(bg), icon="check" if hi else "arrow", max_lines=3)
    d.add("Two columns", c)

    c, bg, fg, soft = d.frame("Key number")
    num = re.search(r"\d+(?:[.,]\d+)?\s?%|\d+x|\d{2,}", " ".join([job.f("notes", "about_and_wishes", "copy_text")]))
    c.fit_text(M, 260, W - 2 * M, 360, num.group(0) if num else "3x", b.heading, max_size=360, min_size=120, fill=d.acc(bg), max_lines=1)
    c.paragraph(M, 680, 1200, job.sub(0), b.body, 36, fill=fg, max_lines=2)
    if not num:
        c.text(M, 840, "Replace with your own figure", b.label, 18, fill=soft, tracking=0.14, upper=True)
    d.add("Big number", c)

    c, bg, fg, soft = d.frame("Results")
    d.heading(c, "Results at a glance", fg)
    vals, labs = [42, 58, 71, 88], ["Q1", "Q2", "Q3", "Q4"]
    bar_chart(c, b, M, 330, W - 2 * M - 500, 560, vals, labs, color=col.mix(b.primary, bg, 0.45), text=fg, grid=col.mix(fg, bg, 0.75), highlight=3, accent=d.acc(bg))
    c.paragraph(W - M - 420, 400, 420, "Sample data shown. The chart is fully editable: replace the values with your own.", b.body, 24, fill=soft, max_lines=5)
    d.add("Chart", c)

    c = Canvas(W, H)
    bg, fg, soft = background(c, b, "light")
    draw_icon(c, "quote", M, 220, 140, d.acc(bg))
    c.fit_text(M, 420, W - 2 * M, 330, job.business_line() or job.sub(0), b.display if b.style in ("Luxury", "Vintage") else b.heading, max_size=78,
               min_size=36, fill=fg, max_lines=4)
    c.text(M, 860, b.name, b.label, 22, fill=soft, tracking=0.2, upper=True)
    d.add("Quote", c)

    c = Canvas(W, H)
    bg, fg, soft = background(c, b, "dark")
    draw_logo(c, b, "lockup", 460, 300, 1000, 260, Scheme.full(b, bg))
    c.text(W / 2, 700, "Thank you", b.heading, 72, fill=fg, anchor="middle")
    c.text(W / 2, 770, "Questions?", b.body, 30, fill=soft, anchor="middle")
    d.add("Closing", c)

    n = job.number("slide_count", 9, 6, 14)
    slides = d.slides[: max(6, min(n, len(d.slides)) - 1)] + [d.slides[-1]] if n < len(d.slides) else d.slides
    return _deck_result(job, slides, f"{b.name} - presentation", f"{len(slides)}-slide {purpose.lower()} deck and master layouts for {b.name}")


def _deck_result(job: Job, slides: List[Tuple[str, str]], pdf_name: str, summary: str) -> Result:
    res = Result()
    for i, (nm, svg) in enumerate(slides, 1):
        res.arts.append(Art(f"Slide {i:02d} - {nm}", svg, W, H, f"Slide {i}: {nm}", role="primary" if i == 1 else "page", group="Slides", pdf=pdf_name))
    res.pdfs[pdf_name] = 144
    res.arts.insert(0, Art(f"{job.b.name} - deck overview", _board(job, pdf_name.split(" - ", 1)[-1].capitalize() + f" for {job.b.name}",
                                                                [(svg, W, H) for _, svg in slides[:9]], cols=3, sub=f"{len(slides)} slides · 16:9 · PDF + PNG + SVG"),
                           W, H, "Deck overview", role="board", group="Presentation", svg_file=False))
    res.board = res.arts[0].name
    outline = "\n".join(f"{i}. {nm}" for i, (nm, _) in enumerate(slides, 1))
    res.texts.append(("Deck outline and notes.md", f"# {pdf_name}\n\n{outline}\n\nCopy on the slides comes from your brief and the Content Agent. "
                      "Replace any figures marked as sample data with your own before sending.\n"))
    res.summary = summary + " (PDF + PNG + SVG slides)."
    return res
