import json
import logging
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from src.thaqib.api.dependencies import RequireRole
from src.thaqib.api.ws_manager import manager
from src.thaqib.config.settings import get_settings
from src.thaqib.core.security import decode_token
from src.thaqib.db.database import SessionLocal, get_db
from src.thaqib.db.models.exams import Assignment
from src.thaqib.db.models.infrastructure import Hall, HallVoiceChannel
from src.thaqib.db.models.ptt import PttClip
from src.thaqib.db.models.users import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Push-to-Talk"])
settings = get_settings()
require_ptt_status_user = RequireRole(["admin", "referee", "invigilator"])
PTT_UPLOAD_DIR = Path("uploads") / "ptt_clips"


@router.get("/status")
async def ptt_status(_: User = Depends(require_ptt_status_user)):
    """Expose lightweight PTT connection diagnostics for dashboards."""
    connected_clients = sorted(manager.active_connections.keys())
    return {
        "connected_count": len(connected_clients),
        "connected_clients": connected_clients,
    }


def _ensure_hall_channel(db: Session, hall_id: uuid.UUID) -> HallVoiceChannel:
    hall = db.query(Hall).filter(Hall.id == hall_id, Hall.deleted_at.is_(None)).first()
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")
    channel = (
        db.query(HallVoiceChannel)
        .filter(HallVoiceChannel.hall_id == hall_id, HallVoiceChannel.deleted_at.is_(None))
        .first()
    )
    if channel:
        return channel
    channel = HallVoiceChannel(hall_id=hall_id, channel_key=f"hall:{hall_id}", status="active")
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def _can_join_hall(db: Session, user: User, hall_id: uuid.UUID) -> bool:
    if user.role in {"admin", "referee"}:
        return True
    return (
        db.query(Assignment)
        .filter(
            Assignment.hall_id == hall_id,
            Assignment.invigilator_id == user.id,
        )
        .first()
        is not None
    )


def _active_assignment(db: Session, hall_id: uuid.UUID) -> Assignment | None:
    return (
        db.query(Assignment)
        .filter(
            Assignment.hall_id == hall_id,
            Assignment.monitoring_started_at.isnot(None),
            Assignment.monitoring_ended_at.is_(None),
        )
        .order_by(Assignment.monitoring_started_at.desc())
        .first()
    )


def _serialize_hall_status(channel: HallVoiceChannel) -> dict[str, Any]:
    return {
        "hall_id": str(channel.hall_id),
        "channel_id": str(channel.id),
        "channel_key": channel.channel_key,
        **manager.get_channel_presence(str(channel.id)),
    }


@router.get("/halls/{hall_id}/status")
def ptt_hall_status(
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ptt_status_user),
):
    if not _can_join_hall(db, current_user, hall_id):
        raise HTTPException(status_code=403, detail="You cannot access this hall voice channel")
    channel = _ensure_hall_channel(db, hall_id)
    return _serialize_hall_status(channel)


async def _authenticated_ptt_user(websocket: WebSocket) -> User | None:
    origin = websocket.headers.get("origin")
    if settings.app_env == "production" and origin and origin not in settings.cors_origins:
        await websocket.close(code=1008)
        return None

    token = websocket.cookies.get(settings.access_cookie_name)
    if not token:
        token = websocket.query_params.get("access_token")
    payload = decode_token(token) if token else None
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


def _ptt_identity(user: User) -> str:
    return user.ptt_id or user.username or str(user.id)


