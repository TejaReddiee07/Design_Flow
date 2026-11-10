"""Design library: one folder per client, grouped by service, with every design version and delivery.

Admin:  GET /library/clients                  folder cards (one per client)
        GET /library/clients/{client_id}      everything for one client: services -> requests -> drafts + deliveries
        GET /library/designs/{id}/download    ZIP of one draft version
Client: GET /library/me                       their delivered work only ("Your designs" in the portal)
Both:   GET /library/deliveries/{id}/download ZIP of one delivery

Works with rows written before the design engine existed: designs that only have file_id/preview_url and
deliveries that only have file_ids/download_links are turned into the same file-item shape.
"""
from __future__ import annotations

import io
import mimetypes
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.deps import get_current_user, require_admin
from app.db.mongo import DB, Doc, get_db, parallel
from app.services import deliverables
from app.services.file_service import read_file_bytes
from app.services.folders import client_folder, safe_name

router = APIRouter(prefix="/library", tags=["library"])

IMAGE_FORMATS = {"png", "svg", "jpg", "jpeg", "webp", "gif"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _iso(v: Any) -> Optional[str]:
    return v.isoformat() if isinstance(v, datetime) else (v or None)


def _ts(v: Any) -> float:
    return v.timestamp() if isinstance(v, datetime) else 0.0


def _latest(*values: Any) -> Optional[datetime]:
    dates = [v for v in values if isinstance(v, datetime)]
    return max(dates) if dates else None


def _fmt_of(f: Optional[Doc], fallback_name: str = "") -> str:
    name = (f.get("original_name") if f else None) or fallback_name or ""
    ext = Path(name).suffix.lower().lstrip(".")
    if ext:
        return "jpg" if ext == "jpeg" else ext
    mime = (f.get("mime_type") if f else "") or ""
    guess = (mimetypes.guess_extension(mime) or "").lstrip(".")
    return {"jpe": "jpg", "svgz": "svg"}.get(guess, guess or "file")


def _file_ids_of(items: Iterable[Dict[str, Any]]) -> List[int]:
    out: List[int] = []
    for it in items or []:
        for key in ("file_id", "thumb_file_id"):
            v = it.get(key) if isinstance(it, dict) else None
            if v:
                try:
                    out.append(int(v))
                except (TypeError, ValueError):
                    pass
    return out


def _raw_items_for_design(d: Doc) -> List[Dict[str, Any]]:
    items = [dict(x) for x in (d.get("files") or []) if isinstance(x, dict) and x.get("file_id")]
    if items:
        return items
    if d.get("file_id"):  # legacy: a single preview file
        return [{"file_id": d["file_id"], "role": "board", "label": d.get("title") or f"Design v{d.get('version', 1)}"}]
    return []


def _raw_items_for_delivery(dl: Doc) -> List[Dict[str, Any]]:
    items = [dict(x) for x in (dl.get("files") or []) if isinstance(x, dict) and x.get("file_id")]
    if items:
        return items
    names = {int(l["file_id"]): l.get("name") for l in (dl.get("download_links") or []) if isinstance(l, dict) and l.get("file_id")}
    return [{"file_id": int(fid), "name": names.get(int(fid))} for fid in (dl.get("file_ids") or []) if fid]


def _enrich(items: List[Dict[str, Any]], files: Dict[int, Doc]) -> List[Dict[str, Any]]:
    """Fill each item with name/format/mime/size/download_url from the files collection; drop missing files."""
    out = []
    for it in items:
        try:
            fid = int(it.get("file_id"))
        except (TypeError, ValueError):
            continue
        f = files.get(fid)
        if not f or f.get("kind") == "thumb":
            continue
        meta = f.get("meta") or {}
        name = it.get("name") or f.get("original_name") or f"file-{fid}"
        fmt = (it.get("format") or _fmt_of(f, name)).lower()
        thumb = it.get("thumb_file_id") or meta.get("thumb_file_id")
        out.append(
            {
                "file_id": fid,
                "name": name,
                "format": fmt,
                "role": it.get("role") or meta.get("role") or ("notes" if fmt == "md" else "package" if fmt == "zip" else "primary"),
                "label": it.get("label") or meta.get("label") or Path(name).stem,
                "width": it.get("width") or meta.get("width"),
                "height": it.get("height") or meta.get("height"),
                "page": it.get("page") or meta.get("page"),
                "thumb_file_id": int(thumb) if thumb else None,
                "mime_type": f.get("mime_type") or "application/octet-stream",
                "size_bytes": int(f.get("size_bytes") or 0),
                "is_image": fmt in IMAGE_FORMATS,
                "download_url": f"/api/v1/files/{fid}/download",
            }
        )
    return out


def _cover_of(items: List[Dict[str, Any]]) -> Optional[int]:
    """Best image to represent a version: board, then primary, then any image."""
    images = [i for i in items if (i.get("format") or "").lower() in IMAGE_FORMATS or i.get("thumb_file_id")]
    for role in ("board", "primary"):
        for i in images:
            if i.get("role") == role:
                return i.get("thumb_file_id") or i.get("file_id")
    return (images[0].get("thumb_file_id") or images[0].get("file_id")) if images else None


def _cover_from_raw(items: List[Dict[str, Any]], files: Dict[int, Doc]) -> Optional[int]:
    return _cover_of(_enrich(items, files))


def _client_card_user(users: Dict[int, Doc], client: Doc) -> Doc:
    return users.get(client.get("user_id")) or Doc({})


# ---------------------------------------------------------------------------
# folder list (admin)
# ---------------------------------------------------------------------------
@router.get("/clients")
def client_folders(q: Optional[str] = None, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    clients, users_list, reqs, designs, deliveries, file_counts = parallel(
        lambda: db.clients.find({}, sort=[("_id", 1)]),
        lambda: db.users.find({"role": "client"}, projection={"full_name": 1, "email": 1}),
        lambda: db.requests.find({}, projection={"client_id": 1, "service_id": 1, "submitted_at": 1, "created_at": 1, "updated_at": 1}),
        lambda: db.designs.find({}, projection={"request_id": 1, "status": 1, "version": 1, "created_at": 1, "files": 1, "file_id": 1, "title": 1}),
        lambda: db.deliveries.find({}, projection={"request_id": 1, "delivered_at": 1, "created_at": 1, "files": 1, "file_ids": 1, "download_links": 1, "design_id": 1}),
        lambda: db.files.aggregate([{"$match": {"kind": {"$ne": "thumb"}, "client_id": {"$ne": None}}}, {"$group": {"_id": "$client_id", "n": {"$sum": 1}}}]),
    )
    users = {u.id: u for u in users_list}
    if q:
        rx = re.compile(re.escape(q.strip()), re.I)
        clients = [c for c in clients if rx.search(c.get("company_name") or "") or rx.search(_client_card_user(users, c).get("full_name") or "")
                   or rx.search(_client_card_user(users, c).get("email") or "")]

    req_client = {r.id: r.get("client_id") for r in reqs}
    per: Dict[int, Dict[str, Any]] = {c.id: {"services": set(), "requests": 0, "designs": 0, "delivered": 0, "last": None,
                                             "cover_delivery": None, "cover_approved": None, "cover_any": None} for c in clients}
    for r in reqs:
        p = per.get(r.get("client_id"))
        if p is None:
            continue
        p["services"].add(r.get("service_id"))
        p["requests"] += 1
        p["last"] = _latest(p["last"], r.get("updated_at"), r.get("submitted_at"), r.get("created_at"))
    designs_by_id = {d.id: d for d in designs}
    for d in sorted(designs, key=lambda x: (_ts(x.get("created_at")), x.id)):
        p = per.get(req_client.get(d.get("request_id")))
        if p is None:
            continue
        p["designs"] += 1
        p["last"] = _latest(p["last"], d.get("created_at"))
        p["cover_any"] = d
        if d.get("status") == "approved":
            p["cover_approved"] = d
    for dl in sorted(deliveries, key=lambda x: (_ts(x.get("delivered_at") or x.get("created_at")), x.id)):
        p = per.get(req_client.get(dl.get("request_id")))
        if p is None:
            continue
        p["delivered"] += 1
        p["last"] = _latest(p["last"], dl.get("delivered_at"), dl.get("created_at"))
        p["cover_delivery"] = dl

    # One batched lookup for every file a cover could come from.
    cover_items: Dict[int, List[Dict[str, Any]]] = {}
    for cid, p in per.items():
        src = None
        if p["cover_delivery"] is not None:
            dl = p["cover_delivery"]
            src = _raw_items_for_design(designs_by_id[dl["design_id"]]) if dl.get("design_id") in designs_by_id else _raw_items_for_delivery(dl)
        elif p["cover_approved"] is not None:
            src = _raw_items_for_design(p["cover_approved"])
        elif p["cover_any"] is not None:
            src = _raw_items_for_design(p["cover_any"])
        if src:
            cover_items[cid] = src
    needed = {fid for items in cover_items.values() for fid in _file_ids_of(items)}
    files = db.files.by_ids(needed) if needed else {}
    counts = {row["_id"]: row["n"] for row in file_counts}

    cards = []
    for c in clients:
        p = per[c.id]
        u = _client_card_user(users, c)
        cards.append(
            {
                "client_id": c.id,
                "company_name": c.get("company_name") or "Client",
                "client_name": u.get("full_name") or "",
                "email": u.get("email") or "",
                "industry": c.get("industry"),
                "folder": client_folder(db, c.id, c),
                "services": len([s for s in p["services"] if s is not None]),
                "requests": p["requests"],
                "designs": p["designs"],
                "delivered": p["delivered"],
                "files": int(counts.get(c.id, 0)),
                "last_activity": _iso(_latest(p["last"], c.get("created_at"))),
                "cover_file_id": _cover_from_raw(cover_items.get(c.id, []), files) if c.id in cover_items else None,
            }
        )
    cards.sort(key=lambda x: x["last_activity"] or "", reverse=True)
    return cards


# ---------------------------------------------------------------------------
# one client's folder
# ---------------------------------------------------------------------------
def _folder(db: DB, client: Doc, *, delivered_only: bool) -> Dict[str, Any]:
    cuser, reqs = parallel(
        lambda: db.users.get(client.get("user_id")),
        lambda: db.requests.find({"client_id": client.id}, sort=[("submitted_at", -1), ("_id", -1)]),
    )
    req_ids = [r.id for r in reqs]
    services, designs, deliveries = parallel(
        lambda: db.services.by_ids({r.get("service_id") for r in reqs}),
        lambda: [] if delivered_only or not req_ids else db.designs.find({"request_id": {"$in": req_ids}}, sort=[("version", -1)]),
        lambda: db.deliveries.find({"request_id": {"$in": req_ids}}, sort=[("version", -1), ("_id", -1)]) if req_ids else [],
    )
    raw_design_items = {d.id: _raw_items_for_design(d) for d in designs}
    req_by_id = {r.id: r for r in reqs}

    def _delivered(dl: Doc) -> List[Dict[str, Any]]:  # only the designs the client actually receives
        r = req_by_id.get(dl.get("request_id"))
        svc = services.get(r.get("service_id")) if r else None
        return deliverables.for_delivery(dl, (svc or {}).get("slug") or "", (r or {}).get("brief"))

    raw_delivery_items = {dl.id: _delivered(dl) for dl in deliveries}
    needed = {fid for items in list(raw_design_items.values()) + list(raw_delivery_items.values()) for fid in _file_ids_of(items)}
    files = db.files.by_ids(needed) if needed else {}

    designs_by_req: Dict[int, List[Dict[str, Any]]] = {}
    for d in designs:
        items = _enrich(raw_design_items[d.id], files)
        designs_by_req.setdefault(d.get("request_id"), []).append(
            {
                "id": d.id, "version": int(d.get("version") or 1), "title": d.get("title"), "status": d.get("status") or "draft",
                "qa_score": d.get("qa_score"), "generated_by": d.get("generated_by"), "created_at": _iso(d.get("created_at")),
                "package_file_id": d.get("package_file_id"), "cover_file_id": _cover_of(items), "files": items,
            }
        )
    deliveries_by_req: Dict[int, List[Dict[str, Any]]] = {}
    for dl in deliveries:
        items = _enrich(raw_delivery_items[dl.id], files)
        deliveries_by_req.setdefault(dl.get("request_id"), []).append(
            {
                "id": dl.id, "version": int(dl.get("version") or 1), "delivered_at": _iso(dl.get("delivered_at") or dl.get("created_at")),
                "message": dl.get("message"), "delivered_by": dl.get("delivered_by"), "design_id": dl.get("design_id"),
                "package_file_id": dl.get("package_file_id"), "cover_file_id": _cover_of(items), "files": items,
            }
        )

    groups: Dict[Any, Dict[str, Any]] = {}
    for r in reqs:
        dels = deliveries_by_req.get(r.id, [])
        if delivered_only and not dels:
            continue
        svc = services.get(r.get("service_id"))
        key = r.get("service_id")
        if key not in groups:
            groups[key] = {
                "service_id": key, "slug": svc.get("slug") if svc else "other", "name": svc.get("name") if svc else "Other",
                "icon": svc.get("icon") if svc else "custom", "category": svc.get("category") if svc else "",
                "sort_order": int(svc.get("sort_order") or 0) if svc else 9999, "requests": [],
            }
        groups[key]["requests"].append(
            {
                "id": r.id, "title": r.get("title"), "status": r.get("status"), "pipeline_stage": r.get("pipeline_stage"),
                "submitted_at": _iso(r.get("submitted_at") or r.get("created_at")), "completed_at": _iso(r.get("completed_at")),
                "revision_count": int(r.get("revision_count") or 0),
                "designs": [] if delivered_only else designs_by_req.get(r.id, []),
                "deliveries": dels,
            }
        )
    service_list = sorted(groups.values(), key=lambda g: (g["sort_order"], g["name"]))
    for g in service_list:
        g.pop("sort_order", None)
        g["request_count"] = len(g["requests"])
    total_delivered = sum(len(r["deliveries"]) for g in service_list for r in g["requests"])
    total_designs = sum(len(r["designs"]) for g in service_list for r in g["requests"])
    return {
        "client": {
            "id": client.id, "company_name": client.get("company_name") or "Client", "client_name": (cuser or {}).get("full_name") or "",
            "email": (cuser or {}).get("email") or "", "industry": client.get("industry"), "website": client.get("website"),
            "folder": client_folder(db, client.id, client), "created_at": _iso(client.get("created_at")),
        },
        "totals": {"services": len(service_list), "requests": sum(g["request_count"] for g in service_list), "designs": total_designs, "delivered": total_delivered},
        "services": service_list,
    }


@router.get("/clients/{client_id}")
def client_folder_detail(client_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    client = db.clients.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _folder(db, client, delivered_only=False)


@router.get("/me")
def my_designs(db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    client = user.get("client")
    if not client:
        raise HTTPException(status_code=403, detail="Client account required")
    return _folder(db, client, delivered_only=True)


# ---------------------------------------------------------------------------
# ZIP downloads
# ---------------------------------------------------------------------------
def _zip_response(data: bytes, filename: str) -> Response:
    ascii_name = filename.encode("ascii", "ignore").decode() or "designs.zip"
    from urllib.parse import quote

    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _build_zip(db: DB, items: List[Dict[str, Any]], root: str) -> bytes:
    files = db.files.by_ids({int(i["file_id"]) for i in items if i.get("file_id")})
    buf = io.BytesIO()
    used: set = set()
    written = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for it in items:
            f = files.get(int(it.get("file_id") or 0))
            if not f or f.get("kind") == "thumb":
                continue
            name = safe_name(it.get("name") or f.get("original_name") or f"file-{f.id}", limit=120)
            if Path(name).suffix.lower() == ".zip":  # a package inside a package adds nothing
                continue
            stem, ext = Path(name).stem, Path(name).suffix
            arc, n = name, 2
            while arc.lower() in used:
                arc = f"{stem} ({n}){ext}"
                n += 1
            try:
                data = read_file_bytes(f)
            except Exception:
                continue
            used.add(arc.lower())
            zf.writestr(f"{root}/{arc}", data)
            written += 1
        if not written:
            zf.writestr(f"{root}/README.txt", "No files are attached to this version yet.\n")
    return buf.getvalue()


def _package_or_build(db: DB, package_file_id: Optional[int], items: List[Dict[str, Any]], root: str) -> bytes:
    if package_file_id:
        pkg = db.files.get(package_file_id)
        if pkg:
            try:
                return read_file_bytes(pkg)
            except Exception:
                pass
    return _build_zip(db, items, root)


def _names(db: DB, req: Doc) -> tuple[str, str]:
    client, service = parallel(lambda: db.clients.get(req.get("client_id")), lambda: db.services.get(req.get("service_id")))
    return (client.get("company_name") if client else "Client", service.get("name") if service else "Design")


@router.get("/deliveries/{delivery_id}/download")
def download_delivery(delivery_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    dl = db.deliveries.get(delivery_id)
    req = db.requests.get(dl.get("request_id")) if dl else None
    if not dl or not req:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if not user.get("is_admin"):
        client = user.get("client")
        if not client or req.get("client_id") != client.id:
            raise HTTPException(status_code=404, detail="Delivery not found")
    company, service = _names(db, req)
    filename = safe_name(f"{company} - {service} - delivery {int(dl.get('version') or 1)}", limit=150)
    if dl.get("selected") or user.get("is_admin"):  # selected: the package already holds exactly the delivered designs
        data = _package_or_build(db, dl.get("package_file_id"), _raw_items_for_delivery(dl), filename)
    else:
        svc = db.services.get(req.get("service_id")) or {}
        data = _build_zip(db, deliverables.for_delivery(dl, svc.get("slug") or "", req.get("brief")), filename)
    return _zip_response(data, f"{filename}.zip")


@router.get("/designs/{design_id}/download")
def download_design(design_id: int, db: DB = Depends(get_db), user: Doc = Depends(require_admin)):
    d = db.designs.get(design_id)
    req = db.requests.get(d.get("request_id")) if d else None
    if not d or not req:
        raise HTTPException(status_code=404, detail="Design not found")
    company, service = _names(db, req)
    filename = safe_name(f"{company} - {service} - draft v{int(d.get('version') or 1)}", limit=150)
    data = _package_or_build(db, d.get("package_file_id"), _raw_items_for_design(d), filename)
    return _zip_response(data, f"{filename}.zip")
