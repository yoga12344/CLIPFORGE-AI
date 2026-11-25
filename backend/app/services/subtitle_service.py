"""
ClipForge AI - Subtitle Service
Manages clip subtitle tracks, clip-relative timestamp transformations,
word-level editing, segment split/merge, validation, and preset persistence.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Clip, CaptionPreset, SubtitleTrack, Transcript, TranscriptSegment
from app.schemas.subtitle_schemas import (
    CaptionPresetSchema,
    SubtitleSegment,
    SubtitleTrackResponse,
    SubtitleWord,
)
from app.services.subtitle_renderer import DEFAULT_PRESETS

logger = logging.getLogger("clipforge.services.subtitles")


class SubtitleService:

    @classmethod
    async def ensure_default_presets(cls, db: AsyncSession):
        """Seed default presets if database table is empty."""
        res = await db.execute(select(CaptionPreset).limit(1))
        if res.scalars().first() is None:
            for p in DEFAULT_PRESETS:
                db_preset = CaptionPreset(
                    id=p.id,
                    name=p.name,
                    font_family=p.font_family,
                    font_size=p.font_size,
                    primary_color=p.primary_color,
                    highlight_color=p.highlight_color,
                    outline_color=p.outline_color,
                    outline_width=p.outline_width,
                    shadow_width=p.shadow_width,
                    bold=p.bold,
                    italic=p.italic,
                    alignment=p.alignment,
                    margin_v=p.margin_v,
                    margin_l=p.margin_l,
                    margin_r=p.margin_r,
                    max_words_per_line=p.max_words_per_line,
                    max_lines=p.max_lines,
                    bg_color=p.bg_color,
                    bg_padding=p.bg_padding,
                    animation_style=p.animation_style,
                    is_default=p.is_default,
                    created_at=datetime.utcnow(),
                )
                db.add(db_preset)
            await db.commit()

    @classmethod
    async def extract_subtitles_from_transcript(
        cls,
        db: AsyncSession,
        clip: Clip,
        preset_id: Optional[str] = None,
    ) -> SubtitleTrack:
        """
        Extract dialogue segments from parent video transcript and convert to clip-relative time.
        clip_time = source_time - clip.start_time
        """
        # Load transcript for source video
        stmt = (
            select(Transcript)
            .where(Transcript.video_id == clip.video_id)
            .options(selectinload(Transcript.segments))
        )
        res = await db.execute(stmt)
        transcript = res.scalars().first()

        clip_start = clip.start_time
        clip_end = clip.end_time
        clip_duration = max(0.1, clip_end - clip_start)

        extracted_segments: List[Dict[str, Any]] = []

        if transcript and transcript.segments:
            for s in transcript.segments:
                # Check segment overlap with clip boundaries
                if s.end_time < clip_start - 0.2 or s.start_time > clip_end + 0.2:
                    continue

                words_data = s.words or []
                filtered_words: List[Dict[str, Any]] = []

                if words_data:
                    for w in words_data:
                        w_start = float(w.get("start", s.start_time))
                        w_end = float(w.get("end", s.end_time))

                        # Include word if it falls within clip interval
                        if w_end >= clip_start - 0.1 and w_start <= clip_end + 0.1:
                            rel_start = max(0.0, min(clip_duration, w_start - clip_start))
                            rel_end = max(rel_start + 0.05, min(clip_duration, w_end - clip_start))

                            filtered_words.append({
                                "word": str(w.get("word", "")).strip(),
                                "start": round(rel_start, 3),
                                "end": round(rel_end, 3),
                                "prob": float(w.get("prob", 1.0)),
                                "edited": False,
                            })

                if filtered_words:
                    seg_start = filtered_words[0]["start"]
                    seg_end = filtered_words[-1]["end"]
                    seg_text = " ".join(w["word"] for w in filtered_words)
                else:
                    # Fallback to segment text if word timings are missing
                    seg_start = max(0.0, min(clip_duration, s.start_time - clip_start))
                    seg_end = max(seg_start + 0.3, min(clip_duration, s.end_time - clip_start))
                    seg_text = s.text.strip()

                if seg_text:
                    extracted_segments.append({
                        "id": f"seg_{uuid.uuid4().hex[:8]}",
                        "start": round(seg_start, 3),
                        "end": round(seg_end, 3),
                        "text": seg_text,
                        "words": filtered_words,
                        "speaker_id": s.speaker_id,
                    })

        # Check existing default preset
        if not preset_id:
            await cls.ensure_default_presets(db)
            p_res = await db.execute(select(CaptionPreset).where(CaptionPreset.is_default == True))
            default_p = p_res.scalars().first()
            if default_p:
                preset_id = default_p.id

        track = SubtitleTrack(
            clip_id=clip.id,
            preset_id=preset_id,
            language="en",
            is_enabled=True,
            style_overrides=None,
            segments=extracted_segments,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(track)
        await db.commit()
        
        # Reload with eager loaded preset
        stmt = (
            select(SubtitleTrack)
            .where(SubtitleTrack.id == track.id)
            .options(selectinload(SubtitleTrack.preset))
        )
        t_res = await db.execute(stmt)
        return t_res.scalars().first()

    @classmethod
    async def get_or_create_subtitle_track(
        cls,
        db: AsyncSession,
        clip_id: str,
    ) -> SubtitleTrack:
        """Fetch existing subtitle track for clip or auto-extract from transcript."""
        stmt = (
            select(SubtitleTrack)
            .where(SubtitleTrack.clip_id == clip_id)
            .options(selectinload(SubtitleTrack.preset))
        )
        res = await db.execute(stmt)
        track = res.scalars().first()

        if track:
            return track

        # Otherwise load clip and extract
        c_stmt = select(Clip).where(Clip.id == clip_id)
        c_res = await db.execute(c_stmt)
        clip = c_res.scalars().first()
        if not clip:
            raise ValueError(f"Clip {clip_id} not found")

        return await cls.extract_subtitles_from_transcript(db, clip)

    @classmethod
    async def update_segment(
        cls,
        db: AsyncSession,
        clip_id: str,
        segment_id: str,
        text: Optional[str] = None,
        start: Optional[float] = None,
        end: Optional[float] = None,
        words: Optional[List[SubtitleWord]] = None,
    ) -> SubtitleTrack:
        """Update segment text, boundaries, or word-level timings."""
        track = await cls.get_or_create_subtitle_track(db, clip_id)
        segments = list(track.segments)
        found = False

        for i, seg in enumerate(segments):
            if seg["id"] == segment_id:
                if text is not None:
                    seg["text"] = text.strip()
                if start is not None:
                    seg["start"] = max(0.0, float(start))
                if end is not None:
                    seg["end"] = max(float(seg["start"]) + 0.1, float(end))
                if words is not None:
                    seg["words"] = [w.model_dump() for w in words]
                    if words:
                        seg["start"] = words[0].start
                        seg["end"] = words[-1].end
                        seg["text"] = " ".join(w.word for w in words)
                found = True
                break

        if not found:
            raise ValueError(f"Segment {segment_id} not found in track {track.id}")

        track.segments = segments
        flag_modified(track, "segments")
        track.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(track)
        return track

    @classmethod
    async def split_segment(
        cls,
        db: AsyncSession,
        clip_id: str,
        segment_id: str,
        word_index: int,
    ) -> SubtitleTrack:
        """Split a segment into two at word_index."""
        track = await cls.get_or_create_subtitle_track(db, clip_id)
        segments = list(track.segments)
        found_idx = -1

        for i, seg in enumerate(segments):
            if seg["id"] == segment_id:
                found_idx = i
                break

        if found_idx == -1:
            raise ValueError(f"Segment {segment_id} not found")

        target_seg = segments[found_idx]
        words = target_seg.get("words", [])
        if word_index <= 0 or word_index >= len(words):
            raise ValueError(f"Cannot split segment with {len(words)} words at index {word_index}")

        words_a = words[:word_index]
        words_b = words[word_index:]

        seg_a = {
            "id": f"seg_{uuid.uuid4().hex[:8]}",
            "start": words_a[0]["start"],
            "end": words_a[-1]["end"],
            "text": " ".join(w["word"] for w in words_a),
            "words": words_a,
            "speaker_id": target_seg.get("speaker_id"),
        }

        seg_b = {
            "id": f"seg_{uuid.uuid4().hex[:8]}",
            "start": words_b[0]["start"],
            "end": words_b[-1]["end"],
            "text": " ".join(w["word"] for w in words_b),
            "words": words_b,
            "speaker_id": target_seg.get("speaker_id"),
        }

        # Replace target segment with seg_a and seg_b
        segments = segments[:found_idx] + [seg_a, seg_b] + segments[found_idx + 1 :]
        track.segments = segments
        flag_modified(track, "segments")
        track.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(track)
        return track

    @classmethod
    async def merge_segments(
        cls,
        db: AsyncSession,
        clip_id: str,
        segment_id_1: str,
        segment_id_2: str,
    ) -> SubtitleTrack:
        """Merge two adjacent segments into one."""
        track = await cls.get_or_create_subtitle_track(db, clip_id)
        segments = list(track.segments)

        idx1, idx2 = -1, -1
        for i, seg in enumerate(segments):
            if seg["id"] == segment_id_1:
                idx1 = i
            elif seg["id"] == segment_id_2:
                idx2 = i

        if idx1 == -1 or idx2 == -1:
            raise ValueError("Both segments must exist to merge")

        first_idx = min(idx1, idx2)
        second_idx = max(idx1, idx2)

        first_seg = segments[first_idx]
        second_seg = segments[second_idx]

        combined_words = first_seg.get("words", []) + second_seg.get("words", [])
        combined_text = (first_seg.get("text", "") + " " + second_seg.get("text", "")).strip()

        merged_seg = {
            "id": first_seg["id"],
            "start": min(first_seg["start"], second_seg["start"]),
            "end": max(first_seg["end"], second_seg["end"]),
            "text": combined_text,
            "words": combined_words,
            "speaker_id": first_seg.get("speaker_id"),
        }

        segments = segments[:first_idx] + [merged_seg] + segments[first_idx + 1 : second_idx] + segments[second_idx + 1 :]
        track.segments = segments
        flag_modified(track, "segments")
        track.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(track)
        return track

    @classmethod
    async def list_presets(cls, db: AsyncSession) -> List[CaptionPreset]:
        """List all caption presets (seeds defaults if table is empty)."""
        await cls.ensure_default_presets(db)
        res = await db.execute(select(CaptionPreset).order_by(CaptionPreset.is_default.desc(), CaptionPreset.name.asc()))
        return res.scalars().all()

    @classmethod
    async def save_custom_preset(cls, db: AsyncSession, preset: CaptionPresetSchema) -> CaptionPreset:
        """Create or update a custom styling preset."""
        preset_id = preset.id or f"preset_{uuid.uuid4().hex[:8]}"
        res = await db.execute(select(CaptionPreset).where(CaptionPreset.id == preset_id))
        existing = res.scalars().first()

        if existing:
            for k, v in preset.model_dump(exclude_unset=True).items():
                if k != "id" and hasattr(existing, k):
                    setattr(existing, k, v)
            record = existing
        else:
            record = CaptionPreset(
                id=preset_id,
                name=preset.name,
                font_family=preset.font_family,
                font_size=preset.font_size,
                primary_color=preset.primary_color,
                highlight_color=preset.highlight_color,
                outline_color=preset.outline_color,
                outline_width=preset.outline_width,
                shadow_width=preset.shadow_width,
                bold=preset.bold,
                italic=preset.italic,
                alignment=preset.alignment,
                margin_v=preset.margin_v,
                margin_l=preset.margin_l,
                margin_r=preset.margin_r,
                max_words_per_line=preset.max_words_per_line,
                max_lines=preset.max_lines,
                bg_color=preset.bg_color,
                bg_padding=preset.bg_padding,
                animation_style=preset.animation_style,
                is_default=preset.is_default,
                created_at=datetime.utcnow(),
            )
            db.add(record)

        await db.commit()
        await db.refresh(record)
        return record

    @classmethod
    async def delete_preset(cls, db: AsyncSession, preset_id: str) -> bool:
        """Delete custom preset."""
        res = await db.execute(delete(CaptionPreset).where(CaptionPreset.id == preset_id))
        await db.commit()
        return res.rowcount > 0
