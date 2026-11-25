"""
ClipForge AI - Audio-Visual Active Speaker Detection Schemas
Pydantic definitions for frame observations, active speaker intervals, and identity associations.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActiveSpeakerObservation(BaseModel):
    """Instantaneous observation for a single face track at a specific timestamp."""
    timestamp_seconds: float
    face_track_id: str
    raw_logit: float = Field(..., description="Uncalibrated model output logit")
    speaking_probability: float = Field(..., ge=0.0, le=1.0, description="Calibrated softmax probability")
    is_speaking: bool = Field(..., description="Binary thresholded decision")
    sync_confidence: float = Field(1.0, ge=0.0, le=1.0)
    normalized_model_score: Optional[float] = Field(None, description="Normalized model score [0.0, 1.0]")
    lip_motion_evidence: float = Field(0.0, ge=0.0, le=1.0, description="Normalized lip motion dynamics")
    vad_evidence: float = Field(0.0, ge=0.0, le=1.0, description="Acoustic VAD speech probability")
    state: str = Field("inactive", description="active, inactive, unknown, off_screen, overlapping")


class ActiveSpeakerSegment(BaseModel):
    """
    Contiguous temporal segment classified under Concept A (Active Speaker Detection).
    """
    id: Optional[str] = None
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., ge=0.0)
    duration: float = Field(..., ge=0.0)
    face_track_id: Optional[str] = None
    speaker_id: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    speaking_score: float = Field(..., description="Average speaking score during interval")
    state: str = Field(
        "active_speaker",
        description="active_speaker (active), silent_listener (inactive), off_screen_speaker (off_screen), unknown, overlapping"
    )
    raw_model_logit: Optional[float] = None
    lip_motion_score: Optional[float] = None
    vad_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpeakerFaceMatch(BaseModel):
    """
    Global identity association between an acoustic speaker and a visual face track (Concept B).
    """
    id: Optional[str] = None
    speaker_id: str = Field(..., description="Diarization speaker ID (e.g. SPEAKER_00)")
    face_track_id: Optional[str] = Field(None, description="Associated face track ID or None if off-screen")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Association confidence [0.0, 1.0]")
    overlap_duration: float = Field(0.0, ge=0.0, description="Total seconds of coincident speech & active face")
    turn_consistency: float = Field(0.0, ge=0.0, le=1.0, description="Consistency across multiple speaker turns")
    status: str = Field("confirmed", description="confirmed, provisional, off_screen, unknown")
    turns_matched: int = Field(0, ge=0, description="Number of turns where face was active")
    total_turns: int = Field(0, ge=0, description="Total diarization turns for this speaker")
    is_manual: bool = Field(False, description="True if manually assigned or overridden by user")
    is_off_screen: bool = Field(False, description="True if acoustic speaker is off-camera")
    evidence_notes: Optional[str] = None


class ActiveSpeakerAnalysisResult(BaseModel):
    """Complete multimodal active speaker analysis result for a video."""
    video_id: str
    status: str = "completed"
    model_used: str = "light_asd_onnx"
    active_segments: List[ActiveSpeakerSegment] = Field(default_factory=list)
    associations: List[SpeakerFaceMatch] = Field(default_factory=list)
    total_active_speech_seconds: float = 0.0
    total_face_tracks_analyzed: int = 0
    rtf: float = 0.0
    processing_time_seconds: float = 0.0
