"""
HydraControl — WebSocket Broadcast Hub & Connection Manager
Provides real-time multi-tenant WebSocket connection management, channel-based subscription
filtering, robust dead-socket cleanup, and strict tenant-boundary authorization.
"""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Sequence, Any
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus
from app.models.station import Station
from app.models.controller import Controller
from app.models.motor import Motor
from app.services.site_auth import validate_site_access_policy, MAINTENANCE_ALLOWED_ROLES
from app.services.tenant import get_org_scoped_resource

logger = logging.getLogger("hydracontrol.websocket.hub")


@dataclass
class WebSocketConnection:
    """Metadata tracking an active client WebSocket connection."""
    websocket: WebSocket
    user_id: uuid.UUID
    organization_id: Optional[uuid.UUID]
    role: UserRole
    subscriptions: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebSocketHub:
    """
    Central in-memory asynchronous WebSocket connection registry and broadcast hub.
    Maintains subscriber indices, routes event payloads without blocking, and ensures
    strict tenant isolation across channels.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        # Map websocket -> Connection metadata
        self._connections: Dict[WebSocket, WebSocketConnection] = {}
        # Map channel_name -> Set of Websockets
        self._channel_subscribers: Dict[str, Set[WebSocket]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID],
        role: UserRole
    ) -> WebSocketConnection:
        """Registers a newly accepted WebSocket connection."""
        async with self._lock:
            conn = WebSocketConnection(
                websocket=websocket,
                user_id=user_id,
                organization_id=organization_id,
                role=role,
            )
            self._connections[websocket] = conn
            logger.info(
                f"WebSocket connected: user_id={user_id}, org_id={organization_id}, role={role.value}"
            )
            return conn

    async def disconnect(self, websocket: WebSocket) -> Optional[WebSocketConnection]:
        """Unregisters a disconnecting WebSocket and clears all channel subscriptions."""
        async with self._lock:
            conn = self._connections.pop(websocket, None)
            if conn:
                for channel in conn.subscriptions:
                    if channel in self._channel_subscribers:
                        self._channel_subscribers[channel].discard(websocket)
                        if not self._channel_subscribers[channel]:
                            del self._channel_subscribers[channel]
                logger.info(f"WebSocket disconnected: user_id={conn.user_id}")
            return conn

    async def get_connection(self, websocket: WebSocket) -> Optional[WebSocketConnection]:
        """Retrieves connection metadata for an active WebSocket."""
        async with self._lock:
            return self._connections.get(websocket)

    async def get_active_connection_count(self) -> int:
        """Returns the number of currently active connections."""
        async with self._lock:
            return len(self._connections)

    async def get_active_channel_count(self) -> int:
        """Returns the number of active subscribed channels."""
        async with self._lock:
            return len(self._channel_subscribers)

    async def subscribe(self, websocket: WebSocket, channel: str) -> bool:
        """Subscribes a connected client to a specific validated channel."""
        async with self._lock:
            conn = self._connections.get(websocket)
            if not conn:
                return False
            conn.subscriptions.add(channel)
            if channel not in self._channel_subscribers:
                self._channel_subscribers[channel] = set()
            self._channel_subscribers[channel].add(websocket)
            return True

    async def unsubscribe(self, websocket: WebSocket, channel: str) -> bool:
        """Unsubscribes a connected client from a specific channel."""
        async with self._lock:
            conn = self._connections.get(websocket)
            if not conn:
                return False
            conn.subscriptions.discard(channel)
            if channel in self._channel_subscribers:
                self._channel_subscribers[channel].discard(websocket)
                if not self._channel_subscribers[channel]:
                    del self._channel_subscribers[channel]
            return True

    async def validate_and_subscribe(
        self,
        websocket: WebSocket,
        channels: List[str],
        user: User,
        session: AsyncSession
    ) -> Tuple[List[str], List[Dict[str, str]]]:
        """
        Validates channel subscription requests against domain tenant hierarchies,
        site authorization rules, and RBAC policies.
        Returns (successful_channels, failed_channels_with_reasons).
        """
        success = []
        failed = []

        for ch in channels:
            if not isinstance(ch, str) or ":" not in ch:
                failed.append({"channel": str(ch), "reason": "Invalid channel format. Expected 'type:identifier'."})
                continue

            parts = ch.split(":", 1)
            ch_type = parts[0].strip().lower()
            ch_id = parts[1].strip()

            is_valid, reason = await self._validate_channel_access(
                ch_type=ch_type,
                ch_id=ch_id,
                user=user,
                session=session
            )

            if is_valid:
                canonical_channel = f"{ch_type}:{ch_id}"
                await self.subscribe(websocket, canonical_channel)
                success.append(canonical_channel)
            else:
                failed.append({"channel": ch, "reason": reason})

        return success, failed

    async def _validate_channel_access(
        self,
        ch_type: str,
        ch_id: str,
        user: User,
        session: AsyncSession
    ) -> Tuple[bool, str]:
        """
        Validates individual channel types against the user's tenant organization and site policies.
        """
        is_super_admin = (user.role == UserRole.SUPER_ADMIN)

        if ch_type == "org":
            try:
                org_uuid = uuid.UUID(ch_id)
            except ValueError:
                return False, "Invalid organization UUID format"

            if not is_super_admin and user.organization_id != org_uuid:
                return False, "Access denied: channel belongs to another organization"

            # Check organization status
            stmt = select(Organization).where(Organization.id == org_uuid)
            res = await session.execute(stmt)
            org = res.scalar_one_or_none()
            if not org:
                return False, "Organization not found"
            if org.status != OrganizationStatus.ACTIVE:
                return False, f"Organization is {org.status.value.lower()}"
            return True, ""

        elif ch_type == "site":
            try:
                site_uuid = uuid.UUID(ch_id)
            except ValueError:
                return False, "Invalid site UUID format"

            stmt = select(Site).where(Site.id == site_uuid)
            if not is_super_admin:
                if not user.organization_id:
                    return False, "User has no organization context"
                stmt = stmt.where(Site.organization_id == user.organization_id)

            res = await session.execute(stmt)
            site = res.scalar_one_or_none()
            if not site:
                return False, "Site not found or access denied"

            # Validate site operational policy
            try:
                validate_site_access_policy(site, user)
            except Exception as e:
                return False, f"Site access policy restriction: {str(e)}"
            return True, ""

        elif ch_type == "station":
            try:
                station_uuid = uuid.UUID(ch_id)
            except ValueError:
                return False, "Invalid station UUID format"

            stmt = (
                select(Station)
                .options(selectinload(Station.site))
                .join(Site, Station.site_id == Site.id)
                .where(Station.id == station_uuid)
            )
            if not is_super_admin:
                if not user.organization_id:
                    return False, "User has no organization context"
                stmt = stmt.where(Site.organization_id == user.organization_id)

            res = await session.execute(stmt)
            station = res.scalar_one_or_none()
            if not station or not station.site:
                return False, "Station not found or access denied"

            try:
                validate_site_access_policy(station.site, user)
            except Exception as e:
                return False, f"Parent site policy restriction: {str(e)}"
            return True, ""

        elif ch_type == "motor":
            try:
                motor_uuid = uuid.UUID(ch_id)
            except ValueError:
                return False, "Invalid motor UUID format"

            stmt = (
                select(Motor)
                .join(Controller, Motor.controller_id == Controller.id)
                .join(Station, Controller.station_id == Station.id)
                .join(Site, Station.site_id == Site.id)
                .options(
                    selectinload(Motor.controller)
                    .selectinload(Controller.station)
                    .selectinload(Station.site)
                )
                .where(Motor.id == motor_uuid)
            )
            if not is_super_admin:
                if not user.organization_id:
                    return False, "User has no organization context"
                stmt = stmt.where(Site.organization_id == user.organization_id)

            res = await session.execute(stmt)
            motor = res.scalar_one_or_none()
            if not motor or not motor.controller or not motor.controller.station or not motor.controller.station.site:
                return False, "Motor not found or access denied"

            try:
                validate_site_access_policy(motor.controller.station.site, user)
            except Exception as e:
                return False, f"Parent site policy restriction: {str(e)}"
            return True, ""

        elif ch_type == "device":
            device_uid = ch_id.strip()
            if not device_uid:
                return False, "Device UID cannot be empty"

            stmt = (
                select(Controller)
                .join(Station, Controller.station_id == Station.id)
                .join(Site, Station.site_id == Site.id)
                .options(
                    selectinload(Controller.station)
                    .selectinload(Station.site)
                )
                .where(Controller.device_uid == device_uid)
            )
            if not is_super_admin:
                if not user.organization_id:
                    return False, "User has no organization context"
                stmt = stmt.where(Site.organization_id == user.organization_id)

            res = await session.execute(stmt)
            controller = res.scalar_one_or_none()
            if not controller or not controller.station or not controller.station.site:
                return False, "Device not found or access denied"

            try:
                validate_site_access_policy(controller.station.site, user)
            except Exception as e:
                return False, f"Parent site policy restriction: {str(e)}"
            return True, ""

        else:
            return False, f"Unsupported channel type '{ch_type}'. Supported types: org, site, station, motor, device"

    async def broadcast_to_channels(self, channels: Sequence[str], message: Dict[str, Any]) -> int:
        """
        Broadcasts a JSON message to all active subscribers across the given list of channels.
        Guarantees de-duplicated delivery (each client connection receives the message at most once),
        non-blocking concurrent transmission, and automatic removal of dead sockets.
        Returns the count of successfully notified clients.
        """
        target_sockets: Set[WebSocket] = set()

        async with self._lock:
            for ch in channels:
                subs = self._channel_subscribers.get(ch)
                if subs:
                    target_sockets.update(subs)

        if not target_sockets:
            return 0

        # Send concurrently to all target websockets
        dead_sockets: List[WebSocket] = []
        delivered_count = 0

        async def _safe_send(ws: WebSocket):
            nonlocal delivered_count
            try:
                await ws.send_json(message)
                delivered_count += 1
            except (WebSocketDisconnect, RuntimeError, ConnectionResetError, Exception) as e:
                logger.warning(f"Failed sending WebSocket message to client: {e}")
                dead_sockets.append(ws)

        await asyncio.gather(*[_safe_send(ws) for ws in target_sockets], return_exceptions=True)

        if dead_sockets:
            for dead_ws in dead_sockets:
                await self.disconnect(dead_ws)

        return delivered_count

    async def broadcast(self, channel: str, message: Dict[str, Any]) -> int:
        """Broadcasts a message to a single channel."""
        return await self.broadcast_to_channels([channel], message)


# Global singleton instance
hub = WebSocketHub()
