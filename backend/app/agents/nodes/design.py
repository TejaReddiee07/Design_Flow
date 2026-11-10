"""Design Agent: creative direction from the model, then the design engine renders the finished deliverables.

The engine works from what the client actually asked for: the request form (brief), their uploaded logo and
brand colours, any photos attached to the request, the Strategy and Content agents' output, and feedback from
reworks or revisions. Every file is stored in the client's own folder:
    clients/<Company> #<id>/<Service>/Request <id> - <title>/Drafts/v<version>/...
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any, Dict, List, Optional

from app.agents import control, live
from app.agents.llm import complete
from app.agents.nodes.common import as_list, pretty, request_context
from app.core.config import settings
from app.db.mongo import DB, Doc, get_db
from app.services.file_service import read_file_bytes, store_bytes
from app.services.folders import request_folder, safe_name
from app.services.notification_service import broadcast_request_update

log = logging.getLogger("agents.design")
KEY = "design"
SYSTEM = """You are the Design Agent at a premium design studio. Decide the creative direction a designer will execute
immediately for this exact service. Follow the client's description of their business and wishes first, then the
strategy. Respect any brand colours they gave.
Return JSON with keys: concepts (list of 2 objects with title, description, layout, palette (hex list), typography,
imagery), recommended (index of the best concept), rationale (1-2 sentences explaining why it fits this client)."""

IMAGE_MIMES = ("image/png", "image/jpeg", "image/webp", "image/svg+xml")


def _data_uri(row: Doc, max_side: int = 1600) -> Optional[str]:
    try:
        data = read_file_bytes(row)
    except Exception:  # file missing on disk
        return None
    mime = row.get("mime_type") or ""
    if mime == "image/svg+xml":
        return "data:image/svg+xml;base64," + base64.b64encode(data).decode()
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data))
        im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        if im.mode in ("RGBA", "LA", "P"):
            im.convert("RGBA").save(buf, "PNG")
            return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        im.convert("RGB").save(buf, "JPEG", quality=88)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _engine_context(db: DB, req: Doc, state: Dict[str, Any], version: int, concept: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    service = db.services.get(req.get("service_id")) or Doc({})
    client = db.clients.get(req.get("client_id")) or Doc({})
    user = db.users.get(client.get("user_id")) if client.get("user_id") else None
    assets = db.assets.find({"client_id": client.get("id")}, sort=[("_id", -1)]) if client.get("id") else []
    logo_href = None
    for a in assets:
        if a.get("type") == "logo" and a.get("file_id"):
            f = db.files.get(a["file_id"])
            if f and (f.get("mime_type") or "") in IMAGE_MIMES:
                logo_href = _data_uri(f, 1200)
                if logo_href:
                    break
    asset_colors = [a.get("value") for a in assets if a.get("type") == "color" and a.get("value")]
    photos: List[str] = []
    for f in db.files.find({"request_id": req.id, "kind": {"$in": ["upload", "revision"]}}, sort=[("_id", 1)], limit=12):
        if (f.get("mime_type") or "") in IMAGE_MIMES[:3]:
            uri = _data_uri(f)
            if uri:
                photos.append(uri)
        if len(photos) >= 4:
            break
    from app.agents.tools import ai_images

    ai = ai_images.generate if ai_images.available() else None
    slug = service.get("slug", "")
    # one AI hero image for layout-led services when the client sent no photos (logos are generated separately)
    if ai and not photos and slug not in ("logo-design", "business-card-design", "infographic-design", "youtube-thumbnail-design"):
        brief = req.get("brief") or {}
        content = state.get("content") or {}
        subject = (brief.get("product") or brief.get("offer") or brief.get("event_or_offer") or brief.get("topic") or brief.get("what") or req.get("title") or "")
        hero_prompt = (
            f"High-end editorial image for {client.get('company_name') or brief.get('brand_name') or 'the brand'}: {str(subject)[:200]}. "
            f"Context from the client: {str(brief.get('about_and_wishes') or '')[:350]} "
            f"Mood: {brief.get('style') or brief.get('mood') or 'premium, warm, modern'}. Use the brand colours {brief.get('brand_colors') or ''}. "
            "Photographic or illustrated, beautifully lit, one clear subject, calm background with space for a headline. "
            "No text, no letters, no logos, no watermark."
        )
        img = ai(hero_prompt)
        if img:
            photos.append("data:image/png;base64," + base64.b64encode(img).decode())
    feedback: List[str] = []
    rev = state.get("revision") or {}
    feedback += [str(x) for x in as_list(rev.get("change_items"))]
    if state.get("approval_message"):
        feedback.append(str(state["approval_message"]))
    qa = state.get("qa") or {}
    if qa and not qa.get("pass", True):
        feedback += [str(x) for x in as_list(qa.get("issues"))]
    return {
        "request_id": req.id, "version": version, "service_slug": service.get("slug", ""), "service_name": service.get("name", ""),
        "title": req.get("title", ""), "description": req.get("description") or "", "brief": req.get("brief") or {},
        "client": {"company_name": client.get("company_name"), "website": client.get("website"), "industry": client.get("industry"),
                   "brand_notes": client.get("brand_notes"), "contact_name": (user or {}).get("full_name"), "email": (user or {}).get("email")},
        "content": state.get("content") or {}, "strategy": state.get("strategy") or {},
        "concept": {**concept, "rationale": data.get("rationale") or concept.get("rationale")},
        "feedback": feedback, "logo_href": logo_href, "photos": photos, "asset_colors": asset_colors,
        "concepts": (data.get("concepts") or []) if isinstance(data.get("concepts"), list) else [], "ai_image": ai,
        "scale": 0.25 if settings.app_env == "test" else 1.0,
    }


def _store_output(db: DB, req: Doc, version: int, out: Any, service: Doc, client: Doc) -> Dict[str, Any]:
    """Save every engine file in the client's folder and return the design's file list."""
    from app.agents.tools.design_engine import export

    base = request_folder(db, req, f"Drafts/v{version}", service=service, client=client)
    items: List[Dict[str, Any]] = []
    board_id = None
    for f in out.files:
        folder = base + (f"/{f.group}" if f.group else "")
        row = store_bytes(db, data=f.data, filename=f.name, mime_type=f.mime, folder=folder, kind="design", owner_user_id=None,
                          client_id=req.get("client_id"), request_id=req.id,
                          meta={"role": f.role, "format": f.format, "width": f.width, "height": f.height, "design_version": version,
                                "service_slug": service.get("slug"), "label": f.label, "group": f.group})
        thumb_id = None
        if f.thumb:
            t = store_bytes(db, data=f.thumb, filename=f"{f.name.rsplit('.', 1)[0]} (preview).jpg", mime_type="image/jpeg", folder=base + "/_previews",
                            kind="thumb", owner_user_id=None, client_id=req.get("client_id"), request_id=req.id, meta={"thumb_of": row.id})
            thumb_id = t.id
        item = {"file_id": row.id, "name": f.name, "format": f.format, "role": f.role, "label": f.label, "width": f.width, "height": f.height,
                "page": f.page, "group": f.group, "thumb_file_id": thumb_id}
        items.append(item)
        if out.board is f:
            board_id = row.id
    # ZIP of this version, folders as in the engine output
    pkg_name = f"{safe_name(client.get('company_name') or 'Client')} - {safe_name(service.get('name') or 'Design')} - v{version}.zip"
    pkg = export.zip_files([((f.group + "/" if f.group else "") + f.name, f.data) for f in out.files])
    pkg_row = store_bytes(db, data=pkg, filename=pkg_name, mime_type="application/zip", folder=base, kind="design", owner_user_id=None,
                          client_id=req.get("client_id"), request_id=req.id, meta={"role": "package", "format": "zip", "design_version": version})
    items.append({"file_id": pkg_row.id, "name": pkg_name, "format": "zip", "role": "package", "label": "All files (ZIP)", "width": 0, "height": 0,
                  "page": None, "group": "", "thumb_file_id": None})
    return {"files": items, "board_id": board_id or (items[0]["file_id"] if items else None), "package_id": pkg_row.id}


def node(state: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    req = db.requests.update(state["request_id"], {"pipeline_stage": "design"})
    client = db.clients.get(req.client_id) or Doc({})
    service = db.services.get(req.service_id) or Doc({})
    attempt = int(state.get("qa_attempts") or 0)
    with control.running(db, KEY, f"Designing: {req.title}" + (f" (rework #{attempt})" if attempt else ""), run_id=state.get("run_id"), request_id=req.id) as ctx:
        prompt = request_context(db, req)
        if state.get("strategy"):
            prompt += f"\n\nStrategy:\n{pretty(state['strategy'], 1500)}"
        if state.get("content"):
            prompt += f"\n\nCopy options:\n{pretty(state['content'], 1500)}"
        if state.get("revision"):
            prompt += f"\n\nREVISION REQUESTED. Apply these changes:\n{pretty(state['revision'], 1500)}"
        if state.get("approval_message"):
            prompt += f"\n\nThe studio director sent the last draft back with this note. Apply it:\n{state['approval_message']}"
        if state.get("qa") and not state["qa"].get("pass", True):
            prompt += f"\n\nPrevious QA feedback to fix:\n{pretty(state['qa'], 1200)}"
        res = complete(KEY, SYSTEM, prompt)
        data = res.data or {"concepts": [], "recommended": 0}
        concepts = data.get("concepts") or []
        rec = data.get("recommended") or 0
        if not isinstance(rec, int) or rec >= len(concepts):
            rec = 0
        chosen = concepts[rec] if concepts else {"title": "Concept", "description": res.text[:300]}
        existing = db.designs.find({"request_id": req.id}, sort=[("version", -1)], limit=1)
        version = (int(existing[0].get("version", 0)) + 1) if existing else 1

        live.emit(db, req.id, "design_rendering", agent_key=KEY, run_id=state.get("run_id"), title=f"Rendering draft v{version}",
                  body="Building the finished files from the brief: layouts, typography, colour and exports.", data={"version": version})
        stored: Dict[str, Any] = {}
        engine_summary = ""
        engine_brand: Dict[str, Any] = {}
        try:
            from app.agents.tools.design_engine import generate

            out = generate(_engine_context(db, req, state, version, chosen, data))
            stored = _store_output(db, req, version, out, service, client)
            engine_summary, engine_brand = out.summary, out.brand
        except Exception as exc:  # never lose the pipeline because of a rendering problem
            log.exception("design engine failed for request %s", req.id)
            live.emit(db, req.id, "agent_note", agent_key=KEY, run_id=state.get("run_id"), level="warn", title="Engine fallback",
                      body=f"The design engine hit a problem ({exc}); a simple concept card was produced instead.")
            from app.agents.tools.images import generate_preview

            headline = (as_list((state.get("content") or {}).get("headlines")) or [req.title])[0]
            preview = generate_preview(db, concept=chosen, headline=headline, brand=client.get("company_name", ""), request_id=req.id,
                                       client_id=req.client_id, version=version)
            if preview:
                stored = {"files": [{"file_id": preview.id, "name": preview.get("original_name"), "format": "svg", "role": "board", "label": "Concept card",
                                     "width": 1200, "height": 630, "page": None, "group": "", "thumb_file_id": None}], "board_id": preview.id, "package_id": None}

        concept_md = "\n\n".join(
            f"### {c.get('title', 'Concept')}\n{c.get('description', '')}\n- Layout: {c.get('layout', '')}\n- Typography: {c.get('typography', '')}\n- Imagery: {c.get('imagery', '')}"
            for c in concepts
        ) or res.text
        if engine_summary:
            concept_md = f"**Delivered in this version:** {engine_summary}\n\n" + concept_md
        board_id = stored.get("board_id")
        design = db.designs.insert(
            {
                "request_id": req.id,
                "version": version,
                "title": chosen.get("title") or f"Design v{version}",
                "concept": concept_md + (f"\n\n**Recommended:** {chosen.get('title')}. {data.get('rationale', '')}" if concepts else ""),
                "concept_data": {**data, "engine": engine_brand},
                "file_id": board_id,
                "preview_url": f"/api/v1/files/{board_id}/download" if board_id else None,
                "files": stored.get("files", []),
                "package_file_id": stored.get("package_id"),
                "service_slug": service.get("slug"),
                "generated_by": "agent",
                "status": "draft",
                "qa_score": None,
                "qa_notes": None,
            }
        )
        ctx.update(tokens_in=res.tokens_in, tokens_out=res.tokens_out, output=pretty({"summary": engine_summary, "brand": engine_brand, **data}), model=res.model)
        broadcast_request_update(db, req, {"event": "design", "design_id": design.id})
        gallery = [f for f in stored.get("files", []) if f.get("format") in ("png", "pdf", "zip", "md")][:60]
        live.emit(
            db, req.id, "design_rendered", agent_key=KEY, run_id=state.get("run_id"),
            title=f"Draft v{version} ready: {len([f for f in gallery if f['format'] == 'png'])} images" + (", PDF" if any(f["format"] == "pdf" for f in gallery) else ""),
            body=engine_summary or str(chosen.get("description") or ""),
            data={
                "design_id": design.id, "version": version, "title": design.get("title"), "file_id": board_id, "preview_url": design.get("preview_url"),
                "files": gallery, "package_file_id": stored.get("package_id"), "brand": engine_brand,
                "palette": list((engine_brand.get("palette") or {}).values()) or as_list(chosen.get("palette")), "layout": chosen.get("layout"),
                "typography": ", ".join((engine_brand.get("fonts") or {}).values()) or chosen.get("typography"), "imagery": chosen.get("imagery"),
                "concepts": concepts, "recommended": rec, "rationale": data.get("rationale"), "attempt": attempt,
            },
        )
    return {"design": {**data, "engine_summary": engine_summary}, "design_id": design.id, "design_version": version, "stage": "design"}
