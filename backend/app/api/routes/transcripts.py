from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.security import verify_session_token
from ...db.models import Transcript, TranscriptSegment, Video
from ...services.transcript_repository import TranscriptRepository
from ...services.transcription_service import TranscriptionService
from ...schemas.api_schemas import (
    TranscriptResponse, TranscriptSegmentResponse, TranscriptUpdateSchema,
    SegmentUpdateSchema, TranscribeVideoRequest, VideoActionResponse
)

router = APIRouter(prefix="", tags=["Transcripts"])

@router.get("/videos/{video_id}/transcript", response_model=TranscriptResponse)
async def get_video_transcript(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve full transcript and word-level segments for a video."""
    transcript = await TranscriptRepository.get_by_video_id(db, video_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="No transcript found for this video")
    return transcript

@router.get("/transcripts/{transcript_id}", response_model=TranscriptResponse)
async def get_transcript_by_id(
    transcript_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve transcript by transcript ID."""
    transcript = await TranscriptRepository.get_by_id(db, transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript

@router.patch("/transcripts/{transcript_id}", response_model=TranscriptResponse)
async def update_transcript(
    transcript_id: str,
    data: TranscriptUpdateSchema,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Update top-level transcript text or language."""
    updated = await TranscriptRepository.update_transcript_metadata(
        db=db,
        transcript_id=transcript_id,
        full_text=data.full_text,
        language=data.language
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return updated

@router.get("/transcripts/{transcript_id}/segments", response_model=List[TranscriptSegmentResponse])
async def get_transcript_segments(
    transcript_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """List all timestamped segments for a transcript."""
    transcript = await TranscriptRepository.get_by_id(db, transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript.segments

@router.patch("/transcripts/segments/{segment_id}", response_model=TranscriptSegmentResponse)
async def update_segment_text(
    segment_id: str,
    data: SegmentUpdateSchema,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Edit text for a specific transcript segment."""
    seg = await TranscriptRepository.update_segment_text(
        db=db,
        segment_id=segment_id,
        new_text=data.text
    )
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    return seg

@router.post("/transcripts/{transcript_id}/retranscribe", response_model=VideoActionResponse)
async def retranscribe(
    transcript_id: str,
    data: Optional[TranscribeVideoRequest] = None,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Re-run transcription for the video associated with this transcript."""
    transcript = await TranscriptRepository.get_by_id(db, transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    job = await TranscriptionService.enqueue_transcription(
        video_id=transcript.video_id,
        config=data
    )
    return VideoActionResponse(
        job_id=job.id,
        message="Retranscription job queued successfully."
    )

@router.delete("/transcripts/{transcript_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transcript(
    transcript_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Delete transcript and all associated word segments."""
    deleted = await TranscriptRepository.delete_transcript(db, transcript_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return None
