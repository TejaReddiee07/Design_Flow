"""What a client receives for an order: only the finished designs, in the formats of the service they bought.

Each service delivers the formats its listing promises, narrowed by the choices the client made in the brief
(platforms, sizes, print or digital, PDF only, ...). Studio-only files never go to the client: overview boards,
editable sources (unless the brief asks for SVG/vector/source files), copy notes, draft packages and delivery notes.

`select(slug, brief, items)` works on file items shaped like design/delivery entries:
{file_id, name, format, role, label, width, height, group, page}.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

STUDIO_ROLES = {"board", "package", "notes"}
SIZE_RE = re.compile(r"(\d{2,4})x(\d{2,4})")

# placement -> engine sizes it maps to
PORTRAIT, SQUARE, STORY, LANDSCAPE = "1080x1350", "1080x1080", "1080x1920", "landscape"
PLATFORM_SIZES = {
    "instagram": {PORTRAIT, STORY},
    "facebook": {SQUARE, LANDSCAPE},
    "linkedin": {SQUARE, LANDSCAPE},
    "x": {LANDSCAPE},
    "tiktok": {STORY},
    "pinterest": {PORTRAIT},
}
AD_PLATFORM_SIZES = {
    "meta": {SQUARE, PORTRAIT, STORY},
    "google": {"300x250", "728x90", LANDSCAPE},
    "tiktok": {STORY},
    "linkedin": {SQUARE, LANDSCAPE},
    "x": {LANDSCAPE},
}


def _text(brief: Dict[str, Any], *keys: str) -> str:
    out = []
    for k in keys:
        v = brief.get(k)
        if isinstance(v, list):
            out.append(" ".join(map(str, v)))
        elif v:
            out.append(str(v))
    return " ".join(out).lower()


def _choices(brief: Dict[str, Any], key: str) -> List[str]:
    v = brief.get(key)
    if isinstance(v, list):
        return [str(x).lower() for x in v if str(x).strip()]
    return [x.strip().lower() for x in str(v or "").split(",") if x.strip()]


def _size_of(item: Dict[str, Any]) -> Optional[str]:
    """Placement key of an image item: '1080x1350', '1080x1920', 'landscape', '300x250', ..."""
    txt = f"{item.get('name') or ''} {item.get('group') or ''}"
    m = SIZE_RE.search(txt)
    if not m:
        w, h = int(item.get("width") or 0), int(item.get("height") or 0)
        if not (w and h):
            return None
        size = f"{w}x{h}"
    else:
        size = m.group(0)
    w, h = (int(x) for x in size.split("x"))
    if w > h * 1.6 and size not in ("728x90",):
        return LANDSCAPE
    return size


def _requested_sizes(brief: Dict[str, Any]) -> Set[str]:
    """Sizes ticked in a 'sizes' multiselect, e.g. '1080x1080 (Square)', '1920x1080 (Landscape)'."""
    out: Set[str] = set()
    for c in _choices(brief, "sizes"):
        if "landscape" in c or "1920x1080" in c:
            out.add(LANDSCAPE)
        else:
            m = SIZE_RE.search(c)
            if m:
                out.add(m.group(0))
    return out


def wants_sources(brief: Dict[str, Any]) -> bool:
    return bool(re.search(r"\bsvg\b|vector|editable|source files?|\.ai\b|\beps\b|illustrator", _text(brief, "formats", "about_and_wishes", "format", "what")))


def _by_size(items: List[Dict[str, Any]], allowed: Set[str]) -> List[Dict[str, Any]]:
    keep = [i for i in items if _size_of(i) in allowed]
    return keep or items


def select(slug: str, brief: Optional[Dict[str, Any]], items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    brief = brief or {}
    items = [dict(i) for i in items if i]
    sources_ok = wants_sources(brief)
    designs = [i for i in items if (i.get("role") or "") not in STUDIO_ROLES and (i.get("format") or "").lower() not in ("md", "zip", "txt")]
    if not sources_ok:
        designs = [i for i in designs if i.get("role") != "source"]
    images = [i for i in designs if (i.get("format") or "").lower() in ("png", "jpg", "jpeg", "webp")]
    pdfs = [i for i in designs if (i.get("format") or "").lower() == "pdf"]
    svgs = [i for i in designs if (i.get("format") or "").lower() == "svg"]
    keep: List[Dict[str, Any]]

    if slug == "social-media-design":
        allowed = _requested_sizes(brief)
        if not allowed:
            for p in _choices(brief, "platforms"):
                allowed |= PLATFORM_SIZES.get(p.split()[0], set())
        keep = _by_size(images, allowed or {PORTRAIT})
    elif slug == "instagram-post-design":
        kind = _text(brief, "post_type")
        if "carousel" in kind:
            keep = [i for i in images if (i.get("role") in ("primary", "page")) or "slide" in (i.get("name") or "").lower()] or images
        elif "story" in kind:
            keep = _by_size(images, {STORY})
        else:
            keep = images  # listing promises 1080x1350 + 1080x1080 exports and a story version
    elif slug == "ad-creative-design":
        allowed = _requested_sizes(brief)
        if not allowed:
            for p in _choices(brief, "platform"):
                key = "meta" if ("meta" in p or "fb" in p or "ig" in p) else "google" if "google" in p else p.split()[0]
                allowed |= AD_PLATFORM_SIZES.get(key, set())
        keep = _by_size(images, allowed) if allowed else images
    elif slug == "product-advertisement-design":
        allowed = _requested_sizes(brief)
        hero = [i for i in images if not (i.get("group") or "").lower().startswith("adaptation")]
        adapt = [i for i in images if (i.get("group") or "").lower().startswith("adaptation")]
        keep = hero + ([i for i in adapt if _size_of(i) in allowed] if allowed else adapt)
    elif slug in ("pitch-deck-design", "presentation-design"):
        fmt = _text(brief, "format")
        keep = pdfs if ("pdf only" in fmt and pdfs) else pdfs + images
    elif slug == "linkedin-carousel-design":
        keep = pdfs + images  # LinkedIn takes the PDF; slides as PNG for re-use
    elif slug in ("brochure-design", "company-profile-design"):
        keep = pdfs or images  # print / interactive PDF
    elif slug == "flyer-design":
        size, sides = _text(brief, "size"), _text(brief, "sides")
        digital = [i for i in images if "social" in (i.get("name") or "").lower() or (i.get("group") or "").lower() == "digital"]
        if "digital only" in size:
            keep = digital or images
        else:
            prints = [i for i in images if i not in digital]
            if "single" in sides:
                prints = [i for i in prints if "back" not in (i.get("name") or "").lower()]
            keep = pdfs + prints + digital
    elif slug == "poster-design":
        size = _text(brief, "size")
        digital = [i for i in images if (i.get("group") or "").lower() == "digital" or "digital" in (i.get("name") or "").lower()]
        keep = (digital or images) if ("digital screen" in size) else pdfs + images
    elif slug == "ecommerce-creative-design":
        markets = " ".join(_choices(brief, "marketplace"))
        aplus_ok = not markets or "amazon" in markets or "flipkart" in markets
        keep = [i for i in images if aplus_ok or "a+" not in (i.get("group") or i.get("name") or "").lower()]
    elif slug == "business-card-design":
        keep = pdfs + images
    elif slug == "custom-design-requests":
        fmts = _text(brief, "formats")
        keep = list(images)
        if "pdf" in fmts:
            keep += pdfs
        if not keep:
            keep = pdfs
    else:
        # logo (exactly the 3 logos + extras the brief asked for), thumbnails, banners, reels covers, infographics
        keep = images + pdfs

    if sources_ok and svgs:
        stems = {(i.get("name") or "").rsplit(".", 1)[0] for i in keep}
        keep += [s for s in svgs if (s.get("name") or "").rsplit(".", 1)[0] in stems and s not in keep]
    seen: Set[Any] = set()
    out = []
    for i in keep:
        k = i.get("file_id") or i.get("name")
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


# ---------------------------------------------------------------------------
# deliveries -> what the client may see
# ---------------------------------------------------------------------------
def delivery_items(dl: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Raw file items of a delivery (new deliveries carry `files`; older ones only file_ids/download_links)."""
    items = [dict(x) for x in (dl.get("files") or []) if isinstance(x, dict) and x.get("file_id")]
    if not items:
        names = {int(l["file_id"]): l.get("name") for l in (dl.get("download_links") or []) if isinstance(l, dict) and l.get("file_id")}
        items = [{"file_id": int(fid), "name": names.get(int(fid))} for fid in (dl.get("file_ids") or []) if fid]
    for it in items:
        if not it.get("format") and it.get("name"):
            it["format"] = str(it["name"]).rsplit(".", 1)[-1].lower() if "." in str(it["name"]) else ""
    return items


