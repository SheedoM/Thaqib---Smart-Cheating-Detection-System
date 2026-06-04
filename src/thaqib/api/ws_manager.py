import json
import logging
from typing import Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages active WebSocket connections for the Thaqib system.
    Handles routing messages between users (e.g., Invigilating App and Control Room).
    """
    def __init__(self):
        # Maps user_id / ptt_id to a connected WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        self.channel_connections: Dict[str, Dict[str, Dict[str, Any]]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected. Total active: {len(self.active_connections)}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected. Total active: {len(self.active_connections)}")
        for channel_id in list(self.channel_connections.keys()):
            if user_id in self.channel_connections[channel_id]:
                del self.channel_connections[channel_id][user_id]
            if not self.channel_connections[channel_id]:
                del self.channel_connections[channel_id]

    async def connect_channel(
        self,
        websocket: WebSocket,
        channel_id: str,
        user_id: str,
        role: str,
        full_name: str,
    ):
        await websocket.accept()
        self.channel_connections.setdefault(channel_id, {})[user_id] = {
            "websocket": websocket,
            "role": role,
            "full_name": full_name,
            "mic_state": "idle",
            "is_transmitting": False,
        }
        self.active_connections[user_id] = websocket
        await self.broadcast_channel_presence(channel_id)

    def disconnect_channel(self, channel_id: str, user_id: str):
        users = self.channel_connections.get(channel_id)
        if users and user_id in users:
            del users[user_id]
            if not users:
                del self.channel_connections[channel_id]
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    def set_channel_user_state(self, channel_id: str, user_id: str, **updates: Any):
        user_state = self.channel_connections.get(channel_id, {}).get(user_id)
        if user_state:
            user_state.update(updates)

    def get_channel_presence(self, channel_id: str) -> dict[str, Any]:
        users = self.channel_connections.get(channel_id, {})
        control_users = [
            user for user in users.values() if user.get("role") in {"admin", "referee"}
        ]
        invigilator_users = [
            user for user in users.values() if user.get("role") == "invigilator"
        ]
        return {
            "control_connected": bool(control_users),
            "invigilator_connected": bool(invigilator_users),
            "control_mic_state": _best_mic_state(control_users),
            "invigilator_mic_state": _best_mic_state(invigilator_users),
            "is_transmitting": any(bool(user.get("is_transmitting")) for user in users.values()),
            "participants": [
                {
                    "role": user.get("role"),
                    "full_name": user.get("full_name"),
                    "mic_state": user.get("mic_state", "idle"),
                    "is_transmitting": bool(user.get("is_transmitting")),
                }
                for user in users.values()
            ],
        }

    async def send_channel_message(
        self,
        channel_id: str,
        message: Dict[str, Any],
        exclude_user: str | None = None,
    ):
        disconnected_users = []
        for uid, user in self.channel_connections.get(channel_id, {}).items():
            if uid == exclude_user:
                continue
            websocket = user["websocket"]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send channel message to {uid}: {e}")
                disconnected_users.append(uid)
        for uid in disconnected_users:
            self.disconnect_channel(channel_id, uid)

    async def send_channel_bytes(
        self,
        channel_id: str,
        data: bytes,
        exclude_user: str | None = None,
    ):
        disconnected_users = []
        for uid, user in self.channel_connections.get(channel_id, {}).items():
            if uid == exclude_user:
                continue
            websocket = user["websocket"]
            try:
                await websocket.send_bytes(data)
            except Exception as e:
                logger.error(f"Failed to send channel bytes to {uid}: {e}")
                disconnected_users.append(uid)
        for uid in disconnected_users:
            self.disconnect_channel(channel_id, uid)

    async def broadcast_channel_presence(self, channel_id: str):
        await self.send_channel_message(
            channel_id,
            {"type": "presence", **self.get_channel_presence(channel_id)},
        )

    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """Send a JSON message to a specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send personal message to {user_id}: {e}")
                self.disconnect(user_id)
        else:
            logger.warning(f"Message targeted to offline user: {user_id}")

    async def send_personal_bytes(self, data: bytes, user_id: str):
        """Send binary audio data to a specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_bytes(data)
            except Exception as e:
                logger.error(f"Failed to send binary message to {user_id}: {e}")
                self.disconnect(user_id)

    async def broadcast(self, message: Dict[str, Any], exclude_user: str = None):
        """Broadcast a message to all connected clients except potentially the sender"""
        disconnected_users = []
        for uid, connection in self.active_connections.items():
            if uid == exclude_user:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {uid}: {e}")
                disconnected_users.append(uid)

        # Cleanup failed connections
        for uid in disconnected_users:
            self.disconnect(uid)

    async def broadcast_bytes(self, data: bytes, exclude_user: str = None):
        """Broadcast binary audio data to all connected clients except potentially the sender"""
        disconnected_users = []
        for uid, connection in self.active_connections.items():
            if uid == exclude_user:
                continue
            try:
                await connection.send_bytes(data)
            except Exception as e:
                logger.error(f"Failed to broadcast bytes to {uid}: {e}")
                disconnected_users.append(uid)

        for uid in disconnected_users:
            self.disconnect(uid)

# Global connection manager instance
manager = ConnectionManager()


def _best_mic_state(users: list[dict[str, Any]]) -> str:
    states = {user.get("mic_state", "idle") for user in users}
    for state in ("ready", "requesting", "blocked", "error"):
        if state in states:
            return state
    return "idle"
