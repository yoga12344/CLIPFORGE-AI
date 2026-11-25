import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.database import init_db
from .core.security import verify_session_token
from .api.router import api_router
from .workers.job_manager import JobManager
from .workers.job_events import JobEventBroadcaster

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    print(f"[{settings.APP_NAME}] Initializing database schema...")
    await init_db()
    print(f"[{settings.APP_NAME}] Starting background video job manager...")
    await JobManager.get_instance().start()
    print(f"[{settings.APP_NAME}] Backend initialized successfully.")
    yield
    print(f"[{settings.APP_NAME}] Shutting down background video job manager...")
    await JobManager.get_instance().stop()
    print(f"[{settings.APP_NAME}] Backend shut down complete.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ClipForge AI - Professional Local-First Desktop Video Repurposing",
    lifespan=lifespan
)

# Desktop Local Origin CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "null",  # Electron file:// origin
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Static file mounts for clips and exports
app.mount(
    "/storage/clips",
    StaticFiles(directory=str(settings.CLIPS_DIR)),
    name="clips"
)
app.mount(
    "/storage/thumbnails",
    StaticFiles(directory=str(settings.THUMBNAILS_DIR)),
    name="thumbnails"
)
app.mount(
    "/storage/projects",
    StaticFiles(directory=str(settings.PROJECTS_DIR)),
    name="projects"
)

# WebSocket endpoint for real-time video processing and job progress updates
@app.websocket("/ws/jobs")
async def websocket_jobs(websocket: WebSocket):
    await JobEventBroadcaster.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle client ping
            await websocket.send_json({"event": "pong", "client_data": data})
    except WebSocketDisconnect:
        JobEventBroadcaster.disconnect(websocket)
    except Exception:
        JobEventBroadcaster.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
