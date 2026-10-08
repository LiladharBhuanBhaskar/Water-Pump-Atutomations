from fastapi import APIRouter, status, Response, HTTPException
from datetime import datetime, timezone

try:
    from app.core.config import settings
    from app.db.session import check_db_health
    from app.mqtt.client import mqtt_client_service
    from app.core.metrics import get_prometheus_metrics_response
except ImportError:
    from backend.app.core.config import settings
    from backend.app.db.session import check_db_health
    from backend.app.mqtt.client import mqtt_client_service
    from backend.app.core.metrics import get_prometheus_metrics_response

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Overall application health probe."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0-alpha",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def health_live():
    """Liveness probe: verifies process is running and responding."""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def health_ready(response: Response):
    """Readiness probe: verifies service can serve operational traffic."""
    db_status = await check_db_health()
    db_healthy = db_status.get("status") in ("connected", "healthy") or db_status.get("ping") == "ok"

    if not db_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "Database connection unhealthy",
            "database": db_status,
        }

    return {
        "status": "ready",
        "database": "connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/deep", status_code=status.HTTP_200_OK)
async def health_deep():
    """Detailed diagnostics health probe across all subsystems without credential leakage."""
    db_diag = await check_db_health()
    mqtt_diag = mqtt_client_service.get_health_status()
    db_healthy = db_diag.get("status") in ("connected", "healthy") or db_diag.get("ping") == "ok"

    return {
        "status": "healthy" if db_healthy else "degraded",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": {
            "status": db_diag.get("status"),
            "database_type": db_diag.get("database"),
            "ping": db_diag.get("ping"),
        },
        "mqtt": {
            "status": mqtt_diag.get("status"),
            "connected": mqtt_diag.get("connected"),
            "subscriptions": mqtt_diag.get("subscriptions_count", 0),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/db", status_code=status.HTTP_200_OK)
async def health_db():
    """Database connectivity health probe."""
    return await check_db_health()


@router.get("/health/mqtt", status_code=status.HTTP_200_OK)
async def health_mqtt():
    """MQTT Broker connectivity health probe."""
    diag = mqtt_client_service.get_health_status()
    return {
        "status": "ready",
        "connection_status": diag.get("status"),
        "connected": diag.get("connected"),
        "broker_host": settings.MQTT_BROKER_HOST,
        "broker_port": settings.MQTT_BROKER_PORT,
        "client_id": diag.get("client_id"),
        "subscriptions_count": diag.get("subscriptions_count", 0)
    }


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics scrape endpoint."""
    return get_prometheus_metrics_response()


@router.get("/health/time", status_code=status.HTTP_200_OK)
async def health_time():
    """Time & Timezone diagnostics endpoint for laptop and scheduler synchronization."""
    from app.services.timer_scheduler_service import get_local_datetime
    utc_now = datetime.now(timezone.utc)
    local_now = get_local_datetime(utc_now, "Asia/Kolkata")
    weekday_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    weekday_codes = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    return {
        "utc_time": utc_now.isoformat(),
        "local_time": local_now.strftime("%Y-%m-%d %H:%M:%S"),
        "time_hm": local_now.strftime("%H:%M"),
        "timezone": "Asia/Kolkata",
        "offset": "+05:30",
        "date": local_now.strftime("%Y-%m-%d"),
        "weekday": weekday_names[local_now.weekday()],
        "weekday_code": weekday_codes[local_now.weekday()],
    }
