"""Lead discovery providers for the Lead Agent.

web     - (default, no key) searches DuckDuckGo for businesses that need the kinds of design we sell,
          opens their websites and extracts the company name and a contact email.
serpapi - Google Maps local results via SerpAPI (LEAD_PROVIDER=serpapi + SERPAPI_KEY).
"""
from __future__ import annotations

import html as htmlmod
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.core.config import settings

log = logging.getLogger("agents.leads")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DesignflowLeadBot/1.0"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SKIP_DOMAINS = (
    "duckduckgo.", "google.", "facebook.", "instagram.", "linkedin.", "youtube.", "twitter.", "x.com", "tiktok.",
    "yelp.", "tripadvisor.", "wikipedia.", "amazon.", "pinterest.", "reddit.", "glassdoor.", "indeed.", "crunchbase.",
    "yellowpages.", "clutch.", "upwork.", "fiverr.", "behance.", "dribbble.", "canva.", "shopify.com", "wix.com",
)
BAD_EMAIL = ("example.", "sentry", "wixpress", "@2x", ".png", ".jpg", "noreply", "no-reply", "donotreply", "@domain")

# Which kinds of businesses tend to buy each service. The agent rotates through these.
SERVICE_QUERIES: Dict[str, List[str]] = {
    "logo-design": ["new restaurant opening", "startup launched", "boutique shop", "new cafe"],
    "social-media-design": ["restaurant", "fitness studio", "dental clinic", "beauty salon"],
    "youtube-thumbnail-design": ["youtube channel podcast", "online course creator", "gaming channel", "finance youtuber"],
    "ad-creative-design": ["ecommerce store", "shopify store", "online boutique", "direct to consumer brand"],
    "pitch-deck-design": ["startup raising seed round", "tech startup", "saas startup", "pre-seed startup"],
    "ecommerce-creative-design": ["amazon seller", "etsy shop", "online store", "product brand"],
    "brochure-design": ["law firm", "dental practice", "real estate agency", "consulting firm"],
}


def _clean_name(title: str, domain: str) -> str:
    t = htmlmod.unescape(title or "")
    t = re.split(r"\s[|\-–:•]\s", t)[0].strip()
    if not t or len(t) < 2:
        t = domain.split(".")[0].replace("-", " ").title()
    return t[:120]


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def _ddg_links(query: str, client: httpx.Client, max_links: int = 12) -> List[str]:
    try:
        r = client.post("https://html.duckduckgo.com/html/", data={"q": query}, timeout=15)
        if r.status_code != 200:
            return []
    except Exception as exc:
        log.warning("DuckDuckGo search failed: %s", exc)
        return []
    links: List[str] = []
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"', r.text):
        href = htmlmod.unescape(m.group(1))
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if not href.startswith("http"):
            continue
        d = _domain(href)
        if any(s in d for s in SKIP_DOMAINS):
            continue
        base = f"{urlparse(href).scheme}://{urlparse(href).netloc}"
        if base not in links:
            links.append(base)
        if len(links) >= max_links:
            break
    return links


def _inspect_site(url: str, client: httpx.Client) -> Optional[Dict[str, Any]]:
    try:
        r = client.get(url, timeout=12, follow_redirects=True)
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
            return None
        page = r.text
    except Exception:
        return None
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    emails = [e for e in EMAIL_RE.findall(page) if not any(b in e.lower() for b in BAD_EMAIL)]
    if not emails:
        for path in ("/contact", "/contact-us", "/about"):
            try:
                r2 = client.get(url.rstrip("/") + path, timeout=8, follow_redirects=True)
                if r2.status_code < 400:
                    emails = [e for e in EMAIL_RE.findall(r2.text) if not any(b in e.lower() for b in BAD_EMAIL)]
                    if emails:
                        break
            except Exception:
                continue
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I))
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "company_name": _clean_name(title.group(1) if title else "", _domain(url)),
        "website": url,
        "contact_email": emails[0].lower() if emails else None,
        "site_text": text[:3000],
    }


def web_find(industry: Optional[str], location: Optional[str], count: int, service_slug: Optional[str] = None) -> List[Dict[str, Any]]:
    """Real discovery: search → open sites → extract contact. Returns up to `count` businesses."""
    themes = SERVICE_QUERIES.get(service_slug or "", []) or [q for qs in SERVICE_QUERIES.values() for q in qs]
    if industry:
        themes = [industry] + themes
    out: List[Dict[str, Any]] = []
    seen: set = set()
    with httpx.Client(headers=HEADERS) as client:
        for theme in themes:
            if len(out) >= count:
                break
            query = f"{theme} {location or ''} official website contact".strip()
            for link in _ddg_links(query, client):
                if len(out) >= count:
                    break
                d = _domain(link)
                if d in seen:
                    continue
                seen.add(d)
                info = _inspect_site(link, client)
                if not info:
                    continue
                info.update({"industry": industry or theme.title(), "location": location, "contact_name": None, "contact_phone": None,
                             "source": "agent:web", "query": query, "service_slug": service_slug})
                out.append(info)
                time.sleep(0.5)
    return out


def serpapi_find(industry: Optional[str], location: Optional[str], count: int) -> List[Dict[str, Any]]:
    if not settings.serpapi_key:
        raise RuntimeError("SERPAPI_KEY not set")
    q = f"{industry or 'small business'} in {location or 'United States'}"
    params = {"engine": "google_maps", "q": q, "type": "search", "api_key": settings.serpapi_key}
    with httpx.Client(timeout=20) as client:
        r = client.get("https://serpapi.com/search.json", params=params)
        r.raise_for_status()
        data = r.json()
    out = []
    for item in (data.get("local_results") or [])[:count]:
        out.append({"company_name": item.get("title") or "Unknown", "website": item.get("website"), "industry": industry or (item.get("type") or ""),
                    "location": item.get("address") or location, "contact_name": None, "contact_email": None, "contact_phone": item.get("phone"),
                    "source": "agent:serpapi", "site_text": ""})
    return out


def find_businesses(industry: Optional[str], location: Optional[str], count: int = 5, service_slug: Optional[str] = None) -> List[Dict[str, Any]]:
    provider = settings.lead_provider.lower()
    if provider == "serpapi":
        try:
            return serpapi_find(industry, location, count)
        except Exception as exc:
            log.warning("SerpAPI failed (%s); using web search", exc)
    return web_find(industry, location, count, service_slug)
