"""
ClipForge AI - Intelligent Composition Subject Evaluator
Fuses multi-modal visual, active speaker, and acoustic diarization signals
to score and rank candidate subjects across the composition timeline.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from ..schemas.layout import NormalizedRect


@dataclass
class SubjectCandidate:
    """Evaluated subject candidate at a specific point in time."""
    face_track_id: Optional[str]
    speaker_id: Optional[str]
    bbox: NormalizedRect
    importance_score: float
    is_active_speaker: bool
    confidence: float
    strategy: str = "active_speaker"


class SubjectEvaluator:
    """
    Evaluates multi-modal signals to identify dominant and secondary visual subjects.
    Weights:
    - Active speaker detection flag & score (Phase 8 Stage 4)
    - Acoustic speaker diarization turn (Phase 8 Stage 3)
    - Face bounding box scale / area (Phase 6)
    - Centrality / composition balance (Phase 6)
    """

    def __init__(
        self,
        weight_active_speaker: float = 0.50,
        weight_diarization: float = 0.20,
        weight_face_area: float = 0.15,
        weight_centrality: float = 0.15,
    ):
        self.w_active = weight_active_speaker
        self.w_diar = weight_diarization
        self.w_area = weight_face_area
        self.w_center = weight_centrality

    def evaluate_candidates_at(
        self,
        timestamp_sec: float,
        face_tracks: List[Dict[str, Any]],
        active_intervals: List[Dict[str, Any]],
        speaker_turns: List[Dict[str, Any]],
        speaker_face_map: Optional[Dict[str, str]] = None,
    ) -> List[SubjectCandidate]:
        """
        Evaluate and rank all visible face tracks at the specified timestamp.
        """
        speaker_face_map = speaker_face_map or {}
        candidates: List[SubjectCandidate] = []

        # Find active speaker intervals at timestamp
        active_track_scores: Dict[str, float] = {}
        for interval in active_intervals:
            if interval["start_time"] <= timestamp_sec <= interval["end_time"]:
                track_id = interval.get("face_track_id")
                state = interval.get("state", "")
                if track_id and state in ("active_speaker", "active"):
                    conf = float(interval.get("confidence", 1.0))
                    active_track_scores[track_id] = max(active_track_scores.get(track_id, 0.0), conf)

        # Find diarization speaker turn at timestamp
        active_acoustic_speakers: set = set()
        for turn in speaker_turns:
            if turn["start_time"] <= timestamp_sec <= turn["end_time"]:
                spk_id = turn.get("speaker_id")
                if spk_id:
                    active_acoustic_speakers.add(spk_id)

        for track in face_tracks:
            track_id = track.get("track_id")
            start = track.get("start_time", 0.0)
            end = track.get("end_time", 0.0)
            if not (start <= timestamp_sec <= end):
                continue

            # Determine bounding box at timestamp
            bbox_dict = self._interpolate_track_bbox(track, timestamp_sec)
            if not bbox_dict:
                continue

            try:
                rect = NormalizedRect(
                    x=max(0.0, min(0.99, bbox_dict.get("x", 0.0))),
                    y=max(0.0, min(0.99, bbox_dict.get("y", 0.0))),
                    width=max(0.01, min(1.0 - max(0.0, bbox_dict.get("x", 0.0)), bbox_dict.get("width", 0.2))),
                    height=max(0.01, min(1.0 - max(0.0, bbox_dict.get("y", 0.0)), bbox_dict.get("height", 0.2))),
                )
            except Exception:
                continue

            # Calculate individual feature scores
            # 1. Active speaker visual score
            is_active = track_id in active_track_scores
            score_active = active_track_scores.get(track_id, 0.0) if is_active else 0.0

            # 2. Diarization turn alignment score
            # Check if this track is mapped to currently speaking acoustic identity
            mapped_speaker_id = None
            for s_id, t_id in speaker_face_map.items():
                if t_id == track_id:
                    mapped_speaker_id = s_id
                    break

            is_diar_speaking = mapped_speaker_id in active_acoustic_speakers if mapped_speaker_id else False
            score_diar = 1.0 if is_diar_speaking else 0.0

            # 3. Face size score (larger faces get higher priority, normalized up to area 0.2)
            score_area = min(1.0, rect.area / 0.15)

            # 4. Centrality score (closer to frame center X = 0.5)
            score_center = max(0.0, 1.0 - 2.0 * abs(rect.center_x - 0.5))

            # Composite weighted importance score
            importance = (
                (self.w_active * score_active)
                + (self.w_diar * score_diar)
                + (self.w_area * score_area)
                + (self.w_center * score_center)
            )

            # Strategy tag
            if is_active:
                strategy = "active_speaker"
            elif is_diar_speaking:
                strategy = "acoustic_diarization"
            elif score_area > 0.6:
                strategy = "largest_face"
            else:
                strategy = "centroid"

            candidates.append(
                SubjectCandidate(
                    face_track_id=track_id,
                    speaker_id=mapped_speaker_id,
                    bbox=rect,
                    importance_score=round(importance, 4),
                    is_active_speaker=is_active,
                    confidence=score_active if is_active else track.get("average_confidence", 0.8),
                    strategy=strategy,
                )
            )

        # Sort descending by importance score
        candidates.sort(key=lambda c: c.importance_score, reverse=True)
        return candidates

    def _interpolate_track_bbox(self, track: Dict[str, Any], timestamp_sec: float) -> Optional[Dict[str, float]]:
        """Get or interpolate bounding box for face track at given timestamp."""
        samples = track.get("samples")
        if not samples or not isinstance(samples, list):
            return track.get("average_bbox")

        # Find closest sample by timestamp
        best_sample = None
        min_delta = float("inf")
        for sample in samples:
            t = sample.get("timestamp_seconds", sample.get("timestamp", 0.0))
            delta = abs(t - timestamp_sec)
            if delta < min_delta:
                min_delta = delta
                best_sample = sample

        if best_sample and "bbox" in best_sample:
            return best_sample["bbox"]
        if best_sample and "x" in best_sample:
            return best_sample
        return track.get("average_bbox")
