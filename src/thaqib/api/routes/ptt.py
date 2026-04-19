import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from thaqib.api.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Push-to-Talk"])

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
    await manager.connect(websocket, client_id)
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
                    await manager.broadcast_bytes(audio_data, exclude_user=client_id)
                    
            elif "text" in message:
                data = message["text"]
                try:
                    import json
                    parsed = json.loads(data)
                    msg_type = parsed.get("type")
                    target_id = parsed.get("target_id")
                    
                    logger.info(f"[{client_id}] -> [{target_id}]: {msg_type}")

                    # Handle Keep-Alive Pings
                    if msg_type == "ping":
                        await manager.send_personal_message({"type": "pong"}, client_id)
                        continue

                    if msg_type == "start_speak":
                        current_target = target_id
                        forward_msg = {"type": msg_type, "sender_id": client_id}
                        if target_id:
                            await manager.send_personal_message(forward_msg, target_id)
                        else:
                            await manager.broadcast(forward_msg, exclude_user=client_id)
                            
                    elif msg_type == "stop_speak":
                        forward_msg = {"type": msg_type, "sender_id": client_id}
                        if target_id:
                            await manager.send_personal_message(forward_msg, target_id)
                        else:
                            await manager.broadcast(forward_msg, exclude_user=client_id)
                        current_target = None
                        
                    else:
                        logger.warning(f"Unknown message type from {client_id}: {msg_type}")
                        
                except json.JSONDecodeError:
                    logger.error(f"Received non-JSON text from {client_id}: {data}")
                
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected.")
        manager.disconnect(client_id)
