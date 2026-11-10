def test_notifications_mark_read(client, admin):
    r = client.get("/api/v1/notifications/unread-count", headers=admin)
    assert r.status_code == 200
    start = r.json()["unread_count"]
    notes = client.get("/api/v1/notifications", params={"unread_only": True}, headers=admin).json()
    if notes:
        r = client.post(f"/api/v1/notifications/{notes[0]['id']}/read", headers=admin)
        assert r.json()["unread_count"] == start - 1
    r = client.post("/api/v1/notifications/mark-all-read", headers=admin)
    assert r.json()["unread_count"] == 0


def test_chat_roundtrip(client, admin, client_headers):
    r = client.post("/api/v1/chat/messages", json={"body": "Hello from client"}, headers=client_headers)
    assert r.status_code == 201, r.text
    conv_id = r.json()["conversation_id"]
    convs = client.get("/api/v1/chat/conversations", headers=admin).json()
    conv = next(c for c in convs if c["id"] == conv_id)
    assert conv["unread"] == 1
    r = client.post("/api/v1/chat/messages", params={"conversation_id": conv_id}, json={"body": "Hi back"}, headers=admin)
    assert r.status_code == 201
    msgs = client.get("/api/v1/chat/messages", headers=client_headers).json()
    assert [m["body"] for m in msgs][-2:] == ["Hello from client", "Hi back"]
    conv = next(c for c in client.get("/api/v1/chat/conversations", headers=admin).json() if c["id"] == conv_id)
    assert conv["unread"] == 0  # admin read it when sending/listing


def test_support_ticket(client, admin, client_headers):
    r = client.post("/api/v1/support/tickets", json={"subject": "Billing question", "message": "How does proration work?"}, headers=client_headers)
    assert r.status_code == 201
    tid = r.json()["id"]
    r = client.post(f"/api/v1/support/tickets/{tid}/reply", json={"message": "Prorated daily.", "status": "resolved"}, headers=admin)
    assert r.json()["status"] == "resolved"
    assert len(r.json()["messages"]) == 2


def test_contact_form_creates_lead(client, admin):
    r = client.post("/api/v1/public/contact", json={"name": "Jane Lead", "email": "jane@lead.example.com", "company": "LeadCo", "message": "Need a logo please"})
    assert r.status_code == 201
    leads = client.get("/api/v1/leads", headers=admin).json()
    assert any(l["company_name"] == "LeadCo" and l["source"] == "website" for l in leads["items"])


def test_public_pricing_and_currencies(client):
    rows = client.get("/api/v1/public/services-pricing").json()
    assert len(rows) == 19 and all(set(r["prices"]) == {"USD", "GBP", "INR"} and r["turnaround_days"] >= 1 for r in rows)
    cur = client.get("/api/v1/billing/currencies").json()
    assert cur["currencies"] == ["USD", "GBP", "INR"]


def test_primary_admin_is_locked(client, admin):
    r = client.post("/api/v1/auth/change-password", json={"current_password": "Admin123!", "new_password": "Other1234"}, headers=admin)
    assert r.status_code == 403
    users = client.get("/api/v1/admin/users", headers=admin).json()
    me = next(u for u in users if u["email"] == "admin@designflow.local")
    assert client.patch(f"/api/v1/admin/users/{me['id']}", json={"is_active": False}, headers=admin).status_code == 403


def test_clients_admin(client, admin):
    r = client.get("/api/v1/clients", headers=admin)
    assert r.status_code == 200
    c = next(x for x in r.json()["items"] if x["company_name"] == "Testco")
    assert c["currency"] == "USD" and "unpaid_requests" in c
    r = client.get(f"/api/v1/clients/{c['id']}/overview", headers=admin)
    assert r.status_code == 200
    assert r.json()["client"]["id"] == c["id"]
    r = client.patch(f"/api/v1/clients/{c['id']}", json={"status": "active", "brand_notes": "Teal"}, headers=admin)
    assert r.json()["brand_notes"] == "Teal"


def test_analytics_overview(client, admin):
    r = client.get("/api/v1/analytics/overview", headers=admin)
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {"clients", "revenue", "requests", "conversion", "agents"}
    assert "unpaid" in d["revenue"] and d["revenue"]["currency"] == "INR"
    # active clients = clients with an open order (test_requests left Testco with completed/rejected/pending ones)
    open_clients = {r["client_id"] for r in client.get("/api/v1/requests", params={"status": "pending,accepted,in_progress,review", "page_size": 200}, headers=admin).json()["items"]}
    assert d["clients"]["active"] == len(open_clients)
    assert d["clients"]["total"] >= d["clients"]["active"]
    for ep in ("revenue", "requests", "agents", "leads", "sales"):
        assert client.get(f"/api/v1/analytics/{ep}", headers=admin).status_code == 200


def test_agents_control(client, admin):
    agents = client.get("/api/v1/agents", headers=admin).json()
    assert len(agents) == 11
    assert {a["key"] for a in agents} >= {"lead", "design", "qa", "delivery", "marketing"}
    r = client.post("/api/v1/agents/design/pause", headers=admin)
    assert r.json()["status"] == "paused"
    r = client.post("/api/v1/agents/design/stop", headers=admin)
    assert r.json()["status"] == "stopped" and r.json()["enabled"] is False
    r = client.post("/api/v1/agents/design/start", headers=admin)
    assert r.json()["status"] == "idle" and r.json()["enabled"] is True
    r = client.post("/api/v1/agents/design/restart", headers=admin)
    assert r.json()["status"] == "idle"
    logs = client.get("/api/v1/agents/design/logs", headers=admin).json()
    assert len(logs) >= 4
    r = client.patch("/api/v1/agents/lead", json={"schedule": "0 7 * * *"}, headers=admin)
    assert r.json()["schedule"] == "0 7 * * *"
    assert client.get("/api/v1/agents/summary", headers=admin).status_code == 200


def test_admin_users_and_audit(client, admin):
    r = client.post("/api/v1/admin/users", json={"email": "staff@designflow.local", "password": "Staff123!", "full_name": "Staff One", "role": "staff"}, headers=admin)
    assert r.status_code == 201
    r = client.get("/api/v1/admin/audit", headers=admin)
    assert r.status_code == 200 and r.json()["total"] > 0
    assert client.get("/api/v1/admin/settings", headers=admin).json()["billing"] == "mock"


def test_leads_crud(client, admin):
    r = client.post("/api/v1/leads", json={"company_name": "Manual Co", "contact_email": "m@manual.example.com", "score": 70}, headers=admin)
    assert r.status_code == 201
    lid = r.json()["id"]
    r = client.patch(f"/api/v1/leads/{lid}", json={"status": "qualified"}, headers=admin)
    assert r.json()["status"] == "qualified"
    assert client.get("/api/v1/leads/stats", headers=admin).json()["total"] >= 1
