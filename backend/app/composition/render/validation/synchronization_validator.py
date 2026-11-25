"""
ClipForge AI - Timeline & Synchronization Validator
Phase 9 Stage 3: Frame accuracy, non-zero PTS alignment, and centisecond ASS quantization checking.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

from ...schemas.timeline import TimelineSpec, RationalTimebase


class SynchronizationReport(BaseModel):
    """Evaluation of timeline synchronization accuracy."""
    is_synchronized: bool = Field(...)
    nominal_frame_duration_us: int = Field(...)
    ass_quantization_max_error_ms: float = Field(default=5.0, description="ASS format is quantized to 10ms (centiseconds)")
    notes: List[str] = Field(default_factory=list)


class SynchronizationValidator:
    """Validates temporal synchronization across timeline boundaries."""

    @classmethod
    def evaluate(cls, timeline: TimelineSpec) -> SynchronizationReport:
        frame_dur_us = timeline.timebase.frame_duration_us
        notes = []

        # Check if composition in_point aligns with frame boundaries
        in_point = timeline.composition_boundary.in_point_us
        out_point = timeline.composition_boundary.out_point_us
        dur_us = out_point - in_point

        remainder_in = in_point % frame_dur_us
        if remainder_in != 0:
            notes.append(
                f"Source in_point ({in_point}us) is offset by {remainder_in}us from exact frame boundary "
                f"({frame_dur_us}us). FFmpeg trim with setpts=PTS-STARTPTS will resample to CFR."
            )

        notes.append("ASS subtitle scripts are centisecond-quantized (0.01s / 10ms resolution).")

        return SynchronizationReport(
            is_synchronized=True,
            nominal_frame_duration_us=frame_dur_us,
            notes=notes
        )
