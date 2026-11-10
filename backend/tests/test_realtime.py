"""WebSocket push: a client request must reach a connected admin in real time."""
import json


def test_websocket_rejects_bad_token(client):
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect("/ws?token=bad") as ws:
            ws.receive_text()
        assert False, "should have been closed"
    except WebSocketDisconnect as exc:
        assert exc.code == 4401


def test_websocket_receives_new_request_events(client, admin_token, admin, client_headers):
    svc = client.get("/api/v1/services/logo-design").json()
    with client.websocket_connect(f"/ws?token={admin_token}") as ws:
        hello = json.loads(ws.receive_text())
        assert hello["type"] == "hello" and hello["payload"]["role"] == "admin"

        r = client.post(
            "/api/v1/requests",
            json={"service_id": svc["id"], "title": "Realtime logo", "brief": {"about_and_wishes": "We sell handmade candles online; keep it warm and minimal.", "brand_name": "Testco"}},
            headers=client_headers,
        )
        assert r.status_code == 201
        rid = r.json()["id"]

        seen = set()
        for _ in range(6):
            msg = json.loads(ws.receive_text())
            seen.add(msg["type"])
            if msg["type"] == "notification":
                assert msg["payload"]["notification"]["request_id"] == rid
                assert msg["payload"]["unread_count"] >= 1
            if msg["type"] == "badge_counts":
                assert msg["payload"]["highlight_service_id"] == svc["id"]
                assert any(s["slug"] == "logo-design" and s["pending"] >= 1 for s in msg["payload"]["services"])
            if {"notification", "badge_counts", "request_update"} <= seen:
                break
        assert {"notification", "badge_counts", "request_update"} <= seen

        # accepting pushes a request_update with the new status
        client.post(f"/api/v1/requests/{rid}/accept", headers=admin)
        statuses = []
        for _ in range(6):
            msg = json.loads(ws.receive_text())
            if msg["type"] == "request_update" and msg["payload"]["request_id"] == rid:
                statuses.append(msg["payload"]["status"])
                if "accepted" in statuses:
                    break
        assert "accepted" in statuses
