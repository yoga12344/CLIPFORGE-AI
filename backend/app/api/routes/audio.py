"""
ClipForge AI - Audio Intelligence & Voice Activity Detection API Routes
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.security import verify_session_token
from ...core.database import get_db
from ...db.models import AudioAnalysis, Job, Video
from ...schemas.audio_schemas import (
    AudioAnalysisResponse,
    AudioCapabilitiesResponse,
    SpeechIntervalSchema,
    StartAudioAnalysisRequest,
)
from ...services.audio_analysis_service import AudioAnalysisService
from ...workers.job_manager import JobManager

router = APIRouter(tags=["Audio Intelligence & VAD"], dependencies=[Depends(verify_session_token)])


@router.get("/audio/capabilities", response_model=AudioCapabilitiesResponse)
async def get_audio_capabilities():
    """
    Return local VAD engine capabilities, model specifications, and default parameters.
    """
    return AudioAnalysisService.get_capabilities()


@router.post("/videos/{video_id}/audio-analysis", status_code=status.HTTP_202_ACCEPTED)
async def start_audio_analysis(
    video_id: str,
    req: Optional[StartAudioAnalysisRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Enqueue a background job to extract audio, compute signal health metrics,
    and detect voice activity intervals using local Silero VAD.
    """
    v_res = await db.execute(select(Video).where(Video.id == video_id))
    video = v_res.scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    config_dict = None
    force_reprocess = False
    if req:
        force_reprocess = req.force_reprocess
        if req.config:
            config_dict = req.config.model_dump()

    jm = JobManager.get_instance()
    await jm.start()

    job = await jm.enqueue_job(
        job_type="audio_analysis",
        project_id=video.project_id,
        params={
            "video_id": video.id,
            "force_reprocess": force_reprocess,
            "config": config_dict,
        },
    )

    return {
        "job_id": job.id,
        "status": "queued",
        "message": "Audio analysis queued successfully",
        "video_id": video.id,
    }


@router.get("/videos/{video_id}/audio-analysis", response_model=AudioAnalysisResponse)
async def get_latest_audio_analysis(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the most recent completed AudioAnalysis and speech intervals for a video.
    """
    analysis = await AudioAnalysisService.get_latest_analysis_for_video(db, video_id)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"No audio analysis found for video {video_id}",
        )
    return AudioAnalysisService.to_response_schema(analysis)


@router.get("/audio-analysis/{analysis_id}/intervals", response_model=List[SpeechIntervalSchema])
async def get_audio_intervals(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all speech intervals for a specific AudioAnalysis record.
    """
    analysis = await AudioAnalysisService.get_analysis_by_id(db, analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"Audio analysis {analysis_id} not found",
        )
    intervals = await AudioAnalysisService.get_intervals_for_analysis(db, analysis_id)
    return [
        SpeechIntervalSchema(
            id=iv.id,
            analysis_id=iv.analysis_id,
            start_time=iv.start_time,
            end_time=iv.end_time,
            duration=iv.duration,
            speech_probability=iv.speech_probability,
            confidence=iv.confidence,
            source=iv.source,
            created_at=iv.created_at,
        )
        for iv in intervals
    ]


@router.post("/audio-analysis/{analysis_id}/cancel")
async def cancel_audio_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel an active or queued audio analysis job.
    """
    analysis = await AudioAnalysisService.get_analysis_by_id(db, analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"Audio analysis {analysis_id} not found",
        )

    # Find active or queued job for this video
    j_res = await db.execute(
        select(Job)
        .where(
            Job.job_type == "audio_analysis",
            Job.project_id == analysis.project_id,
            Job.status.in_(["queued", "running"]),
        )
    )
    jobs = j_res.scalars().all()
    jm = JobManager.get_instance()
    cancelled_any = False
    for j in jobs:
        if j.params and j.params.get("video_id") == analysis.video_id:
            await jm.cancel_job(j.id)
            cancelled_any = True

    analysis.status = "cancelled"
    await db.commit()

    return {
        "status": "cancelled",
        "analysis_id": analysis_id,
        "job_cancelled": cancelled_any,
    }
