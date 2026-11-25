import os
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.security import verify_session_token
from ...core.streaming import stream_file_with_ranges
from ...db.models import Video
from ...schemas.api_schemas import (
    VideoProbeRequest, VideoProbeResponse, VideoImportRequest, VideoResponse,
    VideoActionResponse
)
from ...services.video_service import VideoService
from ...workers.job_manager import JobManager

router = APIRouter(prefix="/videos", tags=["Videos"])

@router.post("/probe", response_model=VideoProbeResponse)
async def probe_video_file(
    data: VideoProbeRequest,
    authorized: bool = Depends(verify_session_token)
):
    """Inspect video file metadata with FFprobe before import."""
    probe = VideoService.probe_video(data.file_path)
    return probe

@router.post("/import", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def import_video(
    data: VideoImportRequest,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Import a validated video into a project."""
    try:
        video = await VideoService.import_video(
            db=db,
            project_id=data.project_id,
            source_file_path=data.file_path,
            copy_to_storage=data.copy_to_storage
        )
        return video
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.get("", response_model=List[VideoResponse])
async def list_all_videos(
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve all videos across projects, optionally filtered by project_id."""
    stmt = select(Video)
    if project_id:
        stmt = stmt.where(Video.project_id == project_id)
    stmt = stmt.order_by(Video.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve video details by ID."""
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

# --- Phase 3 Video Actions ---

@router.post("/{video_id}/inspect", response_model=VideoActionResponse)
async def inspect_video_job(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Enqueue full video inspection with FFprobe."""
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    job = await JobManager.get_instance().enqueue_job(
        job_type="inspect",
        project_id=video.project_id,
        params={"video_id": video_id}
    )
    return VideoActionResponse(job_id=job.id, message="Video inspection queued.")

@router.post("/{video_id}/thumbnail", response_model=VideoActionResponse)
async def generate_thumbnail_job(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Enqueue poster and strip thumbnail generation."""
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    job = await JobManager.get_instance().enqueue_job(
        job_type="thumbnail",
        project_id=video.project_id,
        params={"video_id": video_id, "generate_strip": True, "strip_count": 10}
    )
    return VideoActionResponse(job_id=job.id, message="Thumbnail generation queued.")

@router.post("/{video_id}/extract-audio", response_model=VideoActionResponse)
async def extract_audio_job(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Enqueue 16kHz mono WAV extraction for Whisper."""
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    job = await JobManager.get_instance().enqueue_job(
        job_type="extract_audio",
        project_id=video.project_id,
        params={"video_id": video_id}
    )
    return VideoActionResponse(job_id=job.id, message="Audio extraction queued.")

@router.post("/{video_id}/generate-preview", response_model=VideoActionResponse)
async def generate_preview_job(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Enqueue 720p faststart MP4 preview generation."""
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    job = await JobManager.get_instance().enqueue_job(
        job_type="generate_preview",
        project_id=video.project_id,
        params={"video_id": video_id, "max_height": 720}
    )
    return VideoActionResponse(job_id=job.id, message="Preview generation queued.")

@router.get("/{video_id}/preview")
async def stream_video_preview(
    video_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Stream video preview with HTTP 206 Partial Content range support."""
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Use generated preview if available, otherwise fallback to source file
    target_path = video.preview_path if (video.preview_path and os.path.isfile(video.preview_path)) else video.file_path
    if not target_path or not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail="Media file not found on disk")

    return stream_file_with_ranges(request=request, file_path=target_path)

@router.get("/{video_id}/thumbnail-file")
async def get_video_thumbnail_file(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Serve the video's poster thumbnail image."""
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video or not video.thumbnail_path or not os.path.isfile(video.thumbnail_path):
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    return FileResponse(video.thumbnail_path, media_type="image/jpeg")
