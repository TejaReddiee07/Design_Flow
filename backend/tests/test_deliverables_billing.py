"""Clients receive only the designs of the service they ordered; admins can open any invoice's payment details."""
from __future__ import annotations

import io

from app.db.mongo import get_db
from app.services import deliverables
from app.services.file_service import store_bytes

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _item(name, role, fmt="png", group="", **kw):
    return {"file_id": hash(name) & 0xFFFFFF, "name": name, "role": role, "format": fmt, "group": group, **kw}


# ---------------------------------------------------------------------------
# selection rules (pure)
# ---------------------------------------------------------------------------
def test_youtube_delivers_only_the_thumbnails():
    items = [_item("Preview.png", "board"), _item("Thumbnail A - 1280x720.png", "primary"), _item("Thumbnail B - 1280x720.png", "variant"),
             _item("Thumbnail A - 1280x720.svg", "source", "svg"), _item("Notes.md", "notes", "md")]
    names = [i["name"] for i in deliverables.select("youtube-thumbnail-design", {}, items)]
    assert names == ["Thumbnail A - 1280x720.png", "Thumbnail B - 1280x720.png"]


def test_pitch_deck_pdf_only_vs_powerpoint():
    items = [_item("Deck overview.png", "board"), _item("Slide 01 - Cover.png", "primary"), _item("Slide 02.png", "page"),
             _item("Acme - pitch deck.pdf", "document", "pdf"), _item("Deck outline and notes.md", "notes", "md")]
    assert [i["name"] for i in deliverables.select("pitch-deck-design", {"format": "PDF only"}, items)] == ["Acme - pitch deck.pdf"]
    ppt = [i["name"] for i in deliverables.select("pitch-deck-design", {"format": "PowerPoint"}, items)]
    assert ppt[0] == "Acme - pitch deck.pdf" and "Slide 02.png" in ppt and "Deck overview.png" not in ppt


def test_social_sizes_follow_the_platforms_picked():
    items = [_item(f"Post {n} - portrait 1080x1350.png", "variant") for n in (1, 2)] + [
        _item(f"Post {n} - square 1080x1080.png", "variant") for n in (1, 2)] + [
        _item("Story - 1080x1920.png", "variant"), _item("Landscape - 1200x628.png", "variant"), _item("Captions and hashtags.md", "notes", "md")]
    insta = {i["name"] for i in deliverables.select("social-media-design", {"platforms": ["Instagram"]}, items)}
    assert insta == {"Post 1 - portrait 1080x1350.png", "Post 2 - portrait 1080x1350.png", "Story - 1080x1920.png"}
    linkedin = {i["name"] for i in deliverables.select("social-media-design", {"platforms": ["LinkedIn"]}, items)}
    assert linkedin == {"Post 1 - square 1080x1080.png", "Post 2 - square 1080x1080.png", "Landscape - 1200x628.png"}


def test_ads_follow_platform_and_sources_only_when_asked():
    items = [_item(f"Hook 1 - {s}.png", "variant") for s in ("1080x1080", "1080x1350", "1080x1920", "1200x628", "300x250", "728x90")]
    google = {i["name"] for i in deliverables.select("ad-creative-design", {"platform": ["Google Display"]}, items)}
    assert google == {"Hook 1 - 300x250.png", "Hook 1 - 728x90.png", "Hook 1 - 1200x628.png"}
    logo = [_item("Logo 1.png", "primary"), _item("Logo 1.svg", "source", "svg")]
    assert [i["name"] for i in deliverables.select("logo-design", {}, logo)] == ["Logo 1.png"]
    assert [i["name"] for i in deliverables.select("logo-design", {"about_and_wishes": "Please include SVG vector files"}, logo)] == ["Logo 1.png", "Logo 1.svg"]


