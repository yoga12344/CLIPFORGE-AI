"""
ClipForge AI - Vision Service Layer
Manages persistence of visual analysis results, face tracks, manual crop keyframes,
and reframe presets in SQLite.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, desc
from sqlalchemy.orm import selectinload

from app.db.models import VisionAnalysis, FaceTrack, ManualCropCorrection, ReframePreset, Video
from app.ai.vision.schemas import (
    CropCoordinate,
    FaceDetection,
    ManualCropInput,
    NormalizedBBox,
    ReframeConfig,
    SceneComposition,
    TrackedFace,
)
from app.ai.vision.vision_manager import VisionAnalysisResult
from app.ai.vision.reframe_engine import ReframeEngine

logger = logging.getLogger("clipforge.services.vision")


class VisionService:

    @classmethod
    async def save_analysis(
        cls,
        db: AsyncSession,
        video_id: str,
        result: VisionAnalysisResult,
        clip_id: Optional[str] = None,
    ) -> VisionAnalysis:
        """
        Persist visual analysis results and face tracks into the database.
        """
        analysis = VisionAnalysis(
            video_id=video_id,
            clip_id=clip_id,
            status="completed",
            model_used=result.model_name,
            sampling_fps=result.sampling_fps,
            total_frames_sampled=result.total_frames_sampled,
            frames_with_faces=result.frames_with_faces,
            scene_type=result.composition.scene_type,
            composition_data=result.composition.model_dump(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(analysis)
        await db.flush()

        # Save face tracks
        for trk in result.tracked_faces:
            face_track = FaceTrack(
                vision_analysis_id=analysis.id,
                track_id=trk.track_id,
                start_time=trk.start_time,
                end_time=trk.end_time,
                detection_count=trk.detection_count,
                average_confidence=trk.average_confidence,
                average_bbox=trk.average_bbox.model_dump(),
                samples=[s.model_dump() for s in trk.samples],
                created_at=datetime.utcnow(),
            )
            db.add(face_track)

        await db.commit()
        await db.refresh(analysis)
        return analysis

    @classmethod
    async def get_latest_analysis_for_video(
        cls,
        db: AsyncSession,
        video_id: str,
    ) -> Optional[VisionAnalysis]:
        """
        Retrieve the most recent completed vision analysis for a video.
        """
        stmt = (
            select(VisionAnalysis)
            .where(VisionAnalysis.video_id == video_id)
            .options(
                selectinload(VisionAnalysis.tracks),
                selectinload(VisionAnalysis.manual_crops),
            )
            .order_by(desc(VisionAnalysis.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def get_analysis_by_id(
        cls,
        db: AsyncSession,
        analysis_id: str,
    ) -> Optional[VisionAnalysis]:
        """
        Retrieve a specific vision analysis by its ID.
        """
        stmt = (
            select(VisionAnalysis)
            .where(VisionAnalysis.id == analysis_id)
            .options(
                selectinload(VisionAnalysis.tracks),
                selectinload(VisionAnalysis.manual_crops),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def add_manual_crop(
        cls,
        db: AsyncSession,
        analysis_id: str,
        crop_input: ManualCropInput,
    ) -> ManualCropCorrection:
        """
        Add or update a manual crop keyframe.
        """
        # Check if one already exists for this exact timestamp
        stmt = select(ManualCropCorrection).where(
            ManualCropCorrection.vision_analysis_id == analysis_id,
            ManualCropCorrection.timestamp_seconds == crop_input.timestamp_seconds,
        )
        existing = (await db.execute(stmt)).scalars().first()

        if existing:
            existing.crop_x = crop_input.crop_x
            existing.crop_y = crop_input.crop_y
            existing.crop_width = crop_input.crop_width
            existing.crop_height = crop_input.crop_height
            record = existing
        else:
            record = ManualCropCorrection(
                vision_analysis_id=analysis_id,
                timestamp_seconds=crop_input.timestamp_seconds,
                crop_x=crop_input.crop_x,
                crop_y=crop_input.crop_y,
                crop_width=crop_input.crop_width,
                crop_height=crop_input.crop_height,
                created_at=datetime.utcnow(),
            )
            db.add(record)

        await db.commit()
        await db.refresh(record)
        return record

    @classmethod
    async def delete_manual_crop(
        cls,
        db: AsyncSession,
        analysis_id: str,
        crop_id: str,
    ) -> bool:
        """
        Delete a manual crop correction.
        """
        stmt = delete(ManualCropCorrection).where(
            ManualCropCorrection.id == crop_id,
            ManualCropCorrection.vision_analysis_id == analysis_id,
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount > 0

    @classmethod
    async def calculate_trajectory(
        cls,
        db: AsyncSession,
        analysis_id: str,
        config: ReframeConfig,
    ) -> List[CropCoordinate]:
        """
        Generate smooth crop trajectory based on stored tracks, manual crops,
        and source video dimensions.
        """
        analysis = await cls.get_analysis_by_id(db, analysis_id)
        if not analysis:
            raise ValueError(f"VisionAnalysis {analysis_id} not found")

        # Load video dimensions
        video_stmt = select(Video).where(Video.id == analysis.video_id)
        video = (await db.execute(video_stmt)).scalars().first()
        if not video:
            raise ValueError(f"Video {analysis.video_id} not found")

        source_w = video.width or 1920
        source_h = video.height or 1080

        # Build frame detections reconstruction from tracks
        frame_detections: Dict[float, List[FaceDetection]] = {}
        for trk in analysis.tracks:
            for s in trk.samples or []:
                ts = round(s["timestamp_seconds"], 3)
                if ts not in frame_detections:
                    frame_detections[ts] = []
                frame_detections[ts].append(
                    FaceDetection(
                        bbox=NormalizedBBox(**s["bbox"]),
                        confidence=s.get("confidence", 1.0),
                        frame_index=s.get("frame_index", 0),
                        timestamp_seconds=ts,
                        track_id=trk.track_id,
                    )
                )

        # Convert manual crops
        manual_corrections: List[ManualCropInput] = [
            ManualCropInput(
                timestamp_seconds=mc.timestamp_seconds,
                crop_x=mc.crop_x,
                crop_y=mc.crop_y,
                crop_width=mc.crop_width,
                crop_height=mc.crop_height,
            )
            for mc in analysis.manual_crops
        ]

        return ReframeEngine.generate_trajectory(
            source_width=source_w,
            source_height=source_h,
            frame_detections=frame_detections,
            config=config,
            manual_corrections=manual_corrections,
        )

    @classmethod
    async def get_presets(cls, db: AsyncSession) -> List[ReframePreset]:
        """Retrieve all reframe presets."""
        stmt = select(ReframePreset).order_by(ReframePreset.created_at)
        return (await db.execute(stmt)).scalars().all()

    @classmethod
    async def save_preset(cls, db: AsyncSession, preset_data: Dict[str, Any]) -> ReframePreset:
        """Create or update a preset."""
        preset = ReframePreset(
            name=preset_data["name"],
            aspect_ratio=preset_data.get("aspect_ratio", "9:16"),
            strategy=preset_data.get("strategy", "largest_face"),
            smoothing_strength=preset_data.get("smoothing_strength", 0.85),
            crop_padding=preset_data.get("crop_padding", 0.15),
            headroom=preset_data.get("headroom", 0.20),
            max_crop_velocity_per_sec=preset_data.get("max_crop_velocity_per_sec", 0.50),
            is_default=preset_data.get("is_default", False),
            created_at=datetime.utcnow(),
        )
        db.add(preset)
        await db.commit()
        await db.refresh(preset)
        return preset
