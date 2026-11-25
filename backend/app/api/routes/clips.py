import os
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.security import verify_session_token
from ...core.streaming import stream_file_with_ranges
from ...db.models import Clip, Video, Project
from ...schemas.api_schemas import ClipGenerateRequest, ClipResponse
from ...workers.job_manager import JobManager

router = APIRouter(prefix="/clips", tags=["Clips"])

@router.post("/generate", response_model=ClipResponse, status_code=status.HTTP_201_CREATED)
async def generate_clip(
    data: ClipGenerateRequest,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """
    Create a new clip record and enqueue the background clip rendering job.
    """
    # Verify project and video exist
    video_res = await db.execute(select(Video).where(Video.id == data.video_id))
    video = video_res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Source video not found")

    clip = Clip(
        project_id=data.project_id,
        video_id=data.video_id,
        title=data.title,
        start_time=data.start_time,
        end_time=data.end_time,
        duration_seconds=data.end_time - data.start_time,
        aspect_ratio=data.aspect_ratio,
        status="rendering"
    )
    db.add(clip)
    await db.commit()
    await db.refresh(clip)

    # Enqueue render job
    await JobManager.get_instance().enqueue_job(
        job_type="generate_clip",
        project_id=data.project_id,
        params={
            "clip_id": clip.id,
            "video_id": data.video_id,
            "start_time": data.start_time,
            "end_time": data.end_time,
            "aspect_ratio": data.aspect_ratio,
            "reframe_mode": data.reframe_mode
        }
    )

    return clip

@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve clip details by ID."""
    res = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = res.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip

@router.get("/project/{project_id}", response_model=List[ClipResponse])
async def get_project_clips(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve all clips belonging to a project."""
    res = await db.execute(
        select(Clip).where(Clip.project_id == project_id).order_by(Clip.created_at.desc())
    )
    return res.scalars().all()

@router.delete("/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clip(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Delete a clip record and its associated rendered media files."""
    res = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = res.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Safely remove rendered files
    if clip.file_path and os.path.isfile(clip.file_path):
        try:
            os.remove(clip.file_path)
        except Exception:
            pass

    if clip.thumbnail_path and os.path.isfile(clip.thumbnail_path):
        try:
            os.remove(clip.thumbnail_path)
        except Exception:
            pass

    await db.delete(clip)
    await db.commit()
    return None

@router.get("/{clip_id}/stream")
async def stream_clip(
    clip_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Stream rendered clip video with byte-range support."""
    res = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = res.scalar_one_or_none()
    if not clip or not clip.file_path or not os.path.isfile(clip.file_path):
        raise HTTPException(status_code=404, detail="Rendered clip video not found on disk")

    return stream_file_with_ranges(request=request, file_path=clip.file_path)

@router.get("/{clip_id}/thumbnail")
async def get_clip_thumbnail(
    clip_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Serve the clip's thumbnail image."""
    res = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = res.scalar_one_or_none()
    if not clip or not clip.thumbnail_path or not os.path.isfile(clip.thumbnail_path):
        raise HTTPException(status_code=404, detail="Clip thumbnail not found")

    return FileResponse(clip.thumbnail_path, media_type="image/jpeg")
