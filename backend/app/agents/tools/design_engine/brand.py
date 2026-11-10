"""Brand kit: everything the layouts need, derived from what the client actually wrote.

Priority of sources: the request form (brief) > the client's brand assets > the Design Agent's concept >
industry defaults. Feedback from reworks/revisions ("warmer", "darker", "bigger headline", "use navy") is
applied on top, and every new version uses the next layout variant so a rework always looks different.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.agents.tools.design_engine import color as col
from app.agents.tools.design_engine.fonts import Face, face
from app.agents.tools.design_engine.icons import CLICHES, detect_industry, motif_preferences

STYLES = ["Minimal", "Bold", "Playful", "Luxury", "Corporate", "Modern", "Vintage"]

# heading, body, label (small caps), display alternative
STYLE_FONTS: Dict[str, Dict[str, Tuple[str, int]]] = {
    "Minimal": {"heading": ("Montserrat", 600), "body": ("Inter", 400), "label": ("Inter", 600), "display": ("Montserrat", 300)},
    "Bold": {"heading": ("Archivo Black", 400), "body": ("Inter", 500), "label": ("Oswald", 600), "display": ("Oswald", 700)},
    "Playful": {"heading": ("Nunito", 900), "body": ("Nunito", 600), "label": ("Nunito", 800), "display": ("Pacifico", 400)},
    "Luxury": {"heading": ("Playfair Display", 600), "body": ("Montserrat", 400), "label": ("Montserrat", 500), "display": ("Playfair Display", 400)},
    "Corporate": {"heading": ("Montserrat", 700), "body": ("Inter", 400), "label": ("Inter", 600), "display": ("Montserrat", 800)},
    "Modern": {"heading": ("Space Grotesk", 700), "body": ("Inter", 400), "label": ("Space Grotesk", 500), "display": ("Space Grotesk", 600)},
    "Vintage": {"heading": ("DM Serif Display", 400), "body": ("Raleway", 500), "label": ("Raleway", 700), "display": ("Abril Fatface", 400)},
}
STYLE_RADIUS = {"Minimal": 6, "Bold": 10, "Playful": 30, "Luxury": 0, "Corporate": 10, "Modern": 20, "Vintage": 4}
STYLE_CASE = {"Minimal": "upper", "Bold": "upper", "Playful": "title", "Luxury": "upper", "Corporate": "title", "Modern": "title", "Vintage": "upper"}

_STOP = {"and", "&", "the", "of", "co", "co.", "ltd", "limited", "inc", "llc", "plc", "a"}


@dataclass
class Tweaks:
    hue_shift: float = 0.0
    saturation: float = 1.0
    theme: Optional[str] = None  # "dark" | "light"
    headline_scale: float = 1.0
    minimal: bool = False
    font_pref: Optional[str] = None  # "serif" | "sans" | "script"
    radius: Optional[float] = None
    primary: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class Brand:
    name: str
    initials: str
    tagline: str
    descriptor: str
    location: str
    industry: str
    motif: str
    style: str
    case: str
    radius: float
    primary: str
    secondary: str
    accent: str
    dark: str
    light: str
    paper: str
    ink: str
    muted: str
    heading: Face
    body: Face
    label: Face
    display: Face
    body_bold: Face
    theme: str
    variant: int
    website: str = ""
    handle: str = ""
    avoid: List[str] = field(default_factory=list)  # symbols the client does not want (e.g. "bean")
    avoid_phrases: List[str] = field(default_factory=list)  # their own words: "coffee-bean clichés", "nothing corporate"
    logo_href: Optional[str] = None  # client's own logo (data URI) if they uploaded one
    photos: List[str] = field(default_factory=list)  # data URIs of client photos for this request
    tweaks: Tweaks = field(default_factory=Tweaks)

    def cased(self, s: str) -> str:
        return s.upper() if self.case == "upper" else s

    @property
    def palette(self) -> List[Tuple[str, str]]:
        return [("Primary", self.primary), ("Secondary", self.secondary), ("Accent", self.accent), ("Dark", self.dark), ("Light", self.light)]

    def on(self, bg: str) -> str:
        """Readable text colour on a background."""
        return col.readable_on(bg, self.ink, self.dark, self.light, "#FFFFFF")

    def soft_on(self, bg: str) -> str:
        t = self.on(bg)
        return col.mix(t, bg, 0.32)


def _get(brief: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = brief.get(k)
        if isinstance(v, list):
            v = ", ".join(map(str, v))
        if v not in (None, ""):
            return str(v).strip()
    return ""


def initials_of(name: str) -> str:
    words = [w for w in re.split(r"[\s\-_/]+", name) if w and w.lower() not in _STOP and re.search(r"[A-Za-z0-9]", w)]
    if not words:
        return (name[:1] or "B").upper()
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[1][0]).upper()


def infer_style(text: str) -> str:
    t = text.lower()
    rules = [
        (r"luxur|premium|elegan|high[- ]end|sophisticat|exclusive|boutique", "Luxury"),
        (r"vintage|retro|heritage|classic|handcraft|artisan|rustic|traditional|old[- ]school|craft", "Vintage"),
        (r"playful|fun\b|kids|children|colourful|colorful|friendly|cute|whimsical", "Playful"),
        (r"\bbold\b|loud|energetic|punchy|striking|high energy|mrbeast", "Bold"),
        (r"minimal|clean|simple|understated|scandi|less is more", "Minimal"),
        (r"corporate|professional|enterprise|b2b|trustworth|finance|law|consult", "Corporate"),
    ]
    for pat, style in rules:
        if re.search(pat, t):
            return style
    return "Modern"


def parse_feedback(items: List[str]) -> Tweaks:
    tw = Tweaks()
    text = " ".join(i for i in items if i).lower()
    if not text:
        return tw
    tw.notes = [i for i in items if i][:6]
    if re.search(r"warm(er)?", text):
        tw.hue_shift -= 14
    if re.search(r"cool(er)?|colder", text):
        tw.hue_shift += 14
    if re.search(r"dark (mode|background|theme)|darker|moodier|black background", text):
        tw.theme = "dark"
    if re.search(r"light (background|theme)|lighter|brighter|white background|airier", text):
        tw.theme = "light"
    if re.search(r"(bigger|larger|bolder|more prominent).{0,20}(headline|title|text|heading|name)|(headline|title|heading|name).{0,20}(bigger|larger|bolder)", text):
        tw.headline_scale = 1.18
    if re.search(r"(smaller|subtler).{0,20}(headline|title|text|heading)|(headline|title|heading).{0,20}smaller", text):
        tw.headline_scale = 0.85
    if re.search(r"less text|fewer words|simpler|more minimal|declutter|cleaner|too busy|too much", text):
        tw.minimal = True
    if re.search(r"more colou?r|vibrant|saturated|pop more|punchier", text):
        tw.saturation = 1.25
    if re.search(r"muted|softer|pastel|calmer|desaturat", text):
        tw.saturation = 0.75
    if re.search(r"\bserif\b|elegant font|classic font", text):
        tw.font_pref = "serif"
    if re.search(r"sans[- ]?serif|modern font|clean font", text):
        tw.font_pref = "sans"
    if re.search(r"script|handwritten|cursive", text):
        tw.font_pref = "script"
    if re.search(r"round(ed|er)?\b|softer corners", text):
        tw.radius = 28
    if re.search(r"sharp(er)?|square corners|angular", text):
        tw.radius = 0
    named = col.extract([text])
    if named:
        tw.primary = named[0]
    return tw


def _location(text: str) -> str:
    m = re.search(r"\b(?:in|from|based in|located in)\s+([A-Z][a-z]+(?:[ -][A-Z][a-z]+)?)", text or "")
    if m and m.group(1).lower() not in {"the", "our", "a", "we", "my", "your", "every", "each", "this", "english", "british"}:
        return m.group(1)
    return ""


def _domain(url: str) -> str:
    m = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9.-]+\.[a-z]{2,})", (url or "").lower())
    return m.group(1) if m else ""


def build(ctx: Dict[str, Any]) -> Brand:
    brief: Dict[str, Any] = ctx.get("brief") or {}
    client: Dict[str, Any] = ctx.get("client") or {}
    concept: Dict[str, Any] = ctx.get("concept") or {}
    content: Dict[str, Any] = ctx.get("content") or {}
    version = int(ctx.get("version") or 1)
    tweaks = parse_feedback(list(ctx.get("feedback") or []))

    name = _get(brief, "brand_name", "channel_name") or client.get("company_name") or ctx.get("title") or "Your Brand"
    name = re.sub(r"\s+", " ", name).strip()
    about = _get(brief, "about_and_wishes")
    blob = " ".join(filter(None, [about, _get(brief, "industry", "topics", "product", "offer", "event_or_offer", "what", "topic", "data", "notes"),
                                  client.get("industry"), client.get("brand_notes"), ctx.get("title"), ctx.get("description"), name]))
    industry, motif, ind_palette = detect_industry(_get(brief, "industry"), client.get("industry"), blob)
    # the client's own words decide the symbol: "a simple leaf mark" wins, "avoid coffee-bean clichés" is respected
    strategy = ctx.get("strategy") or {}
    client_texts = [about, _get(brief, "notes", "references", "what", "tagline")]
    concepts = [concept] + [c for c in (ctx.get("concepts") or []) if isinstance(c, dict)]
    agent_texts = [" ".join(str(c.get(k) or "") for k in ("imagery", "description", "title")) for c in concepts]
    agent_texts += [str(strategy.get("creative_direction") or ""), " ".join(map(str, strategy.get("dont") or [])) if isinstance(strategy.get("dont"), list) else ""]
    wanted, avoid = motif_preferences(client_texts, agent_texts, brand_name=name, feedback_texts=list(tweaks.notes))
    if re.search(r"clich", " ".join(client_texts + list(tweaks.notes)), re.I):
        avoid |= CLICHES.get(industry, set())
        wanted = [w for w in wanted if w not in avoid]
    if wanted:
        motif = wanted[0]
    elif motif in avoid:
        fallback = {"bean": ["cup", "leaf", "spark"], "cup": ["leaf", "spark"], "wheat": ["sprout", "leaf", "spark"], "cutlery": ["chef", "leaf", "spark"],
                    "chef": ["leaf", "spark"]}.get(motif, ["spark", "star"])
        motif = next((m for m in fallback if m not in avoid), "spark")

    # ---- style --------------------------------------------------------------
    style = _get(brief, "style")
    style_map = {"MrBeast-style bold": "Bold", "Clean & minimal": "Minimal", "Documentary": "Corporate", "Tech review": "Modern", "Vlog": "Playful"}
    style = style_map.get(style, style)
    mood = _get(brief, "mood", "tone")
    mood_map = {"Premium": "Luxury", "Energetic": "Bold", "Natural": "Vintage", "Tech": "Modern", "Playful": "Playful", "Professional": "Corporate",
                "Casual": "Playful", "Bold": "Bold", "Educational": "Modern"}
    if style not in STYLES:
        style = mood_map.get(mood) or infer_style(" ".join([about, _get(brief, "notes", "references"), str(concept.get("typography") or "")]))
    if tweaks.font_pref == "serif" and style not in ("Luxury", "Vintage"):
        style = "Luxury" if style in ("Minimal", "Corporate") else "Vintage"
    elif tweaks.font_pref == "sans" and style in ("Luxury", "Vintage"):
        style = "Modern"

    # ---- palette ------------------------------------------------------------
    mentioned = col.extract([_get(brief, "brand_colors"), about, _get(brief, "notes"), client.get("brand_notes")])
    for c in ctx.get("asset_colors") or []:
        if c not in mentioned:
            mentioned.append(col.norm(c))
    if not mentioned:
        mentioned = [col.norm(c) for c in (concept.get("palette") or []) if isinstance(c, str) and re.fullmatch(r"#?[0-9A-Fa-f]{6}", c.strip())][:4]
    if tweaks.primary:
        mentioned = [tweaks.primary] + [c for c in mentioned if c != tweaks.primary]

    chromatic = [c for c in mentioned if not col.is_neutral(c)]
    darks = sorted([c for c in mentioned if col.luminance(c) < 0.06], key=col.luminance)
    lights = sorted([c for c in mentioned if col.luminance(c) > 0.72], key=col.luminance, reverse=True)
    i_primary, i_dark, i_light, i_accent = ind_palette

    primary = next((c for c in chromatic if 0.03 < col.luminance(c) < 0.65), None) or (chromatic[0] if chromatic else None)
    if not primary:
        primary = darks[0] if darks and not lights else i_primary
        if mentioned and darks and col.luminance(darks[0]) < 0.06 and col.chroma(darks[0]) > 0.08:
            primary = darks[0]
    dark = darks[0] if darks else (col.with_lightness(primary, 0.13) if col.chroma(primary) > 0.1 else i_dark)
    if col.contrast(dark, "#FFFFFF") < 10:
        dark = col.with_lightness(dark, 0.12)
    if col.luminance(primary) < 0.035 or primary == dark:
        # the client's main colour is very dark (e.g. "deep brown", "navy"): keep it for text/dark surfaces and
        # use a richer mid-tone of the same hue as the brand colour so logos and buttons have presence
        dark = primary if col.luminance(primary) < 0.06 else dark
        primary = col.with_lightness(primary, 0.33) if col.chroma(primary) > 0.05 else i_primary
    light = lights[0] if lights else (col.mix(i_light, col.with_lightness(primary, 0.96), 0.35) if mentioned else i_light)
    others = [c for c in chromatic if c not in (primary, dark) and col.contrast(c, primary) > 1.4 and col.contrast(c, dark) > 1.4]
    if others:
        accent = others[0]
    elif col.contrast(i_accent, primary) > 1.4 and abs(col.hls(i_accent)[0] - col.hls(primary)[0]) * 360 % 360 < 200:
        accent = i_accent
    else:  # analogous, slightly warmer and deeper than the primary (never a clashing complementary)
        accent = col.with_lightness(col.rotate(primary, -22), max(0.38, min(0.55, col.hls(primary)[1] - 0.08)))
    secondary = others[1] if len(others) > 1 else col.mix(primary, light, 0.55)

    if tweaks.hue_shift:
        primary, accent, secondary = (col.rotate(c, tweaks.hue_shift) for c in (primary, accent, secondary))
        light = col.mix(light, "#FFF4E6" if tweaks.hue_shift < 0 else "#EEF5FF", 0.35)
    if tweaks.saturation != 1.0:
        primary, accent, secondary = (col.saturate(c, tweaks.saturation) for c in (primary, accent, secondary))

    paper = light if col.luminance(light) > 0.75 else "#FFFFFF"
    ink = dark if col.contrast(dark, paper) >= 7 else "#141414"
    muted = col.mix(ink, paper, 0.42)

    theme = tweaks.theme or {"Luxury": "dark", "Bold": "dark"}.get(style, "light")
    # alternate theme on odd re-works when the client did not say which they want
    if not tweaks.theme and version > 1 and version % 2 == 0:
        theme = "dark" if theme == "light" else "light"

    fonts = STYLE_FONTS[style]
    heading = face(*fonts["heading"])
    body = face(*fonts["body"])
    label = face(*fonts["label"])
    display = face(*fonts["display"])
    if tweaks.font_pref == "script":
        display = face("Pacifico", 400)
    body_bold = face(fonts["body"][0], 700 if fonts["body"][0] not in ("Archivo Black",) else 400)

    tagline = _get(brief, "tagline") or str(concept.get("tagline") or "") or ""
    if not tagline:
        from app.agents.tools.design_engine.common import _as_list as _copy_list

        subs = _copy_list(content.get("subheadlines"))
        if subs and len(subs[0]) <= 48:
            tagline = subs[0].rstrip(".")
    descriptor = _get(brief, "industry") or industry
    website = _domain(_get(brief, "site_url", "website") or client.get("website") or "")
    handle = ""
    m = re.search(r"@([A-Za-z0-9_.]{3,30})", " ".join([_get(brief, "copy_text", "notes", "details"), about]))
    if m:
        handle = "@" + m.group(1)

    neg = re.compile(r"\b(?:avoid|no|not|without|never|nothing|don'?t (?:use|want))\b[^.;:!?\n]{2,48}", re.I)
    avoid_phrases = [m.group(0).strip(" ,") for m in neg.finditer(" ".join(client_texts + list(tweaks.notes)))][:6]
    return Brand(
        avoid=sorted(avoid), avoid_phrases=avoid_phrases,
        name=name, initials=initials_of(name), tagline=tagline, descriptor=descriptor, location=_location(about),
        industry=industry, motif=motif, style=style, case=STYLE_CASE[style],
        radius=tweaks.radius if tweaks.radius is not None else STYLE_RADIUS[style],
        primary=primary, secondary=secondary, accent=accent, dark=dark, light=light, paper=paper, ink=ink, muted=muted,
        heading=heading, body=body, label=label, display=display, body_bold=body_bold, theme=theme, variant=version - 1,
        website=website, handle=handle, logo_href=ctx.get("logo_href"), photos=list(ctx.get("photos") or []), tweaks=tweaks,
    )
