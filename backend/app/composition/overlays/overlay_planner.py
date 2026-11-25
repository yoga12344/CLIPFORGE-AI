"""
ClipForge AI - Overlay Planner
Schedules, validates, and positions B-roll and graphic overlays on the composition timeline.
"""

from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel
from app.composition.schemas.overlays import (
    OverlayCompositionConfig,
    BRollItemSpec,
    GraphicOverlaySpec
)
from app.composition.schemas.layout import NormalizedRect


class ResolvedOverlayPlacement(BaseModel):
    """Calculated pixel bounds and enable timings for FFmpeg overlay execution."""
    item_id: str
    x_expr: str
    y_expr: str
    target_width: int
    target_height: int
    enable_expr: str
    start_seconds: float
    end_seconds: float
    opacity: float


class OverlayPlanner:
    """Plans spatial and temporal alignment of B-roll cutaways and graphic watermarks."""

    @classmethod
    def resolve_graphic_placement(
        cls,
        spec: GraphicOverlaySpec,
        canvas_width: int,
        canvas_height: int
    ) -> ResolvedOverlayPlacement:
        """Translates normalized bounds to pixel coordinates and enable expression."""
        gw = int(canvas_width * spec.bounds.width)
        gh = int(canvas_height * spec.bounds.height)
        # Ensure even dimensions
        gw = gw - (gw % 2)
        gh = gh - (gh % 2)
        gw = max(2, gw)
        gh = max(2, gh)

        gx = int(canvas_width * spec.bounds.x)
        gy = int(canvas_height * spec.bounds.y)

        start_s = spec.timeline_start_seconds
        end_s = start_s + spec.duration_seconds

        enable_expr = f"between(t,{start_s:.3f},{end_s:.3f})"

        return ResolvedOverlayPlacement(
            item_id=spec.graphic_id,
            x_expr=str(gx),
            y_expr=str(gy),
            target_width=gw,
            target_height=gh,
            enable_expr=enable_expr,
            start_seconds=start_s,
            end_seconds=end_s,
            opacity=spec.opacity
        )

    @classmethod
    def resolve_broll_placement(
        cls,
        spec: BRollItemSpec,
        canvas_width: int,
        canvas_height: int
    ) -> ResolvedOverlayPlacement:
        """Calculates canvas dimensions, offset coordinates, and enable timings for B-roll insert."""
        start_s = spec.timeline_start_seconds
        end_s = start_s + spec.duration_seconds
        enable_expr = f"between(t,{start_s:.3f},{end_s:.3f})"

        if spec.display_mode == "full_frame_cutaway":
            return ResolvedOverlayPlacement(
                item_id=spec.item_id,
                x_expr="0",
                y_expr="0",
                target_width=canvas_width,
                target_height=canvas_height,
                enable_expr=enable_expr,
                start_seconds=start_s,
                end_seconds=end_s,
                opacity=spec.opacity
            )

        elif spec.display_mode == "pip_inset":
            bounds = spec.pip_bounds or NormalizedRect(x=0.60, y=0.05, width=0.35, height=0.25)
            pw = int(canvas_width * bounds.width)
            ph = int(canvas_height * bounds.height)
            pw = max(2, pw - (pw % 2))
            ph = max(2, ph - (ph % 2))
            px = int(canvas_width * bounds.x)
            py = int(canvas_height * bounds.y)

            return ResolvedOverlayPlacement(
                item_id=spec.item_id,
                x_expr=str(px),
                y_expr=str(py),
                target_width=pw,
                target_height=ph,
                enable_expr=enable_expr,
                start_seconds=start_s,
                end_seconds=end_s,
                opacity=spec.opacity
            )

        # Fallback to full frame
        return ResolvedOverlayPlacement(
            item_id=spec.item_id,
            x_expr="0",
            y_expr="0",
            target_width=canvas_width,
            target_height=canvas_height,
            enable_expr=enable_expr,
            start_seconds=start_s,
            end_seconds=end_s,
            opacity=spec.opacity
        )
