import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload

from ..db.models import Transcript, TranscriptSegment
from ..ai.transcription_engine import TranscriptionResult

logger = logging.getLogger("clipforge.services.transcripts")

class TranscriptRepository:
    @classmethod
    async def get_by_video_id(cls, db: AsyncSession, video_id: str) -> Optional[Transcript]:
        """Fetch transcript by video ID with segments eagerly loaded."""
        res = await db.execute(
            select(Transcript)
            .where(Transcript.video_id == video_id)
            .options(selectinload(Transcript.segments))
        )
        return res.scalar_one_or_none()

    @classmethod
    async def get_by_id(cls, db: AsyncSession, transcript_id: str) -> Optional[Transcript]:
        """Fetch transcript by primary ID with segments eagerly loaded."""
        res = await db.execute(
            select(Transcript)
            .where(Transcript.id == transcript_id)
            .options(selectinload(Transcript.segments))
        )
        return res.scalar_one_or_none()

    @classmethod
    async def save_transcription_result(
        cls,
        db: AsyncSession,
        video_id: str,
        result: TranscriptionResult
    ) -> Transcript:
        """
        Persist a complete transcription result into SQLite with full word timestamps.
        If an existing transcript exists for this video, it is replaced atomically.
        """
        # Remove any existing transcript for this video
        existing = await cls.get_by_video_id(db, video_id)
        if existing:
            await db.delete(existing)
            await db.flush()

        transcript = Transcript(
            video_id=video_id,
            language=result.language,
            model_used=result.model_used,
            device_used=result.device_used,
            processing_duration_seconds=result.processing_duration_seconds,
            status="completed",
            task_type="transcribe",
            full_text=result.full_text,
            created_at=datetime.utcnow()
        )
        db.add(transcript)
        await db.flush()

        # Add segments
        for seg in result.segments:
            words_json = [w.model_dump() for w in seg.words]
            segment_row = TranscriptSegment(
                transcript_id=transcript.id,
                segment_index=seg.segment_index,
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
                words=words_json,
                confidence=seg.confidence
            )
            db.add(segment_row)

        await db.commit()
        return await cls.get_by_id(db, transcript.id)

    @classmethod
    async def update_segment_text(
        cls,
        db: AsyncSession,
        segment_id: str,
        new_text: str
    ) -> Optional[TranscriptSegment]:
        """Update segment text and refresh parent full_text."""
        res = await db.execute(
            select(TranscriptSegment).where(TranscriptSegment.id == segment_id)
        )
        seg = res.scalar_one_or_none()
        if not seg:
            return None

        seg.text = new_text.strip()
        await db.flush()

        # Refresh parent transcript full text
        all_segs_res = await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == seg.transcript_id)
            .order_by(TranscriptSegment.start_time.asc())
        )
        all_segs = all_segs_res.scalars().all()
        full_text = " ".join(s.text for s in all_segs)

        await db.execute(
            update(Transcript)
            .where(Transcript.id == seg.transcript_id)
            .values(full_text=full_text, updated_at=datetime.utcnow())
        )
        await db.commit()
        await db.refresh(seg)
        return seg

    @classmethod
    async def update_transcript_metadata(
        cls,
        db: AsyncSession,
        transcript_id: str,
        full_text: Optional[str] = None,
        language: Optional[str] = None
    ) -> Optional[Transcript]:
        """Update transcript top-level fields."""
        transcript = await cls.get_by_id(db, transcript_id)
        if not transcript:
            return None

        if full_text is not None:
            transcript.full_text = full_text
        if language is not None:
            transcript.language = language

        transcript.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(transcript)
        return transcript

    @classmethod
    async def delete_transcript(cls, db: AsyncSession, transcript_id: str) -> bool:
        """Delete a transcript and cascade delete its segments."""
        transcript = await cls.get_by_id(db, transcript_id)
        if not transcript:
            return False

        await db.delete(transcript)
        await db.commit()
        return True
