import pytest
from fastapi.testclient import TestClient
try:
    from app.main import app
except ImportError:
    from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "version" in data


def test_health_endpoints():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

    response_v1 = client.get("/api/v1/health")
    assert response_v1.status_code == 200

    response_db = client.get("/api/v1/health/db")
    assert response_db.status_code == 200
    assert response_db.json()["status"] == "connected"

    response_mqtt = client.get("/api/v1/health/mqtt")
    assert response_mqtt.status_code == 200
    assert response_mqtt.json()["status"] == "ready"
