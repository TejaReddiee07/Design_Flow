"""Design draft rendering for the Design Agent.

A text model cannot draw. The mock provider renders each concept as an SVG "concept card"
(title, layout note, palette swatches, headline) so the admin and client see a real,
previewable draft. Plug a real image API in generate_preview() when you have one.
"""
from __future__ import annotations

import html
from typing import Any, Dict, Optional

from app.core.config import settings
from app.db.mongo import DB, Doc
from app.services.file_service import store_bytes


def _svg_concept(concept: Dict[str, Any], headline: str, brand: str) -> bytes:
    palette = [c for c in (concept.get("palette") or ["#6366f1", "#06b6d4", "#ec4899"]) if isinstance(c, str)][:5] or ["#6366f1"]
    primary = palette[0]
    accent = palette[1] if len(palette) > 1 else "#ffffff"
    title = html.escape(str(concept.get("title") or "Concept"))
    desc = html.escape(str(concept.get("description") or ""))[:140]
    layout = html.escape(str(concept.get("layout") or ""))
    typo = html.escape(str(concept.get("typography") or ""))[:80]
    head = html.escape(headline[:48] or title)
    swatches = "".join(
        f'<rect x="{60 + i * 56}" y="520" width="44" height="44" rx="10" fill="{html.escape(c)}" stroke="rgba(0,0,0,.15)"/>' for i, c in enumerate(palette)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{html.escape(primary)}"/><stop offset="1" stop-color="{html.escape(accent)}"/></linearGradient>
  </defs>
  <rect width="1200" height="630" fill="#0f1220"/>
  <rect x="640" y="0" width="560" height="630" fill="url(#g)" opacity="0.9"/>
  <circle cx="920" cy="315" r="170" fill="#ffffff" opacity="0.12"/>
  <circle cx="980" cy="250" r="90" fill="#ffffff" opacity="0.18"/>
  <text x="60" y="90" fill="#ffffff" opacity="0.6" font-family="Inter, Arial, sans-serif" font-size="22" letter-spacing="4">{html.escape(brand.upper()[:28])} · DRAFT</text>
  <text x="60" y="200" fill="#ffffff" font-family="Georgia, serif" font-size="68" font-weight="700">{head[:22]}</text>
  <text x="60" y="280" fill="#ffffff" font-family="Georgia, serif" font-size="68" font-weight="700">{head[22:44]}</text>
  <text x="60" y="350" fill="#c3c6da" font-family="Inter, Arial, sans-serif" font-size="24">{desc[:70]}</text>
  <text x="60" y="385" fill="#c3c6da" font-family="Inter, Arial, sans-serif" font-size="24">{desc[70:140]}</text>
  <rect x="60" y="430" width="220" height="56" rx="28" fill="{html.escape(accent)}"/>
  <text x="170" y="466" fill="#0f1220" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700">Get started</text>
  {swatches}
  <text x="60" y="600" fill="#8d91a9" font-family="Inter, Arial, sans-serif" font-size="18">{title} · layout: {layout} · {typo}</text>
</svg>""".encode("utf-8")


def generate_preview(db: DB, *, concept: Dict[str, Any], headline: str, brand: str, request_id: int, client_id: int, version: int) -> Optional[Doc]:
    """Returns a file Doc with a rendered draft, or None when IMAGE_PROVIDER=none."""
    provider = settings.image_provider.lower()
    if provider in ("none", "off", ""):
        return None
    # "mock" (default) renders an SVG concept card. Add real providers here.
    data = _svg_concept(concept, headline, brand)
    return store_bytes(
        db,
        data=data,
        filename=f"concept-v{version}.svg",
        mime_type="image/svg+xml",
        folder=f"clients/{client_id}/requests/{request_id}/designs",
        kind="design",
        owner_user_id=None,
        client_id=client_id,
        request_id=request_id,
        meta={"generated_by": "design_agent", "provider": provider},
    )
