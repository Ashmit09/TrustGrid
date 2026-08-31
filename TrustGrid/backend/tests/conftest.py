"""
conftest.py — shared fixtures for the entire test suite.

API-level tests (TestClient) need the FastAPI app to share the same
SQLite database as the test's session.

We use a file-based temp SQLite database (rather than :memory:) to avoid
SQLAlchemy's per-connection isolation on in-memory databases.
Each test gets a fresh database via drop_all / create_all.
"""
import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ── Shared file-based SQLite for API tests ────────────────────────────────────
# Using a named temp file so all connections within a test share state.

@pytest.fixture(scope="function")
def api_db():
    """
    Fresh file-based SQLite DB for each API test.
    All tables are created fresh; all connections share the same file.
    """
    import app.db.session as _session_module
    from app.db.base import Base

    # Create a temp file for this test's DB
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="tg_test_")
    os.close(fd)
    db_url = f"sqlite:///{db_path}"

    # Swap the global engine + session to this temp DB
    _old_engine  = _session_module.engine
    _old_session = _session_module.SessionLocal

    new_engine  = create_engine(db_url, connect_args={"check_same_thread": False})
    new_session = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
    _session_module.engine       = new_engine
    _session_module.SessionLocal = new_session

    # Create all tables
    Base.metadata.create_all(bind=new_engine)

    session = new_session()
    try:
        yield session
    finally:
        session.close()
        # Restore globals
        _session_module.engine       = _old_engine
        _session_module.SessionLocal = _old_session
        new_engine.dispose()
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest.fixture(scope="function")
def api_client(api_db):
    """
    TestClient with the swapped DB's get_db injected as a dependency.
    """
    from fastapi.testclient import TestClient
    from app.db.session import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: api_db
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.clear()
