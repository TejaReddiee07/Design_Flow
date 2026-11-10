"""LLM factory for the agents.

With ANTHROPIC_API_KEY set: langchain-anthropic ChatAnthropic (the official SDK underneath),
model per agent via LLM_MODEL / LLM_MODEL_<AGENT>. Thinking is adaptive by default on the
Claude 5.x family, so no thinking parameter is sent. Server-side refusal fallbacks are
requested when available and silently dropped if the installed SDK rejects the option.

Without a key: MockLLM returns realistic, deterministic JSON so the whole pipeline runs.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents import live
from app.core.config import settings

log = logging.getLogger("agents.llm")


@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = "mock"
    data: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------------
# Mock model
# --------------------------------------------------------------------------
class MockLLM:
    """Stands in for ChatAnthropic. invoke() returns an AIMessage with JSON content."""

    def __init__(self, agent_key: str) -> None:
        self.agent_key = agent_key
        self.model = "mock"

    def invoke(self, messages: List[Any]) -> AIMessage:
        user = ""
        system = ""
        for m in messages:
            if isinstance(m, HumanMessage):
                user = m.content if isinstance(m.content, str) else str(m.content)
            elif isinstance(m, SystemMessage):
                system = m.content if isinstance(m.content, str) else str(m.content)
        payload = MOCK_OUTPUTS.get(self.agent_key, lambda u: {"result": "ok"})(user + "\n\n" + system)
        text = json.dumps(payload, indent=2)
        return AIMessage(content=text, usage_metadata={"input_tokens": max(50, len(user) // 4), "output_tokens": len(text) // 4, "total_tokens": 0})


def _grab(user: str, key: str, default: str = "") -> str:
    m = re.search(rf"{key}\s*[:=]\s*(.+)", user, re.IGNORECASE)
    return m.group(1).strip()[:120] if m else default


def _mock_project_manager(u: str) -> Dict[str, Any]:
    title = _grab(u, "Title", "the request")
    service = _grab(u, "Service", "design")
    return {
        "summary": f"{service} request: {title}. Brief is complete enough to start; references and brand notes available.",
        "suggested_priority": "high" if re.search(r"urgent|asap|deadline|launch|tomorrow", u, re.I) else "normal",
        "complexity": "medium",
        "estimated_hours": 3,
        "tasks": [
            "Review brand assets and previous deliveries",
            "Research competitors and visual references",
            "Draft copy options",
            "Produce 2 concept directions",
            "QA against brief and brand guidelines",
        ],
        "questions_for_client": [],
    }


def _mock_strategy(u: str) -> Dict[str, Any]:
    return {
        "positioning": "Premium but approachable; lead with the outcome the customer gets, not the feature list.",
        "audience_insights": ["Scans on mobile first", "Responds to social proof and clear CTAs", "Values consistency with existing brand"],
        "competitor_notes": ["Competitors use dense layouts; whitespace is a differentiator", "Most rely on stock imagery; custom compositions stand out"],
        "creative_direction": "Bold headline hierarchy, generous whitespace, one strong focal visual, brand accent used sparingly for the CTA.",
        "do": ["Use the primary brand colour for the single most important element", "Keep copy under 12 words on visuals"],
        "dont": ["Mix more than two typefaces", "Use generic stock photos"],
    }


def _mock_content(u: str) -> Dict[str, Any]:
    company = _grab(u, "Company", "your business").split("\n")[0]
    out: Dict[str, Any] = {
        "headlines": [f"Meet {company}", "Made with care, built to last", "Less noise. More signal."],
        "subheadlines": [f"Everything you love about {company}, in one place", "Thoughtful work for people who notice the details"],
        "body_copy": f"{company} puts care into every detail so your customers feel it from the first look.",
        "cta_options": ["Get started", "Find out more", "Book a call"],
        "captions": [f"Something new from {company}.", "Made for the people who notice the details."],
        "hashtags": ["#design", "#branding", "#smallbusiness"],
    }
    if '"slides"' in u:
        out["slides"] = [
            {"title": t, "body": f"How {company} approaches {t.lower()}.", "bullets": ["Clear and focused", "Built around customers", "Measured and improved"]}
            for t in ("The problem", "Our solution", "How it works", "The market", "Business model", "Roadmap", "Why we win", "Team")
        ]
    if '"sections"' in u:
        out["sections"] = [
            {"title": t, "body": f"{company} {b}", "bullets": ["Personal service", "Consistent quality", "Honest pricing"]}
            for t, b in (("About us", "is an independent business built on care and consistency."), ("What we offer", "offers a focused range done properly."),
                         ("How we work", "listens first, plans carefully and delivers on time."), ("Why choose us", "treats every customer like a regular."))
        ]
    return out


def _mock_design(u: str) -> Dict[str, Any]:
    return {
        "concepts": [
            {
                "title": "Concept A - Editorial",
                "description": "Large serif headline top-left, product/hero visual right, CTA pill bottom-left. Generous margins.",
                "layout": "split-hero",
                "palette": [],
                "typography": "Display serif for headline, humanist sans for body",
                "imagery": "Single hero composition with soft shadow",
            },
            {
                "title": "Concept B - Bold grid",
                "description": "Full-bleed background in primary colour, oversized headline, 3-column feature strip.",
                "layout": "full-bleed",
                "palette": [],
                "typography": "Geometric sans throughout",
                "imagery": "Abstract shapes and gradients",
            },
        ],
        "recommended": 0,
        "rationale": "Concept A matches the brand notes more closely and leaves room for copy variants.",
    }


def _mock_qa(u: str) -> Dict[str, Any]:
    return {
        "score": 93,
        "pass": True,
        "strengths": ["Brand colours used correctly", "Copy fits within safe zones", "Clear hierarchy"],
        "issues": [],
        "suggestions": ["Consider a slightly larger CTA on mobile"],
        "notes": "Meets the brief. Ready for designer finishing and admin approval.",
    }


def _mock_revision(u: str) -> Dict[str, Any]:
    fb = _grab(u, "Feedback", "Adjust per client feedback")
    return {
        "summary": f"Client feedback: {fb}",
        "change_items": [f"Apply: {fb[:80]}", "Re-check contrast and spacing after changes", "Export all requested sizes"],
        "impact": "minor",
    }


def _mock_onboarding(u: str) -> Dict[str, Any]:
    company = _grab(u, "Company", "your company")
    return {
        "welcome_message": f"Welcome to Designflow, {company}! Your workspace is ready. To get the best results, please upload your logo, brand colours, fonts and any guidelines in Files & brand assets. Then submit your first request whenever you're ready.",
        "asset_checklist": ["Logo (SVG or high-res PNG)", "Brand colours", "Fonts", "Brand guidelines (if any)", "Examples of past designs you liked"],
    }


def _mock_lead_analysis(u: str) -> Dict[str, Any]:
    return {
        "score": 78,
        "website_quality": "average",
        "social_presence": "moderate",
        "opportunity": "Visual identity is inconsistent across site and social; no recent campaign creative.",
        "pain_points": ["Dated hero visuals", "Inconsistent post templates", "No clear brand palette"],
        "recommended_services": ["Logo Design", "Social Media Design"],
    }


def _mock_outreach(u: str) -> Dict[str, Any]:
    company = _grab(u, "Company", "your team")
    name = _grab(u, "Contact", "there").split(" ")[0]
    return {
        "subject": f"Quick idea for {company}'s visuals",
        "body": f"Hi {name},\n\nI took a look at {company} and noticed a couple of quick wins in your visuals: your site and social templates don't quite match yet, and a consistent set would make every post feel more premium.\n\nWe run a flat-fee design subscription (unlimited requests, 48h turnaround) and I'd be happy to send over two free concept directions for one of your upcoming posts. No strings.\n\nWould that be useful?\n\nBest,\nDesignflow",
    }


def _mock_marketing(u: str) -> Dict[str, Any]:
    return {
        "linkedin": "Most brands don't have a design problem. They have a consistency problem.\n\nThis week we shipped 14 requests for 6 clients: thumbnails, a pitch deck, a full identity. Every one on-brand, every one in under 48h.\n\nFlat fee. Unlimited requests. One studio, eleven agents.\n\n#design #branding #startup",
        "instagram": "14 requests. 6 brands. 48 hours. ✨ Swipe to see this week's favourites. #designsubscription #branding",
        "x": "Design subscription update: 14 requests shipped this week, avg turnaround 31h. Unlimited requests, flat fee. DM for a free concept.",
    }


def _mock_delivery(u: str) -> Dict[str, Any]:
    return {"message": "Your files are ready. We've included the final exports and the source file. Let us know if you'd like any tweaks - revisions are unlimited."}


MOCK_OUTPUTS = {
    "project_manager": _mock_project_manager,
    "strategy": _mock_strategy,
    "content": _mock_content,
    "design": _mock_design,
    "qa": _mock_qa,
    "revision": _mock_revision,
    "onboarding": _mock_onboarding,
    "lead": _mock_lead_analysis,
    "outreach": _mock_outreach,
    "marketing": _mock_marketing,
    "delivery": _mock_delivery,
}


# --------------------------------------------------------------------------
# Real model
# --------------------------------------------------------------------------
_cache: Dict[str, Any] = {}
_ollama_ok: Optional[bool] = None


def provider() -> str:
    """ollama | anthropic | mock - what will actually be used right now."""
    p = settings.llm_provider.lower()
    if p == "anthropic":
        return "anthropic" if settings.anthropic_api_key else "mock"
    if p == "ollama":
        return "ollama" if ollama_available() else "mock"
    return "mock"


_ollama_checked_at: float = 0.0


def ollama_available(force: bool = False) -> bool:
    """True when the Ollama server answers and has the configured model.
    A positive answer is cached; a negative one is re-checked every 60 s, so if Ollama is
    started AFTER the website the agents switch from placeholder output to the real model
    within a minute - no server restart needed."""
    global _ollama_ok, _ollama_checked_at
    now = time.monotonic()
    if not force:
        if _ollama_ok is True:
            return True
        if _ollama_ok is False and now - _ollama_checked_at < 60:
            return False
    _ollama_checked_at = now
    try:
        import httpx

        r = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=2)
        names = [m.get("name", "") for m in r.json().get("models", [])]
        want = settings.ollama_model
        _ollama_ok = r.status_code == 200 and any(n == want or n.split(":")[0] == want.split(":")[0] for n in names)
        if r.status_code == 200 and not _ollama_ok:
            log.warning("Ollama is running but model '%s' is not pulled (have: %s). Run: ollama pull %s", want, names, want)
    except Exception as exc:
        log.warning("Ollama not reachable at %s (%s); agents use placeholder output and retry within 60 s", settings.ollama_base_url, exc)
        _ollama_ok = False
    return _ollama_ok


def is_live() -> bool:
    return provider() != "mock"


def get_llm(agent_key: str):
    which = provider()
    if which == "mock":
        return MockLLM(agent_key)
    model = settings.llm_model_for(agent_key)
    cache_key = f"{which}:{model}"
    if cache_key in _cache:
        return _cache[cache_key]
    if which == "ollama":
        from langchain_ollama import ChatOllama

        llm = ChatOllama(model=model, base_url=settings.ollama_base_url, temperature=0.4, num_predict=settings.llm_max_tokens, format="json")
        _cache[cache_key] = llm
        return llm
    from langchain_anthropic import ChatAnthropic

    kwargs: Dict[str, Any] = dict(model=model, max_tokens=settings.llm_max_tokens, api_key=settings.anthropic_api_key, timeout=120, max_retries=2)
    llm = None
    try:
        # Server-side refusal fallbacks (Claude 5.x): ignored if the installed SDK rejects it.
        llm = ChatAnthropic(**kwargs, betas=["server-side-fallback-2026-07-01"], model_kwargs={"fallbacks": "default"})
    except Exception as exc:  # pragma: no cover - depends on SDK version
        log.info("fallbacks option unavailable (%s); using plain client", exc)
        llm = ChatAnthropic(**kwargs)
    _cache[cache_key] = llm
    return llm


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _text_of(content: Any) -> str:
    if isinstance(content, list):  # multi-block content
        return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)
    return content or ""


ChunkCallback = Callable[[str, bool], None]  # (accumulated text, done)


def _invoke_streaming(llm: Any, messages: List[Any], on_chunk: ChunkCallback) -> AIMessage:
    """Call the model token by token so the live page can show the agent writing.
    Falls back to a plain invoke() when the provider cannot stream."""
    if isinstance(llm, MockLLM):
        msg = llm.invoke(messages)
        text = _text_of(msg.content)
        step = max(1, len(text) // 10)
        for i in range(step, len(text), step):
            on_chunk(text[:i], False)
            if settings.app_env != "test":
                time.sleep(0.04)
        on_chunk(text, True)
        return msg
    acc = ""
    final = None
    last_push = 0.0
    try:
        for chunk in llm.stream(messages):
            final = chunk if final is None else final + chunk
            piece = _text_of(chunk.content)
            if piece:
                acc += piece
                now = time.monotonic()
                if now - last_push >= 0.12:
                    on_chunk(acc, False)
                    last_push = now
        if final is None:
            raise RuntimeError("model returned an empty stream")
        on_chunk(acc, True)
        return final
    except Exception as exc:
        log.warning("Streaming failed (%s); using a single call instead", exc)
        resp = llm.invoke(messages)
        on_chunk(_text_of(resp.content), True)
        return resp


def complete(agent_key: str, system: str, user: str, *, want_json: bool = True, on_chunk: Optional[ChunkCallback] = None) -> LLMResult:
    """One LLM call. Returns text plus parsed JSON when requested.
    While the model writes, partial output is streamed to the live page of the request the
    calling agent is working on (see control.running / live.set_context)."""
    llm = get_llm(agent_key)
    if want_json:
        system = system.rstrip() + "\n\nRespond with a single JSON object only. No prose, no markdown fences."
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    model_name = "mock" if isinstance(llm, MockLLM) else str(getattr(llm, "model", ""))

    def _chunk(text: str, done: bool) -> None:
        if on_chunk:
            on_chunk(text, done)
        live.stream_from_context(text, done=done, model=model_name)

    resp = _invoke_streaming(llm, messages, _chunk)
    content = _text_of(resp.content)
    meta = getattr(resp, "usage_metadata", None) or {}
    stop = (getattr(resp, "response_metadata", None) or {}).get("stop_reason")
    if stop == "refusal":
        log.warning("Model refused request for agent %s", agent_key)
        content = ""
    result = LLMResult(
        text=content or "",
        tokens_in=int(meta.get("input_tokens", 0) or 0),
        tokens_out=int(meta.get("output_tokens", 0) or 0),
        model=str(getattr(llm, "model", "mock")) if not isinstance(llm, MockLLM) else "mock",
    )
    if want_json and result.data is None and isinstance(llm, MockLLM) is False and provider() == "ollama" and not result.text.strip():
        # Ollama returned nothing (model busy/unloaded): fall back to mock for this call so the pipeline keeps moving
        log.warning("Empty Ollama response for %s; using mock output for this step", agent_key)
        mock = MockLLM(agent_key).invoke(messages)
        result.text = mock.content
        result.model = "mock-fallback"
    if want_json:
        result.data = parse_json(result.text)
        if result.data is None and not isinstance(llm, MockLLM):
            # one retry asking for strict JSON
            retry = llm.invoke(messages + [HumanMessage(content="That was not valid JSON. Return only the JSON object.")])
            result.text = retry.content if isinstance(retry.content, str) else str(retry.content)
            result.data = parse_json(result.text)
    return result
