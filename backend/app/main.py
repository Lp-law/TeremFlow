from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.security import constant_time_equals
from app.db.init_db import ensure_seeded
from app.db.session import Base, engine

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    origins = settings.cors_origins or ["https://teremflow-frontend.onrender.com"]
    if not origins:
        origins = ["https://teremflow-frontend.onrender.com"]
    logger.info("CORS allow_origins=%s", origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Backup-Id", "X-Backup-Sha256", "Content-Disposition"],
    )

    def _cors_headers_for_request(request: Request) -> dict[str, str]:
        """Echo CORS headers so error responses (e.g. 500) are not blocked by the browser."""
        origin = request.headers.get("origin", "").strip()
        if origin and origin in origins:
            allow_origin = origin
        else:
            allow_origin = origins[0] if origins else "*"
        return {
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }

    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception):
        """Return 500 with CORS headers so the frontend sees the error instead of 'blocked by CORS'."""
        if isinstance(exc, HTTPException):
            # Let FastAPI handle 4xx with its default handler (which may not add CORS on error path)
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=_cors_headers_for_request(request),
            )
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers=_cors_headers_for_request(request),
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    _CSRF_EXEMPT_PATHS = frozenset({"/auth/login", "/auth/logout", "/import/excel", "/admin/wipe-case-data"})

    @app.middleware("http")
    async def _csrf_middleware(request: Request, call_next):
        """
        Production CSRF protection for cookie-auth endpoints.
        - Only enforced in production.
        - Only for unsafe methods (OPTIONS is preflight, skip).
        - Skip for exempt paths: /auth/login, /auth/logout, /import/excel.
        - Only when the auth cookie is present.
        """
        if settings.environment == "production":
            if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                path = request.url.path.rstrip("/") or "/"
                if path in _CSRF_EXEMPT_PATHS:
                    pass  # exempt: login, logout, multipart import
                else:
                    has_session = bool(request.cookies.get(settings.jwt_cookie_name))
                    if has_session:
                        csrf_cookie = request.cookies.get("teremflow_csrf")
                        csrf_header = request.headers.get("X-CSRF-Token")
                        if not constant_time_equals(csrf_cookie, csrf_header):
                            raise HTTPException(status_code=403, detail="CSRF token missing/invalid")
        return await call_next(request)

    @app.on_event("startup")
    def _startup() -> None:
        """
        Local-dev helper: allow running without Postgres by using SQLite.
        - Creates tables (without Alembic) when DATABASE_URL points at sqlite.
        - Seeds default users so login works immediately.
        """
        db_url = settings.database_url or ""
        if settings.environment == "development" and db_url.startswith("sqlite"):
            Base.metadata.create_all(bind=engine)
            from app.db.session import SessionLocal

            db = SessionLocal()
            try:
                ensure_seeded(db)
            finally:
                db.close()

    app.include_router(api_router)
    return app


app = create_app()


