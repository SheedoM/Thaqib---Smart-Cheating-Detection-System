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

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected. Total active: {len(self.active_connections)}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected. Total active: {len(self.active_connections)}")

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
