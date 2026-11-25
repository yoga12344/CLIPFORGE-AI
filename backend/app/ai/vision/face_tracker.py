"""
ClipForge AI - Multi-Face Spatial-Temporal Tracker
Associates face detections across sampled video frames using IoU and centroid distance matching.
Maintains track persistence, handles temporary occlusion, and computes track trajectories.
"""

import math
from typing import Dict, List, Optional, Tuple
from app.ai.vision.schemas import FaceDetection, NormalizedBBox, TrackedFace, TrackSample


def calculate_iou(box_a: NormalizedBBox, box_b: NormalizedBBox) -> float:
    """Calculate Intersection-over-Union between two normalized bounding boxes."""
    x_left = max(box_a.x, box_b.x)
    y_top = max(box_a.y, box_b.y)
    x_right = min(box_a.x + box_a.width, box_b.x + box_b.width)
    y_bottom = min(box_a.y + box_a.height, box_b.y + box_b.height)

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    area_a = box_a.area
    area_b = box_b.area
    union_area = area_a + area_b - intersection_area

    if union_area <= 0:
        return 0.0

    return intersection_area / union_area


def calculate_centroid_distance(box_a: NormalizedBBox, box_b: NormalizedBBox) -> float:
    """Calculate Euclidean distance between box centroids in normalized coordinates."""
    dx = box_a.center_x - box_b.center_x
    dy = box_a.center_y - box_b.center_y
    return math.sqrt(dx * dx + dy * dy)


class FaceTrackInternal:
    """Internal mutable tracking state for an identified subject."""

    def __init__(self, track_id: str, initial_detection: FaceDetection):
        self.track_id = track_id
        self.samples: List[TrackSample] = [
            TrackSample(
                timestamp_seconds=initial_detection.timestamp_seconds,
                frame_index=initial_detection.frame_index,
                bbox=initial_detection.bbox,
                confidence=initial_detection.confidence,
            )
        ]
        self.last_bbox = initial_detection.bbox
        self.last_timestamp = initial_detection.timestamp_seconds
        self.last_frame_index = initial_detection.frame_index
        self.frames_since_update = 0

    def add_sample(self, detection: FaceDetection):
        self.samples.append(
            TrackSample(
                timestamp_seconds=detection.timestamp_seconds,
                frame_index=detection.frame_index,
                bbox=detection.bbox,
                confidence=detection.confidence,
            )
        )
        self.last_bbox = detection.bbox
        self.last_timestamp = detection.timestamp_seconds
        self.last_frame_index = detection.frame_index
        self.frames_since_update = 0

    def mark_missed(self):
        self.frames_since_update += 1

    def to_tracked_face(self) -> TrackedFace:
        if not self.samples:
            return TrackedFace(
                track_id=self.track_id,
                start_time=0.0,
                end_time=0.0,
                detection_count=0,
                average_confidence=0.0,
                average_bbox=NormalizedBBox(x=0.0, y=0.0, width=0.0, height=0.0),
                samples=[],
            )

        start_time = self.samples[0].timestamp_seconds
        end_time = self.samples[-1].timestamp_seconds
        total_conf = sum(s.confidence for s in self.samples)
        avg_conf = total_conf / len(self.samples)

        avg_x = sum(s.bbox.x for s in self.samples) / len(self.samples)
        avg_y = sum(s.bbox.y for s in self.samples) / len(self.samples)
        avg_w = sum(s.bbox.width for s in self.samples) / len(self.samples)
        avg_h = sum(s.bbox.height for s in self.samples) / len(self.samples)

        return TrackedFace(
            track_id=self.track_id,
            start_time=round(start_time, 3),
            end_time=round(end_time, 3),
            detection_count=len(self.samples),
            average_confidence=round(avg_conf, 3),
            average_bbox=NormalizedBBox(
                x=round(avg_x, 4),
                y=round(avg_y, 4),
                width=round(avg_w, 4),
                height=round(avg_h, 4),
            ),
            samples=self.samples,
        )


