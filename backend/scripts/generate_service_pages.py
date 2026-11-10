"""Generate the 20 static service pages, the services index and services-data.js
from the single source of truth in app/db/seed_data.py.

    python scripts/generate_service_pages.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.seed_data import SERVICES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
TEMPLATE = Path(__file__).resolve().parent / "templates" / "service_page.html"

NAV = """<a class="skip-link" href="#main">Skip to content</a>
<div class="scroll-progress" aria-hidden="true"><span></span></div>
<header class="site-nav pr-nav" id="nav">
  <a href="/" class="pr-brand" aria-label="Designflow home"><img src="/assets/img/logo-gold.svg" alt="" width="30" height="30"><span>Designflow</span></a>
  <div class="nav-pill">
    <nav class="nav-links" aria-label="Primary">
      <span class="nav-indicator" aria-hidden="true"></span>
      <a href="/#process" data-section="process">Process</a>
      <a href="/services" data-section="services">Services</a>
      <a href="/#work" data-section="work">Work</a>
      <a href="/#pricing" data-section="pricing">Pricing</a>
      <a href="/#faq" data-section="faq">FAQ</a>
    </nav>
    <a href="/register" class="pr-btn pr-btn-white pr-btn-sm" data-cta>Start a project <svg class="icon icon-sm" aria-hidden="true"><use href="/assets/img/icons.svg#arrow-up-right"></use></svg></a>
  </div>
  <div class="pr-nav-end">
    <a href="/login" class="pr-link" data-auth-link>Log in</a>
    <button class="pr-burger" data-burger aria-label="Open menu" aria-controls="mobile-menu"><svg class="icon" aria-hidden="true"><use href="/assets/img/icons.svg#menu"></use></svg></button>
  </div>
</header>
<div class="mobile-menu pr-menu" id="mobile-menu">
  <a href="/#process">Process</a>
  <a href="/services">Services</a>
  <a href="/#work">Work</a>
  <a href="/#pricing">Pricing</a>
  <a href="/#faq">FAQ</a>
  <a href="/#contact">Contact</a>
  <a href="/login" data-auth-link>Log in</a>
  <a href="/register" class="pr-btn pr-btn-white" data-cta>Start a project <svg class="icon icon-sm" aria-hidden="true"><use href="/assets/img/icons.svg#arrow-up-right"></use></svg></a>
</div>"""

FOOTER = """<footer class="pr-footer site-footer">
  <div class="pr-container">
    <div class="pr-footer-top">
      <div class="pr-footer-brand">
        <a href="/" class="pr-brand"><img src="/assets/img/logo-gold.svg" alt="" width="30" height="30"><span>Designflow</span></a>
        <p>Fixed-price design, one request at a time. AI agents prepare, a designer finishes, you approve. Pay in USD, GBP or INR.</p>
        <div class="footer-share pr-share">
          <span>Share Designflow</span>
          <a data-share="linkedin" href="https://www.linkedin.com/" target="_blank" rel="noopener" aria-label="Share on LinkedIn"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.6c0-1.34-.03-3.06-1.86-3.06-1.87 0-2.15 1.46-2.15 2.96V21H9z"/></svg></a>
          <a data-share="x" href="https://x.com/" target="_blank" rel="noopener" aria-label="Share on X"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.75 3h3.07l-6.7 7.66L22 21h-6.17l-4.83-6.32L5.47 21H2.4l7.17-8.2L2 3h6.33l4.37 5.77zm-1.08 16.17h1.7L7.4 4.74H5.58z"/></svg></a>
          <a data-share="whatsapp" href="https://wa.me/" target="_blank" rel="noopener" aria-label="Share on WhatsApp"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.04 2A9.9 9.9 0 0 0 3.5 16.9L2 22l5.25-1.38A9.9 9.9 0 1 0 12.04 2zm0 18.1a8.2 8.2 0 0 1-4.18-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 1 1 6.97 3.86z"/></svg></a>
          <a data-share="email" href="mailto:" aria-label="Share by email"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm9 7.2L4.4 7H19.6zm-8-3.36V17h16V8.84l-8 5.46z"/></svg></a>
        </div>
      </div>
      <div class="pr-footer-cols">
        <div><h4>Product</h4><ul><li><a href="/services">Services</a></li><li><a href="/#process">How it works</a></li><li><a href="/#pricing">Pricing</a></li><li><a href="/portal">Client portal</a></li><li><a href="/login">Log in</a></li></ul></div>
        <div><h4>Popular services</h4><ul><li><a href="/services/logo-design">Logo Design</a></li><li><a href="/services/social-media-design">Social Media Design</a></li><li><a href="/services/youtube-thumbnail-design">YouTube Thumbnails</a></li><li><a href="/services/pitch-deck-design">Pitch Decks</a></li><li><a href="/services">All 19 services</a></li></ul></div>
        <div><h4>Company</h4><ul><li><a href="/#contact">Contact</a></li><li><a href="/#faq">FAQ</a></li><li><a href="/privacy">Privacy</a></li><li><a href="/terms">Terms</a></li></ul></div>
      </div>
    </div>
    <div class="pr-footer-bottom">
      <span>&copy; <span id="year"></span> Designflow. All rights reserved.</span>
      <span>Built by Nagateja Goli</span>
      <nav aria-label="Legal"><a href="/privacy">Privacy</a><a href="/terms">Terms</a><a href="/#contact">Contact</a></nav>
    </div>
  </div>
