"""
ClipForge AI - Final Export & Render Queue API Routes
"""

import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from ...core.database import get_db
from ...core.security import verify_session_token
from ...core.streaming import stream_file_with_ranges
from ...db.models import Clip, Export, Project
from ...schemas.subtitle_schemas import ExportResponse, RenderExportRequest
from ...workers.job_manager import JobManager

router = APIRouter(tags=["Exports & Final Render"], dependencies=[Depends(verify_session_token)])


@router.post("/clips/{clip_id}/render", status_code=status.HTTP_202_ACCEPTED)
async def start_clip_render(
    clip_id: str,
    req: RenderExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enqueue a background final rendering job with smart reframing and karaoke subtitle burn-in."""
    res = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = res.scalars().first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    jm = JobManager.get_instance()
    await jm.start()

    job = await jm.enqueue_job(
        job_type="render_export",
        project_id=clip.project_id,
        params={
            "clip_id": clip.id,
            "preset_id": req.preset_id,
            "resolution": req.resolution,
            "fps": req.fps,
            "bitrate_kbps": req.bitrate_kbps,
            "burn_subtitles": req.burn_subtitles,
            "reframe_mode": req.reframe_mode,
            "use_vision_tracking": req.use_vision_tracking,
            "custom_style": req.custom_style,
            "codec": req.codec,
        },
    )

    return {
        "job_id": job.id,
        "status": "queued",
        "clip_id": clip.id,
        "resolution": req.resolution,
        "burn_subtitles": req.burn_subtitles,
        "message": "Final render job queued successfully",
    }


@router.get("/exports", response_model=List[ExportResponse])
async def list_all_exports(db: AsyncSession = Depends(get_db)):
    """Retrieve all exports across the entire application."""
    res = await db.execute(select(Export).order_by(desc(Export.created_at)))
    return res.scalars().all()


@router.get("/clips/{clip_id}/exports", response_model=List[ExportResponse])
async def list_clip_exports(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve all rendered exports for a specific clip."""
    res = await db.execute(select(Export).where(Export.clip_id == clip_id).order_by(desc(Export.created_at)))
    return res.scalars().all()


@router.get("/projects/{project_id}/exports", response_model=List[ExportResponse])
async def list_project_exports(project_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve all exports across a project."""
    stmt = (
        select(Export)
        .join(Clip, Export.clip_id == Clip.id)
        .where(Clip.project_id == project_id)
        .order_by(desc(Export.created_at))
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/exports/{export_id}", response_model=ExportResponse)
async def get_export_details(export_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch details of a single export record."""
    res = await db.execute(select(Export).where(Export.id == export_id))
    export_rec = res.scalars().first()
    if not export_rec:
        raise HTTPException(status_code=404, detail="Export not found")
    return export_rec


@router.get("/exports/{export_id}/stream")
async def stream_export(
    export_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stream exported MP4 video with HTTP 206 byte-range support."""
    res = await db.execute(select(Export).where(Export.id == export_id))
    export_rec = res.scalars().first()
    if not export_rec or not export_rec.output_path or not os.path.isfile(export_rec.output_path):
        raise HTTPException(status_code=404, detail="Exported video file not found on disk")

    return stream_file_with_ranges(request=request, file_path=export_rec.output_path)


@router.get("/exports/{export_id}/download")
async def download_export(export_id: str, db: AsyncSession = Depends(get_db)):
    """Download exported MP4 file."""
    res = await db.execute(select(Export).where(Export.id == export_id))
    export_rec = res.scalars().first()
    if not export_rec or not export_rec.output_path or not os.path.isfile(export_rec.output_path):
        raise HTTPException(status_code=404, detail="Exported video file not found on disk")

    filename = os.path.basename(export_rec.output_path)
    return FileResponse(export_rec.output_path, media_type="video/mp4", filename=filename)


@router.delete("/exports/{export_id}")
async def delete_export(export_id: str, db: AsyncSession = Depends(get_db)):
    """Delete export record and remove output file from disk."""
    res = await db.execute(select(Export).where(Export.id == export_id))
    export_rec = res.scalars().first()
    if not export_rec:
        raise HTTPException(status_code=404, detail="Export not found")

    if export_rec.output_path and os.path.isfile(export_rec.output_path):
        try:
            os.remove(export_rec.output_path)
        except Exception:
            pass

    await db.delete(export_rec)
    await db.commit()
    return {"success": True, "message": "Export deleted successfully"}
