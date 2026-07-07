from fastapi import WebSocket
from typing import List
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """Envoie un message à tous les clients connectés"""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Si l'envoi échoue, on retire le client
                self.disconnect(connection)

# Instance globale unique
manager = ConnectionManager()