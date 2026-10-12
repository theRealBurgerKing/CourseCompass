import pytest
from fastapi.testclient import TestClient

from app.dependencies import require_auth
from app.main import app
from app.rate_limit import chat_limiter


@pytest.fixture(autouse=True)
def _reset_limiter():
    chat_limiter.reset()
    yield
    chat_limiter.reset()


@pytest.fixture
def client():
    """TestClient without lifespan (no FAISS load) and with authentication stubbed out."""
    app.dependency_overrides[require_auth] = lambda: {"sub": "user-1"}
    yield TestClient(app)
    app.dependency_overrides.clear()
