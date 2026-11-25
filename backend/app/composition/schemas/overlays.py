"""
ClipForge AI - Overlay and B-Roll Composition Models
B-roll cutaway clips, picture-in-picture insets, channel logos, and graphic watermarks.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from .assets import validate_asset_uri_string
from .layout import NormalizedRect
from .timeline import us_to_seconds


class BRollItemSpec(BaseModel):
    """B-roll cutaway or picture-in-picture video insert."""
    item_id: str = Field(..., description="Unique B-roll item identifier")
    asset_uri: str = Field(..., description="Project-scoped logical URI (e.g. asset://broll/cutaway_01)")
    timeline_start_us: int = Field(..., ge=0, description="Start position on composition timeline (microseconds)")
    duration_us: int = Field(..., gt=0, description="Duration of overlay in microseconds")
    source_offset_us: int = Field(0, ge=0, description="In-point offset within the B-roll asset (microseconds)")
    display_mode: Literal["full_frame_cutaway", "pip_inset", "split_slot"] = "full_frame_cutaway"
    pip_bounds: Optional[NormalizedRect] = Field(None, description="Normalized bounds if display_mode == 'pip_inset'")
    opacity: float = Field(1.0, ge=0.0, le=1.0)
    mute_audio: bool = Field(True, description="True to mute B-roll audio and keep dialogue; False to mix")
    transition_in: Literal["cut", "fade", "slide_left", "zoom_in"] = "cut"
    transition_out: Literal["cut", "fade", "slide_right", "zoom_out"] = "cut"

    @field_validator("asset_uri")
    @classmethod
    def check_asset_uri(cls, v: str) -> str:
        return validate_asset_uri_string(v)

    @property
    def timeline_start_seconds(self) -> float:
        return us_to_seconds(self.timeline_start_us)

    @property
    def duration_seconds(self) -> float:
        return us_to_seconds(self.duration_us)


class GraphicOverlaySpec(BaseModel):
    """Still image overlay (logo, watermark, channel badge, lower-third)."""
    graphic_id: str = Field(..., description="Unique graphic overlay identifier")
    asset_uri: str = Field(..., description="Project-scoped logical URI (e.g. asset://images/logo_01)")
    timeline_start_us: int = Field(0, ge=0, description="Start timestamp on timeline")
    duration_us: int = Field(..., gt=0, description="Duration in microseconds")
    bounds: NormalizedRect = Field(..., description="Normalized placement bounds on canvas")
    opacity: float = Field(1.0, ge=0.0, le=1.0)

    @field_validator("asset_uri")
    @classmethod
    def check_asset_uri(cls, v: str) -> str:
        return validate_asset_uri_string(v)

    @property
    def timeline_start_seconds(self) -> float:
        return us_to_seconds(self.timeline_start_us)

    @property
    def duration_seconds(self) -> float:
        return us_to_seconds(self.duration_us)


class OverlayCompositionConfig(BaseModel):
    """All B-roll and graphic overlays configured for the composition."""
    b_roll_items: List[BRollItemSpec] = Field(default_factory=list)
    graphic_items: List[GraphicOverlaySpec] = Field(default_factory=list)
