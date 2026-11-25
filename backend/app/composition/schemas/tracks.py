"""
ClipForge AI - Composition Track and Segment Models
Typed timeline tracks: Video, Audio, Subtitle, B-roll, and Overlays.
"""

from typing import List, Optional, Literal, Union, Annotated
from pydantic import BaseModel, Field, model_validator, field_validator
from .assets import validate_asset_uri_string
from .timeline import us_to_seconds


class TrackSegment(BaseModel):
    """
    Continuous slice of media on a track with microsecond timing.
    """
    segment_id: str = Field(..., description="Unique segment identifier")
    source_asset_uri: str = Field(..., description="Logical URI of source media asset")
    source_start_us: int = Field(..., ge=0, description="In-point in source asset (microseconds)")
    source_end_us: int = Field(..., ge=0, description="Out-point in source asset (microseconds)")
    timeline_start_us: int = Field(..., ge=0, description="Placement start on composition timeline (microseconds)")
    timeline_end_us: int = Field(..., ge=0, description="Placement end on composition timeline (microseconds)")
    duration_us: int = Field(..., gt=0, description="Playback duration in microseconds")
    speed_factor: float = Field(1.0, gt=0.1, le=10.0, description="Playback speed multiplier")
    enabled: bool = Field(True, description="Whether this segment is active")

    @field_validator("source_asset_uri")
    @classmethod
    def check_asset_uri(cls, v: str) -> str:
        return validate_asset_uri_string(v)

    @model_validator(mode="after")
    def validate_durations(self) -> "TrackSegment":
        if self.source_end_us <= self.source_start_us:
            raise ValueError(f"source_end_us ({self.source_end_us}) must exceed source_start_us ({self.source_start_us})")
        if self.timeline_end_us <= self.timeline_start_us:
            raise ValueError(f"timeline_end_us ({self.timeline_end_us}) must exceed timeline_start_us ({self.timeline_start_us})")
        
        timeline_len = self.timeline_end_us - self.timeline_start_us
        if self.duration_us != timeline_len:
            raise ValueError(f"duration_us ({self.duration_us}) must match timeline span ({timeline_len})")
        return self

    @property
    def timeline_start_seconds(self) -> float:
        return us_to_seconds(self.timeline_start_us)

    @property
    def timeline_end_seconds(self) -> float:
        return us_to_seconds(self.timeline_end_us)

    @property
    def duration_seconds(self) -> float:
        return us_to_seconds(self.duration_us)


class VideoTrack(BaseModel):
    """Visual camera feed track."""
    track_id: str = Field(..., description="Unique track ID (e.g. track_video_0)")
    track_type: Literal["video"] = "video"
    name: str = Field("Camera Video", description="User-visible track label")
    order: int = Field(0, description="Visual stacking order")
    enabled: bool = Field(True)
    opacity: float = Field(1.0, ge=0.0, le=1.0)
    z_index: int = Field(0)
    target_slot_id: Optional[str] = Field("slot_0", description="Associated layout slot")
    segments: List[TrackSegment] = Field(default_factory=list)


class AudioTrack(BaseModel):
    """Audio dialogue or sound track."""
    track_id: str = Field(..., description="Unique track ID (e.g. track_audio_voice)")
    track_type: Literal["audio"] = "audio"
    name: str = Field("Voice Dialogue", description="User-visible track label")
    order: int = Field(1)
    enabled: bool = Field(True)
    gain_db: float = Field(0.0, ge=-60.0, le=24.0, description="Volume gain in decibels")
    mute: bool = Field(False)
    pan: float = Field(0.0, ge=-1.0, le=1.0, description="Stereo pan: -1 left, +1 right")
    is_voice_dialogue: bool = Field(True, description="Identifies primary voice for audio ducking triggers")
    segments: List[TrackSegment] = Field(default_factory=list)


class SubtitleTrackSpec(BaseModel):
    """Subtitle track metadata."""
    track_id: str = Field(..., description="Unique track ID")
    track_type: Literal["subtitle"] = "subtitle"
    name: str = Field("Subtitles", description="User-visible track label")
    order: int = Field(2)
    enabled: bool = Field(True)
    preset_id: str = Field("preset_bold_creator")


class BrollTrackSpec(BaseModel):
    """Cutaway B-roll footage track."""
    track_id: str = Field(..., description="Unique track ID")
    track_type: Literal["broll"] = "broll"
    name: str = Field("B-Roll", description="User-visible track label")
    order: int = Field(3)
    enabled: bool = Field(True)
    segments: List[TrackSegment] = Field(default_factory=list)


class OverlayTrackSpec(BaseModel):
    """Visual graphic overlay track (logos, watermarks, lower-thirds)."""
    track_id: str = Field(..., description="Unique track ID")
    track_type: Literal["overlay"] = "overlay"
    name: str = Field("Overlays", description="User-visible track label")
    order: int = Field(4)
    enabled: bool = Field(True)
    segments: List[TrackSegment] = Field(default_factory=list)


CompositionTrack = Annotated[
    Union[VideoTrack, AudioTrack, SubtitleTrackSpec, BrollTrackSpec, OverlayTrackSpec],
    Field(discriminator="track_type")
]
