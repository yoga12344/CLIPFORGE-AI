"""
ClipForge AI - Subtitle Collision Avoidance
Dynamically calculates caption vertical positioning to avoid occluding face tracks.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.composition.schemas.subtitles import SubtitleCollisionConfig


@dataclass
class FaceBoxSample:
    """Face bounding box at a given timestamp in canvas coordinates (pixels)."""
    timestamp_s: float
    x: float
    y: float
    width: float
    height: float

    @property
    def top_y(self) -> float:
        return self.y

    @property
    def bottom_y(self) -> float:
        return self.y + self.height


@dataclass
class SubtitlePlacementDirective:
    """Positional placement directive for a subtitle chunk/segment."""
    alignment: int  # ASS alignment: 2 = bottom-center, 8 = top-center, 5 = mid-center
    margin_v: int  # Vertical margin in pixels
    pos_tag: Optional[str] = None  # Optional explicit ASS pos tag e.g. "{\\pos(540, 1400)}"


class CollisionAvoidancePlanner:
    """
    Evaluates subtitle bounding boxes against active face detections and determines
    safe vertical margins or repositioning to prevent occluding faces.
    """

    def __init__(
        self,
        config: SubtitleCollisionConfig,
        canvas_width: int = 1080,
        canvas_height: int = 1920,
        base_bottom_margin: int = 280,
        subtitle_box_height: int = 160,
    ):
        self.config = config
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.base_bottom_margin = base_bottom_margin
        self.subtitle_box_height = subtitle_box_height
        self.clearance_px = int(canvas_height * config.min_clearance_fraction)

    def calculate_placement(
        self,
        start_s: float,
        end_s: float,
        face_boxes: List[FaceBoxSample],
        default_mode: str = "bottom_safe",
        custom_y_fraction: Optional[float] = None,
    ) -> SubtitlePlacementDirective:
        """
        Calculates safe subtitle placement for the time window [start_s, end_s].
        """
        if default_mode == "top_safe":
            return SubtitlePlacementDirective(alignment=8, margin_v=200)

        if default_mode == "custom" and custom_y_fraction is not None:
            target_y = int(self.canvas_height * custom_y_fraction)
            return SubtitlePlacementDirective(
                alignment=2,
                margin_v=self.canvas_height - target_y,
                pos_tag=f"{{\\pos({self.canvas_width // 2}, {target_y})}}"
            )

        if not self.config.enabled or not face_boxes:
            return SubtitlePlacementDirective(alignment=2, margin_v=self.base_bottom_margin)

        # Find all face boxes occurring during this subtitle display window
        active_faces = [
            f for f in face_boxes
            if start_s <= f.timestamp_s <= end_s or abs(f.timestamp_s - (start_s + end_s) / 2.0) <= 0.5
        ]

        if not active_faces:
            return SubtitlePlacementDirective(alignment=2, margin_v=self.base_bottom_margin)

        # Baseline subtitle placement (ASS alignment 2 uses distance from bottom)
        # Subtitle bottom is at canvas_height - base_bottom_margin
        sub_bottom_y = self.canvas_height - self.base_bottom_margin
        sub_top_y = sub_bottom_y - self.subtitle_box_height

        # Check for collision with any face box in the window
        colliding_faces = []
        for face in active_faces:
            # Check vertical overlap with safety clearance
            face_top = face.top_y - self.clearance_px
            face_bottom = face.bottom_y + self.clearance_px

            # Overlap occurs if face intersects with [sub_top_y, sub_bottom_y]
            if not (face_bottom < sub_top_y or face_top > sub_bottom_y):
                colliding_faces.append(face)

        if not colliding_faces:
            return SubtitlePlacementDirective(alignment=2, margin_v=self.base_bottom_margin)

        # Collision detected!
        # Find highest top boundary among colliding faces
        min_face_top = min(face.top_y for face in colliding_faces)

        # Attempt to shift subtitle upwards directly above the face
        required_sub_bottom = min_face_top - self.clearance_px
        shifted_margin_v = int(self.canvas_height - required_sub_bottom)

        # If shifted position is within comfortable bounds (bottom 60% of canvas)
        if shifted_margin_v < int(self.canvas_height * 0.60):
            return SubtitlePlacementDirective(
                alignment=2,
                margin_v=max(self.base_bottom_margin, shifted_margin_v)
            )

        # If shifting up pushes into upper half (e.g. face covers large area or tall subject),
        # relocate to top_safe to preserve readability and face visibility
        return SubtitlePlacementDirective(alignment=8, margin_v=220)
