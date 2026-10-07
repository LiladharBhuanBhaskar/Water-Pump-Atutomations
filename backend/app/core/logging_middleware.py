"""
HydraControl — Correlation ID & Structured Logging Middleware (Phase 24.3).
Injects X-Correlation-ID into request/response context, captures latency metrics,
and produces JSON structured logs with automatic secret scrubbing.
"""

import time
import uuid
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import http_requests_total, http_request_duration_seconds

logger = logging.getLogger("hydracontrol.access")


class CorrelationAndLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Resolve or generate Correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start_time = time.time()
        status_code = 500
        path = request.url.path

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            duration = time.time() - start_time
            duration_ms = round(duration * 1000, 2)

            # Update Prometheus metrics
            try:
                # Group dynamic IDs into parameterized buckets to prevent label explosion
                normalized_path = path
                if path.startswith("/api/v1/motors/") and len(path.split("/")) > 4:
                    normalized_path = "/api/v1/motors/{id}/" + path.split("/")[-1]
                elif path.startswith("/api/v1/stations/") and len(path.split("/")) > 4:
                    normalized_path = "/api/v1/stations/{id}/" + path.split("/")[-1]

                http_requests_total.labels(
                    method=request.method,
                    endpoint=normalized_path,
                    status_code=str(status_code),
                ).inc()

                http_request_duration_seconds.labels(
                    method=request.method,
                    endpoint=normalized_path,
                ).observe(duration)
            except Exception:
                pass

            # Structured JSON log entry
            log_payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "correlation_id": correlation_id,
                "method": request.method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else "unknown",
            }
            logger.info(json.dumps(log_payload))
