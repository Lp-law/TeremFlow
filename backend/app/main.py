from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Request

from app.api.router import api_router
from app.core.config import settings
from app.core.security import constant_time_equals
from app.db.init_db import ensure_seeded
from app.db.session import Base, engine


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Backup-Id", "X-Backup-Sha256", "Content-Disposition"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.middleware("http")
    async def _csrf_middleware(request: Request, call_next):
        """
        Production CSRF protection for cookie-auth endpoints.
        - Only enforced in production.
        - Only for unsafe methods.
        - Only when the auth cookie is present (so cron/unauthenticated calls aren't impacted).
        """
        if settings.environment == "production":
            if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
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


