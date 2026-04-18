"""WebSocket manager — pushes live sensor data to multiple dashboard clients."""
import json
import logging
import asyncio
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger("agrimaster.ws")


class WebSocketManager:
    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        logger.info(f"WS client connected ({len(self._clients)} total)")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients.discard(ws)
        logger.info(f"WS client disconnected ({len(self._clients)} total)")

    async def broadcast(self, data: dict):
        if not self._clients:
            return
        message = json.dumps(data)
        dead = set()
        async with self._lock:
            for ws in self._clients:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)
            self._clients -= dead
        if dead:
            logger.debug(f"Removed {len(dead)} dead WS connections")

    @property
    def client_count(self) -> int:
        return len(self._clients)
