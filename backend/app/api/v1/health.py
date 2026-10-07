from fastapi import APIRouter, status
try:
    from app.core.config import settings
    from app.db.session import check_db_health
    from app.mqtt.client import mqtt_client_service
except ImportError:
    from backend.app.core.config import settings
    from backend.app.db.session import check_db_health
    from backend.app.mqtt.client import mqtt_client_service

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Overall application health probe."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0-alpha"
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

