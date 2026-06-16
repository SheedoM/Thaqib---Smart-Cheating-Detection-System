"""
Minimal hall voice channel.

A single WebSocket per hall that relays audio between everyone connected to that
hall (control room <-> invigilator). Deliberately tiny: no approval state machine,
no clip recording, no DB writes. Auth is via the HttpOnly access cookie that the
browser sends on the WebSocket handshake (same-origin).

Microphone capture on the client requires a secure context (HTTPS or localhost),
so the app must be served over HTTPS for phones to transmit.
"""

import json
import logging
import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from src.thaqib.config.settings import get_settings
from src.thaqib.core.security import decode_token
from src.thaqib.core.scoping import accessible_institution_ids
from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.exams import Assignment, ExamAdminAssignment, ExamSession, exam_session_halls
from src.thaqib.db.models.infrastructure import Hall
from src.thaqib.db.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Voice"])
settings = get_settings()

VOICE_MAX_TEXT_BYTES = 4_096
VOICE_MAX_BINARY_BYTES = 65_536

# hall_id -> { connection_id: {"ws": WebSocket, "user_id": str, "role": str, "name": str} }
_rooms: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        return True

    configured = get_settings().cors_origins
    return "*" in configured or origin in configured


async def _authenticate(websocket: WebSocket, db: Session) -> User | None:
    token = websocket.cookies.get(get_settings().access_cookie_name)
    if not token:
        await websocket.close(code=1008)
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        await websocket.close(code=1008)
        return None

    user = db.query(User).filter(User.username == payload["sub"]).first()
    if not user or user.status != "active":
        await websocket.close(code=1008)
        return None
    return user


def _parse_hall_id(hall_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(hall_id)
    except ValueError:
        return None


def _admin_assigned_to_hall(db: Session, user: User, hall_uuid: uuid.UUID) -> bool:
    scope = accessible_institution_ids(db, user.institution_id)
    return (
        db.query(ExamAdminAssignment.id)
        .join(ExamSession, ExamAdminAssignment.exam_session_id == ExamSession.id)
        .join(exam_session_halls, exam_session_halls.c.exam_session_id == ExamSession.id)
        .filter(
            ExamAdminAssignment.admin_id == user.id,
            exam_session_halls.c.hall_id == hall_uuid,
            ExamSession.deleted_at.is_(None),
            ExamSession.institution_id.in_(scope),
        )
        .first()
        is not None
    )


def _invigilator_assigned_to_hall(db: Session, user: User, hall_uuid: uuid.UUID) -> bool:
    return (
        db.query(Assignment.id)
        .join(ExamSession, Assignment.exam_session_id == ExamSession.id)
        .filter(
            Assignment.invigilator_id == user.id,
            Assignment.hall_id == hall_uuid,
            ExamSession.deleted_at.is_(None),
        )
        .first()
        is not None
    )


def _can_join_hall_voice(db: Session, user: User, hall_id: str) -> bool:
    hall_uuid = _parse_hall_id(hall_id)
    if hall_uuid is None:
        return False

    hall = db.query(Hall).filter(Hall.id == hall_uuid, Hall.deleted_at.is_(None)).first()
    if hall is None:
        return False

    if user.role == "super_admin":
        return hall.institution_id in accessible_institution_ids(db, user.institution_id)
    if user.role == "admin":
        return _admin_assigned_to_hall(db, user, hall_uuid)
    if user.role == "invigilator":
        return _invigilator_assigned_to_hall(db, user, hall_uuid)
    return False


def _presence(hall_id: str) -> dict[str, Any]:
    return {
        "type": "presence",
        "participants": [
            {
                "id": p["user_id"],
                "connection_id": connection_id,
                "role": p["role"],
                "name": p["name"],
            }
            for connection_id, p in _rooms.get(hall_id, {}).items()
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
    if not _origin_allowed(websocket):
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    try:
        user = await _authenticate(websocket, db)
        if user is None:
            return
        if not _can_join_hall_voice(db, user, hall_id):
            await websocket.close(code=1008)
            return
    finally:
        db.close()

    user_id = user.username
    connection_id = f"{user_id}:{uuid.uuid4().hex}"
    await websocket.accept()
    _rooms[hall_id][connection_id] = {
        "ws": websocket,
        "user_id": user_id,
        "role": user.role,
        "name": user.full_name,
    }
    logger.info("voice connect hall=%s user=%s role=%s total=%d", hall_id, user_id, user.role, len(_rooms[hall_id]))
    await _broadcast(hall_id, _presence(hall_id))

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if message.get("bytes") is not None:
                if len(message["bytes"]) > VOICE_MAX_BINARY_BYTES:
                    await websocket.close(code=1009)
                    break
                # Relay raw PCM audio to everyone else in the hall.
                await _broadcast_bytes(hall_id, message["bytes"], exclude=connection_id)
                continue

            if message.get("text") is not None:
                if len(message["text"].encode("utf-8")) > VOICE_MAX_TEXT_BYTES:
                    await websocket.close(code=1009)
                    break
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
                        exclude=connection_id,
                    )
    except WebSocketDisconnect:
        pass
    finally:
        _rooms.get(hall_id, {}).pop(connection_id, None)
        if hall_id in _rooms and not _rooms[hall_id]:
            _rooms.pop(hall_id, None)
        await _broadcast(hall_id, _presence(hall_id))
        logger.info("voice disconnect hall=%s user=%s", hall_id, user_id)
