from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    # Local/dev accounts: allow 7+ characters (e.g. "lior123", "iris 123").
    password: str = Field(min_length=7, max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    csrf_token: str  # For X-CSRF-Token header on mutating requests (cross-origin safe)