</footer>"""

CHECK = '<svg class="icon" aria-hidden="true"><use href="/assets/img/icons.svg#check"></use></svg>'
# pieces whose artwork is landscape or square: shown from the wide render, never cropped
WIDE = {"logo-design", "youtube-thumbnail-design", "website-banner-design", "pitch-deck-design", "presentation-design", "brochure-design", "business-card-design", "custom-design-requests", "ecommerce-creative-design"}
ARROW = '<svg class="icon icon-sm" aria-hidden="true"><use href="/assets/img/icons.svg#arrow-up-right"></use></svg>'


def e(s) -> str:
    return html.escape(str(s or ""), quote=True)


def prices(s: dict) -> dict:
    from app.core.config import settings

    usd = float(s["starting_price"])
    return {"USD": settings.convert_price(usd, "USD"), "GBP": settings.convert_price(usd, "GBP"), "INR": settings.convert_price(usd, "INR")}


# ---------------------------------------------------------------------------------------------
# Format mockups: same markup as frontend/assets/js/landing/mockups.js (keep the two in step).
SHOW = "/assets/img/showcase/"
IMG_V = "?v=2"  # bump when the showcase images are re-rendered (same as mockups.js)
MAIN_W = {
    "ad-creative-design": 960, "brochure-design": 1200, "business-card-design": 1200, "company-profile-design": 855,
    "custom-design-requests": 1200, "ecommerce-creative-design": 1200, "flyer-design": 856, "infographic-design": 600,
    "instagram-post-design": 960, "linkedin-carousel-design": 960, "logo-design": 1200, "pitch-deck-design": 1200,
    "poster-design": 675, "presentation-design": 1200, "product-advertisement-design": 960, "reels-cover-design": 675,
    "social-media-design": 960, "website-banner-design": 1200, "youtube-thumbnail-design": 1200,
}
FORMAT = {
    "logo-design": "artboard", "social-media-design": "trio", "instagram-post-design": "post",
    "linkedin-carousel-design": "carousel", "youtube-thumbnail-design": "video", "ad-creative-design": "ad",
    "website-banner-design": "browser", "pitch-deck-design": "deck", "presentation-design": "monitor",
    "brochure-design": "trifold", "flyer-design": "paper", "poster-design": "poster", "infographic-design": "scroll",
    "reels-cover-design": "reel", "ecommerce-creative-design": "shop", "product-advertisement-design": "story",
    "business-card-design": "proof", "company-profile-design": "booklet", "custom-design-requests": "select",
}


def _img(slug: str, kind: str, sizes: str, alt: str = "") -> str:
    if kind == "tall":
        src = f"{SHOW}{slug}-tall.webp{IMG_V}"
        srcset = f"{SHOW}{slug}-tall-sm.webp{IMG_V} 480w, {src} 960w"
    elif kind == "thumb":
        src = f"{SHOW}{slug}-thumb.webp{IMG_V}"
        srcset = f"{SHOW}{slug}-thumb-sm.webp{IMG_V} 240w, {src} 480w"
    else:
        w = MAIN_W.get(slug, 1200)
        src = f"{SHOW}{slug}.webp{IMG_V}"
        srcset = f"{SHOW}{slug}-sm.webp{IMG_V} 600w, {src} {w}w" if w > 600 else f"{src} {w}w"
    return f'<img src="{src}" srcset="{srcset}" sizes="{sizes}" alt="{alt}" loading="lazy" decoding="async">'


def _ic(n: str) -> str:
    return f'<svg class="mk-ic" aria-hidden="true"><use href="/assets/img/icons.svg#{n}"></use></svg>'


def _line(w: int) -> str:
    return f'<i class="mk-line" style="--w:{w}%"></i>'


def _head(sponsored: bool) -> str:
    sub = "<small>Sponsored</small>" if sponsored else _line(46)
    return f'<span class="mk-head"><i class="mk-avatar"></i><span class="mk-lines"><b>designflow</b>{sub}</span>{_ic("more")}</span>'


def mockup(slug: str, size: str = "max(18rem, 15vw)", alt: str = "") -> tuple[str, str]:
    t = FORMAT.get(slug, "artboard")
    m = _img(slug, "main", size, alt)
    actions = f'<span class="mk-actions">{_ic("heart")}{_ic("message")}{_ic("send")}</span>'
    if t == "post":
        h = f'<span class="mk mk-post">{_head(False)}<span class="mk-media r45">{m}</span>{actions}{_line(72)}</span>'
    elif t == "ad":
        h = f'<span class="mk mk-post is-ad">{_head(True)}<span class="mk-media r45">{m}</span><span class="mk-cta">Learn more {_ic("chevron-right")}</span>{actions}</span>'
    elif t == "trio":
        h = (f'<span class="mk mk-trio"><span class="mk-tile t-story">{_img(slug, "tall", size, alt)}<small>Story</small></span>'
             f'<span class="mk-tile t-post">{m}<small>Post</small></span><span class="mk-tile t-square">{_img(slug, "thumb", size)}<small>Square</small></span></span>')
    elif t == "reel":
        h = (f'<span class="mk mk-phone"><span class="mk-screen">{m}<span class="mk-bars"><i></i><i></i><i></i></span>'
             f'<span class="mk-side">{_ic("heart")}{_ic("message")}{_ic("send")}</span><span class="mk-cap">{_line(58)}{_line(36)}</span></span></span>')
    elif t == "story":
        h = (f'<span class="mk mk-phone"><span class="mk-screen">{_img(slug, "tall", size, alt)}<span class="mk-bars"><i></i><i></i></span>'
             f'<span class="mk-chip">Sponsored</span><span class="mk-shop-now">Shop now</span></span></span>')
    elif t == "carousel":
        h = (f'<span class="mk mk-carousel"><span class="mk-slide is-next">{m}</span><span class="mk-slide">{m}</span>'
             f'<span class="mk-arrow">{_ic("chevron-right")}</span><span class="mk-dots"><i class="on"></i><i></i><i></i><i></i></span></span>')
    elif t == "video":
        h = (f'<span class="mk mk-video"><span class="mk-player">{m}<span class="mk-play">{_ic("play")}</span><span class="mk-progress"><i></i></span></span>'
             f'<span class="mk-vmeta"><i class="mk-avatar"></i><span class="mk-lines">{_line(92)}{_line(56)}</span></span></span>')
    elif t == "browser":
        h = (f'<span class="mk mk-browser"><span class="mk-chrome"><i></i><i></i><i></i><b></b></span><span class="mk-page"><span class="mk-banner">{m}</span>'
             f'<span class="mk-blocks"><i></i><i></i><i></i></span>{_line(82)}{_line(60)}</span></span>')
    elif t == "deck":
        h = (f'<span class="mk mk-deck"><span class="mk-sheet b2"></span><span class="mk-sheet b1"></span><span class="mk-sheet front">{m}</span>'
             f'<span class="mk-dots"><i class="on"></i><i></i><i></i><i></i></span></span>')
    elif t == "monitor":
        h = f'<span class="mk mk-monitor"><span class="mk-display">{m}</span><i class="mk-neck"></i><i class="mk-base"></i></span>'
    elif t == "trifold":
        h = f'<span class="mk mk-trifold"><span class="mk-panel l">{m}</span><span class="mk-panel c">{m}</span><span class="mk-panel r">{m}</span></span>'
    elif t == "paper":
        h = f'<span class="mk mk-paper"><span class="mk-sheet back"></span><span class="mk-sheet front">{m}</span></span>'
    elif t == "poster":
        h = f'<span class="mk mk-poster">{m}<i class="mk-tape l"></i><i class="mk-tape r"></i></span>'
    elif t == "scroll":
        h = f'<span class="mk mk-scroll"><span class="mk-view">{m}</span><i class="mk-track"><i></i></i></span>'
    elif t == "shop":
        h = f'<span class="mk mk-shop"><span class="mk-media r11">{m}</span><span class="mk-lines">{_line(84)}{_line(48)}</span><span class="mk-buy">Add to cart</span></span>'
    elif t == "proof":
        h = (f'<span class="mk mk-proof"><span class="mk-art">{m}</span><i class="mk-cm tl"></i><i class="mk-cm tr"></i><i class="mk-cm bl"></i>'
             f'<i class="mk-cm br"></i><span class="mk-note">Print-ready PDF</span></span>')
    elif t == "booklet":
        h = f'<span class="mk mk-booklet"><i class="mk-pg p3"></i><i class="mk-pg p2"></i><span class="mk-pg front">{m}</span></span>'
    elif t == "select":
        h = (f'<span class="mk mk-select"><span class="mk-board">{m}<i class="mk-sel"></i><i class="mk-h tl"></i><i class="mk-h tr"></i><i class="mk-h bl"></i>'
             f'<i class="mk-h br"></i><span class="mk-size">1200 × 675</span></span><svg class="mk-cursor" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3l14 8-6.2 1.6L10 19z"/></svg></span>')
    else:
        h = f'<span class="mk mk-artboard"><span class="mk-label">Logo directions</span><span class="mk-board">{m}</span></span>'
    return t, h


def card(s: dict) -> str:
    p = prices(s)
    slug = e(s["slug"])
    fmt, media = mockup(s["slug"], "(max-width: 600px) 70vw, max(14rem, 11.67vw)")
    return (
        f'<a class="service-card pr-svc" href="/services/{slug}" data-cat="{e(s["category"])}">'
        f'<span class="pr-svc-media" data-format="{fmt}">{media}</span>'
        f'<span class="pr-svc-body"><span class="pr-svc-cat">{e(s["category"])}</span><span class="pr-svc-name">{e(s["name"])}</span>'
        f'<span class="pr-svc-tag">{e(s["tagline"])}</span>'
        f'<span class="pr-svc-meta"><span><b class="price" data-usd="{p["USD"]}" data-gbp="{p["GBP"]}" data-inr="{p["INR"]}">${p["USD"]}</b> {e(s.get("price_unit", "per request"))}</span>'
        f'<span>{s["turnaround_days"]}&#8209;day delivery</span></span></span></a>'
    )


def render_page(s: dict, template: str) -> str:
    deliverables = "\n".join(f"          <li>{CHECK}{e(d)}</li>" for d in s["deliverables"])
    type_labels = {"text": "short text", "textarea": "text", "select": "choice", "multiselect": "multiple choice", "number": "number", "url": "link", "color": "colour", "file": "file"}
    req_mark = ' <span class="req">*</span>'
    fields = "\n".join(
        f'          <li><span>{e(f["label"])}{req_mark if f.get("required") else ""}</span><span>{e(type_labels.get(f.get("type", "text"), f.get("type")))}</span></li>'
        for f in s["form_schema"]
    )
    related = [x for x in SERVICES if x["slug"] != s["slug"] and x["category"] == s["category"]]
    if len(related) < 4:
        related += [x for x in SERVICES if x["slug"] != s["slug"] and x not in related][: 4 - len(related)]
    related_html = "\n".join(f"        {card(x)}" for x in related[:4])
    out = template
    p = prices(s)
    repl = {
        "{{price_usd}}": str(p["USD"]),
        "{{price_gbp}}": str(p["GBP"]),
        "{{price_inr}}": str(p["INR"]),
        "{{price_unit}}": e(s.get("price_unit", "per request")),
        "{{nav}}": NAV,
        "{{footer}}": FOOTER,
        "{{name}}": e(s["name"]),
        "{{name_lower}}": e(s["name"].lower().replace(" design", "") if s["name"].lower().endswith(" design") else s["name"].lower()),
        "{{slug}}": e(s["slug"]),
        "{{icon}}": e(s["icon"]),
        "{{category}}": e(s["category"]),
        "{{tagline}}": e(s["tagline"]),
        "{{description}}": e(s["description"]),
        "{{long_description}}": e(s["long_description"]),
        "{{turnaround_days}}": str(s["turnaround_days"]),
        "{{deliverables}}": deliverables,
        "{{fields}}": fields,
        "{{related}}": related_html,
        "{{mockup}}": mockup(s["slug"], "(max-width: 900px) 80vw, max(28rem, 23.33vw)", f"A Designflow {e(s['name'].lower())} example, shown in its real format")[1],
    }
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>All services — Designflow</title>
  <meta name="description" content="19 design services at fixed prices, pay per request: branding, social media, advertising, presentations, print and custom requests.">
  <meta name="theme-color" content="#000000">
  <meta name="color-scheme" content="dark">
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Barlow:wght@300;400;500;600&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/tokens.css?v=20261109t">
  <link rel="stylesheet" href="/assets/css/base.css?v=20261109t">
  <link rel="stylesheet" href="/assets/css/components.css?v=20261109t">
  <link rel="stylesheet" href="/assets/vendor/lenis.css?v=20261109t">
  <link rel="stylesheet" href="/assets/css/prism.css?v=20261109t">
  <script>(function(){document.documentElement.classList.add('js');})();</script>
</head>
<body class="sf pr pr-page" data-nav-active="services">
__NAV__
<main id="main">
  <section class="pr-page-hero">
    <div class="pr-container">
      <nav class="pr-crumbs" aria-label="Breadcrumb"><a href="/">Home</a><span aria-hidden="true">/</span><span aria-current="page">Services</span></nav>
      <header class="pr-head pr-head-left pr-page-head">
        <p class="pr-tag">All services</p>
        <h1 class="pr-title pr-title-xl">19 services. Fixed prices.</h1>
        <p class="pr-sub">Pay per request in USD, GBP or INR. Every service has its own brief form, price and delivery time.</p>
      </header>
      <div class="cat-filters pr-chips" id="cat-filters" role="toolbar" aria-label="Filter services by category"></div>
      <div class="pr-grid" id="services-grid">
__CARDS__
      </div>
    </div>
  </section>
  <section class="pr-section pr-mini-cta">
    <div class="pr-container">
      <div class="pr-mini-cta-card">
        <h2 class="pr-title">Ready when you are.</h2>
        <p class="pr-sub">Create your account and order your first design in under five minutes.</p>
        <a href="/register" class="pr-btn pr-btn-white" data-cta>Get started __ARROW__</a>
      </div>
    </div>
  </section>
</main>
__FOOTER__
<script src="/assets/vendor/gsap.min.js?v=20261109t" defer></script>
<script src="/assets/vendor/ScrollTrigger.min.js?v=20261109t" defer></script>
<script src="/assets/vendor/lenis.min.js?v=20261109t" defer></script>
<script type="module" src="/assets/js/landing/main.js?v=20261109t"></script>
</body>
</html>
"""


