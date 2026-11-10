"""Delivery Agent: packages the approved design, stores the final files in the client's folder, notifies the client.

Final package location: clients/<Company> #<id>/<Service>/Request <id> - <title>/Final/
The client sees the delivery in their portal under "Your designs" and can download each file or everything as a ZIP.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.agents import control, live
from app.agents.llm import complete
from app.db.mongo import Doc, get_db, utcnow
from app.models.enums import NotificationType
from app.services import request_service as rs
from app.services.file_service import read_file_bytes, store_bytes
from app.services.folders import request_folder, safe_name
from app.services import deliverables
from app.services.notification_service import notify

KEY = "delivery"
SYSTEM = """You are the Delivery Agent at Designflow, a premium design studio. Write a short, warm delivery note to the
client (2-4 sentences): say the work is ready, describe what is included in plain words, and remind them that
revisions are included. Address the client by their company name. Sign off as "The Designflow team". Never invent
file names and never use placeholders such as [Your Name] or [Client].
Return JSON with key: message."""


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    from app.agents.tools.design_engine import export

    db = get_db()
    req = db.requests.update(state["request_id"], {"pipeline_stage": "delivery"})
    service = db.services.get(req.service_id) or Doc({})
    client = db.clients.get(req.client_id) or Doc({})
    with control.running(db, KEY, f"Delivering: {req.title}", run_id=state.get("run_id"), request_id=req.id) as ctx:
        designs = db.designs.find({"request_id": req.id}, sort=[("version", 1)])
        approved = [d for d in designs if d.get("status") == "approved"]
        chosen = approved[-1] if approved else (designs[-1] if designs else None)
        if chosen and chosen.get("status") != "approved":
            chosen = db.designs.update(chosen.id, {"status": "approved"})

        # what goes to the client: only the finished designs, in the formats of the service they ordered
        # (see app/services/deliverables.py) + anything the admin uploaded for delivery
        items: List[Dict[str, Any]] = [dict(f) for f in (chosen.get("files") or [])] if chosen else []
        items = deliverables.select(service.get("slug") or "", req.get("brief") or {}, items)
        file_ids = [f["file_id"] for f in items]
        def _studio(f: Doc) -> bool:  # earlier packages / notes, boards, sources: never re-sent as "extras"
            return (f.get("meta") or {}).get("role") in ("package", "notes", "board", "source")

        extra = [f for f in db.files.find({"request_id": req.id, "kind": "delivery"}, sort=[("_id", 1)]) if not _studio(f)]
        if not items:  # older or hand-made designs: fall back to their preview + uploads
            legacy = db.files.find({"request_id": req.id, "kind": {"$in": ["design", "delivery"]}}, sort=[("_id", 1)])
            extra = [f for f in legacy if f.id not in file_ids and not _studio(f)]
        for f in extra:
            if f.id not in file_ids:
                file_ids.append(f.id)
                items.append({"file_id": f.id, "name": f.get("original_name"), "format": (f.get("original_name") or "").rsplit(".", 1)[-1].lower(),
                              "role": "variant", "label": f.get("original_name"), "width": 0, "height": 0, "page": None, "group": "Your uploads",
                              "thumb_file_id": None})

        final_folder = request_folder(db, req, "Final", service=service, client=client)

        # one ZIP with the same files, folders preserved
        entries = []
        for f in items:
            row = db.files.get(f["file_id"])
            if not row:
                continue
            try:
                entries.append(((f.get("group") + "/" if f.get("group") else "") + (f.get("name") or row.get("original_name")), read_file_bytes(row)))
            except Exception:
                continue
        pkg_name = f"{safe_name(client.get('company_name') or 'Client')} - {safe_name(service.get('name') or 'Design')} - final.zip"
        pkg = store_bytes(db, data=export.zip_files(entries), filename=pkg_name, mime_type="application/zip", folder=final_folder, kind="delivery",
                          owner_user_id=None, client_id=req.client_id, request_id=req.id, meta={"role": "package", "format": "zip"})

        res = complete(
            KEY, SYSTEM,
            f"Request: {req.title}\nService: {service.get('name', '')}\nClient company: {client.get('company_name') or 'the client'}\n"
            f"Included: {', '.join(sorted({(f.get('label') or '').split(' (')[0] for f in items if f.get('label')}))[:900]}\n"
            f"Admin note: {state.get('approval_message') or ''}",
        )
        message = (res.data or {}).get("message") or f"Your {service.get('name', 'design').lower()} is ready to download."
        if state.get("approval_message"):
            message = f"{message}\n\nNote from your designer: {state['approval_message']}"
        links = [{"name": f.get("name"), "url": f"/api/v1/files/{f['file_id']}/download", "file_id": f["file_id"]} for f in items]
        links.insert(0, {"name": pkg_name, "url": f"/api/v1/files/{pkg.id}/download", "file_id": pkg.id})
        version = db.deliveries.count({"request_id": req.id}) + 1
        delivery = db.deliveries.insert(
            {
                "request_id": req.id, "message": message, "file_ids": [pkg.id] + file_ids, "download_links": links, "files": items,
                "design_id": chosen.id if chosen else None, "package_file_id": pkg.id, "client_id": req.client_id, "service_id": req.service_id,
                "delivered_by": "agent", "version": version, "delivered_at": utcnow(), "selected": True,
            }
        )
        deliverables.invalidate(req.client_id)
        db.revisions.update_many({"request_id": req.id, "status": {"$ne": "completed"}}, {"status": "completed", "resolved_at": utcnow()})
        if client.get("user_id"):
            notify(
                db, [client.user_id], type=NotificationType.DELIVERY.value, title=f"Your designs are ready: {req.title}",
                body=message[:200], link="/portal#/designs", service_id=req.service_id, request_id=req.id,
            )
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=f"Delivery #{delivery.id}: {len(items)} file(s) + ZIP", model=res.model)
        live.emit(
            db, req.id, "delivered", agent_key=KEY, run_id=state.get("run_id"), title=f"Delivered {len(items)} file(s) to the client", body=message,
            data={"delivery_id": delivery.id, "version": version, "links": links[:30], "design_id": chosen.id if chosen else None, "package_file_id": pkg.id},
        )
    req = db.requests.get(req.id)
    rs.transition(db, req, "completed", actor=f"agent:{KEY}", note=f"Delivered {len(items)} file(s)", force=True)
    live.emit(db, req.id, "completed", agent_key=KEY, run_id=state.get("run_id"), title="Request completed",
              body="The client has been notified and can download everything from Your designs in their portal.", data={"delivery_id": delivery.id})
    return {"delivery_id": delivery.id, "stage": "complete"}
