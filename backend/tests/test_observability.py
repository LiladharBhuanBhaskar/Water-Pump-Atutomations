"""
HydraControl — Observability & Health Verification Suite (Phase 24).
Verifies health probes (/live, /ready, /deep), Prometheus metrics endpoint,
correlation ID propagation, and absence of credential leaks.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_enhanced_health_probes(client: TestClient):
    """Verify liveness, readiness, and deep diagnostic health endpoints."""
    # 1. Liveness
    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "alive"

    # 2. Readiness
    ready_resp = client.get("/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"

    # 3. Deep Diagnostics
    deep_resp = client.get("/health/deep")
    assert deep_resp.status_code == 200
    deep_data = deep_resp.json()
    assert "database" in deep_data
    assert "mqtt" in deep_data
    # Verify no secret leakage
    raw_text = deep_resp.text.lower()
    assert "password" not in raw_text
    assert "secret" not in raw_text


def test_prometheus_metrics_endpoint(client: TestClient):
    """Verify /metrics exports valid Prometheus format gauges and counters."""
    # Generate some traffic first
    client.get("/health")
    client.get("/health/live")

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "text/plain" in metrics_resp.headers.get("content-type", "") or "version=0.0.4" in metrics_resp.headers.get("content-type", "")

    body = metrics_resp.text
    assert "hydracontrol_http_requests_total" in body
    assert "hydracontrol_http_request_duration_seconds" in body
    assert "hydracontrol_active_websocket_connections" in body


def test_correlation_id_propagation(client: TestClient):
    """Verify X-Correlation-ID is preserved when supplied and generated when absent."""
    # 1. When supplied by client
    custom_cid = f"test-trace-{uuid.uuid4().hex}"
    resp1 = client.get("/health", headers={"X-Correlation-ID": custom_cid})
    assert resp1.status_code == 200
    assert resp1.headers.get("X-Correlation-ID") == custom_cid

    # 2. When absent, server generates a valid UUID correlation ID
    resp2 = client.get("/health")
    assert resp2.status_code == 200
    generated_cid = resp2.headers.get("X-Correlation-ID")
    assert generated_cid is not None
    assert len(generated_cid) >= 10
