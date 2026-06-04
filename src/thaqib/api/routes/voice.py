"""
Minimal hall voice channel.

A single WebSocket per hall that relays audio between everyone connected to that
hall (control room <-> invigilator). Deliberately tiny: no approval state machine,
no clip recording, no DB writes. Auth is via the HttpOnly access cookie that the
browser sends on the WebSocket handshake (same-origin), with an optional
?access_token= query fallback.

Microphone capture on the client requires a secure context (HTTPS or localhost),
so the app must be served over HTTPS for phones to transmit.
"""

import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.thaqib.config.settings import get_settings
from src.thaqib.core.security import decode_token
from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Voice"])
settings = get_settings()

# hall_id -> { user_id: {"ws": WebSocket, "role": str, "name": str} }
_rooms: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)


async def _authenticate(websocket: WebSocket) -> User | None:
    token = websocket.cookies.get(settings.access_cookie_name) or websocket.query_params.get("access_token")
    if not token:
        await websocket.close(code=1008)
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        await websocket.close(code=1008)
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == payload["sub"]).first()
        if not user or user.status != "active":
            await websocket.close(code=1008)
            return None
        return user
    finally:
        db.close()


def _presence(hall_id: str) -> dict[str, Any]:
    return {
        "type": "presence",
        "participants": [
            {"id": uid, "role": p["role"], "name": p["name"]}
            for uid, p in _rooms.get(hall_id, {}).items()
        ],
    }


async def _broadcast(hall_id: str, message: dict[str, Any], exclude: str | None = None) -> None:
    dead: list[str] = []
    for uid, p in list(_rooms.get(hall_id, {}).items()):
        if uid == exclude:
            continue
        try:
            await p["ws"].send_json(message)
        except Exception:
            dead.append(uid)
    for uid in dead:
        _rooms.get(hall_id, {}).pop(uid, None)


async def _broadcast_bytes(hall_id: str, data: bytes, exclude: str | None = None) -> None:
    dead: list[str] = []
    for uid, p in list(_rooms.get(hall_id, {}).items()):
        if uid == exclude:
            continue
        try:
            await p["ws"].send_bytes(data)
        except Exception:
            dead.append(uid)
    for uid in dead:
        _rooms.get(hall_id, {}).pop(uid, None)


async def notify_hall(hall_id: str, message: dict[str, Any]) -> None:
    """Push a JSON message (e.g. a confirmed-incident card) to everyone connected
    to a hall's voice channel. Safe to call when nobody is connected — it's a no-op."""
    await _broadcast(hall_id, message)


@router.websocket("/ws/{hall_id}")
async def voice_ws(websocket: WebSocket, hall_id: str):
    user = await _authenticate(websocket)
    if user is None:
        return

    user_id = user.username
    await websocket.accept()
    _rooms[hall_id][user_id] = {"ws": websocket, "role": user.role, "name": user.full_name}
    logger.info("voice connect hall=%s user=%s role=%s total=%d", hall_id, user_id, user.role, len(_rooms[hall_id]))
    await _broadcast(hall_id, _presence(hall_id))

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if message.get("bytes") is not None:
                # Relay raw PCM audio to everyone else in the hall.
                await _broadcast_bytes(hall_id, message["bytes"], exclude=user_id)
                continue

            if message.get("text") is not None:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                msg_type = data.get("type")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type in ("talk_start", "talk_stop"):
                    await _broadcast(
                        hall_id,
                        {"type": msg_type, "id": user_id, "name": user.full_name, "role": user.role},
                        exclude=user_id,
                    )
    except WebSocketDisconnect:
        pass
    finally:
        _rooms.get(hall_id, {}).pop(user_id, None)
        if hall_id in _rooms and not _rooms[hall_id]:
            _rooms.pop(hall_id, None)
        await _broadcast(hall_id, _presence(hall_id))
        logger.info("voice disconnect hall=%s user=%s", hall_id, user_id)