def for_delivery(dl: Dict[str, Any], slug: str, brief: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The files of a delivery the client actually receives."""
    items = delivery_items(dl)
    if dl.get("delivered_by") == "admin":  # hand-picked by the designer: send what they chose, minus packages
        return [i for i in items if (i.get("format") or "") != "zip"]
    if package := dl.get("package_file_id"):
        items = [i for i in items if i.get("file_id") != package]
    return select(slug, brief, items)


_VISIBLE: Dict[int, Tuple[float, Set[int]]] = {}
_TTL = 20.0


def invalidate(client_id: Optional[int] = None) -> None:
    if client_id is None:
        _VISIBLE.clear()
    else:
        _VISIBLE.pop(int(client_id), None)


def client_visible_file_ids(db: Any, client_id: int) -> Set[int]:
    """Studio files (kinds design / delivery / thumb) a client may open: their delivered designs and those previews."""
    hit = _VISIBLE.get(int(client_id))
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    from app.db.mongo import parallel

    reqs = db.requests.find({"client_id": client_id}, projection={"brief": 1, "service_id": 1})
    ids = [r.id for r in reqs]
    visible: Set[int] = set()
    if ids:
        services, deliveries = parallel(
            lambda: db.services.by_ids({r.get("service_id") for r in reqs}),
            lambda: db.deliveries.find({"request_id": {"$in": ids}}),
        )
        by_id = {r.id: r for r in reqs}
        for dl in deliveries:
            r = by_id.get(dl.get("request_id"))
            svc = services.get(r.get("service_id")) if r else None
            for it in for_delivery(dl, (svc or {}).get("slug") or "", (r or {}).get("brief")):
                visible.add(int(it["file_id"]))
                if it.get("thumb_file_id"):
                    visible.add(int(it["thumb_file_id"]))
            if dl.get("selected") and dl.get("package_file_id"):  # ZIP built from exactly those designs
                visible.add(int(dl["package_file_id"]))
    _VISIBLE[int(client_id)] = (time.monotonic(), visible)
    return visible
