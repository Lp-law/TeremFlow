from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.services.users import create_user


def upsert_user(db: Session, *, username: str, password: str, role: UserRole) -> None:
    """
    Seed helper:
    - If user exists, update password + role (so local dev can reset credentials without wiping DB).
    - If user does not exist, create it.
    """
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.password_hash = hash_password(password)
        user.role = role
        user.is_active = True
        db.commit()
        return
    create_user(db, username=username, password=password, role=role)


def seed_initial_users(db: Session) -> None:
    """
    MVP seed:
    - lidor (admin)
    - iris (user)
    - lior (admin)
    """

    upsert_user(db, username="lidor", password="lidor123", role=UserRole.ADMIN)
    upsert_user(db, username="iris", password="iris 123", role=UserRole.USER)
    upsert_user(db, username="lior", password="lior123", role=UserRole.ADMIN)


def ensure_seeded(db: Session) -> None:
    exists = db.query(User).first()
    if exists:
        return
    seed_initial_users(db)


if __name__ == "__main__":
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        ensure_seeded(db)
        print("Seeded initial users.")
    finally:
        db.close()