class FaceTracker:
    """
    Multi-face tracking engine with spatial-temporal association,
    handling occlusions and track lifecycle.
    """

    def __init__(
        self,
        iou_threshold: float = 0.25,
        max_centroid_distance: float = 0.25,
        max_missed_frames: int = 5,
        min_detections_for_valid_track: int = 2,
    ):
        self.iou_threshold = iou_threshold
        self.max_centroid_distance = max_centroid_distance
        self.max_missed_frames = max_missed_frames
        self.min_detections_for_valid_track = min_detections_for_valid_track

        self._active_tracks: List[FaceTrackInternal] = []
        self._completed_tracks: List[FaceTrackInternal] = []
        self._next_track_idx: int = 1

    def reset(self):
        """Reset all tracking state."""
        self._active_tracks.clear()
        self._completed_tracks.clear()
        self._next_track_idx = 1

    def update(
        self,
        detections: List[FaceDetection],
        frame_index: int,
        timestamp_seconds: float,
    ) -> List[FaceDetection]:
        """
        Process detections for a frame, associate with active tracks,
        create new tracks, and update missed counts.
        Returns the detections with track_id populated.
        """
        # If no active tracks, initialize all detections as new tracks
        if not self._active_tracks:
            for det in detections:
                tid = f"track_{self._next_track_idx}"
                self._next_track_idx += 1
                det.track_id = tid
                self._active_tracks.append(FaceTrackInternal(tid, det))
            return detections

        # Compute cost/match matrix between active tracks and current detections
        # We greedily match by highest IoU or closest centroid within threshold
        matched_detections = set()
        matched_tracks = set()

        matches: List[Tuple[float, int, int]] = [] # (score, track_idx, det_idx)

        for t_idx, track in enumerate(self._active_tracks):
            for d_idx, det in enumerate(detections):
                iou = calculate_iou(track.last_bbox, det.bbox)
                dist = calculate_centroid_distance(track.last_bbox, det.bbox)

                # Prioritize IoU match, fallback to centroid distance if reasonable
                if iou >= self.iou_threshold:
                    score = 1.0 + iou # > 1.0 indicates strong spatial overlap
                    matches.append((score, t_idx, d_idx))
                elif dist <= self.max_centroid_distance:
                    score = 1.0 - dist # 0.75 - 1.0
                    matches.append((score, t_idx, d_idx))

        # Sort matches descending by score
        matches.sort(key=lambda m: m[0], reverse=True)

        for score, t_idx, d_idx in matches:
            if t_idx in matched_tracks or d_idx in matched_detections:
                continue

            track = self._active_tracks[t_idx]
            det = detections[d_idx]
            det.track_id = track.track_id
            track.add_sample(det)

            matched_tracks.add(t_idx)
            matched_detections.add(d_idx)

        # Mark unmatched active tracks as missed
        unmatched_tracks = []
        for t_idx, track in enumerate(self._active_tracks):
            if t_idx not in matched_tracks:
                track.mark_missed()
                if track.frames_since_update > self.max_missed_frames:
                    # Move to completed
                    self._completed_tracks.append(track)
                else:
                    unmatched_tracks.append(track)
            else:
                unmatched_tracks.append(track)

        self._active_tracks = unmatched_tracks

        # Create new tracks for unmatched detections
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_detections:
                tid = f"track_{self._next_track_idx}"
                self._next_track_idx += 1
                det.track_id = tid
                self._active_tracks.append(FaceTrackInternal(tid, det))

        return detections

    def finalize(self) -> List[TrackedFace]:
        """
        Finalize all active and completed tracks, filtering out noise/flickers.
        Returns a sorted list of TrackedFace objects.
        """
        all_tracks = self._completed_tracks + self._active_tracks
        valid_faces: List[TrackedFace] = []

        for trk in all_tracks:
            if len(trk.samples) >= self.min_detections_for_valid_track:
                valid_faces.append(trk.to_tracked_face())

        # Sort tracks by detection count descending (primary subjects first)
        valid_faces.sort(key=lambda f: f.detection_count, reverse=True)
        return valid_faces
