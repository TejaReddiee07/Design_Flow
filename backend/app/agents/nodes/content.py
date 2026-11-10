"""Content Agent: headlines, captions, ad copy, plus the structure each service needs (slides, sections, point details)."""
from __future__ import annotations

from typing import Any, Dict

from app.agents import control
from app.agents.llm import complete
from app.agents.nodes.common import pretty, request_context
from app.db.mongo import get_db

KEY = "content"
SYSTEM = """You are the Content Agent at a premium design studio. Write the words that will appear on or
around the design. Match the brand voice. Keep on-visual copy short. Use the client's own text exactly where
they supplied it and never invent statistics, prices, dates, names or testimonials.
Return JSON with keys: headlines (3, max 8 words each), subheadlines (2, max 14 words), body_copy (string, max 40 words),
cta_options (3, max 3 words each), captions (2 social captions), hashtags (list)."""

# Extra structure per service, so decks, brochures and carousels get real, business-specific content.
EXTRA = {
    "pitch-deck-design": 'Also return "slides": a list of 8 objects {"title", "body" (max 25 words), "bullets" (2-4 short items)} for: '
                         "Problem, Solution, How it works, Market, Business model, Roadmap, Why we win, Team.",
    "presentation-design": 'Also return "slides": a list of 6 objects {"title", "body" (max 25 words), "bullets" (2-4 short items)} '
                           "that cover the purpose of the presentation in order.",
    "linkedin-carousel-design": 'Also return "slides": one object per key point {"title" (the point, max 8 words), "body" (one or two sentences '
                                "explaining it, max 30 words)} in the same order as the client's key points.",
    "instagram-post-design": 'If the post type is Carousel, also return "slides": 4-6 objects {"title", "body" (max 25 words)}.',
    "brochure-design": 'Also return "sections": 4 objects {"title", "body" (max 45 words), "bullets" (2-4 items)}: about the business, '
                       "what it offers, how it works, why choose it.",
    "company-profile-design": 'Also return "sections": 5 objects {"title", "body" (max 60 words), "bullets" (2-4 items)}: about us, services, '
                              "process, why us, values.",
    "infographic-design": 'Also return "facts": 3-5 short facts drawn only from the data the client supplied.',
}


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    req = db.requests.update(state["request_id"], {"pipeline_stage": "content"})
    service = db.services.get(req.get("service_id")) or {}
    slug = service.get("slug", "")
    with control.running(db, KEY, f"Writing copy: {req.title}", run_id=state.get("run_id"), request_id=req.id) as ctx:
        prompt = request_context(db, req)
        strategy = state.get("strategy") or {}
        if strategy:
            prompt += f"\n\nStrategy:\n{pretty(strategy, 2000)}"
        system = SYSTEM + ("\n" + EXTRA[slug] if slug in EXTRA else "")
        res = complete(KEY, system, prompt)
        data = res.data or {}
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty(data), model=res.model)
    return {"content": data, "stage": "content"}
