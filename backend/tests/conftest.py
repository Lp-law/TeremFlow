"""Pytest fixtures for TeremFlow tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base

# Ensure all models are loaded for create_all
import app.models  # noqa: F401


@pytest.fixture(scope="function")
def db():
    """Create an in-memory SQLite DB with all tables for tests."""
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
