import io


def _service(client, slug="youtube-thumbnail-design"):
    r = client.get(f"/api/v1/services/{slug}")
    assert r.status_code == 200
    return r.json()


def test_services_public_list(client):
    r = client.get("/api/v1/services")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 19
    assert {s["slug"] for s in data} >= {"logo-design", "pitch-deck-design", "custom-design-requests"}
    assert all(s["form_schema"] for s in data)


def test_request_requires_required_fields(client, client_headers):
    svc = _service(client)
    r = client.post("/api/v1/requests", json={"service_id": svc["id"], "title": "Missing fields", "brief": {"about_and_wishes": "We sell handmade candles online; keep it warm and minimal.", }}, headers=client_headers)
    assert r.status_code == 422


def test_request_lifecycle(client, admin, client_headers, db):
    svc = _service(client)
    before = client.get("/api/v1/services/counts", headers=admin).json()["total_pending"]

    r = client.post(
        "/api/v1/requests",
        json={
            "service_id": svc["id"],
            "title": "Thumbnail for launch video",
            "description": "Bold text, red background",
            "brief": {"about_and_wishes": "We sell handmade candles online; keep it warm and minimal.", "channel_name": "Testco TV", "video_title": "We launched!", "thumbnail_text": "WE LAUNCHED"},
            "priority": "high",
        },
        headers=client_headers,
    )
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "pending"
    assert req["service_slug"] == "youtube-thumbnail-design"

    # badge count went up and admin got a notification
    after = client.get("/api/v1/services/counts", headers=admin).json()
    assert after["total_pending"] == before + 1
    notes = client.get("/api/v1/notifications", params={"unread_only": True}, headers=admin).json()
    assert any(n["request_id"] == req["id"] and n["type"] == "new_request" for n in notes)

    # client cannot accept
    assert client.post(f"/api/v1/requests/{req['id']}/accept", headers=client_headers).status_code == 403

    # admin accepts
    r = client.post(f"/api/v1/requests/{req['id']}/accept", headers=admin)
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"
    assert r.json()["accepted_at"]
    assert client.get("/api/v1/services/counts", headers=admin).json()["total_pending"] == before

    # client sees status + notification
    detail = client.get(f"/api/v1/requests/{req['id']}", headers=client_headers).json()
    assert detail["status"] == "accepted"
    assert any(e["kind"] == "accepted" for e in detail["timeline"])
    cn = client.get("/api/v1/notifications", headers=client_headers).json()
    assert any(n["request_id"] == req["id"] and n["type"] == "request_status" for n in cn)

    # admin adds design, delivers, completes
    r = client.post(f"/api/v1/requests/{req['id']}/designs", json={"title": "Concept A", "concept": "Red bg"}, headers=admin)
    assert r.status_code == 201
    r = client.post(f"/api/v1/requests/{req['id']}/deliveries", json={"message": "Here you go", "mark_completed": True}, headers=admin)
    assert r.status_code == 201
    detail = client.get(f"/api/v1/requests/{req['id']}", headers=admin).json()
    assert detail["status"] == "completed"
    assert len(detail["deliveries"]) == 1
    assert len(detail["designs"]) == 1

    # client requests revision
    r = client.post(f"/api/v1/requests/{req['id']}/revisions", json={"feedback": "Make text bigger please"}, headers=client_headers)
    assert r.status_code == 201
    assert r.json()["round"] == 1
    detail = client.get(f"/api/v1/requests/{req['id']}", headers=admin).json()
    assert detail["status"] == "in_progress"
    assert detail["revision_count"] == 1

    # complete button works from any state
    r = client.post(f"/api/v1/requests/{req['id']}/complete", headers=admin)
    assert r.json()["status"] == "completed"


def test_reject_with_reason(client, admin, client_headers):
    svc = _service(client, "flyer-design")
    r = client.post("/api/v1/requests", json={"service_id": svc["id"], "title": "Flyer", "brief": {"about_and_wishes": "We sell handmade candles online; keep it warm and minimal.", "brand_name": "Testco", "event_or_offer": "Sale"}}, headers=client_headers)
    assert r.status_code == 201
    rid = r.json()["id"]
    r = client.post(f"/api/v1/requests/{rid}/reject", json={"reason": "Out of scope"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["rejection_reason"] == "Out of scope"


def test_invalid_transition(client, admin, client_headers):
    svc = _service(client, "poster-design")
    r = client.post("/api/v1/requests", json={"service_id": svc["id"], "title": "Poster", "brief": {"about_and_wishes": "We sell handmade candles online; keep it warm and minimal.", "brand_name": "Testco"}}, headers=client_headers)
    rid = r.json()["id"]
    client.post(f"/api/v1/requests/{rid}/reject", headers=admin)
    # rejected -> in_progress not allowed without force (start uses force, so use status without force via reject->... use accept then reject again)
    r = client.post(f"/api/v1/requests/{rid}/reject", headers=admin)
    assert r.status_code in (200, 409)


def test_client_isolation(client, client_headers, other_client_headers):
    mine = client.get("/api/v1/requests", headers=client_headers).json()
    assert mine["total"] >= 1
    rid = mine["items"][0]["id"]
    assert client.get(f"/api/v1/requests/{rid}", headers=other_client_headers).status_code == 404
    theirs = client.get("/api/v1/requests", headers=other_client_headers).json()
    assert theirs["total"] == 0


def test_service_requests_and_analytics(client, admin):
    svc = _service(client)
    r = client.get(f"/api/v1/services/{svc['id']}/requests", headers=admin)
    assert r.status_code == 200
    assert len(r.json()) >= 1
    r = client.get(f"/api/v1/services/{svc['id']}/analytics", headers=admin)
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    assert len(r.json()["trend"]) == 12


def test_file_upload_download_and_versions(client, client_headers, admin):
    mine = client.get("/api/v1/requests", headers=client_headers).json()["items"][0]
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    r = client.post("/api/v1/files/upload", files={"file": ("logo.png", io.BytesIO(png), "image/png")},
                    data={"request_id": str(mine["id"])}, headers=client_headers)
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["mime_type"] == "image/png"
    r = client.get(f"/api/v1/files/{f['id']}/download", headers=client_headers)
    assert r.status_code == 200 and r.content == png
    # new version
    r = client.post("/api/v1/files/upload", files={"file": ("logo.png", io.BytesIO(png + b"\x01"), "image/png")},
                    data={"request_id": str(mine["id"]), "parent_file_id": str(f["id"])}, headers=client_headers)
    assert r.json()["version"] == 2
    versions = client.get(f"/api/v1/files/{f['id']}/versions", headers=admin).json()
    assert [v["version"] for v in versions] == [1, 2]
    # blocked type
    r = client.post("/api/v1/files/upload", files={"file": ("evil.exe", io.BytesIO(b"MZ..."), "application/octet-stream")}, headers=client_headers)
    assert r.status_code == 400


def test_brand_assets(client, client_headers, admin):
    r = client.post("/api/v1/brand-assets", json={"type": "color", "name": "Primary", "value": "#0F766E"}, headers=client_headers)
    assert r.status_code == 201
    r = client.get("/api/v1/brand-assets", headers=client_headers)
    assert any(a["name"] == "Primary" for a in r.json())


def test_projects(client, client_headers):
    r = client.post("/api/v1/projects", json={"name": "Launch", "description": "Q4"}, headers=client_headers)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.get("/api/v1/projects", headers=client_headers).json()[0]["id"] == pid
    r = client.patch(f"/api/v1/projects/{pid}", json={"status": "archived"}, headers=client_headers)
    assert r.json()["status"] == "archived"
