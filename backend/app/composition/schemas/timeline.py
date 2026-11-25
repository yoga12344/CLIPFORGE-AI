"""
ClipForge AI - Composition Timeline & Timebase Models
Microsecond-accurate temporal representation, rational frame rates, and coordinate conversions.
"""

from fractions import Fraction
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


def us_to_seconds(us: int) -> float:
    """Convert integer microseconds to floating point seconds."""
    return float(us) / 1_000_000.0


def seconds_to_us(seconds: float) -> int:
    """Convert floating point seconds to integer microseconds (rounded to nearest integer)."""
    if seconds < 0:
        raise ValueError(f"Seconds cannot be negative: {seconds}")
    return int(round(seconds * 1_000_000.0))


def format_us_to_ffmpeg(us: int) -> str:
    """Format integer microseconds into FFmpeg compatible timestamp string (S.ffffff)."""
    return f"{us / 1_000_000.0:.6f}"


def source_to_composition_us(source_us: int, clip_start_source_us: int) -> int:
    """
    Convert a timestamp from the source video timeline to the composition timeline.
    t_comp = t_src - clip_start_src
    """
    comp_us = source_us - clip_start_source_us
    if comp_us < 0:
        raise ValueError(
            f"Timestamp {source_us} us occurs before clip start {clip_start_source_us} us"
        )
    return comp_us


def composition_to_source_us(comp_us: int, clip_start_source_us: int) -> int:
    """
    Convert a timestamp from the composition timeline to the source video timeline.
    t_src = t_comp + clip_start_src
    """
    if comp_us < 0:
        raise ValueError(f"Composition timestamp cannot be negative: {comp_us}")
    return comp_us + clip_start_source_us


def composition_to_output_us(comp_us: int, output_offset_us: int = 0) -> int:
    """
    Convert a timestamp from the composition timeline to the final rendered output timeline.
    t_out = t_comp + output_offset_us
    """
    out_us = comp_us + output_offset_us
    if out_us < 0:
        raise ValueError(f"Output timestamp cannot be negative: {out_us}")
    return out_us


def output_to_composition_us(output_us: int, output_offset_us: int = 0) -> int:
    """
    Convert a timestamp from the output timeline back to composition timeline.
    t_comp = t_out - output_offset_us
    """
    comp_us = output_us - output_offset_us
    if comp_us < 0:
        raise ValueError(f"Timestamp {output_us} occurs before composition start")
    return comp_us


class RationalTimebase(BaseModel):
    """
    Exact rational representation of frame rate or time base (numerator / denominator).
    Guarantees zero precision loss for standards like 29.97 fps (30000/1001), 23.976 fps (24000/1001).
    """
    numerator: int = Field(..., gt=0, description="Numerator (e.g. 30000)")
    denominator: int = Field(..., gt=0, description="Denominator (e.g. 1001)")

    def as_float(self) -> float:
        """Return the rational value as a standard float."""
        return float(self.numerator) / float(self.denominator)

    @classmethod
    def from_float(cls, fps: float, max_denominator: int = 10000) -> "RationalTimebase":
        """
        Derive an accurate rational timebase from float fps.
        Handles standard NTSC and PAL rates natively.
        """
        if fps <= 0:
            raise ValueError(f"Frame rate must be strictly positive: {fps}")

        # Check standard presets first
        tolerance = 1e-4
        standard_presets = [
            (24000, 1001, 24000 / 1001),    # 23.976
            (24, 1, 24.0),                  # 24.0
            (25, 1, 25.0),                  # 25.0 (PAL)
            (30000, 1001, 30000 / 1001),    # 29.97 (NTSC)
            (30, 1, 30.0),                  # 30.0
            (50, 1, 50.0),                  # 50.0
            (60000, 1001, 60000 / 1001),    # 59.94
            (60, 1, 60.0),                  # 60.0
        ]
        for num, den, val in standard_presets:
            if abs(fps - val) < tolerance:
                return cls(numerator=num, denominator=den)

        # Fallback to Fraction limit_denominator
        frac = Fraction(fps).limit_denominator(max_denominator)
        return cls(numerator=frac.numerator, denominator=frac.denominator)


class ClipBoundary(BaseModel):
    """
    Defines the source clip boundaries in integer microseconds.
    """
    source_start_us: int = Field(..., ge=0, description="Start timestamp in source video (microseconds)")
    source_end_us: int = Field(..., ge=0, description="End timestamp in source video (microseconds)")
    duration_us: int = Field(..., gt=0, description="Exact clip duration (microseconds)")
    approved_candidate_id: Optional[str] = Field(None, description="Optional Phase 5 highlight candidate reference")

    @model_validator(mode="after")
    def validate_bounds(self) -> "ClipBoundary":
        if self.source_end_us <= self.source_start_us:
            raise ValueError(
                f"source_end_us ({self.source_end_us}) must be strictly greater than "
                f"source_start_us ({self.source_start_us})"
            )
        computed_duration = self.source_end_us - self.source_start_us
        if self.duration_us != computed_duration:
            raise ValueError(
                f"duration_us ({self.duration_us}) must equal "
                f"source_end_us - source_start_us ({computed_duration})"
            )
        return self

    @property
    def source_start_seconds(self) -> float:
        return us_to_seconds(self.source_start_us)

    @property
    def source_end_seconds(self) -> float:
        return us_to_seconds(self.source_end_us)

    @property
    def duration_seconds(self) -> float:
        return us_to_seconds(self.duration_us)


class TimelineSceneBoundary(BaseModel):
    """Marks a detected or user-defined scene cut on the composition timeline."""
    scene_index: int = Field(..., ge=0)
    cut_timestamp_us: int = Field(..., ge=0, description="Position on composition timeline (microseconds)")
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class TimelineTransition(BaseModel):
    """Transition interval between visual scenes or camera slots."""
    transition_type: str = Field("cut", description="cut, smooth_pan, dissolve, fade_to_black")
    timeline_start_us: int = Field(..., ge=0)
    timeline_end_us: int = Field(..., ge=0)
    duration_us: int = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_transition(self) -> "TimelineTransition":
        if self.timeline_end_us < self.timeline_start_us:
            raise ValueError("timeline_end_us cannot be less than timeline_start_us")
        computed = self.timeline_end_us - self.timeline_start_us
        if self.duration_us != computed:
            raise ValueError(f"duration_us ({self.duration_us}) must equal end - start ({computed})")
        return self


class TimelineSpec(BaseModel):
    """
    Central timeline description containing clip duration, frame rate timebase,
    scene cuts, and transitions.
    """
    total_duration_us: int = Field(..., gt=0, description="Total composition length in microseconds")
    timebase: RationalTimebase = Field(default_factory=lambda: RationalTimebase(numerator=30, denominator=1))
    is_vfr_source: bool = Field(False, description="Whether original source media had variable frame rate")
    scene_boundaries: List[TimelineSceneBoundary] = Field(default_factory=list)
    transitions: List[TimelineTransition] = Field(default_factory=list)

    @property
    def total_duration_seconds(self) -> float:
        return us_to_seconds(self.total_duration_us)
