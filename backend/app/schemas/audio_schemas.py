"""
ClipForge AI - Audio Analysis & VAD Schemas
Defines request, response, and metadata models for audio preprocessing and voice activity detection.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AudioMetadataSchema(BaseModel):
    source_sample_rate: Optional[int] = None
    source_channels: Optional[int] = None
    source_codec: Optional[str] = None
    source_duration: float = 0.0
    processed_sample_rate: int = 16000
    processed_channels: int = 1
    sample_format: str = "pcm_s16le"
    audio_available: bool = True
    audio_is_silent: bool = False
    peak_amplitude: float = 0.0
    rms_level: float = 0.0
    clipping_detected: bool = False
    processing_duration: float = 0.0
    processing_device: str = "cpu"


class SpeechIntervalSchema(BaseModel):
    id: Optional[str] = None
    analysis_id: Optional[str] = None
    start_time: float
    end_time: float
    duration: float
    speech_probability: float = 1.0
    confidence: float = 1.0
    source: str = "silero_vad"
    created_at: Optional[datetime] = None


class VADConfigSchema(BaseModel):
    threshold: float = Field(0.5, ge=0.1, le=0.95, description="Speech probability threshold (0.1 to 0.95)")
    min_speech_duration_ms: int = Field(250, ge=50, le=2000, description="Minimum speech duration in milliseconds")
    min_silence_duration_ms: int = Field(350, ge=50, le=5000, description="Minimum silence duration in milliseconds")
    speech_pad_ms: int = Field(100, ge=0, le=1000, description="Padding added to start/end of speech in ms")
    max_merge_gap_ms: int = Field(250, ge=0, le=2000, description="Maximum silence gap to bridge between speech bursts in ms")
    chunk_duration_sec: float = Field(30.0, ge=5.0, le=120.0, description="Processing chunk size in seconds")
    chunk_overlap_sec: float = Field(1.0, ge=0.0, le=5.0, description="Overlap between consecutive chunks in seconds")


class StartAudioAnalysisRequest(BaseModel):
    config: Optional[VADConfigSchema] = None
    force_reprocess: bool = False


class AudioAnalysisResponse(BaseModel):
    id: str
    project_id: str
    video_id: str
    status: str
    source_sample_rate: Optional[int] = None
    source_channels: Optional[int] = None
    processed_sample_rate: int = 16000
    processed_channels: int = 1
    duration_seconds: float = 0.0
    speech_duration_seconds: float = 0.0
    speech_percentage: float = 0.0
    audio_available: bool = True
    audio_is_silent: bool = False
    vad_model: str = "silero-vad-v4"
    vad_version: str = "1.2.1"
    processing_device: str = "cpu"
    processing_duration_seconds: float = 0.0
    configuration: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    speech_intervals: List[SpeechIntervalSchema] = []
    created_at: datetime
    updated_at: datetime


class AudioCapabilitiesResponse(BaseModel):
    vad_available: bool = True
    vad_model: str = "silero-vad-v4"
    vad_version: str = "1.2.1"
    cpu_available: bool = True
    gpu_available: bool = False
    supported_sample_rates: List[int] = [8000, 16000, 22050, 44100, 48000]
    default_config: VADConfigSchema = VADConfigSchema()
