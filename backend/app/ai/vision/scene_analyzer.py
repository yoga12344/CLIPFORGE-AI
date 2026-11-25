"""
ClipForge AI - Scene Composition & Video Structure Analyzer
Analyzes face density, primary subject presence, and scene category classification.
"""

from typing import Dict, List, Optional
from app.ai.vision.schemas import FaceDetection, SceneComposition, TrackedFace


class SceneAnalyzer:
    """
    Analyzes visual frame detections and tracked faces to classify scene dynamics.
    """

    @staticmethod
    def analyze_composition(
        total_frames_sampled: int,
        frame_detections: Dict[int, List[FaceDetection]], # frame_index -> detections
        tracked_faces: List[TrackedFace],
    ) -> SceneComposition:
        """
        Evaluate scene composition metrics and classify scene type.
        """
        if total_frames_sampled <= 0:
            return SceneComposition(
                total_frames_sampled=0,
                frames_with_faces=0,
                max_simultaneous_faces=0,
                average_face_count=0.0,
                primary_track_id=None,
                has_multiple_subjects=False,
                has_no_faces=True,
                scene_type="b_roll",
            )

        frames_with_faces = 0
        max_simultaneous_faces = 0
        total_face_instances = 0
        frames_with_multiple_faces = 0

        for frame_idx, detections in frame_detections.items():
            count = len(detections)
            if count > 0:
                frames_with_faces += 1
                total_face_instances += count
                if count > max_simultaneous_faces:
                    max_simultaneous_faces = count
                if count >= 2:
                    frames_with_multiple_faces += 1

        avg_face_count = total_face_instances / total_frames_sampled if total_frames_sampled > 0 else 0.0

        # Determine primary track (subject present in most frames / highest detection count)
        primary_track_id: Optional[str] = None
        if tracked_faces:
            primary_track_id = tracked_faces[0].track_id

        # Classify scene
        has_no_faces = frames_with_faces == 0
        has_multiple_subjects = max_simultaneous_faces >= 2

        if has_no_faces or (frames_with_faces / total_frames_sampled < 0.20):
            scene_type = "b_roll"
        elif max_simultaneous_faces >= 4:
            scene_type = "crowd"
        elif (frames_with_multiple_faces / max(1, frames_with_faces)) > 0.25:
            scene_type = "multi_person"
        else:
            scene_type = "single_subject"

        return SceneComposition(
            total_frames_sampled=total_frames_sampled,
            frames_with_faces=frames_with_faces,
            max_simultaneous_faces=max_simultaneous_faces,
            average_face_count=round(avg_face_count, 2),
            primary_track_id=primary_track_id,
            has_multiple_subjects=has_multiple_subjects,
            has_no_faces=has_no_faces,
            scene_type=scene_type,
        )
