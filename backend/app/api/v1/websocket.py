"""
HydraControl — WebSocket Real-Time Streaming Endpoint
Handles WebSocket upgrade, JWT authentication, channel subscription requests,
heartbeat (PING/PONG), and safe client lifecycle disconnection.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from jose import JWTError
from sqlalchemy.future import select

from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.websocket.hub import hub

logger = logging.getLogger("hydracontrol.api.websocket")

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Real-Time WebSocket Streaming Endpoint.
    Clients connect via /api/v1/ws?token=<jwt_token>.
    Authenticates JWT token against user repository, verifies tenant boundary,
    and processes channel subscription / heartbeat commands.
    """
    if not token:
        logger.warning("WebSocket connection rejected: Missing token")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return

    try:
        payload = decode_access_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        token_type = payload.get("type")
        if not user_id_str or token_type == "device":
            logger.warning("WebSocket connection rejected: Invalid token claims")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token claims")
            return
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError) as e:
        logger.warning(f"WebSocket connection rejected: JWT validation failed ({e})")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
        return

    # Verify user in database
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.id == user_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user or not user.is_active:
            logger.warning(f"WebSocket connection rejected: User {user_id} inactive or not found")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User inactive or not found")
            return

        user_org_id = user.organization_id
        user_role = user.role
        current_user = user

    # Accept WebSocket connection
    await websocket.accept()
    await hub.connect(
        websocket=websocket,
        user_id=current_user.id,
        organization_id=user_org_id,
        role=user_role
    )

    # Send initial connection acknowledgment
    await websocket.send_json({
        "type": "CONNECTED",
        "user_id": str(current_user.id),
        "organization_id": str(user_org_id) if user_org_id else None,
        "role": user_role.value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "ERROR",
                    "message": "Malformed JSON payload. Expected structured JSON message."
                })
                continue

            if not isinstance(data, dict):
                await websocket.send_json({
                    "type": "ERROR",
                    "message": "Invalid payload format. Expected JSON object."
                })
                continue

            action = data.get("action") or data.get("type")
            if not action or not isinstance(action, str):
                await websocket.send_json({
                    "type": "ERROR",
                    "message": "Missing or invalid 'action'/'type' field in payload."
                })
                continue

            action = action.upper().strip()

            if action == "PING":
                await websocket.send_json({
                    "type": "PONG",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            elif action == "SUBSCRIBE":
                channels = data.get("channels")
                if not channels or not isinstance(channels, list):
                    await websocket.send_json({
                        "type": "ERROR",
                        "message": "SUBSCRIBE action requires a 'channels' list of channel strings."
                    })
                    continue

                async with AsyncSessionLocal() as session:
                    # Refresh user context in session
                    stmt = select(User).where(User.id == current_user.id)
                    res = await session.execute(stmt)
                    active_user = res.scalar_one_or_none()
                    if not active_user or not active_user.is_active:
                        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User deactivated")
                        break

                    success, failed = await hub.validate_and_subscribe(
                        websocket=websocket,
                        channels=channels,
                        user=active_user,
                        session=session
                    )

                await websocket.send_json({
                    "type": "SUBSCRIBED",
                    "channels": success,
                    "failed": failed
                })

            elif action == "UNSUBSCRIBE":
                channels = data.get("channels")
                if not channels or not isinstance(channels, list):
                    await websocket.send_json({
                        "type": "ERROR",
                        "message": "UNSUBSCRIBE action requires a 'channels' list of channel strings."
                    })
                    continue

                unsubscribed = []
                for ch in channels:
                    if isinstance(ch, str):
                        await hub.unsubscribe(websocket, ch)
                        unsubscribed.append(ch)

                await websocket.send_json({
                    "type": "UNSUBSCRIBED",
                    "channels": unsubscribed
                })

            else:
                await websocket.send_json({
                    "type": "ERROR",
                    "message": f"Unknown action '{action}'. Supported actions: SUBSCRIBE, UNSUBSCRIBE, PING."
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected cleanly: user_id={current_user.id}")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for user_id={current_user.id}: {e}", exc_info=True)
    finally:
        await hub.disconnect(websocket)
