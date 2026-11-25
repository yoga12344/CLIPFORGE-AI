import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket
from pydantic import BaseModel, Field

logger = logging.getLogger("clipforge.workers.events")

class JobEvent(BaseModel):
    job_id: str
    project_id: Optional[str] = None
    job_type: str
    event_type: str  # created, started, progress, completed, failed, cancelled
    progress_percent: int = 0
    stage_description: str = ""
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    timestamp: float = Field(default_factory=time.time)

class JobEventBroadcaster:
    _active_connections: Set[WebSocket] = set()

    @classmethod
    async def connect(cls, websocket: WebSocket):
        await websocket.accept()
        cls._active_connections.add(websocket)
        logger.info(f"WebSocket client connected for jobs. Active count: {len(cls._active_connections)}")

    @classmethod
    def disconnect(cls, websocket: WebSocket):
        cls._active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Active count: {len(cls._active_connections)}")

    @classmethod
    async def broadcast(cls, event: JobEvent):
        if not cls._active_connections:
            return

        payload = event.model_dump_json()
        dead_connections = set()

        for conn in cls._active_connections:
            try:
                await conn.send_text(payload)
            except Exception as e:
                logger.debug(f"Failed to send to client: {e}")
                dead_connections.add(conn)

        for dead in dead_connections:
            cls._active_connections.discard(dead)