def _save_ptt_clip(
    *,
    hall_id: uuid.UUID,
    channel_id: uuid.UUID,
    speaker: User,
    started_at: datetime,
    ended_at: datetime,
    chunks: list[bytes],
    clip_type: str,
    alert_id: str | None,
) -> None:
    if not chunks:
        return

    db = SessionLocal()
    try:
        assignment = _active_assignment(db, hall_id)
        if not assignment:
            logger.warning(
                "PTT clip NOT saved for hall %s — no active monitoring session "
                "(invigilator must start monitoring before clips are recorded).",
                hall_id,
            )
            return

        clip_id = uuid.uuid4()
        session_id = assignment.exam_session_id
        hall_dir = PTT_UPLOAD_DIR / str(session_id) / str(hall_id)
        hall_dir.mkdir(parents=True, exist_ok=True)
        relative_path = hall_dir / f"{clip_id}.wav"

        with wave.open(str(relative_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"".join(chunks))

        duration_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
        normalized_alert_id = None
        if alert_id:
            try:
                normalized_alert_id = uuid.UUID(alert_id)
            except ValueError:
                normalized_alert_id = None

        db.add(
            PttClip(
                id=clip_id,
                exam_session_id=session_id,
                hall_id=hall_id,
                channel_id=channel_id,
                speaker_id=speaker.id,
                speaker_role=speaker.role,
                speaker_name=speaker.full_name,
                clip_type="incident" if normalized_alert_id else clip_type,
                alert_id=normalized_alert_id,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=duration_ms,
                audio_file_path=str(relative_path).replace("\\", "/"),
                metadata_json={"sample_rate": 16000, "encoding": "pcm_s16le"},
            )
        )
        db.commit()
    finally:
        db.close()

@router.websocket("/ws/{client_id}")
async def ptt_websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time Push-to-Talk (PTT) communication.
    Supports a two-way (anytime) communication protocol between Invigilators and Control Room.
    
    Expected JSON Protocol:
    1. {"type": "start_speak", "target_id": "control_room_1"}
    2. {"type": "stop_speak", "target_id": "control_room_1"}
    3. {"type": "ping"} / {"type": "pong"}
    """
    user = await _authenticated_ptt_user(websocket)
    if user is None:
        return
    authenticated_client_id = _ptt_identity(user)

    if authenticated_client_id != client_id:
        logger.info("PTT client id supplied by caller was ignored in favor of authenticated identity.")

    await manager.connect(websocket, authenticated_client_id)
    current_target = None
    
    try:
        while True:
            # Receive raw message to handle both JSON text and Binary audio chunks
            message = await websocket.receive()
            
            if "bytes" in message:
                audio_data = message["bytes"]
                # Route binary audio to current target, or broadcast
                if current_target:
                    await manager.send_personal_bytes(audio_data, current_target)
                else:
                    await manager.broadcast_bytes(audio_data, exclude_user=authenticated_client_id)
                    
            elif "text" in message:
                data = message["text"]
                try:
                    parsed = json.loads(data)
                    msg_type = parsed.get("type")
                    target_id = parsed.get("target_id")
                    
                    logger.info(f"[{authenticated_client_id}] -> [{target_id}]: {msg_type}")

                    # Handle Keep-Alive Pings
                    if msg_type == "ping":
                        await manager.send_personal_message({"type": "pong"}, authenticated_client_id)
                        continue

                    if msg_type == "start_speak":
                        current_target = target_id
                        forward_msg = {"type": msg_type, "sender_id": authenticated_client_id}
                        if target_id:
                            await manager.send_personal_message(forward_msg, target_id)
                        else:
                            await manager.broadcast(forward_msg, exclude_user=authenticated_client_id)
                            
                    elif msg_type == "stop_speak":
                        forward_msg = {"type": msg_type, "sender_id": authenticated_client_id}
                        if target_id:
                            await manager.send_personal_message(forward_msg, target_id)
                        else:
                            await manager.broadcast(forward_msg, exclude_user=authenticated_client_id)
                        current_target = None
                        
                    else:
                        logger.warning(f"Unknown message type from {authenticated_client_id}: {msg_type}")
                        
                except json.JSONDecodeError:
                    logger.error(f"Received non-JSON text from {client_id}: {data}")
                
    except WebSocketDisconnect:
        logger.info(f"Client {authenticated_client_id} disconnected.")
        manager.disconnect(authenticated_client_id)


@router.websocket("/ws/halls/{hall_id}")
async def ptt_hall_websocket_endpoint(websocket: WebSocket, hall_id: uuid.UUID):
    user = await _authenticated_ptt_user(websocket)
    if user is None:
        return

    db = SessionLocal()
    try:
        if not _can_join_hall(db, user, hall_id):
            await websocket.close(code=1008)
            return
        channel = _ensure_hall_channel(db, hall_id)
        channel_id = str(channel.id)
    finally:
        db.close()

    user_id = _ptt_identity(user)
    await manager.connect_channel(websocket, channel_id, user_id, user.role, user.full_name)
    current_clip: dict[str, Any] | None = None

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message:
                audio_data = message["bytes"]
                if current_clip is not None:
                    current_clip["chunks"].append(audio_data)
                await manager.send_channel_bytes(channel_id, audio_data, exclude_user=user_id)
                continue

            if "text" not in message:
                continue

            try:
                parsed = json.loads(message["text"])
            except json.JSONDecodeError:
                logger.error("Received non-JSON hall PTT text from %s", user_id)
                continue

            msg_type = parsed.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "mic_status":
                manager.set_channel_user_state(
                    channel_id,
                    user_id,
                    mic_state=parsed.get("mic_state") or "idle",
                )
                await manager.broadcast_channel_presence(channel_id)
                continue

            if msg_type == "start_speak":
                manager.set_channel_user_state(channel_id, user_id, is_transmitting=True)
                current_clip = {
                    "started_at": datetime.now(timezone.utc),
                    "chunks": [],
                    "clip_type": parsed.get("clip_type") or "normal",
                    "alert_id": parsed.get("alert_id"),
                }
                await manager.send_channel_message(
                    channel_id,
                    {
                        "type": "start_speak",
                        "sender_id": user_id,
                        "sender_name": user.full_name,
                        "sender_role": user.role,
                    },
                    exclude_user=user_id,
                )
                await manager.broadcast_channel_presence(channel_id)
                continue

            if msg_type == "stop_speak":
                manager.set_channel_user_state(channel_id, user_id, is_transmitting=False)
                if current_clip is not None:
                    _save_ptt_clip(
                        hall_id=hall_id,
                        channel_id=uuid.UUID(channel_id),
                        speaker=user,
                        started_at=current_clip["started_at"],
                        ended_at=datetime.now(timezone.utc),
                        chunks=current_clip["chunks"],
                        clip_type=current_clip["clip_type"],
                        alert_id=current_clip["alert_id"],
                    )
                    current_clip = None
                await manager.send_channel_message(
                    channel_id,
                    {
                        "type": "stop_speak",
                        "sender_id": user_id,
                        "sender_name": user.full_name,
                        "sender_role": user.role,
                    },
                    exclude_user=user_id,
                )
                await manager.broadcast_channel_presence(channel_id)
    except WebSocketDisconnect:
        logger.info("Hall PTT client %s disconnected from %s.", user_id, channel_id)
        manager.disconnect_channel(channel_id, user_id)
        await manager.broadcast_channel_presence(channel_id)