# ---------------------------------------------------------------------------
# what a client can see through the API
# ---------------------------------------------------------------------------
def _register(client, email, company):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Deliver123!", "full_name": f"{company} Owner", "company_name": company})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_client_sees_only_delivered_designs(client, admin):
    db = get_db()
    h = _register(client, "owner@thumbco.example", "Thumb Co")
    svc = client.get("/api/v1/services/youtube-thumbnail-design").json()
    brief = {f["key"]: ((f.get("options") or ["x"])[0] if f["type"] in ("select", "multiselect") else "Thumb Co") for f in svc["form_schema"] if f.get("required")}
    req = client.post("/api/v1/requests", json={"service_id": svc["id"], "title": "Thumbs", "brief": brief}, headers=h).json()
    rid, cid = req["id"], req["client_id"]

    def put(name, role, fmt="png", mime="image/png"):
        f = store_bytes(db, data=PNG, filename=name, mime_type=mime, folder="clients/thumbco/Drafts", kind="design", owner_user_id=None,
                        client_id=cid, request_id=rid, meta={"role": role, "format": fmt})
        return {"file_id": f.id, "name": name, "role": role, "format": fmt, "group": "", "label": name}

    files = [put("Thumb Co - preview.png", "board"), put("Thumbnail A - 1280x720.png", "primary"), put("Thumbnail B - 1280x720.png", "variant"),
             put("Thumbnail A - 1280x720.svg", "source", "svg", "image/svg+xml")]
    design = db.designs.insert({"request_id": rid, "version": 1, "title": "v1", "concept": "", "concept_data": {}, "file_id": files[0]["file_id"],
                                "preview_url": None, "generated_by": "agent", "status": "approved", "files": files, "service_slug": svc["slug"]})
    notes = store_bytes(db, data=b"# notes", filename="Delivery notes.md", mime_type="text/markdown", folder="clients/thumbco/Final", kind="delivery",
                        owner_user_id=None, client_id=cid, request_id=rid, meta={"role": "notes", "format": "md"})
    db.deliveries.insert({"request_id": rid, "message": "Ready", "file_ids": [f["file_id"] for f in files] + [notes.id], "download_links": [],
                          "delivered_by": "agent", "version": 1, "design_id": design.id,
                          "files": files + [{"file_id": notes.id, "name": "Delivery notes.md", "format": "md", "role": "notes"}]})
    deliverables.invalidate()

    detail = client.get(f"/api/v1/requests/{rid}", headers=h).json()
    delivered = [l["name"] for l in detail["deliveries"][0]["download_links"]]
    assert delivered == ["Thumbnail A - 1280x720.png", "Thumbnail B - 1280x720.png"]
    assert detail["designs"][0]["file_id"] == files[1]["file_id"]  # the thumbnail, not the studio board
    listed = {f["original_name"] for f in client.get("/api/v1/files", headers=h).json()}
    assert "Thumb Co - preview.png" not in listed and "Delivery notes.md" not in listed and "Thumbnail A - 1280x720.svg" not in listed
    assert client.get(f"/api/v1/files/{files[0]['file_id']}/download", headers=h).status_code == 404
    assert client.get(f"/api/v1/files/{files[1]['file_id']}/download", headers=h).status_code == 200
    mine = client.get("/api/v1/library/me", headers=h).json()
    got = [f["name"] for g in mine["services"] for r in g["requests"] for d in r["deliveries"] for f in d["files"]]
    assert sorted(got) == ["Thumbnail A - 1280x720.png", "Thumbnail B - 1280x720.png"]
    # the admin still sees every draft file
    assert client.get(f"/api/v1/files/{files[0]['file_id']}/download", headers=admin).status_code == 200


# ---------------------------------------------------------------------------
# billing: payment details
# ---------------------------------------------------------------------------
def test_payment_details_for_a_manual_payment(client, admin):
    h = _register(client, "owner@payco.example", "Pay Co")
    me = client.get("/api/v1/auth/me", headers=h).json()
    cid = (me.get("client") or {}).get("id")
    r = client.post("/api/v1/billing/payments", json={"client_id": cid, "amount": 120, "currency": "GBP", "status": "paid",
                                                      "description": "Bank transfer 12 Nov"}, headers=admin)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    d = client.get(f"/api/v1/billing/payments/{pid}", headers=admin)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["method"]["provider"] == "manual" and body["status"] == "paid" and body["amount"] == 120
    assert body["company_name"] == "Pay Co" and body["client_email"] == "owner@payco.example"
    assert body["history"][0]["title"] == "Invoice created"
    assert client.get(f"/api/v1/billing/payments/{pid}", headers=h).status_code == 403
    assert client.get("/api/v1/billing/payments/999999", headers=admin).status_code == 404


def test_billing_summary_has_settled_totals(client, admin):
    s = client.get("/api/v1/billing/summary", headers=admin).json()
    assert {"currency", "paid", "pending"} <= set(s["settled"])
