from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File as FileParam, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from app.core.audit import audit
from app.core.deps import get_current_user, require_admin
from app.db.mongo import DB, Doc, get_db
from app.models.enums import NotificationType
from app.schemas.misc import BrandAssetIn, BrandAssetOut
from app.services import deliverables
from app.services.file_service import file_to_dict, read_file_bytes, store_upload
from app.services.folders import brand_assets_folder, client_folder, request_folder
from app.services.notification_service import notify, notify_admins

router = APIRouter(prefix="/files", tags=["files"])
KINDS = ("upload", "design", "delivery", "brand_asset", "chat", "revision")


def _can_access(user: Doc, f: Doc) -> bool:
    if user.get("is_admin"):
        return True
    client = user.get("client")
    if client and f.get("client_id") == client.id:
        return True
    return f.get("owner_user_id") == user.id


KIND_FOLDERS = {"upload": "Uploads", "design": "Designs", "delivery": "Deliveries", "chat": "Chat", "revision": "Revisions"}
REQUEST_SUBFOLDERS = {"design": "Drafts", "delivery": "Final"}  # everything else a request receives goes to "Uploads"


def _upload_folder(db: DB, *, kind: str, client_id: Optional[int], req: Optional[Doc]) -> str:
    """Readable per-client folders (see app/services/folders.py)."""
    if kind == "brand_asset":
        return brand_assets_folder(db, client_id)
    if req is not None:
        return request_folder(db, req, REQUEST_SUBFOLDERS.get(kind, "Uploads"))
    return f"{client_folder(db, client_id)}/{KIND_FOLDERS.get(kind, 'Uploads')}"


STUDIO_KINDS = ("design", "delivery", "thumb")  # made by the studio; a client only sees what was delivered to them


def _client_may_see(db: DB, user: Doc, f: Doc) -> bool:
    if user.get("is_admin") or f.get("kind") not in STUDIO_KINDS:
        return True
    if f.get("kind") == "delivery" and not (f.get("meta") or {}).get("role"):
        return True  # a file the designer uploaded by hand for this client
    client = user.get("client")
    return bool(client) and f.id in deliverables.client_visible_file_ids(db, client.id)


def _get_file(db: DB, file_id: int, user: Doc) -> Doc:
    f = db.files.get(file_id)
    if not f or not _can_access(user, f) or not _client_may_see(db, user, f):
        raise HTTPException(status_code=404, detail="File not found")
    return f


@router.post("/upload", status_code=201)
async def upload(
    http_request: Request,
    file: UploadFile = FileParam(...),
    request_id: Optional[int] = Form(None),
    kind: str = Form("upload"),
    client_id: Optional[int] = Form(None),
    parent_file_id: Optional[int] = Form(None),
    db: DB = Depends(get_db),
    user: Doc = Depends(get_current_user),
):
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail="Invalid kind")
    cid = client_id if user.get("is_admin") else (user["client"].id if user.get("client") else None)
    req = None
    if request_id:
        req = db.requests.get(request_id)
        if not req or (not user.get("is_admin") and req.get("client_id") != cid):
            raise HTTPException(status_code=404, detail="Request not found")
        cid = req.get("client_id")
    folder = _upload_folder(db, kind=kind, client_id=cid, req=req)
    row = await store_upload(db, file, folder=folder, kind=kind, owner_user_id=user.id, client_id=cid, request_id=request_id, parent_file_id=parent_file_id)
    audit(db, action="file.upload", entity="file", entity_id=row.id, user=user,
          after={"name": row.get("original_name"), "size": row.get("size_bytes"), "request_id": request_id}, request=http_request)
    if req:
        client = db.clients.get(req.get("client_id"))
        if not user.get("is_admin"):
            notify_admins(db, type=NotificationType.FILE_UPLOAD.value, title=f"Files uploaded: {req.get('title')}",
                          body=f"{client.get('company_name') if client else 'Client'} uploaded {row.get('original_name')}.",
                          link=f"/admin#/requests/{req.id}", service_id=req.get("service_id"), request_id=req.id)
        elif client and client.get("user_id") and kind == "delivery":
            notify(db, [client["user_id"]], type=NotificationType.FILE_UPLOAD.value, title=f"New file: {req.get('title')}",
                   body=row.get("original_name"), link=f"/portal#/requests/{req.id}", request_id=req.id)
    return file_to_dict(row)


@router.get("")
def list_files(
    request_id: Optional[int] = None,
    client_id: Optional[int] = None,
    kind: Optional[str] = None,
    limit: int = Query(200, le=1000),
    db: DB = Depends(get_db),
    user: Doc = Depends(get_current_user),
):
    flt: Dict = {}
    if not user.get("is_admin"):
        flt["client_id"] = user["client"].id if user.get("client") else -1
    elif client_id:
        flt["client_id"] = client_id
    if request_id:
        flt["request_id"] = request_id
    # Thumbnails are internal previews of design files: only listed when asked for explicitly.
    flt["kind"] = kind if kind else {"$ne": "thumb"}
    rows = db.files.find(flt, sort=[("created_at", -1)], limit=limit)
    if not user.get("is_admin"):
        rows = [f for f in rows if _client_may_see(db, user, f)]
    return [file_to_dict(f) for f in rows]


