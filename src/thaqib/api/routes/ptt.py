import json
import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from src.thaqib.api.dependencies import RequireRole
from src.thaqib.api.ws_manager import manager
from src.thaqib.config.settings import get_settings
from src.thaqib.core.security import decode_token
from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.users import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Push-to-Talk"])
settings = get_settings()
require_ptt_status_user = RequireRole(["admin", "referee", "invigilator"])


@router.get("/status")
async def ptt_status(_: User = Depends(require_ptt_status_user)):
    """Expose lightweight PTT connection diagnostics for dashboards."""
    connected_clients = sorted(manager.active_connections.keys())
    return {
        "connected_count": len(connected_clients),
        "connected_clients": connected_clients,
    }


async def _authenticated_ptt_identity(websocket: WebSocket) -> str | None:
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
        return user.ptt_id or user.username or str(user.id)
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
    authenticated_client_id = await _authenticated_ptt_identity(websocket)
    if authenticated_client_id is None:
        return

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