def main() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")
    out_dir = FRONTEND / "services"
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in SERVICES:
        (out_dir / f"{s['slug']}.html").write_text(render_page(s, template), encoding="utf-8")
    cards = "\n".join(f"        {card(s)}" for s in SERVICES)
    index = INDEX_TEMPLATE.replace("__NAV__", NAV).replace("__FOOTER__", FOOTER).replace("__CARDS__", cards).replace("__ARROW__", ARROW)
    (out_dir / "index.html").write_text(index, encoding="utf-8")

    from app.core.config import settings

    data = []
    for s in SERVICES:
        row = {k: s[k] for k in ("slug", "name", "category", "tagline", "description", "icon", "turnaround_days", "deliverables", "price_unit")}
        usd = float(s["starting_price"])
        row["prices"] = {"USD": settings.convert_price(usd, "USD"), "GBP": settings.convert_price(usd, "GBP"), "INR": settings.convert_price(usd, "INR")}
        data.append(row)
    categories = []
    for s in SERVICES:
        if s["category"] not in categories:
            categories.append(s["category"])
    js = (
        "/* Generated by backend/scripts/generate_service_pages.py - do not edit by hand. */\n"
        f"export const SERVICES = {json.dumps(data, indent=2)};\n"
        f"export const CATEGORIES = {json.dumps(categories)};\n"
    )
    (FRONTEND / "assets" / "js" / "landing" / "services-data.js").write_text(js, encoding="utf-8")
    print(f"wrote {len(SERVICES)} service pages, services/index.html and services-data.js")


if __name__ == "__main__":
    main()
