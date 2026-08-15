"""Test configuration - sets up isolated test database BEFORE any app imports."""

import os
import sys

# Set test DATABASE_URL BEFORE any imports that use database.connection
# Use SQLite file-based database for thread-safe sharing across TestClient threads
import tempfile
_test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db_path = _test_db_file.name
_test_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"

# Disable external API calls during tests
os.environ["NVIDIA_API_KEY"] = "test-key"
os.environ["FIRECRAWL_API_KEY"] = "test-key"
os.environ["TAVILY_API_KEY"] = "test-key"

# Create database tables immediately at import time (before test modules are loaded)
from database.connection import engine, Base
from database import models  # noqa: F401

Base.metadata.create_all(bind=engine)


import pytest


@pytest.fixture(autouse=True)
def clear_tables():
    """Clear all tables before each test."""
    from database.connection import SessionLocal
    from database import models  # noqa: F401
    
    # Clear all data from tables
    with SessionLocal() as session:
        # Delete in reverse order due to foreign keys
        session.execute(models.JobRow.__table__.delete())
        session.execute(models.Job.__table__.delete())
        session.commit()
    
    yield
    
    # Cleanup after test
    with SessionLocal() as session:
        session.execute(models.JobRow.__table__.delete())
        session.execute(models.Job.__table__.delete())
        session.commit()


def pytest_sessionfinish(session, exitstatus):
    """Clean up after test session."""
    from database.connection import engine
    engine.dispose()
    # Clean up temp database file
    import os
    if '_test_db_path' in globals():
        try:
            os.unlink(_test_db_path)
        except OSError:
            pass