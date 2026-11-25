from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.security import verify_session_token
from ...db.models import Video
from ...ai.device_detector import DeviceDetector, InferenceDeviceStatus
from ...ai.model_manager import ModelManager, ModelStatus
from ...ai.transcription_config import TranscriptionConfig
from ...services.transcription_service import TranscriptionService
from ...schemas.api_schemas import (
    TranscribeVideoRequest, WhisperModelResponse, VideoActionResponse
)

router = APIRouter(prefix="", tags=["AI & Transcription"])

# --- Inference Hardware Status ---

@router.get("/ai/capabilities", response_model=InferenceDeviceStatus)
async def get_ai_capabilities(
    force_refresh: bool = Query(False),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve CTranslate2 and CUDA inference capabilities."""
    return DeviceDetector.detect(force_refresh=force_refresh)

@router.get("/system/inference-status", response_model=InferenceDeviceStatus)
async def get_system_inference_status(
    authorized: bool = Depends(verify_session_token)
):
    """Alias for system inference telemetry."""
    return DeviceDetector.detect()

# --- Whisper Model Management ---

@router.get("/ai/models", response_model=List[WhisperModelResponse])
async def list_ai_models(
    authorized: bool = Depends(verify_session_token)
):
    """List supported local Whisper models with installation status."""
    return ModelManager.list_models_status()

@router.get("/ai/models/{model_name}", response_model=WhisperModelResponse)
async def get_ai_model(
    model_name: str,
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve installation status of a specific Whisper model."""
    try:
        return ModelManager.check_model_status(model_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/ai/models/{model_name}/download")
async def download_ai_model(
    model_name: str,
    authorized: bool = Depends(verify_session_token)
):
    """Download a local Whisper model on demand."""
    try:
        path = await ModelManager.download_model(model_name)
        return {"status": "installed", "model_name": model_name, "local_path": path}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@router.delete("/ai/models/{model_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_model(
    model_name: str,
    authorized: bool = Depends(verify_session_token)
):
    """Delete a downloaded Whisper model from local disk."""
    try:
        deleted = ModelManager.delete_model(model_name)
        if not deleted:
            raise HTTPException(status_code=404, detail="Model was not installed")
        return None
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

# --- Transcription Job Trigger ---

@router.post("/videos/{video_id}/transcribe", response_model=VideoActionResponse)
async def transcribe_video(
    video_id: str,
    data: Optional[TranscribeVideoRequest] = None,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Enqueue a background speech-to-text transcription job."""
    res = await db.execute(select(Video).where(Video.id == video_id))
    video = res.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    cfg = None
    if data:
        cfg = TranscriptionConfig(
            model_name=data.model_name,
            language=data.language,
            device=data.device,
            compute_type=data.compute_type,
            vad_filter=data.vad_filter,
            vad_threshold=data.vad_threshold,
            beam_size=data.beam_size,
            word_timestamps=data.word_timestamps,
            temperature=data.temperature
        )

    try:
        job = await TranscriptionService.enqueue_transcription(
            video_id=video_id,
            config=cfg
        )
        return VideoActionResponse(
            job_id=job.id,
            message="Video transcription job enqueued successfully."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue transcription: {str(e)}")
