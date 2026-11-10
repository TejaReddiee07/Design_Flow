"""Agent system tests: run the LangGraph pipelines synchronously with the mock LLM."""
from __future__ import annotations

import pytest

from app.agents import control
from app.agents.runner import run_job
from app.core.config import settings


@pytest.fixture(autouse=True)
def _agents_on(monkeypatch):
    """Enable the agent system but swallow API-side background jobs so each pipeline
    runs exactly once, synchronously, when the test calls run_job()."""
    monkeypatch.setattr(settings, "agents_enabled", True)
    monkeypatch.setattr("app.core.jobs._run_inline", lambda job: None)
    yield


def _new_request(client, headers, slug="instagram-post-design", title="Pipeline test post"):
    svc = client.get(f"/api/v1/services/{slug}").json()
    r = client.post("/api/v1/requests", json={"service_id": svc["id"], "title": title,
                                              "brief": {"about_and_wishes": "We sell handmade candles online; keep it warm and minimal.", "brand_name": "Testco", "post_type": "Carousel", "quantity": 3, "copy_text": "Launch week"},
                                              "priority": "normal"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_triage_sets_summary(client, admin, client_headers):
    req = _new_request(client, client_headers, title="URGENT launch post for tomorrow")
    out = run_job({"type": "project_manager_triage", "payload": {"request_id": req["id"]}})
    assert out and out.get("summary")
    detail = client.get(f"/api/v1/requests/{req['id']}", headers=admin).json()
    assert detail["ai_summary"]
    assert detail["priority"] in ("high", "urgent")  # mock PM bumps on "urgent"


def test_full_pipeline_with_admin_approval(client, admin, client_headers):
    req = _new_request(client, client_headers)
    rid = req["id"]
    client.post(f"/api/v1/requests/{rid}/accept", headers=admin)  # agents disabled in API -> no auto run

    out = run_job({"type": "request_pipeline", "payload": {"request_id": rid}})
    assert out["stage"] == "awaiting_approval", out

    detail = client.get(f"/api/v1/requests/{rid}", headers=admin).json()
    assert detail["status"] == "review"
    assert detail["pipeline_stage"] == "admin_approval"
    assert len(detail["designs"]) == 1
    d = detail["designs"][0]
    assert d["generated_by"] == "agent" and d["qa_score"] and d["qa_score"] >= 80
    assert d["preview_url"] and d["file_id"]  # mock image provider rendered an SVG draft
    assert any(e["kind"] == "agent" for e in detail["timeline"])
    notes = client.get("/api/v1/notifications", params={"type": "approval_needed"}, headers=admin).json()
    assert any(n["request_id"] == rid for n in notes)

    # agent logs exist for every pipeline agent
    logs = client.get("/api/v1/agents/logs", params={"request_id": rid, "limit": 200}, headers=admin).json()
    keys = {l["agent_key"] for l in logs}
    assert {"project_manager", "strategy", "content", "design", "qa"} <= keys

    # admin approves -> graph resumes from the checkpoint -> delivery -> completed
    r = client.post(f"/api/v1/requests/{rid}/approve", params={"message": "Looks great"}, headers=admin)
    assert r.status_code == 200
    out = run_job({"type": "request_resume", "payload": {"request_id": rid, "approved": True, "message": "Looks great"}})
    assert out["stage"] == "complete", out
    detail = client.get(f"/api/v1/requests/{rid}", headers=admin).json()
    assert detail["status"] == "completed"
    assert len(detail["deliveries"]) == 1
    dl = detail["deliveries"][0]
    assert dl["delivered_by"] == "agent" and len(dl["download_links"]) >= 2  # svg draft + notes
    assert "Looks great" in dl["message"]
    assert any(f["kind"] == "delivery" for f in detail["files"])
    cn = client.get("/api/v1/notifications", params={"type": "delivery"}, headers=client_headers).json()
    assert any(n["request_id"] == rid for n in cn)

    # the "See in live" feed tells the whole story, in order
    live = client.get(f"/api/v1/requests/{rid}/live", headers=admin).json()
    types = [e["type"] for e in live["events"]]
    assert types[0] == "pipeline_started"
    for t in ("agent_started", "agent_completed", "design_rendered", "qa_scored", "awaiting_approval", "pipeline_resumed", "approved", "delivered", "completed"):
        assert t in types, t
    assert types.index("design_rendered") < types.index("qa_scored") < types.index("awaiting_approval") < types.index("delivered")
    rendered = next(e for e in live["events"] if e["type"] == "design_rendered")
    assert rendered["data"]["preview_url"] and rendered["data"]["version"] == 1 and rendered["agent_key"] == "design"
    done = [e for e in live["events"] if e["type"] == "agent_completed"]
    assert {e["agent_key"] for e in done} >= {"project_manager", "strategy", "content", "design", "qa", "delivery"}
    assert all(e["body"] for e in done if e["agent_key"] in ("strategy", "content", "design"))  # the model output is shown
    assert live["request"]["status"] == "completed" and {a["key"] for a in live["agents"]} >= {"design", "qa", "delivery"}
    assert client.get(f"/admin/live/{rid}").status_code == 200  # the page itself
    # the client who owns the request may watch too; another client may not
    assert client.get(f"/api/v1/requests/{rid}/live", headers=client_headers).status_code == 200

    # client asks for a revision -> revision pipeline -> design v2 -> review again
    r = client.post(f"/api/v1/requests/{rid}/revisions", json={"feedback": "Make the headline bigger"}, headers=client_headers)
    assert r.status_code == 201
    rev_id = r.json()["id"]
    out = run_job({"type": "revision_pipeline", "payload": {"request_id": rid, "revision_id": rev_id}})
    assert out["stage"] == "awaiting_approval", out
    detail = client.get(f"/api/v1/requests/{rid}", headers=admin).json()
    assert detail["status"] == "review"
    assert len(detail["designs"]) == 2 and detail["designs"][-1]["version"] == 2
    assert detail["revisions"][0]["change_items"]

    # admin sends it back for rework (the new "Send back" button) -> design v3 -> review again
    r = client.post(f"/api/v1/requests/{rid}/rework", params={"message": "Try a warmer palette"}, headers=admin)
    assert r.status_code == 200 and r.json()["pipeline_stage"] == "rework"
    out = run_job({"type": "request_resume", "payload": {"request_id": rid, "approved": False, "message": "Try a warmer palette"}})
    assert out["stage"] == "awaiting_approval", out
    detail = client.get(f"/api/v1/requests/{rid}", headers=admin).json()
    assert len(detail["designs"]) == 3
    live = client.get(f"/api/v1/requests/{rid}/live", headers=admin).json()
    assert any(e["type"] == "rework" and "warmer" in (e["body"] or "") for e in live["events"])
    # approve for real
    out = run_job({"type": "request_resume", "payload": {"request_id": rid, "approved": True}})
    assert out["stage"] == "complete"
    detail = client.get(f"/api/v1/requests/{rid}", headers=admin).json()
    assert detail["status"] == "completed" and len(detail["deliveries"]) == 2
    assert detail["revisions"][0]["status"] == "completed"


def test_stop_button_halts_pipeline(client, admin, client_headers, db):
    req = _new_request(client, client_headers, title="Stopped pipeline")
    client.post(f"/api/v1/requests/{req['id']}/accept", headers=admin)
    client.post("/api/v1/agents/content/stop", headers=admin)
    try:
        out = run_job({"type": "request_pipeline", "payload": {"request_id": req["id"]}})
        assert out["stage"] == "stopped"
        detail = client.get(f"/api/v1/requests/{req['id']}", headers=admin).json()
        assert detail["pipeline_stage"] == "stopped"
        assert detail["status"] == "in_progress"
        assert not detail["designs"]
        logs = client.get("/api/v1/agents/content/logs", headers=admin).json()
        assert any(l["status"] == "skipped" for l in logs)
    finally:
        client.post("/api/v1/agents/content/start", headers=admin)


FAKE_BUSINESSES = [
    {"company_name": "Harbor Coffee Roasters", "website": "https://harborcoffee.test", "contact_email": "hello@harborcoffee.test", "industry": "Coffee", "location": "Austin, TX", "site_text": "Specialty coffee roasters in Austin.", "source": "agent:web", "query": "new cafe Austin", "service_slug": "logo-design"},
    {"company_name": "Peak Fitness", "website": "https://peakfit.test", "contact_email": "team@peakfit.test", "industry": "Fitness", "location": "Austin, TX", "site_text": "Gym and classes.", "source": "agent:web", "query": "gym Austin", "service_slug": "logo-design"},
    {"company_name": "Bloom Dental", "website": "https://bloomdental.test", "contact_email": None, "industry": "Dental", "location": "Austin, TX", "site_text": "Family dentist.", "source": "agent:web", "query": "dental Austin", "service_slug": "logo-design"},
]


def test_lead_generation_pipeline(client, admin, monkeypatch):
    # web discovery is real in production; here we stub the search so the test is offline
    monkeypatch.setattr("app.agents.nodes.lead.find_businesses", lambda *a, **k: list(FAKE_BUSINESSES))
    before = client.get("/api/v1/leads/stats", headers=admin).json()["total"]
    out = run_job({"type": "lead_generation", "payload": {"industry": "Coffee", "location": "Austin, TX", "count": 3, "service_slug": "logo-design"}})
    assert len(out["created"]) == 3
    after = client.get("/api/v1/leads/stats", headers=admin).json()["total"]
    assert after == before + 3
    lead = client.get(f"/api/v1/leads/{out['created'][0]}", headers=admin).json()
    assert lead["score"] > 0 and lead["analysis"].get("opportunity")
    # drafting outreach for them
    out = run_job({"type": "outreach_draft", "payload": {"lead_ids": out["created"][:2], "tone": "friendly"}})
    assert len(out["outreach_ids"]) == 2
    o = client.get("/api/v1/outreach", headers=admin).json()["items"]
    assert any(x["status"] == "draft" and x["subject"] for x in o)
    # sending via the API uses the mock email provider
    r = client.post("/api/v1/outreach/send", json={"outreach_ids": out["outreach_ids"]}, headers=admin)
    assert r.json()["sent"] == 2
    # convert the top lead into a client + a logo request in one click
    lead_id = client.get("/api/v1/leads", params={"q": "Harbor"}, headers=admin).json()["items"][0]["id"]
    r = client.post(f"/api/v1/leads/{lead_id}/convert", json={"service_slug": "logo-design", "currency": "USD"}, headers=admin)
    assert r.status_code == 200, r.text
    conv = r.json()
    assert conv["created_account"] and conv["temporary_password"] and conv["request"]["price_amount"] == 19
    assert client.get(f"/api/v1/leads/{lead_id}", headers=admin).json()["status"] == "converted"
    login = client.post("/api/v1/auth/login", json={"email": conv["email"], "password": conv["temporary_password"]})
    assert login.status_code == 200 and login.json()["user"]["role"] == "client"


def test_onboarding_and_marketing(client, admin, other_client_headers):
    me = client.get("/api/v1/clients/me", headers=other_client_headers).json()
    out = run_job({"type": "onboarding", "payload": {"client_id": me["id"]}})
    assert out.get("welcome_message")
    me = client.get("/api/v1/clients/me", headers=other_client_headers).json()
    assert me["onboarding_stage"] == "assets_requested"
    msgs = client.get("/api/v1/chat/messages", headers=other_client_headers).json()
    assert any("Welcome" in (m["body"] or "") for m in msgs)
    tickets = client.get("/api/v1/support/tickets", headers=other_client_headers).json()
    assert any(t["category"] == "onboarding" for t in tickets)

    posts = run_job({"type": "marketing_posts", "payload": {}})
    assert posts.get("linkedin") and posts.get("x")
    ag = client.get("/api/v1/agents/marketing", headers=admin).json()
    assert ag["config"]["posts"][0]["x"]

    snap = run_job({"type": "analytics_snapshot", "payload": {}})
    assert "requests_submitted" in snap


def test_agent_metrics_updated(client, admin):
    agents = {a["key"]: a for a in client.get("/api/v1/agents", headers=admin).json()}
    assert agents["design"]["tasks_completed"] >= 1
    assert agents["qa"]["last_run_at"]
    assert agents["delivery"]["success_rate"] > 0
    summary = client.get("/api/v1/agents/summary", headers=admin).json()
    assert summary["tasks_completed"] >= 5
