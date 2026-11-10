"""Static seed data: the 20 services (with their request forms) and the 11 agents."""
from __future__ import annotations

from typing import Any, Dict, List

# --------------------------------------------------------------------------
# Reusable form fields
# --------------------------------------------------------------------------


def f(key: str, label: str, type_: str = "text", required: bool = False, **extra: Any) -> Dict[str, Any]:
    field = {"key": key, "label": label, "type": type_, "required": required}
    field.update(extra)
    return field


BRAND_FIELDS = [
    f("brand_name", "Brand / company name", required=True, placeholder="Acme Inc."),
    f("brand_colors", "Brand colors (hex or description)", placeholder="#1E40AF, white, warm grey"),
    f("style", "Visual style", "select", options=["Minimal", "Bold", "Playful", "Luxury", "Corporate", "Modern", "Vintage"]),
]

ABOUT_AND_WISHES = f(
    "about_and_wishes",
    "About your business and how you want this done",
    "textarea",
    required=True,
    placeholder="Tell us what your business does, who it is for, and exactly how you want this design to look and feel (style, colours, examples you like, things to avoid, where it will be used).",
    help="The agents and your designer follow this closely. The more specific, the better the first draft.",
)
TARGET_AUDIENCE = f("audience", "Target audience", "textarea", placeholder="Who is this for?")
REFERENCES = f("references", "Reference links or inspiration", "textarea", placeholder="Links, competitors, moodboards")
COPY = f("copy_text", "Text / copy to include", "textarea", placeholder="Headline, body copy, CTA")
SIZES = f("sizes", "Sizes / formats needed", "multiselect", options=["1080x1080 (Square)", "1080x1350 (Portrait)", "1080x1920 (Story)", "1920x1080 (Landscape)", "A4", "Custom"])
CTA = f("cta", "Call to action", placeholder="Shop now, Book a demo...")
NOTES = f("notes", "Anything else we should know?", "textarea")

# --------------------------------------------------------------------------
# Services
# --------------------------------------------------------------------------

