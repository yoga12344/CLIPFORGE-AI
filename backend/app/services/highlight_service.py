"""
ClipForge AI - Highlight Service
Provides database operations, status workflows, manual timestamp editing, and clip creation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, desc, asc

from ..db.models import HighlightCandidate, Clip, Video, Project, ClipScore
from ..ai.highlights.highlight_analyzer import EnrichedHighlightCandidate

logger = logging.getLogger("clipforge.services.highlights")


class HighlightService:
    @classmethod
    async def save_candidates(
        cls,
        db: AsyncSession,
        video_id: str,
        project_id: str,
        candidates: List[EnrichedHighlightCandidate],
        transcript_id: Optional[str] = None,
        model_name: str = "qwen-2.5-3b"
    ) -> List[HighlightCandidate]:
        """Save a batch of discovered candidates into SQLite."""
        db_records: List[HighlightCandidate] = []

        for c in candidates:
            rec = HighlightCandidate(
                project_id=project_id,
                video_id=video_id,
                transcript_id=transcript_id,
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
                score_breakdown=c.score_breakdown.model_dump() if hasattr(c.score_breakdown, "model_dump") else c.score_breakdown,
                model_name=model_name,
                generation_method=c.generation_method,
                status=c.status,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(rec)
            db_records.append(rec)

        await db.commit()
        for r in db_records:
            await db.refresh(r)

        logger.info(f"Persisted {len(db_records)} highlight candidates for video {video_id}.")
        return db_records

    @classmethod
    async def get_by_id(cls, db: AsyncSession, candidate_id: str) -> Optional[HighlightCandidate]:
        res = await db.execute(
            select(HighlightCandidate).where(HighlightCandidate.id == candidate_id)
        )
        return res.scalar_one_or_none()

    @classmethod
    async def get_for_video(
        cls,
        db: AsyncSession,
        video_id: str,
        status: Optional[str] = None,
        sort_by: str = "overall_score"
    ) -> List[HighlightCandidate]:
        """Retrieve candidates for video with optional status filter and sorting."""
        stmt = select(HighlightCandidate).where(HighlightCandidate.video_id == video_id)

        if status:
            stmt = stmt.where(HighlightCandidate.status == status.lower())

        if sort_by == "start_time":
            stmt = stmt.order_by(asc(HighlightCandidate.start_time))
        elif sort_by == "duration":
            stmt = stmt.order_by(desc(HighlightCandidate.duration_seconds))
        else:
            stmt = stmt.order_by(desc(HighlightCandidate.overall_score))

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_for_project(
        cls,
        db: AsyncSession,
        project_id: str,
        status: Optional[str] = None
    ) -> List[HighlightCandidate]:
        stmt = select(HighlightCandidate).where(HighlightCandidate.project_id == project_id)
        if status:
            stmt = stmt.where(HighlightCandidate.status == status.lower())
        stmt = stmt.order_by(desc(HighlightCandidate.overall_score))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def update_status(
        cls,
        db: AsyncSession,
        candidate_id: str,
        new_status: str
    ) -> Optional[HighlightCandidate]:
        """Update candidate status: discovered, approved, rejected, edited, ready_for_render."""
        candidate = await cls.get_by_id(db, candidate_id)
        if not candidate:
            return None

        valid_statuses = ["discovered", "approved", "rejected", "edited", "ready_for_render"]
        if new_status.lower() not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid_statuses}")

        candidate.status = new_status.lower()
        candidate.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(candidate)
        return candidate

    @classmethod
    async def update_candidate(
        cls,
        db: AsyncSession,
        candidate_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        hook: Optional[str] = None
    ) -> Optional[HighlightCandidate]:
        """Allow manual editing of candidate timestamps and title."""
        candidate = await cls.get_by_id(db, candidate_id)
        if not candidate:
            return None

        if start_time is not None:
            if start_time < 0:
                raise ValueError("start_time cannot be negative")
            candidate.start_time = round(start_time, 2)

        if end_time is not None:
            if end_time <= candidate.start_time:
                raise ValueError("end_time must be strictly greater than start_time")
            candidate.end_time = round(end_time, 2)

        candidate.duration_seconds = round(candidate.end_time - candidate.start_time, 2)

        if title is not None and title.strip():
            candidate.title = title.strip()
        if summary is not None:
            candidate.summary = summary.strip()
        if hook is not None:
            candidate.hook = hook.strip()

        candidate.status = "edited"
        candidate.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(candidate)
        return candidate

    @classmethod
    async def delete_candidate(cls, db: AsyncSession, candidate_id: str) -> bool:
        candidate = await cls.get_by_id(db, candidate_id)
        if not candidate:
            return False
        await db.delete(candidate)
        await db.commit()
        return True

    @classmethod
    async def create_clip_from_candidate(
        cls,
        db: AsyncSession,
        candidate_id: str,
        aspect_ratio: str = "9:16",
        reframe_mode: str = "center_crop"
    ) -> Clip:
        """
        Transition an approved/edited candidate into an actual Clip entity.
        Reuses existing Clip and ClipScore models.
        """
        candidate = await cls.get_by_id(db, candidate_id)
        if not candidate:
            raise FileNotFoundError(f"Candidate {candidate_id} not found.")

        # Create Clip record
        clip = Clip(
            project_id=candidate.project_id,
            video_id=candidate.video_id,
            title=candidate.title,
            hook_sentence=candidate.hook,
            reason=candidate.reason,
            start_time=candidate.start_time,
            end_time=candidate.end_time,
            duration_seconds=candidate.duration_seconds,
            aspect_ratio=aspect_ratio,
            transcript_excerpt=candidate.transcript_excerpt or candidate.key_quote,
            status="ready",
            edl_settings={
                "reframe_mode": reframe_mode,
                "aspect_ratio": aspect_ratio,
                "generation_source": "ai_highlight",
                "candidate_id": candidate.id,
                "candidate_score": candidate.overall_score
            }
        )
        db.add(clip)
        await db.flush()

        # Create companion ClipScore record
        breakdown = candidate.score_breakdown or {}
        score = ClipScore(
            clip_id=clip.id,
            overall_score=candidate.overall_score,
            hook_score=int(breakdown.get("hook_strength", 16) * 5),
            flow_score=int(breakdown.get("narrative_completeness", 16) * 5),
            engagement_score=int(breakdown.get("interest_level", 8) * 10),
            value_score=int(breakdown.get("content_value", 16) * 5),
            dimensions=breakdown
        )
        db.add(score)

        # Update candidate state
        candidate.clip_id = clip.id
        candidate.status = "ready_for_render"
        candidate.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(clip)
        logger.info(f"Created Clip {clip.id} from Highlight Candidate {candidate_id}.")
        return clip
