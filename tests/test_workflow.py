import json
import pytest
from fastapi.testclient import TestClient
from main import app
from database import init_db, DB_PATH

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr("database.DB_PATH", tmp_path / "test.db")
    init_db()

@pytest.fixture
def client():
    return TestClient(app)

def sample(**overrides):
    data = {
        "request_id": "vendor-test-001",
        "vendor_name": "Northwind Supplies",
        "country": "India",
        "annual_revenue": 250000,
        "risk_score": 20,
        "documents": ["tax_certificate", "registration"],
        "simulate_dependency_failures": 0
    }
    data.update(overrides)
    return data

def test_happy_path_approved(client):
    response = client.post("/requests", json=sample())
    assert response.status_code == 200
    assert response.json()["decision"] == "APPROVED"
    assert response.json()["status"] == "COMPLETED"

def test_invalid_input(client):
    data = sample(annual_revenue=-10)
    assert client.post("/requests", json=data).status_code == 422

def test_duplicate_is_idempotent(client):
    client.post("/requests", json=sample())
    second = client.post("/requests", json=sample())
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

def test_dependency_failure_then_retry(client):
    first = client.post("/requests", json=sample(simulate_dependency_failures=1))
    assert first.json()["status"] == "RETRY_PENDING"
    second = client.post("/requests/vendor-test-001/retry")
    assert second.json()["status"] == "COMPLETED"

def test_reject_high_risk(client):
    response = client.post("/requests", json=sample(request_id="vendor-test-002", risk_score=95))
    assert response.json()["decision"] == "REJECTED"

def test_manual_review_medium_risk(client):
    response = client.post("/requests", json=sample(request_id="vendor-test-003", risk_score=55))
    assert response.json()["decision"] == "MANUAL_REVIEW"

def test_audit_trail_exists(client):
    client.post("/requests", json=sample())
    events = client.get("/requests/vendor-test-001/audit").json()["events"]
    assert any(e["event_type"] == "DECISION_MADE" for e in events)
