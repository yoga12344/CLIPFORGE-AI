"""
ClipForge AI - Audio-Visual Active Speaker API Routes
Provides endpoints for active speaker intervals, speaker-face identity association,
and manual association overrides.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import verify_session_token
from ...db.models import ActiveSpeakerInterval, Speaker, SpeakerFaceAssociation, Video
from ...ai.audio_visual.schemas import ActiveSpeakerSegment, SpeakerFaceMatch

router = APIRouter(tags=["Active Speaker Detection & AV Fusion"], dependencies=[Depends(verify_session_token)])


class ActiveSpeakerCapabilitiesResponse(BaseModel):
    model_name: str = "Light-ASD & MediaPipe Face Mesh V2"
    framework: str = "ONNX Runtime (CPU Execution Provider)"
    face_mesh_points: int = 478
    asd_parameter_count: str = "1.0M parameters (0.6 GFLOPs)"
    offline_only: bool = True
    supports_manual_override: bool = True


class UpdateSpeakerFaceAssociationRequest(BaseModel):
    face_track_id: Optional[str] = Field(None, description="Face track ID or null for off-screen")
    is_off_screen: bool = Field(False, description="Explicitly mark speaker as off-camera")


class ActiveSpeakerResponse(BaseModel):
    video_id: str
    active_segments: List[ActiveSpeakerSegment]
    associations: List[SpeakerFaceMatch]
    total_active_speech_seconds: float


@router.get("/active-speakers/capabilities", response_model=ActiveSpeakerCapabilitiesResponse)
async def get_active_speaker_capabilities():
    """Return runtime active speaker models and CPU inference engine status."""
    return ActiveSpeakerCapabilitiesResponse()


@router.get("/videos/{video_id}/active-speakers", response_model=ActiveSpeakerResponse)
async def get_video_active_speakers(video_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch all active speaker intervals and speaker-face associations for a video."""
    video_res = await db.execute(select(Video).where(Video.id == video_id))
    video = video_res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    intervals_res = await db.execute(
        select(ActiveSpeakerInterval)
        .where(ActiveSpeakerInterval.video_id == video_id)
        .order_by(ActiveSpeakerInterval.start_time)
    )
    intervals = intervals_res.scalars().all()

    assoc_res = await db.execute(
        select(SpeakerFaceAssociation).where(SpeakerFaceAssociation.video_id == video_id)
    )
    associations = assoc_res.scalars().all()

    active_segs = [
        ActiveSpeakerSegment(
            id=i.id,
            start_time=i.start_time,
            end_time=i.end_time,
            duration=i.duration,
            face_track_id=i.face_track_id,
            speaker_id=i.speaker_id,
            confidence=i.confidence,
            speaking_score=i.speaking_score,
            state=i.state,
        )
        for i in intervals
    ]

    matches = [
        SpeakerFaceMatch(
            id=a.id,
            speaker_id=a.speaker_id,
            face_track_id=a.face_track_id,
            confidence=a.confidence,
            overlap_duration=a.overlap_duration,
            is_manual=a.is_manual,
            is_off_screen=a.is_off_screen,
            evidence_notes=a.evidence_notes,
        )
        for a in associations
    ]

    total_active = sum(s.duration for s in active_segs if s.state == "active_speaker")

    return ActiveSpeakerResponse(
        video_id=video_id,
        active_segments=active_segs,
        associations=matches,
        total_active_speech_seconds=round(total_active, 2),
    )


@router.put("/videos/{video_id}/speakers/{speaker_id}/associate", response_model=SpeakerFaceMatch)
async def update_speaker_face_association(
    video_id: str,
    speaker_id: str,
    req: UpdateSpeakerFaceAssociationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually assign or reassign a speaker identity to a face track, or mark as off-screen.
    Saves is_manual = True to protect from automatic re-clustering.
    """
    spk_res = await db.execute(select(Speaker).where(Speaker.id == speaker_id))
    spk = spk_res.scalar_one_or_none()
    if not spk:
        raise HTTPException(status_code=404, detail="Speaker not found")

    assoc_res = await db.execute(
        select(SpeakerFaceAssociation).where(
            SpeakerFaceAssociation.video_id == video_id,
            SpeakerFaceAssociation.speaker_id == speaker_id,
        )
    )
    assoc = assoc_res.scalar_one_or_none()

    if not assoc:
        assoc = SpeakerFaceAssociation(
            video_id=video_id,
            speaker_id=speaker_id,
            face_track_id=req.face_track_id,
            confidence=1.0,
            overlap_duration=0.0,
            is_manual=True,
            is_off_screen=req.is_off_screen or (req.face_track_id is None),
            evidence_notes="User manual override",
        )
        db.add(assoc)
    else:
        assoc.face_track_id = req.face_track_id
        assoc.is_manual = True
        assoc.is_off_screen = req.is_off_screen or (req.face_track_id is None)
        assoc.confidence = 1.0
        assoc.evidence_notes = "User manual override"

    await db.commit()
    await db.refresh(assoc)

    return SpeakerFaceMatch(
        id=assoc.id,
        speaker_id=assoc.speaker_id,
        face_track_id=assoc.face_track_id,
        confidence=assoc.confidence,
        overlap_duration=assoc.overlap_duration,
        is_manual=assoc.is_manual,
        is_off_screen=assoc.is_off_screen,
        evidence_notes=assoc.evidence_notes,
    )


@router.delete("/videos/{video_id}/active-speakers", status_code=status.HTTP_204_NO_CONTENT)
async def delete_active_speaker_analysis(video_id: str, db: AsyncSession = Depends(get_db)):
    """Delete active speaker intervals and associations without deleting the video or face tracks."""
    await db.execute(delete(ActiveSpeakerInterval).where(ActiveSpeakerInterval.video_id == video_id))
    await db.execute(delete(SpeakerFaceAssociation).where(SpeakerFaceAssociation.video_id == video_id))
    await db.commit()
    return None
