"""Onboarding workflow: a single-node LangGraph wrapping the Onboarding Agent
(workspace folder -> welcome message -> asset request -> notifications)."""
from __future__ import annotations

from typing import Any, Dict, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import onboarding


class OnboardingState(TypedDict, total=False):
    client_id: int
    result: Dict[str, Any]


def _onboard(state: OnboardingState) -> Dict[str, Any]:
    return {"result": onboarding.run(state["client_id"])}


def build_graph():
    g = StateGraph(OnboardingState)
    g.add_node("onboard", _onboard)
    g.add_edge(START, "onboard")
    g.add_edge("onboard", END)
    return g.compile()


graph = build_graph()


def run(client_id: int, **_: Any) -> Dict[str, Any]:
    return graph.invoke({"client_id": int(client_id)}).get("result", {})
