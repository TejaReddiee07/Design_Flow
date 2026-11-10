"""Aggregates every v1 router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    agents,
    analytics,
    auth,
    billing,
    chat,
    clients,
    contact,
    files,
    leads,
    library,
    notifications,
    projects,
    requests,
    services,
    support,
    ws,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(projects.router)
api_router.include_router(services.router)
api_router.include_router(requests.router)
api_router.include_router(files.router)
api_router.include_router(files.assets_router)
api_router.include_router(library.router)
api_router.include_router(notifications.router)
api_router.include_router(chat.router)
api_router.include_router(support.router)
api_router.include_router(contact.router)
api_router.include_router(billing.router)
api_router.include_router(leads.router)
api_router.include_router(leads.outreach_router)
api_router.include_router(agents.router)
api_router.include_router(analytics.router)
api_router.include_router(admin.router)

ws_router = ws.router
