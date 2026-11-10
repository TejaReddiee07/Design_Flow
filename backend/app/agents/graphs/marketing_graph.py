"""Marketing workflow: gather this week's numbers -> write posts -> store + notify."""
from __future__ import annotations

from typing import Any, Dict, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import marketing


class MarketingState(TypedDict, total=False):
    posts: Dict[str, Any]


def _write(state: MarketingState) -> Dict[str, Any]:
    return {"posts": marketing.run()}


def build_graph():
    g = StateGraph(MarketingState)
    g.add_node("write_posts", _write)
    g.add_edge(START, "write_posts")
    g.add_edge("write_posts", END)
    return g.compile()


graph = build_graph()


def run(**_: Any) -> Dict[str, Any]:
    return graph.invoke({}).get("posts", {})
