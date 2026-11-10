"""How a client is named across the app.

Individuals often type a placeholder into the company field ("Personal", "Personal User", "N/A", "Self").
Those are not company names, so the person's own name is used everywhere instead.
"""
from __future__ import annotations

import re
from typing import Optional

PLACEHOLDER_COMPANIES = {
    "personal", "personal user", "personal account", "personal use", "individual", "private", "private individual", "self",
    "self employed", "self-employed", "freelance", "freelancer", "sole trader", "none", "no company", "n/a", "na", "nil", "-", "--", ".",
    "me", "myself", "user", "client", "customer", "test", "home", "not applicable", "no", "nothing",
}


def is_placeholder_company(name: Optional[str]) -> bool:
    text = re.sub(r"\s+", " ", str(name or "")).strip().lower().strip(".")
    return not text or text in PLACEHOLDER_COMPANIES


def company_or_name(company: Optional[str], full_name: Optional[str]) -> str:
    """The company name when it is a real one, otherwise the person's name."""
    if is_placeholder_company(company):
        return (full_name or "").strip() or (company or "").strip()
    return str(company).strip()
