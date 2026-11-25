"""
ClipForge AI - Highlight Candidate Discovery & Management Routes
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.security import verify_session_token
from ...core.database import get_db
from ...db.models import HighlightCandidate, Video, Project
from ...services.highlight_service import HighlightService
from ...workers.job_manager import JobManager

router = APIRouter(tags=["AI Highlights"], dependencies=[Depends(verify_session_token)])


class AnalyzeHighlightsRequest(BaseModel):
    model_name: str = "qwen-2.5-3b"
    content_type: str = "general"
    target_duration_min: float = 30.0
    target_duration_max: float = 60.0
    max_candidates: int = 5
    auto_create_clips: bool = False


class UpdateCandidateRequest(BaseModel):
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    hook: Optional[str] = None


class CreateClipFromHighlightRequest(BaseModel):
    aspect_ratio: str = "9:16"
    reframe_mode: str = "center_crop"


class HighlightCandidateResponse(BaseModel):
    id: str
    project_id: str
    video_id: str
    transcript_id: Optional[str] = None
    clip_id: Optional[str] = None
    start_time: float
    end_time: float
    duration_seconds: float
    title: str
    hook: Optional[str] = None
    summary: Optional[str] = None
    reason: Optional[str] = None
    category: str
    key_quote: Optional[str] = None
    transcript_excerpt: Optional[str] = None
    overall_score: int
    score_breakdown: Optional[Dict[str, Any]] = None
    model_name: str
    generation_method: str
    status: str
    created_at: Any
    updated_at: Any


def format_candidate(c: HighlightCandidate) -> HighlightCandidateResponse:
    return HighlightCandidateResponse(
        id=c.id,
        project_id=c.project_id,
        video_id=c.video_id,
        transcript_id=c.transcript_id,
        clip_id=c.clip_id,
        start_time=c.start_time,
        end_time=c.end_time,
        duration_seconds=c.duration_seconds,
        title=c.title,
        hook=c.hook,
        summary=c.summary,
        reason=c.reason,
        category=c.category,
        key_quote=c.key_quote,
        transcript_excerpt=c.transcript_excerpt,
        overall_score=c.overall_score,
        score_breakdown=c.score_breakdown,
        model_name=c.model_name,
        generation_method=c.generation_method,
        status=c.status,
        created_at=c.created_at,
        updated_at=c.updated_at
    )


# --- Video-Level Endpoints ---

@router.post("/videos/{video_id}/analyze-highlights")
async def analyze_video_highlights(
    video_id: str,
    req: AnalyzeHighlightsRequest,
    db: AsyncSession = Depends(get_db)
):
    """Enqueue an analyze_highlights background job."""
    v_res = await db.execute(select(Video).where(Video.id == video_id))
    video = v_res.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found."
        )

    jm = JobManager.get_instance()
    await jm.start()

    job = await jm.enqueue_job(
        job_type="analyze_highlights",
        project_id=video.project_id,
        params={
            "video_id": video_id,
            "model_name": req.model_name,
            "content_type": req.content_type,
            "target_duration_min": req.target_duration_min,
            "target_duration_max": req.target_duration_max,
            "max_candidates": req.max_candidates,
            "auto_create_clips": req.auto_create_clips,
        }
    )

    return {
        "job_id": job.id,
        "status": job.status,
        "video_id": video_id,
        "project_id": video.project_id,
        "message": "AI highlight analysis queued successfully."
    }


@router.get("/videos/{video_id}/highlight-candidates", response_model=List[HighlightCandidateResponse])
async def list_video_highlight_candidates(
    video_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    sort_by: str = Query("overall_score", pattern="^(overall_score|start_time|duration)$"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all discovered highlight candidates for a video."""
    candidates = await HighlightService.get_for_video(
        db=db,
        video_id=video_id,
        status=status_filter,
        sort_by=sort_by
    )
    return [format_candidate(c) for c in candidates]


# --- Project-Level Endpoints ---

@router.get("/projects/{project_id}/highlights", response_model=List[HighlightCandidateResponse])
async def list_project_highlight_candidates(
    project_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all candidates across a project."""
    candidates = await HighlightService.get_for_project(
        db=db,
        project_id=project_id,
        status=status_filter
    )
    return [format_candidate(c) for c in candidates]


# --- Individual Candidate Operations ---

@router.get("/highlights/{candidate_id}", response_model=HighlightCandidateResponse)
async def get_highlight_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve a single highlight candidate by ID."""
    candidate = await HighlightService.get_by_id(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Highlight candidate '{candidate_id}' not found."
        )
    return format_candidate(candidate)


@router.patch("/highlights/{candidate_id}", response_model=HighlightCandidateResponse)
async def update_highlight_candidate(
    candidate_id: str,
    req: UpdateCandidateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Edit candidate boundaries (start_time, end_time) or title."""
    try:
        updated = await HighlightService.update_candidate(
            db=db,
            candidate_id=candidate_id,
            start_time=req.start_time,
            end_time=req.end_time,
            title=req.title,
            summary=req.summary,
            hook=req.hook
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate '{candidate_id}' not found."
            )
        return format_candidate(updated)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )


@router.post("/highlights/{candidate_id}/approve", response_model=HighlightCandidateResponse)
async def approve_highlight_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Mark candidate as approved."""
    candidate = await HighlightService.update_status(db, candidate_id, "approved")
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found."
        )
    return format_candidate(candidate)


@router.post("/highlights/{candidate_id}/reject", response_model=HighlightCandidateResponse)
async def reject_highlight_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Mark candidate as rejected."""
    candidate = await HighlightService.update_status(db, candidate_id, "rejected")
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found."
        )
    return format_candidate(candidate)


@router.post("/highlights/{candidate_id}/create-clip")
async def create_clip_from_candidate(
    candidate_id: str,
    req: CreateClipFromHighlightRequest,
    db: AsyncSession = Depends(get_db)
):
    """Convert an approved candidate into a permanent Clip and queue its rendering."""
    try:
        clip = await HighlightService.create_clip_from_candidate(
            db=db,
            candidate_id=candidate_id,
            aspect_ratio=req.aspect_ratio,
            reframe_mode=req.reframe_mode
        )

        # Trigger background rendering of the clip using Phase 3 ClipGenerator
        jm = JobManager.get_instance()
        await jm.start()

        job = await jm.enqueue_job(
            job_type="generate_clip",
            project_id=clip.project_id,
            params={
                "clip_id": clip.id,
                "video_id": clip.video_id,
                "start_time": clip.start_time,
                "end_time": clip.end_time,
                "aspect_ratio": req.aspect_ratio,
                "reframe_mode": req.reframe_mode
            }
        )

        return {
            "clip_id": clip.id,
            "job_id": job.id,
            "status": "rendering_queued",
            "title": clip.title,
            "duration_seconds": clip.duration_seconds,
            "aspect_ratio": clip.aspect_ratio
        }

    except FileNotFoundError as fnf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/highlights/{candidate_id}")
async def delete_highlight_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a highlight candidate."""
    deleted = await HighlightService.delete_candidate(db, candidate_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found."
        )
    return {"status": "deleted", "candidate_id": candidate_id}
