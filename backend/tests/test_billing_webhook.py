"""Pay-per-request billing: mock checkout, manual payment, Stripe webhook."""
from __future__ import annotations

from app.api.v1 import billing as billing_api
from app.api.v1 import requests as requests_api


def _new_request(client, headers, slug="logo-design"):
    svc = client.get(f"/api/v1/services/{slug}").json()
    brief = {f["key"]: (f.get("options") or ["Testco value"])[0] if f["type"] in ("select", "multiselect") else "Testco value" for f in svc["form_schema"] if f.get("required")}
    r = client.post("/api/v1/requests", json={"service_id": svc["id"], "title": "Paid logo", "brief": brief}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json(), svc


def test_request_has_price_and_invoice(client, client_headers):
    req, svc = _new_request(client, client_headers)
    assert req["price_amount"] == svc["prices"]["USD"] == 19
    assert req["price_currency"] == "USD" and req["is_paid"] is False and req["turnaround_days"] == 3
    inv = client.get("/api/v1/billing/invoices", headers=client_headers).json()
    mine = [i for i in inv if i["request_id"] == req["id"]]
    assert mine and mine[0]["status"] == "pending" and mine[0]["amount"] == 19


def test_mock_pay_settles_instantly(client, client_headers, admin):
    req, _ = _new_request(client, client_headers, "flyer-design")
    r = client.post(f"/api/v1/requests/{req['id']}/pay", headers=client_headers)
    assert r.status_code == 200 and r.json()["paid"] is True
    detail = client.get(f"/api/v1/requests/{req['id']}", headers=admin).json()
    assert detail["is_paid"] and detail["paid_at"]
    assert any(e["kind"] == "paid" for e in detail["timeline"])
    notes = client.get("/api/v1/notifications", params={"type": "payment"}, headers=admin).json()
    assert any(n["request_id"] == req["id"] for n in notes)
    # paying twice is a no-op
    assert client.post(f"/api/v1/requests/{req['id']}/pay", headers=client_headers).json()["paid"] is True


def test_admin_mark_paid_and_summary(client, client_headers, admin):
    req, svc = _new_request(client, client_headers, "poster-design")
    expected_inr = round(svc["prices"]["USD"] * 84, 2)
    r = client.post(f"/api/v1/requests/{req['id']}/mark-paid", params={"note": "bank transfer"}, headers=admin)
    assert r.status_code == 200 and r.json()["is_paid"]
    s = client.get("/api/v1/billing/summary", headers=admin).json()
    assert s["by_currency"]["USD"]["count_paid"] >= 1
    assert s["settled"]["currency"] == "INR" and s["settled"]["paid"] >= expected_inr
    pays = client.get("/api/v1/billing/payments", headers=admin).json()["items"]
    mine = next(p for p in pays if p["request_id"] == req["id"])
    assert mine["settled_currency"] == "INR" and mine["settled_amount"] == expected_inr
    sales = client.get("/api/v1/analytics/sales", headers=admin).json()
    assert sales["paid_orders"] >= 1 and any(b["slug"] == "poster-design" for b in sales["by_service"])


def test_currency_pricing_for_gbp_client(client):
    r = client.post("/api/v1/auth/register", json={"email": "gbp@example.com", "password": "Gbpuser123", "full_name": "GBP User",
                                                   "company_name": "GBP Co", "currency": "GBP"})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    svc = client.get("/api/v1/services/logo-design").json()
    req = client.post("/api/v1/requests", json={"service_id": svc["id"], "title": "UK logo", "brief": {"brand_name": "GBP Co", "about_and_wishes": "UK tea brand, classic look"}}, headers=h).json()
    assert req["price_currency"] == "GBP" and req["price_amount"] == svc["prices"]["GBP"] == round(19 * 0.79)
    assert svc["prices"]["INR"] == round(19 * 84 / 10) * 10


class FakeStripe:
    name = "stripe"

    def __init__(self, events):
        self.events = list(events)

    def create_request_checkout(self, **kw):
        from app.services.billing.base import CheckoutResult

        return CheckoutResult(provider="stripe", checkout_url="https://checkout.stripe.test/s_123", paid=False)

    def handle_webhook(self, payload, signature):
        return self.events.pop(0)


def test_stripe_checkout_and_webhook(client, client_headers, admin, monkeypatch):
    req, _ = _new_request(client, client_headers, "business-card-design")
    fake = FakeStripe([{"type": "checkout.session.completed", "raw_id": "evt_1", "request_id": req["id"], "amount": 13, "currency": "USD", "payment_id": "pi_1"}])
    monkeypatch.setattr(requests_api, "get_billing", lambda: fake, raising=False)
    monkeypatch.setattr("app.services.billing.get_billing", lambda: fake)
    monkeypatch.setattr(billing_api, "get_billing", lambda: fake)
    r = client.post(f"/api/v1/requests/{req['id']}/pay", headers=client_headers)
    assert r.status_code == 200 and r.json()["paid"] is False and r.json()["checkout_url"].startswith("https://checkout")
    r = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "sig"})
    assert r.status_code == 200
    detail = client.get(f"/api/v1/requests/{req['id']}", headers=admin).json()
    assert detail["is_paid"]
    inv = client.get("/api/v1/billing/invoices", headers=client_headers).json()
    assert any(i["request_id"] == req["id"] and i["status"] == "paid" and i["provider"] == "stripe" for i in inv)
    # replay is idempotent
    fake.events.append({"type": "checkout.session.completed", "raw_id": "evt_1", "request_id": req["id"], "amount": 13, "currency": "USD", "payment_id": "pi_1"})
    client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "sig"})
    inv2 = client.get("/api/v1/billing/invoices", headers=client_headers).json()
    assert len([i for i in inv2 if i["request_id"] == req["id"]]) == 1


def test_webhook_rejects_bad_signature(client, monkeypatch):
    class Bad:
        name = "stripe"

        def handle_webhook(self, payload, signature):
            raise ValueError("bad signature")

    monkeypatch.setattr(billing_api, "get_billing", lambda: Bad())
    r = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "nope"})
    assert r.status_code == 400
