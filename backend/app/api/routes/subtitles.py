"""
ClipForge AI - Subtitle Management & Preset API Routes
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.security import verify_session_token
from ...db.models import Clip, CaptionPreset, SubtitleTrack
from ...schemas.subtitle_schemas import (
    CaptionPresetSchema,
    MergeSegmentsRequest,
    SplitSegmentRequest,
    SubtitleTrackResponse,
    UpdateSegmentRequest,
)
from ...services.subtitle_service import SubtitleService

router = APIRouter(tags=["Subtitles"], dependencies=[Depends(verify_session_token)])


class UpdateTrackSettingsRequest(BaseModel):
    is_enabled: Optional[bool] = None
    preset_id: Optional[str] = None
    style_overrides: Optional[Dict[str, Any]] = None


@router.get("/clips/{clip_id}/subtitles", response_model=SubtitleTrackResponse)
async def get_clip_subtitles(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve or auto-extract subtitle track for a clip."""
    try:
        track = await SubtitleService.get_or_create_subtitle_track(db, clip_id)
        preset_schema = None
        if track.preset:
            preset_schema = CaptionPresetSchema(
                id=track.preset.id,
                name=track.preset.name,
                font_family=track.preset.font_family,
                font_size=track.preset.font_size,
                primary_color=track.preset.primary_color,
                highlight_color=track.preset.highlight_color,
                outline_color=track.preset.outline_color,
                outline_width=track.preset.outline_width,
                shadow_width=track.preset.shadow_width,
                bold=track.preset.bold,
                italic=track.preset.italic,
                alignment=track.preset.alignment,
                margin_v=track.preset.margin_v,
                margin_l=track.preset.margin_l,
                margin_r=track.preset.margin_r,
                max_words_per_line=track.preset.max_words_per_line,
                max_lines=track.preset.max_lines,
                bg_color=track.preset.bg_color,
                bg_padding=track.preset.bg_padding,
                animation_style=track.preset.animation_style,
                is_default=track.preset.is_default,
            )

        return SubtitleTrackResponse(
            id=track.id,
            clip_id=track.clip_id,
            preset_id=track.preset_id,
            language=track.language,
            is_enabled=track.is_enabled,
            style_overrides=track.style_overrides,
            segments=track.segments or [],
            preset=preset_schema,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch subtitle track: {str(e)}")


@router.patch("/clips/{clip_id}/subtitles", response_model=SubtitleTrackResponse)
async def update_clip_subtitle_settings(
    clip_id: str,
    req: UpdateTrackSettingsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update subtitle track enabled state, chosen preset, or custom styling overrides."""
    track = await SubtitleService.get_or_create_subtitle_track(db, clip_id)
    if req.is_enabled is not None:
        track.is_enabled = req.is_enabled
    if req.preset_id is not None:
        track.preset_id = req.preset_id
    if req.style_overrides is not None:
        track.style_overrides = req.style_overrides

    await db.commit()
    await db.refresh(track)
    return await get_clip_subtitles(clip_id, db)


@router.put("/clips/{clip_id}/subtitles/segments/{segment_id}", response_model=SubtitleTrackResponse)
async def update_subtitle_segment(
    clip_id: str,
    segment_id: str,
    req: UpdateSegmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Edit text, boundary timestamps, or word timings in a subtitle segment."""
    try:
        await SubtitleService.update_segment(
            db=db,
            clip_id=clip_id,
            segment_id=segment_id,
            text=req.text,
            start=req.start,
            end=req.end,
            words=req.words,
        )
        return await get_clip_subtitles(clip_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/clips/{clip_id}/subtitles/segments/{segment_id}/split", response_model=SubtitleTrackResponse)
async def split_subtitle_segment(
    clip_id: str,
    segment_id: str,
    req: SplitSegmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Split a subtitle segment into two at specified word index."""
    try:
        await SubtitleService.split_segment(
            db=db,
            clip_id=clip_id,
            segment_id=segment_id,
            word_index=req.word_index,
        )
        return await get_clip_subtitles(clip_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/clips/{clip_id}/subtitles/merge", response_model=SubtitleTrackResponse)
async def merge_subtitle_segments(
    clip_id: str,
    req: MergeSegmentsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Merge two adjacent subtitle segments into one."""
    try:
        await SubtitleService.merge_segments(
            db=db,
            clip_id=clip_id,
            segment_id_1=req.segment_ids[0],
            segment_id_2=req.segment_ids[1],
        )
        return await get_clip_subtitles(clip_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subtitles/presets", response_model=List[CaptionPresetSchema])
@router.get("/caption-presets", response_model=List[CaptionPresetSchema])
async def list_presets(db: AsyncSession = Depends(get_db)):
    """List all available built-in and custom caption styling presets."""
    db_presets = await SubtitleService.list_presets(db)
    return [
        CaptionPresetSchema(
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
        )
        for p in db_presets
    ]


@router.post("/subtitles/presets", response_model=CaptionPresetSchema)
@router.post("/caption-presets", response_model=CaptionPresetSchema)
async def create_or_update_preset(preset: CaptionPresetSchema, db: AsyncSession = Depends(get_db)):
    """Create or update a custom styling preset."""
    rec = await SubtitleService.save_custom_preset(db, preset)
    return CaptionPresetSchema(
        id=rec.id,
        name=rec.name,
        font_family=rec.font_family,
        font_size=rec.font_size,
        primary_color=rec.primary_color,
        highlight_color=rec.highlight_color,
        outline_color=rec.outline_color,
        outline_width=rec.outline_width,
        shadow_width=rec.shadow_width,
        bold=rec.bold,
        italic=rec.italic,
        alignment=rec.alignment,
        margin_v=rec.margin_v,
        margin_l=rec.margin_l,
        margin_r=rec.margin_r,
        max_words_per_line=rec.max_words_per_line,
        max_lines=rec.max_lines,
        bg_color=rec.bg_color,
        bg_padding=rec.bg_padding,
        animation_style=rec.animation_style,
        is_default=rec.is_default,
    )


@router.delete("/subtitles/presets/{preset_id}")
async def delete_preset(preset_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a custom caption preset."""
    success = await SubtitleService.delete_preset(db, preset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"success": True, "message": "Preset deleted"}
