"""
HydraControl — Inbound MQTT Heartbeat Handler
Processes device heartbeat messages and updates liveness tracking in the database.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.controller import Controller, ControllerStatus
from app.models.station import Station
from app.models.site import Site, SiteStatus
from app.mqtt.router import mqtt_router, ROOT_PREFIX, SHORT_PREFIX

logger = logging.getLogger("hydracontrol.mqtt.handlers.heartbeat")


async def process_heartbeat_payload(device_uid: str, payload: Any) -> Optional[Controller]:
    """Process heartbeat for a device UID within an async database session."""
    if not isinstance(payload, dict):
        logger.warning(f"Invalid non-dict heartbeat payload from device '{device_uid}': {payload}")
        return None

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Controller)
            .options(selectinload(Controller.station).selectinload(Station.site))
            .where(Controller.device_uid == device_uid)
        )
        res = await session.execute(stmt)
        controller = res.scalar_one_or_none()

        if controller is None:
            logger.warning(f"Received MQTT heartbeat from unprovisioned device UID '{device_uid}'")
            return None

        # Verify operational state
        if controller.station and controller.station.site:
            if controller.station.site.status == SiteStatus.SUSPENDED:
                logger.warning(f"Heartbeat rejected: Parent site of device '{device_uid}' is suspended.")
                return None

        if controller.status == ControllerStatus.DECOMMISSIONED:
            logger.warning(f"Heartbeat rejected: Device '{device_uid}' is decommissioned.")
            return None

        now = datetime.now(timezone.utc)
        controller.last_seen_at = now

        if "firmware_version" in payload and payload["firmware_version"]:
            controller.firmware_version = str(payload["firmware_version"]).strip()
        if "ip_address" in payload and payload["ip_address"]:
            controller.ip_address = str(payload["ip_address"]).strip()
        if "mac_address" in payload and payload["mac_address"]:
            controller.mac_address = str(payload["mac_address"]).strip()

        # Update controller status if provided
        status_str = payload.get("status") or payload.get("controller_status")
        if status_str and hasattr(ControllerStatus, str(status_str).upper()):
            req_status = ControllerStatus(str(status_str).upper())
            if req_status != ControllerStatus.DECOMMISSIONED:
                controller.status = req_status
        elif controller.status == ControllerStatus.OFFLINE:
            controller.status = ControllerStatus.ACTIVE

        session.add(controller)
        await session.commit()
        await session.refresh(controller)
        logger.info(f"Updated MQTT heartbeat for device '{device_uid}' (Status: {controller.status.value})")
        return controller


@mqtt_router.route(f"{ROOT_PREFIX}/{{device_uid}}/heartbeat")
@mqtt_router.route(f"{SHORT_PREFIX}/{{device_uid}}/heartbeat")
async def handle_device_heartbeat(device_uid: str, payload: Any, **kwargs):
    """MQTT Route handler for device heartbeat."""
    await process_heartbeat_payload(device_uid, payload)
