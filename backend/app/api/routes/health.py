from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
from ...core.database import get_db
from ...core.config import settings
from ...services.hardware import HardwareMonitor
from ...video.capabilities import CapabilityDetector, VideoCapabilities

router = APIRouter(tags=["Health & System"])

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Basic health check and database connectivity verification."""
    db_ok = False
    try:
        result = await db.execute(text("SELECT 1"))
        db_ok = (result.scalar() == 1)
    except Exception as e:
        db_ok = False

    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database_connected": db_ok,
        "storage_dir": str(settings.DATA_DIR),
        "ffmpeg": settings.get_ffmpeg_binary(),
    }

@router.get("/system/status")
async def system_status() -> Dict[str, Any]:
    """Retrieve non-mock, real-time hardware telemetry (GPU, CPU, RAM, Disk)."""
    return HardwareMonitor.get_system_metrics()

@router.get("/system/video-capabilities", response_model=VideoCapabilities)
async def video_capabilities(force_refresh: bool = Query(False)) -> VideoCapabilities:
    """Return verified FFmpeg and hardware encoding capabilities."""
    return CapabilityDetector.detect(force_refresh=force_refresh)
