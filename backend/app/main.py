"""Designflow API + frontend host."""
from __future__ import annotations

import asyncio
import logging
import mimetypes
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.pages import router as pages_router
from app.api.v1.router import api_router, ws_router
from app.core.config import FRONTEND_DIR, settings
from app.core.events import redis_subscriber, set_event_loop
from app.core.rate_limit import limiter

logging.basicConfig(
    level=logging.INFO if not settings.is_production else logging.WARNING,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("designflow")

# Windows' registry often lacks these, so StaticFiles would send them as octet-stream.
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/svg+xml", ".svg")


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_event_loop(asyncio.get_running_loop())
    stop = threading.Event()
    sub_task = None
    if settings.redis_url:
        sub_task = asyncio.create_task(redis_subscriber(stop))
    else:
        log.info("REDIS_URL not set: real-time events dispatched in-process")

    from app.db.mongo import get_db

    db = get_db()
    if not db.ping():
        log.error("MongoDB is not reachable at %s", settings.mongo_uri.split("@")[-1])
    db.ensure_indexes()

    def _warm_up() -> None:
        """Open the pooled Atlas connections and run the Ollama check once, so the first page loads are fast."""
        try:
            from app.db.mongo import parallel

            parallel(*[db.ping for _ in range(8)])
            if settings.app_env != "test":
                from app.agents import llm as _llm

                _llm.provider()
        except Exception as exc:  # pragma: no cover
            log.debug("warm-up skipped: %s", exc)

    threading.Thread(target=_warm_up, daemon=True, name="warmup").start()
    if not settings.redis_url and settings.app_env != "test":
        # In-process mode nothing can still be running when the API boots: clear agents a previous
        # process left in "running" (e.g. the server was restarted mid-pipeline) so the Control Center is truthful.
        try:
            n = db.agents.update_many({"status": "running"}, {"status": "idle", "current_activity": "Idle (server restarted)"})
            if n:
                log.info("Reset %d agent(s) left in 'running' by the previous process", n)
        except Exception as exc:  # pragma: no cover
            log.warning("Agent status reset skipped: %s", exc)
    if settings.app_env != "test":
        # Keep the catalogue, agents and the primary admin in sync with .env on every start.
        from app.db.seed import run_seed

        try:
            run_seed()
        except Exception as exc:  # pragma: no cover
            log.error("Seed failed: %s", exc)

    scheduler = None
    if settings.agents_enabled and not settings.redis_url and settings.app_env != "test":
        try:
            from app.agents.scheduler import start_scheduler

            scheduler = start_scheduler()
        except Exception as exc:  # pragma: no cover
            log.warning("Scheduler not started: %s", exc)
    yield
    stop.set()
    if sub_task:
        sub_task.cancel()
    if scheduler:
        try:
            scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover
            pass


app = FastAPI(
    title=f"{settings.app_name} API",
    version="2.0.0",
    description="Pay-per-request design studio: public site, client portal, admin dashboard and AI agent control center. MongoDB backend.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    ctype = response.headers.get("content-type", "")
    if request.method == "GET" and any(t in ctype for t in ("text/html", "text/css", "javascript")):
        # Without this, browsers reuse stale pages/scripts after a frontend update.
        # no-cache still allows the cached copy; it is just revalidated via ETag (304).
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["system"])
def health():
    from app.db.mongo import get_db

    return {"status": "ok", "app": settings.app_name, "env": settings.app_env, "database": "ok" if get_db().ping() else "unreachable"}


app.include_router(api_router)
app.include_router(ws_router)

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
app.include_router(pages_router)
