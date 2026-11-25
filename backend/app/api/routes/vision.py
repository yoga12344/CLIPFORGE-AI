"""
ClipForge AI - Visual AI, Face Tracking & Smart Reframing API Routes
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.security import verify_session_token
from ...core.database import get_db
from ...db.models import Video, VisionAnalysis, FaceTrack, ManualCropCorrection, ReframePreset
from ...services.vision_service import VisionService
from ...workers.job_manager import JobManager
from ...ai.vision.schemas import CropCoordinate, ManualCropInput, ReframeConfig

router = APIRouter(tags=["Visual AI & Smart Reframing"], dependencies=[Depends(verify_session_token)])


class AnalyzeVisionRequest(BaseModel):
    sampling_fps: float = Field(default=4.0, ge=0.5, le=30.0)
    confidence_threshold: float = Field(default=0.55, ge=0.1, le=1.0)
    start_time: float = Field(default=0.0, ge=0.0)
    end_time: Optional[float] = None
    clip_id: Optional[str] = None


class FaceTrackResponse(BaseModel):
    id: str
    track_id: str
    start_time: float
    end_time: float
    detection_count: int
    average_confidence: float
    average_bbox: Optional[Dict[str, Any]] = None
    sample_count: int = 0


class ManualCropResponse(BaseModel):
    id: str
    timestamp_seconds: float
    crop_x: float
    crop_y: float
    crop_width: float
    crop_height: float


class VisionAnalysisResponse(BaseModel):
    id: str
    video_id: str
    clip_id: Optional[str] = None
    status: str
    model_used: str
    sampling_fps: float
    total_frames_sampled: int
    frames_with_faces: int
    scene_type: str
    composition_data: Optional[Dict[str, Any]] = None
    tracks: List[FaceTrackResponse] = []
    manual_crops: List[ManualCropResponse] = []


class PresetCreateRequest(BaseModel):
    name: str
    aspect_ratio: str = "9:16"
    strategy: str = "largest_face"
    smoothing_strength: float = 0.85
    crop_padding: float = 0.15
    headroom: float = 0.20
    max_crop_velocity_per_sec: float = 0.50
    is_default: bool = False


@router.post("/videos/{video_id}/vision/analyze", status_code=status.HTTP_202_ACCEPTED)
async def start_visual_analysis(
    video_id: str,
    req: AnalyzeVisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enqueue background visual AI frame sampling, face tracking, and scene analysis."""
    v_res = await db.execute(select(Video).where(Video.id == video_id))
    video = v_res.scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    jm = JobManager.get_instance()
    await jm.start()

    job = await jm.enqueue_job(
        job_type="visual_analysis",
        project_id=video.project_id,
        params={
            "video_id": video.id,
            "clip_id": req.clip_id,
            "sampling_fps": req.sampling_fps,
            "confidence_threshold": req.confidence_threshold,
            "start_time": req.start_time,
            "end_time": req.end_time,
        },
    )

    return {
        "job_id": job.id,
        "status": "queued",
        "message": "Visual analysis queued successfully",
        "video_id": video.id,
    }


@router.get("/videos/{video_id}/vision/analysis", response_model=Optional[VisionAnalysisResponse])
async def get_latest_video_analysis(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch the latest visual analysis for a video."""
    analysis = await VisionService.get_latest_analysis_for_video(db, video_id)
    if not analysis:
        return None

    return VisionAnalysisResponse(
        id=analysis.id,
        video_id=analysis.video_id,
        clip_id=analysis.clip_id,
        status=analysis.status,
        model_used=analysis.model_used,
        sampling_fps=analysis.sampling_fps,
        total_frames_sampled=analysis.total_frames_sampled,
        frames_with_faces=analysis.frames_with_faces,
        scene_type=analysis.scene_type,
        composition_data=analysis.composition_data,
        tracks=[
            FaceTrackResponse(
                id=t.id,
                track_id=t.track_id,
                start_time=t.start_time,
                end_time=t.end_time,
                detection_count=t.detection_count,
                average_confidence=t.average_confidence,
                average_bbox=t.average_bbox,
                sample_count=len(t.samples or []),
            )
            for t in analysis.tracks
        ],
        manual_crops=[
            ManualCropResponse(
                id=mc.id,
                timestamp_seconds=mc.timestamp_seconds,
                crop_x=mc.crop_x,
                crop_y=mc.crop_y,
                crop_width=mc.crop_width,
                crop_height=mc.crop_height,
            )
            for mc in analysis.manual_crops
        ],
    )


@router.get("/vision/analyses/{analysis_id}", response_model=VisionAnalysisResponse)
async def get_analysis_by_id(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch specific visual analysis by ID."""
    analysis = await VisionService.get_analysis_by_id(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Vision analysis not found")

    return VisionAnalysisResponse(
        id=analysis.id,
        video_id=analysis.video_id,
        clip_id=analysis.clip_id,
        status=analysis.status,
        model_used=analysis.model_used,
        sampling_fps=analysis.sampling_fps,
        total_frames_sampled=analysis.total_frames_sampled,
        frames_with_faces=analysis.frames_with_faces,
        scene_type=analysis.scene_type,
        composition_data=analysis.composition_data,
        tracks=[
            FaceTrackResponse(
                id=t.id,
                track_id=t.track_id,
                start_time=t.start_time,
                end_time=t.end_time,
                detection_count=t.detection_count,
                average_confidence=t.average_confidence,
                average_bbox=t.average_bbox,
                sample_count=len(t.samples or []),
            )
            for t in analysis.tracks
        ],
        manual_crops=[
            ManualCropResponse(
                id=mc.id,
                timestamp_seconds=mc.timestamp_seconds,
                crop_x=mc.crop_x,
                crop_y=mc.crop_y,
                crop_width=mc.crop_width,
                crop_height=mc.crop_height,
            )
            for mc in analysis.manual_crops
        ],
    )


@router.post("/vision/analyses/{analysis_id}/trajectory", response_model=List[CropCoordinate])
async def calculate_trajectory(
    analysis_id: str,
    config: ReframeConfig,
    db: AsyncSession = Depends(get_db),
):
    """Compute frame-by-frame crop coordinates based on tracks and reframe settings."""
    try:
        return await VisionService.calculate_trajectory(db, analysis_id, config)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate trajectory: {str(e)}")


@router.post("/vision/analyses/{analysis_id}/manual-crops", response_model=ManualCropResponse)
async def add_manual_crop(
    analysis_id: str,
    crop_input: ManualCropInput,
    db: AsyncSession = Depends(get_db),
):
    """Add or update manual crop keyframe adjustment."""
    record = await VisionService.add_manual_crop(db, analysis_id, crop_input)
    return ManualCropResponse(
        id=record.id,
        timestamp_seconds=record.timestamp_seconds,
        crop_x=record.crop_x,
        crop_y=record.crop_y,
        crop_width=record.crop_width,
        crop_height=record.crop_height,
    )


@router.delete("/vision/analyses/{analysis_id}/manual-crops/{crop_id}")
async def delete_manual_crop(
    analysis_id: str,
    crop_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a manual crop correction."""
    deleted = await VisionService.delete_manual_crop(db, analysis_id, crop_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Crop correction not found")
    return {"success": True, "message": "Manual crop deleted"}


@router.get("/vision/presets")
async def list_presets(db: AsyncSession = Depends(get_db)):
    """List all saved reframe presets."""
    presets = await VisionService.get_presets(db)
    return presets


@router.post("/vision/presets")
async def create_preset(
    preset_data: PresetCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new reframe preset."""
    preset = await VisionService.save_preset(db, preset_data.model_dump())
    return preset
