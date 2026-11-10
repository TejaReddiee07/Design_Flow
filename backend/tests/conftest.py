"""Test fixtures: in-memory MongoDB (mongomock), no Redis, agents disabled for API tests."""
from __future__ import annotations

import os
import tempfile

os.environ["APP_ENV"] = "test"
os.environ["MONGO_URI"] = "mongomock://"
os.environ["MONGO_DB"] = "designflow_test"
os.environ["REDIS_URL"] = ""
os.environ["AGENTS_ENABLED"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-123456"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_PATH"] = tempfile.mkdtemp(prefix="designflow-test-uploads-")
os.environ["BILLING_PROVIDER"] = "mock"
os.environ["EMAIL_PROVIDER"] = "mock"
os.environ["ADMIN_EMAIL"] = "admin@designflow.local"
os.environ["ADMIN_PASSWORD"] = "Admin123!"
os.environ["ADMIN_NAME"] = "Test Admin"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["LEAD_PROVIDER"] = "web"
os.environ["FX_GBP"] = "0.79"
os.environ["FX_INR"] = "84"
os.environ["REPORTING_CURRENCY"] = "INR"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.mongo import get_db  # noqa: E402
from app.db.seed import run_seed  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    db = get_db()
    db.drop_all()
    run_seed()
    yield db
    db.drop_all()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    return get_db()


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@designflow.local", "password": "Admin123!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def client_auth(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "tester@example.com", "password": "Tester123!", "full_name": "Test Client", "company_name": "Testco",
              "website": "https://testco.example.com", "industry": "SaaS"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}, "user": data["user"], "refresh": data["refresh_token"]}


@pytest.fixture(scope="session")
def client_headers(client_auth):
    return client_auth["headers"]


@pytest.fixture(scope="session")
def other_client_headers(client):
    r = client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "Other123!", "full_name": "Other Person", "company_name": "Otherco"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
