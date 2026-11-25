"""
ClipForge AI - Speaker Diarization Schemas
Pydantic schemas for speaker identities, turns, embeddings, and API requests/responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DiarizationConfigSchema(BaseModel):
    """Configuration parameters for speaker diarization execution."""
    distance_threshold: float = Field(0.65, ge=0.2, le=1.2, description="AHC cosine distance cutoff")
    expected_speakers: Optional[int] = Field(None, ge=1, le=10, description="Exact number of expected speakers")
    min_speakers: int = Field(1, ge=1, le=10, description="Minimum speakers allowed")
    max_speakers: int = Field(10, ge=1, le=20, description="Maximum speakers allowed")
    window_duration_sec: float = Field(1.5, ge=0.5, le=5.0, description="Analysis window length in seconds")
    step_duration_sec: float = Field(0.75, ge=0.25, le=2.5, description="Window hop step in seconds")
    collar_sec: float = Field(0.25, ge=0.0, le=1.0, description="Tolerance collar for boundary evaluation")


class SpeakerSchema(BaseModel):
    """Pydantic model representing a recognized speaker."""
    id: str
    project_id: str
    analysis_id: Optional[str] = None
    speaker_identifier: Optional[str] = None
    label: str
    display_name: Optional[str] = None
    color: Optional[str] = None
    total_speech_duration: float = 0.0
    turn_count: int = 0
    model_name: str = "3dspeaker_campplus"
    model_version: str = "1.0.0"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SpeakerTurnSchema(BaseModel):
    """Pydantic model representing a continuous speaker utterance interval."""
    id: str
    analysis_id: str
    speaker_id: Optional[str] = None
    speaker_identifier: Optional[str] = None
    display_name: Optional[str] = None
    color: Optional[str] = None
    start_time: float
    end_time: float
    duration: float
    confidence: float = 1.0
    assignment_status: str = "auto"  # "auto", "manual", "provisional"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SpeakerEmbeddingSchema(BaseModel):
    """Pydantic model for window embedding metadata."""
    id: str
    analysis_id: str
    speaker_id: Optional[str] = None
    segment_start_time: float
    segment_end_time: float
    embedding_dimension: int = 512
    quality_score: float = 1.0
    model_version: str = "1.0.0"
    created_at: Optional[datetime] = None


class StartDiarizationRequest(BaseModel):
    """Request payload to initiate speaker diarization."""
    config: Optional[DiarizationConfigSchema] = None
    force_reprocess: bool = False


class UpdateSpeakerTurnRequest(BaseModel):
    """Request payload to modify or reassign a speaker turn."""
    speaker_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    assignment_status: Optional[str] = None


class UpdateSpeakerRequest(BaseModel):
    """Request payload to update speaker display metadata."""
    display_name: Optional[str] = None
    color: Optional[str] = None


class DiarizationSummaryResponse(BaseModel):
    """Response containing full diarization results for an audio analysis."""
    analysis_id: str
    status: str
    num_speakers: int
    total_speech_duration: float
    speakers: List[SpeakerSchema] = []
    speaker_turns: List[SpeakerTurnSchema] = []
    silhouette_score: Optional[float] = None
    processing_duration_seconds: float = 0.0
    processing_device: str = "cpu"


class SpeakerCapabilitiesResponse(BaseModel):
    """Capabilities and model diagnostics for offline speaker diarization."""
    diarization_available: bool = True
    model_name: str = "3D-Speaker CAM++ (VoxCeleb 16k)"
    embedding_dimension: int = 512
    sample_rate: int = 16000
    execution_device: str = "cpu"
    clustering_algorithm: str = "AHC-UPGMA-Cosine"
    default_config: DiarizationConfigSchema = DiarizationConfigSchema()
