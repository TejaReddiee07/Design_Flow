"""Design library: per-client folders (admin "Client files") and delivered work (portal "Your designs").

Rows are created directly / through the manual delivery API so these tests do not depend on the
design engine's exact output (file names, counts); they assert on structure and access rules only.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from app.db.mongo import get_db
from app.services.file_service import store_bytes

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _register(client, email, company):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "Library123!", "full_name": f"{company} Owner", "company_name": company})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _request(client, headers, title):
    svc = client.get("/api/v1/services/logo-design").json()
    brief = {fld["key"]: ((fld.get("options") or ["x"])[0] if fld["type"] in ("select", "multiselect") else "Library Co")
             for fld in svc["form_schema"] if fld.get("required")}
    r = client.post("/api/v1/requests", json={"service_id": svc["id"], "title": title, "brief": brief}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="module")
def lib(client, admin):
    db = get_db()
    a = _register(client, "owner@libraryco.example", "Library Co")
    b = _register(client, "owner@snoopco.example", "Snoop Co")
    delivered = _request(client, a, "Library logo")
    _request(client, a, "Not delivered yet")  # must not appear in the client's "Your designs"
    rid = delivered["id"]
    cid = delivered["client_id"]

    # admin uploads a design file to the request (stored in the client's readable folder)
    up = client.post("/api/v1/files/upload", files={"file": ("concept.png", io.BytesIO(PNG), "image/png")},
                     data={"request_id": str(rid), "kind": "design"}, headers=admin)
    assert up.status_code == 201, up.text
    up = up.json()

    # a design-engine style version: files list + a thumbnail (kind thumb)
    thumb = store_bytes(db, data=PNG, filename="concept-thumb.png", mime_type="image/png", folder="clients/test/thumbs", kind="thumb",
                        owner_user_id=None, client_id=cid, request_id=rid, meta={"thumb_of": up["id"]})
    sheet = store_bytes(db, data=b"%PDF-1.4 test", filename="Library Co - brand guide.pdf", mime_type="application/pdf",
                        folder="clients/test", kind="design", owner_user_id=None, client_id=cid, request_id=rid)
    files = [
        {"file_id": up["id"], "name": "concept.png", "format": "png", "role": "board", "label": "Concept board - 1600x1000", "width": 1600, "height": 1000, "thumb_file_id": thumb.id},
        {"file_id": sheet.id, "name": "Library Co - brand guide.pdf", "format": "pdf", "role": "page", "label": "Brand guide"},
    ]
    new_design = db.designs.insert({"request_id": rid, "version": 2, "title": "Engine concept", "concept": "", "concept_data": {}, "file_id": up["id"],
                                    "preview_url": None, "generated_by": "agent", "status": "approved", "qa_score": 92, "qa_notes": None,
                                    "files": files, "service_slug": "logo-design"})
    legacy_design = db.designs.insert({"request_id": rid, "version": 1, "title": "Legacy concept", "concept": "", "concept_data": {}, "file_id": up["id"],
                                       "preview_url": f"/api/v1/files/{up['id']}/download", "generated_by": "agent", "status": "draft"})

    # 1) legacy/manual delivery through the existing API (only file_ids + download_links)
    r = client.post(f"/api/v1/requests/{rid}/deliveries", json={"message": "Here you go", "file_ids": [up["id"]]}, headers=admin)
    assert r.status_code == 201, r.text
    legacy_delivery = r.json()

    # 2) engine-style delivery with a prebuilt ZIP package
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("Library Co/concept.png", PNG)
    pkg = store_bytes(db, data=zbuf.getvalue(), filename="Library Co - Logo Design - v2.zip", mime_type="application/zip",
                      folder="clients/test/Final", kind="delivery", owner_user_id=None, client_id=cid, request_id=rid)
    pkg_delivery = db.deliveries.insert({"request_id": rid, "message": "Final files", "file_ids": [up["id"], sheet.id, pkg.id], "download_links": [],
                                         "delivered_by": "agent", "version": 2, "design_id": new_design.id, "package_file_id": pkg.id,
                                         "files": files + [{"file_id": pkg.id, "name": "Library Co - Logo Design - v2.zip", "format": "zip", "role": "package"}]})
    return {"a": a, "b": b, "rid": rid, "cid": cid, "upload_id": up["id"], "thumb_id": thumb.id, "new_design": new_design.id,
            "legacy_design": legacy_design.id, "legacy_delivery": legacy_delivery["id"], "pkg_delivery": pkg_delivery.id}


def test_admin_folder_list(client, admin, lib):
    cards = client.get("/api/v1/library/clients", headers=admin).json()
    card = next(c for c in cards if c["client_id"] == lib["cid"])
    assert card["company_name"] == "Library Co" and card["email"] == "owner@libraryco.example"
    assert "Library Co" in card["folder"]
    assert card["services"] == 1 and card["requests"] == 2 and card["designs"] == 2 and card["delivered"] == 2
    assert card["files"] >= 3  # thumbnails are not counted
    assert card["cover_file_id"] in (lib["thumb_id"], lib["upload_id"]) and card["last_activity"]
    only = client.get("/api/v1/library/clients", params={"q": "library"}, headers=admin).json()
    assert [c["client_id"] for c in only] == [lib["cid"]]


def test_admin_folder_detail(client, admin, lib):
    data = client.get(f"/api/v1/library/clients/{lib['cid']}", headers=admin).json()
    assert data["client"]["company_name"] == "Library Co" and data["totals"]["delivered"] == 2
    [svc] = data["services"]
    assert svc["slug"] == "logo-design" and svc["request_count"] == 2
    req = next(r for r in svc["requests"] if r["id"] == lib["rid"])
    versions = {d["version"]: d for d in req["designs"]}
    assert set(versions) == {1, 2}
    engine = versions[2]
    assert engine["status"] == "approved" and engine["cover_file_id"] == lib["thumb_id"]
    board = next(f for f in engine["files"] if f["role"] == "board")
    assert board["download_url"].endswith(f"/files/{lib['upload_id']}/download") and board["is_image"] and board["width"] == 1600
    assert all(f["file_id"] != lib["thumb_id"] for f in engine["files"])
    legacy = versions[1]
    assert len(legacy["files"]) == 1 and legacy["files"][0]["format"] == "png"
    dels = {d["id"]: d for d in req["deliveries"]}
    assert set(dels) == {lib["legacy_delivery"], lib["pkg_delivery"]}
    assert dels[lib["legacy_delivery"]]["files"][0]["name"] == "concept.png"
    assert dels[lib["pkg_delivery"]]["package_file_id"]


def test_client_sees_only_delivered_work(client, lib):
    data = client.get("/api/v1/library/me", headers=lib["a"]).json()
    [svc] = data["services"]
    assert [r["id"] for r in svc["requests"]] == [lib["rid"]]  # "Not delivered yet" is hidden
    req = svc["requests"][0]
    assert req["designs"] == [] and len(req["deliveries"]) == 2
    assert all(f["download_url"] for d in req["deliveries"] for f in d["files"])
    # another client sees nothing of it and cannot open the admin views
    assert client.get("/api/v1/library/me", headers=lib["b"]).json()["services"] == []
    assert client.get("/api/v1/library/clients", headers=lib["b"]).status_code == 403
    assert client.get(f"/api/v1/library/clients/{lib['cid']}", headers=lib["b"]).status_code == 403


def test_delivery_zip_downloads(client, admin, lib):
    r = client.get(f"/api/v1/library/deliveries/{lib['legacy_delivery']}/download", headers=lib["a"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"] and "Library Co - Logo Design - delivery 1" in r.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert any(n.endswith("concept.png") for n in names)
    # the prebuilt package is returned as-is
    r = client.get(f"/api/v1/library/deliveries/{lib['pkg_delivery']}/download", headers=admin)
    assert r.status_code == 200 and zipfile.ZipFile(io.BytesIO(r.content)).namelist() == ["Library Co/concept.png"]
    # browser downloads pass the token as a query parameter
    token = lib["a"]["Authorization"].split()[1]
    assert client.get(f"/api/v1/library/deliveries/{lib['legacy_delivery']}/download", params={"token": token}).status_code == 200
    # someone else's delivery is invisible
    assert client.get(f"/api/v1/library/deliveries/{lib['legacy_delivery']}/download", headers=lib["b"]).status_code == 404


def test_design_zip_is_admin_only(client, admin, lib):
    r = client.get(f"/api/v1/library/designs/{lib['new_design']}/download", headers=admin)
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert len(names) == 2 and all(n.startswith("Library Co - Logo Design - draft v2/") for n in names)
    assert client.get(f"/api/v1/library/designs/{lib['new_design']}/download", headers=lib["a"]).status_code == 403


def test_thumbnails_hidden_and_folders_readable(client, admin, db, lib):
    listed = client.get("/api/v1/files", params={"request_id": lib["rid"]}, headers=admin).json()
    assert lib["thumb_id"] not in [f["id"] for f in listed]
    thumbs = client.get("/api/v1/files", params={"request_id": lib["rid"], "kind": "thumb"}, headers=admin).json()
    assert [f["id"] for f in thumbs] == [lib["thumb_id"]]
    path = db.files.get(lib["upload_id"]).path
    assert path.startswith(f"clients/Library Co #{lib['cid']}/Logo Design/Request {lib['rid']} - Library logo/Drafts/")
    assert path.endswith("concept.png")
