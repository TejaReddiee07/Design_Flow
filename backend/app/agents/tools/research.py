"""Website research helpers used by the Strategy and Lead agents."""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

log = logging.getLogger("agents.research")

_TAG_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_HTML_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def fetch_site_text(url: Optional[str], max_chars: int = 4000, timeout: float = 8.0) -> str:
    """Fetch a page and return its visible text (best effort, never raises)."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    if ".example.com" in url or "localhost" in url:
        return ""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "DesignflowBot/1.0 (+research)"}) as client:
            r = client.get(url)
            if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
                return ""
            html = _TAG_RE.sub(" ", r.text)
            text = _WS_RE.sub(" ", _HTML_RE.sub(" ", html)).strip()
            return text[:max_chars]
    except Exception as exc:
        log.debug("fetch_site_text(%s) failed: %s", url, exc)
        return ""


def extract_title(html_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.S | re.I)
    return _WS_RE.sub(" ", m.group(1)).strip()[:160] if m else ""
