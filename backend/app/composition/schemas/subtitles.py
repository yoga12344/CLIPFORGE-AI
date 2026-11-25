"""
ClipForge AI - Subtitle Composition Models
Word-level subtitle references, preset bindings, speaker styling, and collision avoidance.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator
from .timeline import us_to_seconds


class SubtitleWordRef(BaseModel):
    """Word-level timing reference anchored in microseconds."""
    word: str
    start_us: int = Field(..., ge=0)
    end_us: int = Field(..., ge=0)
    probability: float = Field(1.0, ge=0.0, le=1.0)

    @property
    def start_seconds(self) -> float:
        return us_to_seconds(self.start_us)

    @property
    def end_seconds(self) -> float:
        return us_to_seconds(self.end_us)


class SubtitleSegmentRef(BaseModel):
    """Clip-relative subtitle segment with word timings."""
    segment_id: str
    start_us: int = Field(..., ge=0, description="Clip-relative start timestamp (microseconds)")
    end_us: int = Field(..., ge=0, description="Clip-relative end timestamp (microseconds)")
    text: str
    speaker_id: Optional[str] = Field(None, description="Acoustic speaker ID for speaker-specific styling")
    words: List[SubtitleWordRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_segment(self) -> "SubtitleSegmentRef":
        if self.end_us <= self.start_us:
            raise ValueError(f"end_us ({self.end_us}) must be strictly greater than start_us ({self.start_us})")
        return self

    @property
    def start_seconds(self) -> float:
        return us_to_seconds(self.start_us)

    @property
    def end_seconds(self) -> float:
        return us_to_seconds(self.end_us)

    @property
    def duration_seconds(self) -> float:
        return us_to_seconds(self.end_us - self.start_us)


class SubtitleStyleOverrides(BaseModel):
    """Optional style overrides modifying the base preset."""
    font_family: Optional[str] = None
    font_size: Optional[int] = Field(None, ge=12, le=160)
    primary_color: Optional[str] = None
    highlight_color: Optional[str] = None
    outline_color: Optional[str] = None
    outline_width: Optional[int] = Field(None, ge=0, le=20)
    shadow_width: Optional[int] = Field(None, ge=0, le=20)
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    max_words_per_line: Optional[int] = Field(None, ge=1, le=10)
    animation_style: Optional[Literal["karaoke_pop", "word_by_word", "phrase_fade", "static"]] = None


class SubtitleCollisionConfig(BaseModel):
    """Configuration for automatic collision avoidance between subtitle box and face tracks."""
    enabled: bool = Field(True, description="Dynamically shift captions upward when face is detected in bottom area")
    min_clearance_fraction: float = Field(0.02, ge=0.0, le=0.10, description="Minimum vertical clearance gap")


class SubtitleCompositionConfig(BaseModel):
    """
    Complete subtitle composition specification.
    """
    enabled: bool = Field(True)
    preset_id: str = Field("preset_bold_creator", description="Phase 7 caption preset identifier")
    position_mode: Literal["bottom_safe", "top_safe", "speaker_anchored", "custom"] = Field(
        "bottom_safe",
        description="Vertical alignment mode"
    )
    custom_y_fraction: Optional[float] = Field(None, ge=0.0, le=1.0, description="Explicit Y anchor if custom mode")
    collision: SubtitleCollisionConfig = Field(default_factory=SubtitleCollisionConfig)
    style_overrides: Optional[SubtitleStyleOverrides] = None
    speaker_styles: Dict[str, SubtitleStyleOverrides] = Field(
        default_factory=dict,
        description="Per-speaker custom styling (e.g. SPEAKER_00 -> gold, SPEAKER_01 -> cyan)"
    )
    segments: List[SubtitleSegmentRef] = Field(
        default_factory=list,
        description="Embedded or linked subtitle segments with word timings"
    )