@router.get("/{file_id}")
def file_meta(file_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    return file_to_dict(_get_file(db, file_id, user))


@router.get("/{file_id}/versions")
def versions(file_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    f = _get_file(db, file_id, user)
    chain: Dict[int, Doc] = {f.id: f}
    cur = f
    while cur.get("parent_file_id"):
        cur = db.files.get(cur["parent_file_id"])
        if not cur or cur.id in chain:
            break
        chain[cur.id] = cur
    # walk forward through children (and their children)
    frontier = [f.id]
    while frontier:
        children = db.files.find({"parent_file_id": {"$in": frontier}})
        frontier = [c.id for c in children if c.id not in chain]
        for c in children:
            chain[c.id] = c
    return [file_to_dict(x) for x in sorted(chain.values(), key=lambda x: (int(x.get("version", 1)), x.id))]


@router.get("/{file_id}/download")
def download(file_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    f = _get_file(db, file_id, user)
    try:
        data = read_file_bytes(f)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="File content is no longer available")
    safe_name = str(f.get("original_name", "file")).replace('"', "")
    mime = f.get("mime_type") or "application/octet-stream"
    disposition = "inline" if mime.startswith("image/") or mime == "application/pdf" else "attachment"
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"', "X-Content-Type-Options": "nosniff"})


@router.delete("/{file_id}")
def delete_file(file_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    f = _get_file(db, file_id, user)
    if not user.get("is_admin") and f.get("kind") in ("delivery", "design"):
        raise HTTPException(status_code=403, detail="Cannot delete delivered files")
    audit(db, action="file.delete", entity="file", entity_id=f.id, user=user, before={"name": f.get("original_name")})
    db.assets.update_many({"file_id": f.id}, {"file_id": None})
    db.designs.update_many({"file_id": f.id}, {"file_id": None})
    db.files.delete(f.id)
    return {"ok": True}


# ---- Brand assets --------------------------------------------------------
assets_router = APIRouter(prefix="/brand-assets", tags=["files"])


def _asset_out(a: Doc) -> BrandAssetOut:
    out = BrandAssetOut.model_validate({**a.public(), "meta": a.get("meta") or {}})
    out.download_url = f"/api/v1/files/{a['file_id']}/download" if a.get("file_id") else None
    return out


@assets_router.get("", response_model=List[BrandAssetOut])
def list_assets(client_id: Optional[int] = None, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    cid = client_id if user.get("is_admin") else (user["client"].id if user.get("client") else -1)
    flt: Dict = {"client_id": cid} if cid else {}
    return [_asset_out(a) for a in db.assets.find(flt, sort=[("created_at", -1)])]


@assets_router.post("", response_model=BrandAssetOut, status_code=201)
def create_asset(body: BrandAssetIn, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    cid = body.client_id if user.get("is_admin") else (user["client"].id if user.get("client") else None)
    client = db.clients.get(cid) if cid else None
    if not client:
        raise HTTPException(status_code=400, detail="client_id required")
    if body.file_id:
        f = db.files.get(body.file_id)
        if not f or not _can_access(user, f):
            raise HTTPException(status_code=404, detail="File not found")
        db.files.update(f.id, {"kind": "brand_asset", "client_id": cid})
    prev = db.assets.find_one({"client_id": cid, "name": body.name, "type": body.type}, sort=[("version", -1)])
    a = db.assets.insert({"client_id": cid, "type": body.type, "name": body.name, "file_id": body.file_id, "value": body.value,
                          "version": (int(prev.get("version", 1)) + 1) if prev else 1, "meta": {}})
    audit(db, action="brand_asset.create", entity="brand_asset", entity_id=a.id, user=user, after={"name": body.name, "type": body.type})
    if client.get("onboarding_stage") in ("new", "assets_requested"):
        db.clients.update(client.id, {"onboarding_stage": "assets_received"})
    if not user.get("is_admin"):
        notify_admins(db, type=NotificationType.FILE_UPLOAD.value, title=f"Brand asset added: {client.get('company_name')}",
                      body=f"{body.type}: {body.name}", link=f"/admin#/clients/{cid}")
    return _asset_out(a)


@assets_router.delete("/{asset_id}")
def delete_asset(asset_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    a = db.assets.get(asset_id)
    if not a or (not user.get("is_admin") and (not user.get("client") or a.get("client_id") != user["client"].id)):
        raise HTTPException(status_code=404, detail="Asset not found")
    db.assets.delete(a.id)
    return {"ok": True}
