"""
ClipForge AI - Root Composition Specification (CompositionSpec v1.0.0)
The immutable, deterministic, serializable contract between AI engines, UI editor, and rendering.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Literal, Set
from pydantic import BaseModel, Field, field_validator

from .timeline import ClipBoundary, TimelineSpec, RationalTimebase, us_to_seconds
from .assets import validate_asset_uri_string
from .layout import LayoutConfig
from .camera import CameraPlan
from .tracks import CompositionTrack, VideoTrack, AudioTrack, SubtitleTrackSpec, TrackSegment
from .subtitles import SubtitleCompositionConfig
from .overlays import OverlayCompositionConfig
from .audio import AudioCompositionConfig
from .delivery import DeliveryProfile, get_default_delivery_profile
from .validation import CompositionValidationResult, validate_composition_semantics


class SourceMediaMetadata(BaseModel):
    """Immutable metadata describing the parent source video."""
    video_id: str = Field(..., description="Parent Video database ID")
    asset_uri: str = Field(..., description="Logical URI (e.g. asset://videos/source_01)")
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)
    fps: float = Field(..., gt=0.0)
    timebase: RationalTimebase = Field(default_factory=lambda: RationalTimebase(numerator=30, denominator=1))
    duration_us: int = Field(..., gt=0, description="Source duration in microseconds")
    is_vfr: bool = Field(False, description="True if source used variable frame rates")
    has_audio: bool = Field(True)
    audio_channels: int = Field(2, ge=1, le=8)
    audio_sample_rate: int = Field(48000, gt=0)

    @field_validator("asset_uri")
    @classmethod
    def check_asset_uri(cls, v: str) -> str:
        return validate_asset_uri_string(v)

    @property
    def duration_seconds(self) -> float:
        return us_to_seconds(self.duration_us)


class CompositionSpec(BaseModel):
    """
    Root composition specification (Version 1.0.0).
    Captures complete timeline, camera trajectories, multi-person layouts, subtitles,
    B-roll overlays, audio mixing, and delivery profile.
    """
    schema_version: Literal["1.0.0"] = "1.0.0"
    composition_id: str = Field(..., description="UUID v4 of the composition")
    project_id: str = Field(..., description="Owning project ID")
    source_video_id: str = Field(..., description="Parent source video ID")
    title: str = Field("Untitled Composition", max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Core Pipeline Sections
    source_media: SourceMediaMetadata
    clip_boundary: ClipBoundary
    timeline: TimelineSpec
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    camera: CameraPlan = Field(default_factory=CameraPlan)
    tracks: List[CompositionTrack] = Field(default_factory=list)
    subtitles: SubtitleCompositionConfig = Field(default_factory=SubtitleCompositionConfig)
    overlays: OverlayCompositionConfig = Field(default_factory=OverlayCompositionConfig)
    audio: AudioCompositionConfig = Field(default_factory=AudioCompositionConfig)
    delivery_profile: DeliveryProfile = Field(default_factory=get_default_delivery_profile)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_canonical_json(self) -> str:
        """
        Serialize to deterministic canonical JSON:
        - Sorted keys
        - ISO timestamps
        - Zero extra whitespace
        - Guaranteed byte-identical string across runs with identical data
        """
        raw_dict = self.model_dump(mode="json")
        return json.dumps(raw_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def compute_content_hash(self) -> str:
        """
        Compute SHA-256 hash of the canonical JSON string.
        Used for optimistic concurrency control and tamper verification.
        """
        canon = self.to_canonical_json().encode("utf-8")
        return hashlib.sha256(canon).hexdigest()

    @classmethod
    def from_canonical_json(cls, json_str: str) -> "CompositionSpec":
        """Reconstruct CompositionSpec from JSON string."""
        data = json.loads(json_str)
        return cls.model_validate(data)

    def validate_semantics(self, authorized_asset_uris: Optional[Set[str]] = None) -> CompositionValidationResult:
        """Execute deep semantic validation."""
        return validate_composition_semantics(self, authorized_asset_uris)

    @classmethod
    def create_default(
        cls,
        composition_id: str,
        project_id: str,
        video_id: str,
        source_width: int,
        source_height: int,
        source_fps: float,
        source_duration_us: int,
        clip_start_us: int,
        clip_end_us: int,
        title: str = "New Composition",
        aspect_ratio: str = "9:16",
        approved_candidate_id: Optional[str] = None,
    ) -> "CompositionSpec":
        """
        Convenience factory creating a valid baseline CompositionSpec for a video clip.
        """
        clip_dur = clip_end_us - clip_start_us
        timebase = RationalTimebase.from_float(source_fps)
        clip_bounds = ClipBoundary(
            source_start_us=clip_start_us,
            source_end_us=clip_end_us,
            duration_us=clip_dur,
            approved_candidate_id=approved_candidate_id,
        )
        source_meta = SourceMediaMetadata(
            video_id=video_id,
            asset_uri=f"asset://videos/source_{video_id[:8]}",
            width=source_width,
            height=source_height,
            fps=source_fps,
            timebase=timebase,
            duration_us=source_duration_us,
            has_audio=True,
            audio_channels=2,
            audio_sample_rate=48000,
        )
        timeline = TimelineSpec(
            total_duration_us=clip_dur,
            timebase=timebase,
            is_vfr_source=False,
        )
        delivery = get_default_delivery_profile(aspect_ratio)

        # Default video and audio tracks
        tracks: List[CompositionTrack] = [
            VideoTrack(
                track_id="track_main_video",
                track_type="video",
                name="Primary Video",
                order=0,
                segments=[
                    TrackSegment(
                        segment_id="seg_video_main",
                        source_asset_uri=source_meta.asset_uri,
                        source_start_us=clip_start_us,
                        source_end_us=clip_end_us,
                        timeline_start_us=0,
                        timeline_end_us=clip_dur,
                        duration_us=clip_dur,
                    )
                ],
            ),
            AudioTrack(
                track_id="track_main_audio",
                track_type="audio",
                name="Source Audio",
                order=1,
                segments=[
                    TrackSegment(
                        segment_id="seg_audio_main",
                        source_asset_uri=source_meta.asset_uri,
                        source_start_us=clip_start_us,
                        source_end_us=clip_end_us,
                        timeline_start_us=0,
                        timeline_end_us=clip_dur,
                        duration_us=clip_dur,
                    )
                ],
            ),
            SubtitleTrackSpec(
                track_id="track_subtitles",
                track_type="subtitle",
                name="Captions",
                order=2,
            )
        ]

        return cls(
            schema_version="1.0.0",
            composition_id=composition_id,
            project_id=project_id,
            source_video_id=video_id,
            title=title,
            source_media=source_meta,
            clip_boundary=clip_bounds,
            timeline=timeline,
            tracks=tracks,
            delivery_profile=delivery,
        )