SERVICES: List[Dict[str, Any]] = [
    {
        "slug": "logo-design",
        "name": "Logo Design",
        "category": "Branding",
        "icon": "logo",
        "tagline": "A mark your customers remember.",
        "description": "Distinctive, scalable logos with full vector source files and usage guide.",
        "long_description": "We design logos that work everywhere: favicon to billboard. You receive primary, secondary and icon-only versions, light and dark variants, and a mini usage guide so your brand stays consistent across every channel.",
        "turnaround_days": 3,
        "starting_price": 0,
        "deliverables": ["3 initial concepts", "Primary + icon + wordmark", "SVG, PNG, PDF, AI", "Light & dark variants", "Mini brand guide"],
        "form_schema": BRAND_FIELDS + [
            f("industry", "Industry", placeholder="SaaS, restaurant, fitness..."),
            f("logo_type", "Logo type", "select", options=["Wordmark", "Icon + wordmark", "Icon only", "Emblem", "Not sure - recommend"]),
            f("tagline", "Tagline (optional)"),
            TARGET_AUDIENCE, REFERENCES, NOTES,
        ],
    },
    {
        "slug": "social-media-design",
        "name": "Social Media Design",
        "category": "Social Media",
        "icon": "social",
        "tagline": "Scroll-stopping content for every platform.",
        "description": "Posts, stories, covers and templates for Instagram, Facebook, LinkedIn, X and TikTok.",
        "long_description": "Monthly content packs or one-off assets designed on-brand for each platform's dimensions and behaviour. Includes editable templates so your team can post daily without losing consistency.",
        "turnaround_days": 2,
        "starting_price": 0,
        "deliverables": ["Platform-sized exports", "Editable templates", "Caption suggestions"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("platforms", "Platforms", "multiselect", required=True, options=["Instagram", "Facebook", "LinkedIn", "X", "TikTok", "Pinterest"]),
            f("quantity", "Number of designs", "number", required=True, placeholder="e.g. 10"),
            f("topics", "Topics / themes", "textarea", required=True),
            COPY, SIZES, REFERENCES, NOTES,
        ],
    },
    {
        "slug": "instagram-post-design",
        "name": "Instagram Post Design",
        "category": "Social Media",
        "icon": "instagram",
        "tagline": "Feed-perfect posts and stories.",
        "description": "Single posts, carousels and story sets designed for engagement.",
        "long_description": "Posts crafted for Instagram's feed: strong first slide, cohesive grid aesthetic, legible on mobile. We also supply caption ideas and hashtag groups from the Content Agent.",
        "turnaround_days": 1,
        "starting_price": 0,
        "deliverables": ["1080x1350 + 1080x1080 exports", "Story version", "Caption + hashtags"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("post_type", "Post type", "select", required=True, options=["Single image", "Carousel", "Story set", "Quote", "Announcement", "Product"]),
            f("quantity", "How many posts?", "number", required=True),
            COPY, f("hashtags", "Hashtags (optional)"), REFERENCES, NOTES,
        ],
    },
    {
        "slug": "linkedin-carousel-design",
        "name": "LinkedIn Carousel Design",
        "category": "Social Media",
        "icon": "linkedin",
        "tagline": "Swipeable thought leadership.",
        "description": "Multi-slide PDF carousels that position you as the expert.",
        "long_description": "We turn your ideas into clean, high-retention carousels: hook slide, value slides, summary and CTA. Delivered as PDF for native LinkedIn upload plus PNG slides.",
        "turnaround_days": 2,
        "starting_price": 0,
        "deliverables": ["PDF carousel", "PNG slides", "Hook + CTA copy"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("topic", "Carousel topic", required=True),
            f("key_points", "Key points (one per line)", "textarea", required=True),
            f("slides", "Number of slides", "number", placeholder="8-12 recommended"),
            f("tone", "Tone", "select", options=["Professional", "Casual", "Bold", "Educational"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "youtube-thumbnail-design",
        "name": "YouTube Thumbnail Design",
        "category": "Social Media",
        "icon": "youtube",
        "tagline": "Thumbnails that earn the click.",
        "description": "High-CTR thumbnails with bold text, expressive crops and tested layouts.",
        "long_description": "Click-through rate is the whole game. We design 1280x720 thumbnails with contrast, hierarchy and curiosity built in, and offer A/B variants so you can test what works.",
        "turnaround_days": 1,
        "starting_price": 0,
        "deliverables": ["1280x720 thumbnail", "2 A/B variants", "Layered source file"],
        "form_schema": [
            f("channel_name", "Channel name", required=True),
            f("video_title", "Video title", required=True),
            f("video_url", "Video link or raw footage", "url"),
            f("thumbnail_text", "Text on thumbnail (3-5 words)", placeholder="I QUIT MY JOB"),
            f("face_photo", "Will you upload a face photo?", "select", options=["Yes, attached", "No, use graphics only"]),
            f("style", "Style", "select", options=["MrBeast-style bold", "Clean & minimal", "Documentary", "Tech review", "Vlog"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "ad-creative-design",
        "name": "Ad Creative Design",
        "category": "Advertising",
        "icon": "ads",
        "tagline": "Creatives built for conversion.",
        "description": "Static and animated ad sets for Meta, Google, TikTok and LinkedIn campaigns.",
        "long_description": "Performance-first creatives in every placement size, with hook variations, UGC-style layouts and offer-led designs. Each set includes copy angles from the Content Agent.",
        "turnaround_days": 2,
        "starting_price": 0,
        "deliverables": ["Ad set in all placements", "3 hook variants", "Copy angles"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("platform", "Ad platform", "multiselect", required=True, options=["Meta (FB/IG)", "Google Display", "TikTok", "LinkedIn", "X"]),
            f("offer", "Offer / product being promoted", "textarea", required=True),
            f("goal", "Campaign goal", "select", options=["Sales", "Leads", "App installs", "Awareness", "Retargeting"]),
            TARGET_AUDIENCE, CTA, SIZES, REFERENCES, NOTES,
        ],
    },
    {
        "slug": "website-banner-design",
        "name": "Website Banner Design",
        "category": "Advertising",
        "icon": "banner",
        "tagline": "Hero and promo banners that convert visitors.",
        "description": "Homepage heroes, promo strips, category banners and display ads.",
        "long_description": "Banners sized precisely for your site, retina-ready and optimised for load time. We align the message, visual and CTA so the banner does its one job: move the visitor to action.",
        "turnaround_days": 1,
        "starting_price": 0,
        "deliverables": ["Banner in required sizes", "Retina exports", "Source file"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("site_url", "Website URL", "url"),
            f("placement", "Where will it go?", "select", options=["Homepage hero", "Promo strip", "Category page", "Sidebar", "Pop-up", "Display ad network"]),
            f("dimensions", "Exact dimensions (px)", required=True, placeholder="1920x600"),
            COPY, CTA, REFERENCES, NOTES,
        ],
    },
    {
        "slug": "pitch-deck-design",
        "name": "Pitch Deck Design",
        "category": "Presentations",
        "icon": "deck",
        "tagline": "Decks investors actually read.",
        "description": "Investor-ready pitch decks with clear narrative, data visualisation and polish.",
        "long_description": "From seed to Series B, we structure and design decks that tell a compelling story: problem, solution, traction, market, team, ask. Includes editable PowerPoint/Keynote/Google Slides file.",
        "turnaround_days": 5,
        "starting_price": 0,
        "deliverables": ["Designed deck (PPTX/Keynote/Slides)", "PDF export", "Custom charts & icons"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("stage", "Fundraising stage", "select", options=["Pre-seed", "Seed", "Series A", "Series B+", "Internal / sales deck"]),
            f("slide_count", "Approximate slides", "number", placeholder="12-15"),
            f("content_status", "Content status", "select", required=True, options=["Full content ready (attached)", "Rough outline", "Need help writing"]),
            f("format", "Final format", "select", options=["PowerPoint", "Google Slides", "Keynote", "PDF only"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "presentation-design",
        "name": "Presentation Design",
        "category": "Presentations",
        "icon": "presentation",
        "tagline": "Slides that make you look sharp.",
        "description": "Sales, training, conference and internal presentations redesigned on-brand.",
        "long_description": "Send us your rough slides; get back a consistent, modern deck with a reusable master template, custom graphics and clean data charts.",
        "turnaround_days": 3,
        "starting_price": 0,
        "deliverables": ["Redesigned deck", "Master template", "Icon set"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("purpose", "Purpose", "select", options=["Sales", "Conference talk", "Training", "Board update", "Webinar", "Other"]),
            f("slide_count", "Number of slides", "number"),
            f("format", "Final format", "select", options=["PowerPoint", "Google Slides", "Keynote", "PDF only"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "brochure-design",
        "name": "Brochure Design",
        "category": "Print",
        "icon": "brochure",
        "tagline": "Print collateral with premium finish.",
        "description": "Bi-fold, tri-fold and multi-page brochures, print-ready with bleed.",
        "long_description": "Layouts that guide the reader, typography set for print, images optimised at 300dpi, and press-ready PDFs with bleed and crop marks. Digital flipbook version included.",
        "turnaround_days": 4,
        "starting_price": 0,
        "deliverables": ["Print-ready PDF (bleed)", "Digital PDF", "Source file"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("fold", "Format", "select", required=True, options=["Bi-fold", "Tri-fold", "Z-fold", "Booklet (8+ pages)", "Single sheet"]),
            f("size", "Paper size", "select", options=["A4", "A5", "US Letter", "DL", "Custom"]),
            f("content_status", "Content", "select", required=True, options=["All text & images attached", "Partial", "Need copywriting"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "flyer-design",
        "name": "Flyer Design",
        "category": "Print",
        "icon": "flyer",
        "tagline": "One page. Big impact.",
        "description": "Event, promo and product flyers for print and digital distribution.",
        "long_description": "A flyer has seconds to work. We design a clear hierarchy, one strong visual and an unmissable call to action, in print and social-ready versions.",
        "turnaround_days": 1,
        "starting_price": 0,
        "deliverables": ["Print PDF", "Digital/social version", "Source file"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("event_or_offer", "What is it promoting?", "textarea", required=True),
            f("size", "Size", "select", options=["A4", "A5", "US Letter", "Digital only"]),
            f("sides", "Sides", "select", options=["Single-sided", "Double-sided"]),
            COPY, REFERENCES, NOTES,
        ],
    },
    {
        "slug": "poster-design",
        "name": "Poster Design",
        "category": "Print",
        "icon": "poster",
        "tagline": "Large format, larger presence.",
        "description": "Event, retail and campaign posters from A3 to billboard.",
        "long_description": "Posters that read from across the room. Bold composition, correct resolution for the final size, and versions for digital screens.",
        "turnaround_days": 2,
        "starting_price": 0,
        "deliverables": ["Print-ready poster", "Digital version", "Source file"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("purpose", "Purpose", "select", options=["Event", "Retail / in-store", "Campaign", "Movie / music", "Motivational", "Other"]),
            f("size", "Size", "select", options=["A3", "A2", "A1", "24x36 in", "Digital screen", "Custom"]),
            COPY, REFERENCES, NOTES,
        ],
    },
    {
        "slug": "infographic-design",
        "name": "Infographic Design",
        "category": "Content",
        "icon": "infographic",
        "tagline": "Make data impossible to ignore.",
        "description": "Data stories, process diagrams and statistics turned into shareable visuals.",
        "long_description": "We transform spreadsheets and bullet points into a visual narrative: custom icons, accurate charts and a flow that leads the eye. Formats for blog, social and print.",
        "turnaround_days": 3,
        "starting_price": 0,
        "deliverables": ["Infographic (PNG/PDF)", "Social crops", "Source file"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("data", "Data / content (paste or attach)", "textarea", required=True),
            f("orientation", "Orientation", "select", options=["Vertical (blog/Pinterest)", "Horizontal", "Square (social)", "Multi-part"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "reels-cover-design",
        "name": "Reels Cover Design",
        "category": "Social Media",
        "icon": "reels",
        "tagline": "A grid that looks curated.",
        "description": "Consistent cover images for Reels, TikToks and Shorts.",
        "long_description": "Cover sets that keep your profile grid cohesive and tell viewers what the video is about at a glance. Batch pricing for weekly content.",
        "turnaround_days": 1,
        "starting_price": 0,
        "deliverables": ["1080x1920 covers", "Grid-safe crop", "Template"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("quantity", "Number of covers", "number", required=True),
            f("titles", "Video titles (one per line)", "textarea", required=True),
            f("style", "Style", "select", options=["Text-led", "Photo-led", "Mixed", "Match my grid (attach screenshot)"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "ecommerce-creative-design",
        "name": "E-commerce Creative Design",
        "category": "Advertising",
        "icon": "ecommerce",
        "tagline": "Product visuals that sell.",
        "description": "Listing images, A+ content, lifestyle composites and promo graphics for stores.",
        "long_description": "Amazon, Shopify, Etsy or your own store: we create conversion-focused product images, infographics with benefits, comparison charts and seasonal promo creatives.",
        "turnaround_days": 2,
        "starting_price": 0,
        "deliverables": ["Listing image set", "A+ / EBC modules", "Promo graphics"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("marketplace", "Marketplace / platform", "multiselect", options=["Amazon", "Shopify", "Etsy", "WooCommerce", "Flipkart", "Other"]),
            f("product", "Product name & key benefits", "textarea", required=True),
            f("product_photos", "Product photos attached?", "select", options=["Yes", "No, need stock/3D render"]),
            f("image_count", "Number of images", "number"),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "product-advertisement-design",
        "name": "Product Advertisement Design",
        "category": "Advertising",
        "icon": "product-ad",
        "tagline": "Hero shots and launch visuals.",
        "description": "Launch creatives, feature callouts and lifestyle compositions for products.",
        "long_description": "For launches and campaigns: dramatic product hero images, feature-highlight layouts and multi-format ad adaptations ready for paid and organic use.",
        "turnaround_days": 2,
        "starting_price": 0,
        "deliverables": ["Hero creative", "Feature callouts", "Multi-size adaptations"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("product", "Product name", required=True),
            f("usp", "Key selling points", "textarea", required=True),
            f("mood", "Mood", "select", options=["Premium", "Energetic", "Natural", "Tech", "Playful"]),
            SIZES, CTA, REFERENCES, NOTES,
        ],
    },
    {
        "slug": "business-card-design",
        "name": "Business Card Design",
        "category": "Branding",
        "icon": "business-card",
        "tagline": "Small card. Strong first impression.",
        "description": "Print-ready business cards with front/back designs and finish recommendations.",
        "long_description": "Classic to unconventional: we design cards with correct bleed, safe zones and CMYK, and recommend paper stock and finishes (spot UV, foil, letterpress) to match your brand.",
        "turnaround_days": 1,
        "starting_price": 0,
        "deliverables": ["Front & back print PDF", "Digital card", "Finish recommendations"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("details", "Details to include (name, title, phone, email, address)", "textarea", required=True),
            f("size", "Size", "select", options=["Standard 3.5x2 in", "EU 85x55 mm", "Square", "Custom"]),
            f("finish", "Finish preference", "select", options=["Matte", "Gloss", "Spot UV", "Foil", "Not sure"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "company-profile-design",
        "name": "Company Profile Design",
        "category": "Branding",
        "icon": "profile",
        "tagline": "Your company, beautifully documented.",
        "description": "Corporate profiles and capability documents for sales and partnerships.",
        "long_description": "A multi-page company profile that covers story, services, team, case studies and contact, designed for both print and interactive PDF with clickable navigation.",
        "turnaround_days": 5,
        "starting_price": 0,
        "deliverables": ["Interactive PDF", "Print PDF", "Editable source"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("pages", "Approximate pages", "number", placeholder="8-16"),
            f("sections", "Sections to include", "multiselect", options=["About", "Services", "Team", "Case studies", "Clients", "Process", "Contact"]),
            f("content_status", "Content", "select", required=True, options=["All content attached", "Partial", "Need copywriting"]),
            REFERENCES, NOTES,
        ],
    },
    {
        "slug": "custom-design-requests",
        "name": "Custom Design Requests",
        "category": "Custom",
        "icon": "custom",
        "tagline": "If you can describe it, we can design it.",
        "description": "Anything not covered above: merch, packaging, icons, illustrations, UI mockups.",
        "long_description": "Packaging, merch, app icons, illustrations, email templates, UI screens, signage: describe the outcome and the Project Manager Agent will scope it, estimate turnaround and route it through the pipeline.",
        "turnaround_days": 3,
        "starting_price": 0,
        "deliverables": ["Scoped by Project Manager Agent", "Final files in requested formats"],
        "form_schema": BRAND_FIELDS[:1] + [
            f("what", "What do you need?", "textarea", required=True),
            f("formats", "Final formats needed", placeholder="PNG, SVG, PDF, Figma..."),
            f("deadline", "Ideal deadline", "text", placeholder="e.g. before Friday"),
            REFERENCES, NOTES,
        ],
    },
]

# Fixed per-request launch prices in USD (introductory, 75% below standard rates) (GBP / INR derived with FX_GBP / FX_INR).
PRICES_USD = {
    "logo-design": 19,
    "social-media-design": 25,
    "instagram-post-design": 13,
    "linkedin-carousel-design": 13,
    "youtube-thumbnail-design": 13,
    "ad-creative-design": 17,
    "website-banner-design": 13,
    "pitch-deck-design": 50,
    "presentation-design": 32,
    "brochure-design": 23,
    "flyer-design": 13,
    "poster-design": 13,
    "infographic-design": 17,
    "reels-cover-design": 13,
    "ecommerce-creative-design": 19,
    "product-advertisement-design": 15,
    "business-card-design": 13,
    "company-profile-design": 44,
    "custom-design-requests": 13,
}
# What the price covers (shown next to the price).
PRICE_UNITS = {
    "social-media-design": "per pack of 10 designs",
    "instagram-post-design": "per post",
    "linkedin-carousel-design": "per carousel",
    "youtube-thumbnail-design": "per thumbnail (2 variants)",
    "ad-creative-design": "per ad set",
    "reels-cover-design": "per set of 8 covers",
    "ecommerce-creative-design": "per listing set",
    "custom-design-requests": "starting price, quoted per request",
}

for _i, _s in enumerate(SERVICES):
    _s["sort_order"] = _i + 1
    # Every service asks the client to describe their business and how they want the work done,
    # right after the brand/company fields.
    if not any(fld["key"] == "about_and_wishes" for fld in _s["form_schema"]):
        pos = 1 if _s["form_schema"] and _s["form_schema"][0]["key"] in ("brand_name", "channel_name") else 0
        _s["form_schema"].insert(pos, dict(ABOUT_AND_WISHES))
    _s["starting_price"] = PRICES_USD[_s["slug"]]
    _s["price_unit"] = PRICE_UNITS.get(_s["slug"], "per request")

# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------

AGENTS: List[Dict[str, Any]] = [
    {"key": "lead", "name": "Lead Agent", "description": "Finds businesses, analyses their websites and stores qualified leads.", "schedule": "0 9 * * *"},
    {"key": "outreach", "name": "Outreach Agent", "description": "Writes personalised outreach emails, sends them and schedules follow-ups.", "schedule": "0 8 * * *"},
    {"key": "onboarding", "name": "Onboarding Agent", "description": "Sets up new clients: folders, welcome message, asset collection.", "schedule": None},
    {"key": "project_manager", "name": "Project Manager Agent", "description": "Organises incoming requests, sets priorities and plans the work.", "schedule": None},
    {"key": "strategy", "name": "Strategy Agent", "description": "Researches competitors and brand positioning for each request.", "schedule": None},
    {"key": "content", "name": "Content Agent", "description": "Writes captions, headlines, ad copy and on-design text.", "schedule": None},
    {"key": "design", "name": "Design Agent", "description": "Produces design concepts, layouts and draft visuals.", "schedule": None},
    {"key": "revision", "name": "Revision Agent", "description": "Turns client feedback into concrete change lists and re-runs the pipeline.", "schedule": None},
    {"key": "qa", "name": "QA Agent", "description": "Checks output against the brief and brand guidelines; scores quality.", "schedule": None},
    {"key": "delivery", "name": "Delivery Agent", "description": "Packages final files, uploads to Drive and sends download links.", "schedule": None},
    {"key": "marketing", "name": "Marketing Agent", "description": "Creates LinkedIn, Instagram and X posts promoting the agency.", "schedule": "0 10 * * 1,3,5"},
]

for _i, _a in enumerate(AGENTS):
    _a["sort_order"] = _i + 1
