from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.audit import audit
from app.core.deps import get_current_user
from app.db.mongo import DB, Doc, get_db
from app.schemas.clients import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


def _out(db: DB, p: Doc, client: Optional[Doc] = None) -> ProjectOut:
    client = client or db.clients.get(p.get("client_id"))
    return ProjectOut(
        id=p.id, client_id=p.get("client_id"), company_name=client.get("company_name", "") if client else "",
        name=p.get("name", ""), description=p.get("description"), status=p.get("status", "active"), drive_folder_id=p.get("drive_folder_id"),
        request_count=db.requests.count({"project_id": p.id}), created_at=p.get("created_at"),
    )


def _get(db: DB, project_id: int, user: Doc) -> Doc:
    p = db.projects.get(project_id)
    if not p or (not user.get("is_admin") and (not user.get("client") or p.get("client_id") != user["client"].id)):
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.get("", response_model=List[ProjectOut])
def list_projects(client_id: Optional[int] = None, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    flt: Dict = {}
    if not user.get("is_admin"):
        flt["client_id"] = user["client"].id if user.get("client") else -1
    elif client_id:
        flt["client_id"] = client_id
    rows = db.projects.find(flt, sort=[("created_at", -1)])
    clients = db.clients.by_ids({p.get("client_id") for p in rows})
    return [_out(db, p, clients.get(p.get("client_id"))) for p in rows]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    client_id = body.client_id if user.get("is_admin") else (user["client"].id if user.get("client") else None)
    if not client_id or not db.clients.get(client_id):
        raise HTTPException(status_code=400, detail="client_id required")
    p = db.projects.insert({"client_id": client_id, "name": body.name, "description": body.description, "status": "active", "drive_folder_id": None})
    audit(db, action="project.create", entity="project", entity_id=p.id, user=user, after={"name": body.name})
    return _out(db, p)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    return _out(db, _get(db, project_id, user))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, body: ProjectUpdate, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    p = _get(db, project_id, user)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if data:
        p = db.projects.update(p.id, data)
    audit(db, action="project.update", entity="project", entity_id=p.id, user=user, after=data)
    return _out(db, p)


@router.delete("/{project_id}")
def delete_project(project_id: int, db: DB = Depends(get_db), user: Doc = Depends(get_current_user)):
    p = _get(db, project_id, user)
    audit(db, action="project.delete", entity="project", entity_id=p.id, user=user)
    db.requests.update_many({"project_id": p.id}, {"project_id": None})
    db.projects.delete(p.id)
    return {"ok": True}
