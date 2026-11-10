"""Lead Agent workflow: discover -> analyse -> notify."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import lead


class LeadState(TypedDict, total=False):
    run_id: str
    industry: Optional[str]
    location: Optional[str]
    service_slug: Optional[str]
    count: int
    candidates: List[Dict[str, Any]]
    lead_ids: List[int]
    notified: bool


def build_graph():
    g = StateGraph(LeadState)
    g.add_node("discover", lead.discover)
    g.add_node("analyse", lead.analyse)
    g.add_node("notify", lead.notify)
    g.add_edge(START, "discover")
    g.add_edge("discover", "analyse")
    g.add_edge("analyse", "notify")
    g.add_edge("notify", END)
    return g.compile()


graph = build_graph()


def run(industry: Optional[str] = None, location: Optional[str] = None, count: int = 5, service_slug: Optional[str] = None, **_: Any) -> Dict[str, Any]:
    state: LeadState = {"run_id": f"leads-{uuid.uuid4().hex[:8]}", "industry": industry or None, "location": location or None,
                        "count": int(count or 5), "service_slug": service_slug or None}
    result = graph.invoke(state)
    return {"created": result.get("lead_ids", []), "run_id": state["run_id"]}
