"""
ClipForge AI - Composition Layout Specification
Normalized geometry, layout slot topologies, safe areas, and background treatments.
"""

import math
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, model_validator


class NormalizedRect(BaseModel):
    """
    Normalized bounding rectangle in [0.0, 1.0] coordinate space.
    Origin (0,0) is top-left corner.
    """
    x: float = Field(..., ge=0.0, le=1.0, description="Normalized X coordinate [0.0, 1.0]")
    y: float = Field(..., ge=0.0, le=1.0, description="Normalized Y coordinate [0.0, 1.0]")
    width: float = Field(..., gt=0.0, le=1.0, description="Normalized width (0.0, 1.0]")
    height: float = Field(..., gt=0.0, le=1.0, description="Normalized height (0.0, 1.0]")

    @model_validator(mode="after")
    def validate_finite_and_bounds(self) -> "NormalizedRect":
        for attr in ("x", "y", "width", "height"):
            val = getattr(self, attr)
            if not math.isfinite(val):
                raise ValueError(f"Geometry coordinate {attr} must be finite, got {val}")
        
        # Check boundary overflow with small float epsilon
        eps = 1e-5
        if (self.x + self.width) > (1.0 + eps):
            raise ValueError(f"Rectangle x + width ({self.x + self.width}) exceeds 1.0 boundary")
        if (self.y + self.height) > (1.0 + eps):
            raise ValueError(f"Rectangle y + height ({self.y + self.height}) exceeds 1.0 boundary")
        return self

    @property
    def center_x(self) -> float:
        return self.x + (self.width / 2.0)

    @property
    def center_y(self) -> float:
        return self.y + (self.height / 2.0)

    @property
    def area(self) -> float:
        return self.width * self.height


class SafeAreaConfig(BaseModel):
    """
    Platform safe-area margins (normalized [0.0, 1.0]) to protect against UI element obstruction
    (e.g., TikTok/Reels like buttons, captions, profile headers).
    """
    top_margin: float = Field(0.0625, ge=0.0, le=0.35, description="Top margin fraction (e.g. 120px / 1920)")
    bottom_margin: float = Field(0.1458, ge=0.0, le=0.45, description="Bottom margin fraction (e.g. 280px / 1920)")
    side_margin: float = Field(0.0370, ge=0.0, le=0.25, description="Side margin fraction (e.g. 40px / 1080)")


class BackgroundTreatment(BaseModel):
    """Visual treatment for negative space around aspect-ratio converted footage."""
    type: Literal["solid_color", "blurred_source", "transparent", "custom_image"] = "blurred_source"
    color_hex: str = Field("#000000", description="Background hex color for solid_color mode")
    blur_radius: int = Field(30, ge=1, le=100, description="Box/Gaussian blur radius for blurred_source")
    custom_asset_uri: Optional[str] = Field(None, description="Logical URI to background image if custom_image")


class LayoutSlot(BaseModel):
    """Individual visual aperture or camera slot within a multi-person or layered composition."""
    slot_id: str = Field(..., description="Unique slot identifier within composition (e.g. slot_0, slot_top)")
    bounds: NormalizedRect = Field(..., description="Normalized viewport rectangle in canvas coordinates")
    z_order: int = Field(0, description="Stacking order (lower is rendered first)")
    aspect_ratio_mode: Literal["fit", "fill", "stretch"] = "fill"
    crop_behavior: Literal["center", "face_tracking", "manual"] = "face_tracking"
    assigned_face_track_id: Optional[str] = Field(None, description="Bound Phase 6 FaceTrack ID")
    assigned_speaker_id: Optional[str] = Field(None, description="Bound Phase 8 acoustic speaker ID")
    crop_padding: float = Field(0.15, ge=0.0, le=0.50, description="Padding around detected subject bounding box")
    headroom: float = Field(0.20, ge=0.0, le=0.50, description="Vertical headroom fraction above face top")


class LayoutConfig(BaseModel):
    """
    Complete geometric and spatial configuration for the video canvas.
    """
    layout_type: Literal[
        "single_full_frame",
        "portrait_crop",
        "split_vertical",
        "split_horizontal",
        "three_person_grid",
        "picture_in_picture",
        "blurred_background",
        "custom"
    ] = "single_full_frame"
    slots: List[LayoutSlot] = Field(default_factory=list)
    background: BackgroundTreatment = Field(default_factory=BackgroundTreatment)
    safe_area: SafeAreaConfig = Field(default_factory=SafeAreaConfig)

    @model_validator(mode="after")
    def validate_slots_for_layout_type(self) -> "LayoutConfig":
        if self.layout_type == "single_full_frame" and not self.slots:
            # Auto-populate full frame slot if empty
            self.slots = [
                LayoutSlot(
                    slot_id="slot_0",
                    bounds=NormalizedRect(x=0.0, y=0.0, width=1.0, height=1.0),
                    z_order=0,
                    aspect_ratio_mode="fill",
                    crop_behavior="center",
                )
            ]
        elif self.layout_type == "split_vertical" and not self.slots:
            # Auto-populate 50/50 vertical split
            self.slots = [
                LayoutSlot(
                    slot_id="slot_top",
                    bounds=NormalizedRect(x=0.0, y=0.0, width=1.0, height=0.5),
                    z_order=0,
                    aspect_ratio_mode="fill",
                    crop_behavior="face_tracking",
                ),
                LayoutSlot(
                    slot_id="slot_bottom",
                    bounds=NormalizedRect(x=0.0, y=0.5, width=1.0, height=0.5),
                    z_order=0,
                    aspect_ratio_mode="fill",
                    crop_behavior="face_tracking",
                ),
            ]
        return self
