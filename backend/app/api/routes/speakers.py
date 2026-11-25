"""
ClipForge AI - Speaker Diarization API Routes
Provides endpoints for offline speaker diarization, turn listing, manual reassignment,
and speaker profile management.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_db
from ...core.security import verify_session_token
from ...db.models import AudioAnalysis, Job, Speaker, SpeakerTurn, Video
from ...schemas.speaker_schemas import (
    DiarizationConfigSchema,
    DiarizationSummaryResponse,
    SpeakerCapabilitiesResponse,
    SpeakerSchema,
    SpeakerTurnSchema,
    StartDiarizationRequest,
    UpdateSpeakerRequest,
    UpdateSpeakerTurnRequest,
)
from ...services.speaker_analysis_service import SpeakerAnalysisService
from ...workers.job_manager import JobManager

router = APIRouter(tags=["Speaker Diarization & Intelligence"], dependencies=[Depends(verify_session_token)])


@router.get("/speakers/capabilities", response_model=SpeakerCapabilitiesResponse)
async def get_speaker_capabilities():
    """Return local 3D-Speaker CAM++ model capabilities, runtime device, and default config."""
    return SpeakerAnalysisService.get_capabilities()


@router.post("/audio-analysis/{analysis_id}/diarize", status_code=status.HTTP_202_ACCEPTED)
async def start_speaker_diarization(
    analysis_id: str,
    req: Optional[StartDiarizationRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Enqueue a background job to execute offline speaker diarization on an existing audio analysis.
    """
    analysis_res = await db.execute(select(AudioAnalysis).where(AudioAnalysis.id == analysis_id))
    analysis = analysis_res.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="AudioAnalysis not found")

    config_dict = None
    force_reprocess = False
    if req:
        force_reprocess = req.force_reprocess
        if req.config:
            config_dict = req.config.model_dump()

    jm = JobManager.get_instance()
    await jm.start()

    job = await jm.enqueue_job(
        job_type="speaker_diarization",
        project_id=analysis.project_id,
        params={
            "analysis_id": analysis.id,
            "video_id": analysis.video_id,
            "force_reprocess": force_reprocess,
            "config": config_dict,
        },
    )

    return {
        "job_id": job.id,
        "status": "queued",
        "message": "Speaker diarization queued successfully",
        "analysis_id": analysis.id,
    }


@router.get("/audio-analysis/{analysis_id}/speakers", response_model=List[SpeakerSchema])
async def get_speakers_for_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch all recognized speakers for an audio analysis."""
    analysis_res = await db.execute(select(AudioAnalysis).where(AudioAnalysis.id == analysis_id))
    if not analysis_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="AudioAnalysis not found")

    return await SpeakerAnalysisService.get_speakers_for_analysis(db, analysis_id)


@router.get("/audio-analysis/{analysis_id}/speaker-turns", response_model=List[SpeakerTurnSchema])
async def get_speaker_turns_for_analysis(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch all speaker turn intervals for an audio analysis."""
    analysis_res = await db.execute(select(AudioAnalysis).where(AudioAnalysis.id == analysis_id))
    if not analysis_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="AudioAnalysis not found")

    return await SpeakerAnalysisService.get_speaker_turns_for_analysis(db, analysis_id)


@router.get("/audio-analysis/{analysis_id}/diarization", response_model=DiarizationSummaryResponse)
async def get_diarization_summary(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch complete diarization summary including speakers, turns, and performance metrics."""
    summary = await SpeakerAnalysisService.get_diarization_summary(db, analysis_id)
    if not summary:
        raise HTTPException(status_code=404, detail="AudioAnalysis not found")
    return summary


@router.patch("/speaker-turns/{turn_id}", response_model=SpeakerTurnSchema)
async def update_speaker_turn(
    turn_id: str,
    req: UpdateSpeakerTurnRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually update a speaker turn (reassign speaker or adjust boundaries).
    """
    updated = await SpeakerAnalysisService.update_speaker_turn(db, turn_id, req)
    if not updated:
        raise HTTPException(status_code=404, detail="SpeakerTurn not found")
    return updated


@router.patch("/speakers/{speaker_id}", response_model=SpeakerSchema)
async def update_speaker(
    speaker_id: str,
    req: UpdateSpeakerRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update speaker display name or UI color.
    """
    updated = await SpeakerAnalysisService.update_speaker(db, speaker_id, req)
    if not updated:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return updated


@router.delete("/audio-analysis/{analysis_id}/speakers", status_code=status.HTTP_200_OK)
async def delete_diarization_results(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete all diarization speakers, turns, and embeddings for an audio analysis.
    """
    analysis_res = await db.execute(select(AudioAnalysis).where(AudioAnalysis.id == analysis_id))
    if not analysis_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="AudioAnalysis not found")

    await SpeakerAnalysisService.delete_diarization_results(db, analysis_id)
    return {"status": "deleted", "analysis_id": analysis_id}
