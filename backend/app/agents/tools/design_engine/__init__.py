"""Designflow design engine.

Turns a request (the client's brief, brand assets, uploaded photos, the agents' strategy/copy/concept and any
feedback) into finished, service-specific deliverables: SVG + PNG files, multi-page PDFs and a ZIP package.

    from app.agents.tools.design_engine import generate
    out = generate(ctx)   # -> Output(files=[OutFile...], board=OutFile, summary=str)

ctx keys: request_id, version, service_slug, service_name, title, description, brief, client {company_name,
website, industry, brand_notes}, content, strategy, concept, feedback [str], logo_href, photos [data URI],
asset_colors [hex], scale (float, <1 for fast test renders).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.agents.tools.design_engine import export
from app.agents.tools.design_engine.brand import build as build_brand
from app.agents.tools.design_engine.common import Art, Job, Result

log = logging.getLogger("design_engine")


@dataclass
class OutFile:
    name: str  # with extension
    data: bytes
    mime: str
    role: str  # board | primary | variant | page | package | notes
    label: str
    format: str
    width: int = 0
    height: int = 0
    page: Optional[int] = None
    group: str = ""
    thumb: Optional[bytes] = None


@dataclass
class Output:
    files: List[OutFile] = field(default_factory=list)
    board: Optional[OutFile] = None
    summary: str = ""
    brand: Dict[str, Any] = field(default_factory=dict)


def _renderer(slug: str) -> Callable[[Job], Result]:
    from app.agents.tools.design_engine import svc_logo

    table: Dict[str, Callable[[Job], Result]] = {"logo-design": svc_logo.render}
    try:
        from app.agents.tools.design_engine import svc_social, svc_print, svc_decks, svc_misc

        table.update({
            "social-media-design": svc_social.render_posts, "instagram-post-design": svc_social.render_posts,
            "linkedin-carousel-design": svc_social.render_carousel, "reels-cover-design": svc_social.render_reels,
            "youtube-thumbnail-design": svc_social.render_thumbnails, "ad-creative-design": svc_social.render_ads,
            "website-banner-design": svc_misc.render_banners, "ecommerce-creative-design": svc_misc.render_ecommerce,
            "product-advertisement-design": svc_misc.render_product_ad, "custom-design-requests": svc_misc.render_custom,
            "pitch-deck-design": svc_decks.render_pitch, "presentation-design": svc_decks.render_presentation,
            "brochure-design": svc_print.render_brochure, "flyer-design": svc_print.render_flyer, "poster-design": svc_print.render_poster,
            "infographic-design": svc_print.render_infographic, "business-card-design": svc_print.render_business_card,
            "company-profile-design": svc_print.render_company_profile,
        })
    except ImportError as exc:  # pragma: no cover - during development
        log.warning("design engine module missing: %s", exc)
    return table.get(slug) or table.get("custom-design-requests") or svc_logo.render


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', " ", name).strip()


def generate(ctx: Dict[str, Any]) -> Output:
    brand = build_brand(ctx)
    job = Job(ctx, brand)
    result = _renderer(job.slug)(job)
    scale = float(ctx.get("scale") or 1.0)
    out = Output(summary=result.summary, brand={
        "name": brand.name, "style": brand.style, "industry": brand.industry, "motif": brand.motif,
        "palette": {k.lower(): v for k, v in brand.palette}, "fonts": {"heading": brand.heading.family, "body": brand.body.family},
        "theme": brand.theme, "tweaks": brand.tweaks.notes,
    })
    pdf_pages: Dict[str, List[bytes]] = {}
    for i, art in enumerate(result.arts):
        width = int((art.export_width or art.w) * scale)
        png = art.png if art.png else export.png(art.svg, width=max(64, width))
        thumb = export.thumb(png, backdrop=art.backdrop if art.transparent else None)
        name = _safe(art.name)
        if art.pdf:
            pdf_pages.setdefault(art.pdf, []).append(png)
        pw, ph = export.size_of(png)
        f_png = OutFile(f"{name}.png", png, "image/png", art.role, art.label, "png", pw, ph, page=len(pdf_pages.get(art.pdf, [])) or None,
                        group=art.group, thumb=thumb)
        out.files.append(f_png)
        if art.svg_file and art.svg and not art.png:
            out.files.append(OutFile(f"{name}.svg", art.svg.encode("utf-8"), "image/svg+xml", art.svg_role or "source",
                                     f"{art.label} (vector SVG)", "svg", art.w, art.h, group=art.group))
        if result.board and art.name == result.board:
            out.board = f_png
    for pdf_name, pages in pdf_pages.items():
        dpi = result.pdfs.get(pdf_name, 150)
        out.files.append(OutFile(f"{_safe(pdf_name)}.pdf", export.pdf(pages, dpi=int(dpi * scale) or 72), "application/pdf", "document",
                                 f"{pdf_name} (PDF, {len(pages)} page{'s' if len(pages) != 1 else ''})", "pdf", group=""))
    for fname, text in result.texts:
        out.files.append(OutFile(fname, text.encode("utf-8"), "text/markdown", "notes", fname.rsplit(".", 1)[0], "md"))
    if out.board is None:
        out.board = next((f for f in out.files if f.format == "png"), None)
    return out
