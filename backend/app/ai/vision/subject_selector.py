"""
ClipForge AI - Intelligent Subject Selector
Selects target focus bounding box based on configured strategy:
largest_face, center_face, manual_track, or group framing.
"""

from typing import List, Optional
from app.ai.vision.schemas import FaceDetection, NormalizedBBox


class SubjectSelector:
    """
    Selects or computes the target bounding box to focus camera reframing on.
    """

    @staticmethod
    def select_target(
        detections: List[FaceDetection],
        strategy: str = "largest_face",
        selected_track_id: Optional[str] = None,
        last_known_bbox: Optional[NormalizedBBox] = None,
    ) -> Optional[NormalizedBBox]:
        """
        Choose the framing focus based on detected faces and strategy.
        Returns NormalizedBBox or None if no faces present.
        """
        if not detections:
            return last_known_bbox

        if strategy == "manual_track" and selected_track_id:
            # Find detection matching selected_track_id
            for det in detections:
                if det.track_id == selected_track_id:
                    return det.bbox
            # If specified track is temporarily absent, prefer last known or fall back to largest
            if last_known_bbox:
                return last_known_bbox

        if strategy == "group":
            # Union bounding box of all faces in the frame
            min_x = min(d.bbox.x for d in detections)
            min_y = min(d.bbox.y for d in detections)
            max_r = max(d.bbox.x + d.bbox.width for d in detections)
            max_b = max(d.bbox.y + d.bbox.height for d in detections)
            return NormalizedBBox(
                x=min_x,
                y=min_y,
                width=max(0.01, max_r - min_x),
                height=max(0.01, max_b - min_y),
            )

        if strategy == "center_face":
            # Face closest to frame horizontal center (x = 0.5)
            best_det = min(
                detections,
                key=lambda d: abs(d.bbox.center_x - 0.5)
            )
            return best_det.bbox

        # Default: largest_face (dominant speaker or close-up)
        best_det = max(detections, key=lambda d: d.bbox.area)
        return best_det.bbox
