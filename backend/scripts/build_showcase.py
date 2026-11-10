"""Build the storefront imagery: Designflow's own showcase pieces, rendered by the
real design engine (the studio is its own client, so no invented customers), then
converted to WebP for the website.

    python scripts/build_showcase.py            -> frontend/assets/img/showcase/
    python scripts/build_showcase.py --out DIR  -> another folder (for comparison)

For every service it writes <slug>.webp (primary piece), <slug>-tall.webp (portrait
card) and <slug>-thumb.webp (480 px square), plus hero-4k.webp / hero.webp / hero-sm.webp, a gallery
wall of the pieces used behind the landing-page hero. Takes a few minutes.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URI", "mongomock://")
os.environ.setdefault("APP_ENV", "test")

from PIL import Image, ImageFilter  # noqa: E402

from app.agents.tools.design_engine import generate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "frontend" / "assets" / "img" / "showcase"

ABOUT = ("Designflow is a fixed-price design studio. AI agents prepare every order and a designer finishes it. "
         "Editorial, luxury feel: deep maroon #6E1F33 and gold #C9A24B on warm cream #F7F1E6. Elegant serif headlines, generous whitespace.")
CONTENT = {
    "headlines": ["Design, delivered in days.", "Fixed price. Finished properly.", "Your brand, beautifully made."],
    "subheadlines": ["19 design services at a fixed price", "AI agents prepare, a designer finishes, you approve"],
    "body_copy": "Pick a service, share a short brief and pay a fixed price. Agents research and draft, a designer finishes, and nothing is delivered until you approve it.",
    "cta_options": ["Start a project", "See prices"],
    "captions": ["Fixed-price design, one request at a time.", "Approved by a designer before it reaches you."],
    "hashtags": ["#designflow", "#branddesign", "#fixedprice"],
}
# The lead headline of each piece names its own service (with real delivery facts), so a card
# never shows artwork that reads as a different service.
CONTENT_BY = {
    "logo-design": {"headlines": ["A mark your customers remember.", "Three logo directions in 3 days."]},
    "social-media-design": {"headlines": ["Social posts that stop the scroll.", "10 designs per pack."], "subheadlines": ["Posts, stories and covers, delivered in 2 days"]},
    "instagram-post-design": {"headlines": ["Feed-perfect Instagram posts.", "Posts and stories in a day."], "subheadlines": ["Delivered in 1 day, unlimited revisions"]},
    "linkedin-carousel-design": {"headlines": ["Carousels people swipe to the end.", "One idea per slide."], "subheadlines": ["LinkedIn carousels, delivered in 2 days"]},
    "youtube-thumbnail-design": {"headlines": ["Thumbnails that earn the click.", "Two variants, one day."], "subheadlines": ["YouTube thumbnails, delivered in 1 day"]},
    "ad-creative-design": {"headlines": ["Ads that stop the scroll.", "Three hooks per ad set.", "Ad creatives at a fixed price."], "subheadlines": ["Ad sets delivered in 2 days"]},
    "website-banner-design": {"headlines": ["Website banners that convert.", "Hero and promo banners."], "subheadlines": ["Delivered in 1 day"]},
    "pitch-deck-design": {"headlines": ["Decks investors actually read.", "Your story, slide by slide."]},
    "presentation-design": {"headlines": ["Slides that make you look sharp.", "Presentations, finished properly."]},
    "brochure-design": {"headlines": ["Brochures with a premium finish.", "Print that earns a second look."]},
    "flyer-design": {"headlines": ["Flyers, delivered in a day.", "One page. Big impact."]},
    "poster-design": {"headlines": ["Posters, made to order.", "Large format, larger presence."]},
    "infographic-design": {"headlines": ["Designflow in numbers.", "Data people actually read."]},
    "reels-cover-design": {"headlines": ["Reels covers in a day.", "A grid that looks curated."]},
    "ecommerce-creative-design": {"headlines": ["Listing images that sell.", "Main image and key benefits."], "subheadlines": ["E-commerce creatives, delivered in 2 days"]},
    "product-advertisement-design": {"headlines": ["Launch visuals that sell.", "Hero shots for every placement."], "subheadlines": ["Product ads, delivered in 2 days"]},
    "business-card-design": {"headlines": ["Small card. Strong first impression."]},
    "company-profile-design": {"headlines": ["Your company, beautifully documented.", "Who we are, what we do."]},
    "custom-design-requests": {"headlines": ["If you can describe it, we can design it.", "Merch, made to order."]},
}
STRATEGY = {"positioning": "A premium, fixed-price design studio where AI agents prepare and a designer finishes every order."}

# Brief per service. Only real product facts: 19 services, USD/GBP/INR, delivery days, unlimited revisions.
JOBS = {
    "logo-design": {"brand_name": "Designflow", "brand_colors": "deep maroon #6E1F33 and gold #C9A24B", "style": "Luxury", "industry": "Design studio",
                    "logo_type": "Not sure - recommend", "tagline": "Design studio", "about_and_wishes": ABOUT},
    "social-media-design": {"brand_name": "Designflow", "platforms": ["Instagram", "LinkedIn"], "quantity": 4, "topics": "Social media design: posts, stories and covers",
                            "copy_text": "Social posts that stop the scroll\n10 designs per pack, delivered in 2 days.\nCTA: Start a project", "about_and_wishes": ABOUT},
    "instagram-post-design": {"brand_name": "Designflow", "post_type": "Announcement", "quantity": 3,
                              "copy_text": "Feed-perfect Instagram posts, ready in a day.", "about_and_wishes": ABOUT},
    "linkedin-carousel-design": {"brand_name": "Designflow", "topic": "LinkedIn carousels people swipe to the end",
                                 "key_points": "A hook on slide one\nOne idea per slide\nYour brand on every slide\nDelivered in 2 days\nUnlimited revisions",
                                 "slides": 7, "tone": "Professional", "about_and_wishes": ABOUT},
    "youtube-thumbnail-design": {"channel_name": "Designflow", "video_title": "How we design YouTube thumbnails that earn the click", "thumbnail_text": "THUMBNAILS IN 1 DAY",
                                 "face_photo": "No, use graphics only", "style": "Bold and premium", "about_and_wishes": ABOUT},
    "ad-creative-design": {"brand_name": "Designflow", "platform": ["Meta (FB/IG)"], "offer": "Ad creatives that stop the scroll, delivered in 2 days",
                           "goal": "Sign-ups", "cta": "Order an ad set", "about_and_wishes": ABOUT},
    "website-banner-design": {"brand_name": "Designflow", "placement": "Homepage hero", "dimensions": "1920x600",
                              "copy_text": "Website banners that convert\nHero and promo banners, delivered in 1 day.", "cta": "Order a banner", "about_and_wishes": ABOUT},
    "pitch-deck-design": {"brand_name": "Designflow", "stage": "Pre-seed", "slide_count": 8, "content_status": "Need help writing", "format": "PDF only",
                          "about_and_wishes": ABOUT + " Designflow sells design per request: 19 services, fixed prices in USD, GBP or INR, no subscription."},
    "presentation-design": {"brand_name": "Designflow", "purpose": "Client onboarding", "slide_count": 7, "format": "PowerPoint",
                            "about_and_wishes": ABOUT + " Explains how an order works: brief, agents, designer approval, delivery."},
    "brochure-design": {"brand_name": "Designflow", "fold": "Tri-fold", "size": "A4", "content_status": "Need copywriting",
                        "about_and_wishes": ABOUT + " Brochure for small businesses that need design without a retainer."},
    "flyer-design": {"brand_name": "Designflow", "event_or_offer": "Flyers from GBP 10, delivered in 1 day", "size": "A5", "sides": "Single-sided",
                     "copy_text": "Flyers, delivered in a day\nOne page. Big impact.", "about_and_wishes": ABOUT},
    "poster-design": {"brand_name": "Designflow", "purpose": "Brand awareness", "size": "A3",
                      "copy_text": "Posters, made to order\nLarge format, larger presence.", "about_and_wishes": ABOUT},
    "infographic-design": {"brand_name": "Designflow", "orientation": "Vertical (blog/Pinterest)", "about_and_wishes": ABOUT,
                           "data": "19 design services\n3 currencies: USD, GBP and INR\n1 to 5 days delivery\n11 AI agents on every order\nUnlimited revisions\nEvery design approved by a designer\nPay per request, no subscription"},
    "reels-cover-design": {"brand_name": "Designflow", "quantity": 3, "titles": "Reels covers in a day\nA grid that looks curated\nEight covers, one price",
                           "style": "Text-led", "about_and_wishes": ABOUT},
    "ecommerce-creative-design": {"brand_name": "Designflow", "marketplace": ["Shopify"], "image_count": 4, "product_photos": "No, need stock/3D render",
                                  "product": "E-commerce listing images: main image and key benefits, delivered in 2 days",
                                  "about_and_wishes": ABOUT},
    "product-advertisement-design": {"brand_name": "Designflow", "product": "Product launch visuals", "mood": "Premium",
                                     "usp": "Hero shots and launch visuals\nSquare and story sizes\nDelivered in 2 days\nUnlimited revisions",
                                     "sizes": ["1080x1080 (Square)", "1080x1920 (Story)"], "cta": "Order product ads", "about_and_wishes": ABOUT},
    "business-card-design": {"brand_name": "Designflow", "details": "Nagateja Goli\nFounder\nDesignflow\nFixed-price design studio", "size": "EU 85x55 mm",
                             "finish": "Foil", "about_and_wishes": ABOUT},
    "company-profile-design": {"brand_name": "Designflow", "pages": 6, "sections": ["About", "Services", "Process", "Contact"],
                               "content_status": "Need copywriting", "about_and_wishes": ABOUT},
    "custom-design-requests": {"brand_name": "Designflow", "what": "Tote bag design for the Designflow studio", "formats": "PNG, SVG", "about_and_wishes": ABOUT},
}

# Which rendered file becomes each asset: slug -> (primary, tall)
PICK = {
    "logo-design": ("Designflow - three logos.png", "Designflow - Logo 3 - Heritage emblem.png"),
    "social-media-design": ("Post 4 - portrait 1080x1350.png", "Story - 1080x1920.png"),
    "instagram-post-design": ("Post 1 - portrait 1080x1350.png", "Story - 1080x1920.png"),
    "linkedin-carousel-design": ("Slide 01.png", "Slide 01.png"),
    "youtube-thumbnail-design": ("Thumbnail A - 1280x720.png", "Thumbnail A - 1280x720.png"),
    "ad-creative-design": ("Hook 1 - 1080x1350.png", "Hook 2 - 1080x1920.png"),
    "website-banner-design": ("Banner 1920x600 @2x.png", "Banner 1920x600 @2x.png"),
    "pitch-deck-design": ("Slide 01 - Cover.png", "Slide 01 - Cover.png"),
    "presentation-design": ("Slide 01 - Title.png", "Slide 04 - Content.png"),
    "brochure-design": ("Brochure Tri-fold - outside.png", "Brochure Tri-fold - outside.png"),
    "flyer-design": ("Flyer A5 - front.png", "Flyer A5 - front.png"),
    "poster-design": ("Poster - digital 1080x1920.png", "Poster - digital 1080x1920.png"),
    "infographic-design": ("Infographic - 1080x2160.png", "Infographic - 1080x2160.png"),
    "reels-cover-design": ("Cover 01 - 1080x1920.png", "Cover 02 - 1080x1920.png"),
    "ecommerce-creative-design": ("Listing image 1 - Main image (white background).png", "Listing image 2 - Key benefits.png"),
    "product-advertisement-design": ("Hero creative - 1080x1350.png", "Adaptation - 1080x1920.png"),
    "business-card-design": ("Designflow - business card mockup.png", "Business card - back.png"),
    "company-profile-design": ("Page 01 - Cover.png", "Page 01 - Cover.png"),
    "custom-design-requests": ("Designflow - merch mockup.png", "Designflow - merch mockup.png"),
}
THUMB = {"logo-design": "Designflow - Logo 1 - Monogram.png", "business-card-design": "Business card - front.png"}
HERO_COLUMNS = [
    ["poster-design", "youtube-thumbnail-design"],
    ["instagram-post-design", "business-card-design", "flyer-design"],
    ["reels-cover-design", "pitch-deck-design"],
    ["logo-design", "ad-creative-design", "company-profile-design"],
    ["infographic-design", "website-banner-design"],
    ["social-media-design", "product-advertisement-design", "brochure-design"],
    ["linkedin-carousel-design", "presentation-design"],
]


def render(slug: str) -> dict[str, Image.Image]:
    name = slug.replace("-", " ").title()
    ctx = {"request_id": 1, "version": 1, "service_slug": slug, "service_name": name, "title": f"Designflow {name}",
           "brief": JOBS[slug], "client": {"company_name": "Designflow"}, "content": {**CONTENT, **CONTENT_BY.get(slug, {})}, "strategy": STRATEGY,
           "concept": {"rationale": "Editorial, premium Designflow brand pieces in maroon and gold."}, "feedback": [], "scale": 1.0}
    out = generate(ctx)
    return {f.name: Image.open(io.BytesIO(f.data)) for f in out.files if f.name.lower().endswith(".png")}


def pick(files: dict[str, Image.Image], name: str) -> Image.Image:
    if name in files:
        return files[name]
    stem = name.split(" (")[0][:20]
    for k, v in files.items():
        if k.startswith(stem):
            return v
    raise KeyError(f"{name} not in {sorted(files)}")


def save(im: Image.Image, path: Path, q: int = 80) -> None:
    im.save(path, "WEBP", quality=q, method=6)


def shadowed(canvas: Image.Image, im: Image.Image, xy: tuple[int, int], radius: int = 28, alpha: int = 110) -> None:
    x, y = xy
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh.paste(Image.new("RGBA", im.size, (30, 8, 14, alpha)), (x + 6, y + 22))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(radius)))
    canvas.alpha_composite(im.convert("RGBA"), (x, y))


def tall_version(im: Image.Image) -> Image.Image:
    w, h = im.size
    if h / w >= 1.2:
        im = im.convert("RGB")
        im.thumbnail((960, 2000), Image.LANCZOS)
        return im
    cw, ch = 960, 1280
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    tw = int(cw * (0.86 if h / w < 0.8 else 0.78))
    th = int(h * tw / w)
    shadowed(canvas, im.convert("RGB").resize((tw, th), Image.LANCZOS), ((cw - tw) // 2, int(ch * 0.56 - th / 2)))
    return canvas


def thumb(im: Image.Image, size: int = 480) -> Image.Image:
    im = im.convert("RGB")
    w, h = im.size
    if w / h > 1.25:
        canvas = Image.new("RGB", (size, size), im.getpixel((4, h // 2)))
        tw = int(size * 0.92)
        th = int(h * tw / w)
        canvas.paste(im.resize((tw, th), Image.LANCZOS), ((size - tw) // 2, (size - th) // 2))
        return canvas
    s = min(w, h)
    left = (w - s) // 2
    top = 0 if h > w * 1.2 else (h - s) // 2
    return im.crop((left, top, left + s, top + s)).resize((size, size), Image.LANCZOS)


def hero(primary: dict[str, Image.Image], out: Path) -> None:
    """Gallery wall composed at 4K (3840 px) and downscaled for smaller screens."""
    k = 1.6
    W, H = 3840, 2240
    wall = Image.new("RGBA", (W, H), (34, 9, 17, 255))
    offsets = [int(o * k) for o in (-160, -40, -260, -90, -210, -20, -140)]
    colw, gap = int(330 * k), int(30 * k)
    for ci, col in enumerate(HERO_COLUMNS):
        x = int(-60 * k) + ci * (colw + gap)
        y = offsets[ci]
        while y < H:
            for slug in col:
                im = primary[slug].convert("RGB")
                th = int(im.height * colw / im.width)
                shadowed(wall, im.resize((colw, th), Image.LANCZOS), (x, y), radius=int(18 * k), alpha=150)
                y += th + gap
                if y >= H:
                    break
    wall = wall.convert("RGB")
    save(wall, out / "hero-4k.webp", 80)
    for name, width, q in (("hero.webp", 2400, 78), ("hero-sm.webp", 1200, 76)):
        save(wall.resize((width, int(H * width / W)), Image.LANCZOS), out / name, q)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", default="", help="comma-separated slugs to re-render (skips the hero wall)")
    args = ap.parse_args()
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    primary: dict[str, Image.Image] = {}
    for slug, (p_name, t_name) in PICK.items():
        if only and slug not in only:
            continue
        t0 = time.perf_counter()
        files = render(slug)
        pim = pick(files, p_name)
        primary[slug] = pim
        big = pim.convert("RGB")
        big.thumbnail((1200, 1200), Image.LANCZOS)
        tall = tall_version(pick(files, t_name))
        th = thumb(pick(files, THUMB[slug]) if slug in THUMB else pim)
        # each image at two sizes: the page's srcset picks per screen (crisp on 4K, light on 1080p)
        for img, name, small in ((big, f"{slug}", 600), (tall, f"{slug}-tall", 480), (th, f"{slug}-thumb", 240)):
            save(img, out / f"{name}.webp", 80)
            save(img.resize((small, round(img.height * small / img.width)), Image.LANCZOS), out / f"{name}-sm.webp", 80)
        print(f"ok  {slug:30s} {time.perf_counter() - t0:5.1f}s", flush=True)
    if only:
        print(f"wrote {len(primary) * 6} images to {out}")
        return
    hero(primary, out)
    print(f"wrote {len(PICK) * 6 + 3} images to {out}")


if __name__ == "__main__":
    main()
