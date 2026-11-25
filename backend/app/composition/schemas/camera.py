"""
ClipForge AI - Camera and Reframing Models
Keyframed crop trajectories, active-speaker camera plans, interpolation modes, and manual overrides.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from .layout import NormalizedRect
from .timeline import us_to_seconds


class SubjectReference(BaseModel):
    """Reference linking a camera framing decision to an AI visual or audio subject."""
    face_track_id: Optional[str] = Field(None, description="Bound Phase 6 FaceTrack ID")
    speaker_id: Optional[str] = Field(None, description="Bound Phase 8 acoustic speaker ID")
    strategy: Literal["active_speaker", "largest_face", "centroid", "manual", "fallback"] = "active_speaker"
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class CameraKeyframe(BaseModel):
    """
    Individual keyframe dictating the crop window for a specific layout slot at a point in time.
    """
    timeline_position_us: int = Field(..., ge=0, description="Timestamp on composition timeline (microseconds)")
    slot_id: str = Field("slot_0", description="Associated layout slot identifier")
    crop_rect: NormalizedRect = Field(..., description="Normalized crop window within source video")
    target_subject: Optional[SubjectReference] = Field(None, description="Target AI subject if automatically driven")
    interpolation_mode: Literal["linear", "smooth", "hold", "cut"] = Field("smooth", description="Motion interpolation")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    is_manual_override: bool = Field(False, description="Whether this keyframe was authored by user")

    @property
    def timeline_position_seconds(self) -> float:
        return us_to_seconds(self.timeline_position_us)


class ManualOverride(BaseModel):
    """
    User-locked manual crop override. AI re-planning MUST respect and interpolate between these.
    """
    timeline_position_us: int = Field(..., ge=0)
    slot_id: str = Field("slot_0")
    crop_rect: NormalizedRect
    is_locked: bool = Field(True, description="Strict lock preventing automatic recalculation")

    @property
    def timeline_position_seconds(self) -> float:
        return us_to_seconds(self.timeline_position_us)


class CameraPlan(BaseModel):
    """
    Complete dynamic camera behavior across the composition timeline.
    """
    default_strategy: Literal["active_speaker", "largest_face", "centroid", "manual"] = "active_speaker"
    smoothing_strength: float = Field(0.85, ge=0.0, le=1.0, description="Exponential moving average factor")
    max_velocity_per_sec: float = Field(0.40, ge=0.05, le=2.0, description="Maximum normalized shift per second")
    min_hold_duration_us: int = Field(
        1_200_000,
        ge=0,
        description="Minimum hold time after cutting to speaker before cutting again (default 1.2s)"
    )
    fallback_behavior: Literal["hold_last_known", "wide_zoom", "center"] = Field(
        "hold_last_known",
        description="Action to take when active speaker confidence is low or face track is lost"
    )
    keyframes: List[CameraKeyframe] = Field(default_factory=list)
    manual_overrides: List[ManualOverride] = Field(default_factory=list)

    @property
    def min_hold_duration_seconds(self) -> float:
        return us_to_seconds(self.min_hold_duration_us)
