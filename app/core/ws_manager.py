from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Registre en mémoire des sockets connectées, groupées par conversation_id."""

    def __init__(self) -> None:
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, conversation_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[conversation_id].append(websocket)

    def disconnect(self, conversation_id: int, websocket: WebSocket) -> None:
        connections = self.active_connections.get(conversation_id)
        if connections and websocket in connections:
            connections.remove(websocket)
            if not connections:
                del self.active_connections[conversation_id]

    async def broadcast(self, conversation_id: int, payload: dict[str, Any]) -> None:
        for connection in list(self.active_connections.get(conversation_id, [])):
            try:
                await connection.send_json(payload)
            except Exception:
                self.disconnect(conversation_id, connection)


manager = ConnectionManager()
