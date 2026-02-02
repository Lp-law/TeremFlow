from __future__ import annotations

import json
from typing import Annotated

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings import NoDecode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TeremFlow"
    environment: str = Field(default="development")  # development | production

    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/teremflow")

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_postgres_url(cls, v: str | None) -> str | None:
        # Render (and others) give postgresql://... which makes SQLAlchemy use psycopg2.
        # We install psycopg (v3), so force the psycopg driver when no driver is specified.
        if v and v.startswith("postgresql://") and "+" not in v.split("?")[0]:
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    # Render provides CORS_ORIGINS as a string (single URL or comma-separated). Support also JSON list.
    # NoDecode prevents pydantic-settings from attempting JSON parsing before validators run.
    # Production fallback: if empty, use frontend URL so CORS never blocks.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        validation_alias="CORS_ORIGINS",
    )

    jwt_secret: str = Field(default="dev-secret-change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expires_minutes: int = Field(default=60 * 24 * 7)  # 7 days
    jwt_cookie_name: str = Field(default="teremflow_session")

    # Render Cron can hit /tasks/daily with this token.
    tasks_daily_secret: str = Field(default="dev-tasks-secret-change-me")

    # Alerts
    deductible_near_pct: float = Field(default=0.10)
    deductible_near_abs_ils: int = Field(default=20000)

    # Email (MVP: if not set, we log instead of sending)
    smtp_host: str | None = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_username: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    smtp_from: str | None = Field(default=None)
    alert_email_recipients: list[str] = Field(default_factory=list)

    # Optional absolute external URL (for email links).
    public_app_url: AnyUrl | None = Field(default=None)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):  # noqa: ANN001
        """
        Accept: string, comma-separated, or JSON list.
        """
        if v is None:
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                except Exception:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            return [p.strip() for p in s.split(",") if p.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(x).strip() for x in v if str(x).strip()]
        return v

    @field_validator("cors_origins", mode="after")
    @classmethod
    def _ensure_cors_origins(cls, v: list[str] | None, info) -> list[str]:  # noqa: ANN001
        """Production fallback: empty CORS blocks all; use frontend URL."""
        if v is None:
            v = []
        result = [x for x in v if x] if isinstance(v, list) else []
        if not result and info.data.get("environment") == "production":
            result = ["https://teremflow-frontend.onrender.com"]
        if not result:
            result = ["http://localhost:5173"]
        return result



settings = Settings()


