"""
ClipForge AI - Lip Geometry & Temporal Dynamics Engine
Extracts anatomical mouth kinematics, Mouth Aspect Ratio (MAR), and velocity from dense 3D facial landmarks.
Local-first, CPU-optimized, zero cloud dependencies.
"""

import collections
import logging
import math
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from .landmark_detector import (
    INDEX_LOWER_LIP_INNER,
    INDEX_LOWER_LIP_OUTER,
    INDEX_MOUTH_LEFT_CORNER,
    INDEX_MOUTH_RIGHT_CORNER,
    INDEX_UPPER_LIP_INNER,
    INDEX_UPPER_LIP_OUTER,
)
from .schemas import DenseFaceLandmarks, LipDynamicsMeasurement

logger = logging.getLogger("clipforge.ai.vision.lip_dynamics")

EPSILON_WIDTH = 1e-6
EPSILON_TIME = 1e-4
MAX_OCCLUSION_GAP_SECONDS = 0.50
MAX_PLAUSIBLE_MAR = 1.80
MAX_JITTER_DELTA_MAR = 0.45


class TrackTemporalState:
    """Tracks state history for a single face track over time."""

    def __init__(self, smoothing_alpha: float = 0.35, window_duration: float = 0.40):
        self.smoothing_alpha = smoothing_alpha
        self.window_duration = window_duration

        self.last_timestamp: Optional[float] = None
        self.last_mar_raw: Optional[float] = None
        self.last_mar_smooth: Optional[float] = None

        # History buffer: deque of (timestamp, mar_raw)
        self.history: Deque[Tuple[float, float]] = collections.deque()

    def reset(self) -> None:
        """Reset temporal smoothing state upon scene cut or tracking interruption."""
        self.last_timestamp = None
        self.last_mar_raw = None
        self.last_mar_smooth = None
        self.history.clear()


class LipDynamicsExtractor:
    """
    Extracts geometric mouth aperture, normalized MAR, temporal velocity, and windowed variance.
    Maintains per-face-track temporal context with automatic occlusion detection and jump rejection.
    """

    def __init__(
        self,
        smoothing_alpha: float = 0.35,
        window_duration: float = 0.40,
        min_face_confidence: float = 0.45,
    ):
        """
        Args:
            smoothing_alpha: EMA weight for current frame (0.1 to 0.9). Lower = smoother.
            window_duration: Sliding temporal window duration in seconds for variance estimation.
            min_face_confidence: Minimum landmark confidence below which measurement is deemed invalid.
        """
        self.smoothing_alpha = smoothing_alpha
        self.window_duration = window_duration
        self.min_face_confidence = min_face_confidence

        # Mapping of track_id -> TrackTemporalState
        self._tracks: Dict[str, TrackTemporalState] = {}

    def reset_track(self, track_id: str) -> None:
        """Explicitly reset state for a specific face track."""
        if track_id in self._tracks:
            self._tracks[track_id].reset()

    def reset_all(self) -> None:
        """Reset state across all face tracks."""
        self._tracks.clear()

    def _get_track_state(self, track_id: str) -> TrackTemporalState:
        if track_id not in self._tracks:
            self._tracks[track_id] = TrackTemporalState(
                smoothing_alpha=self.smoothing_alpha,
                window_duration=self.window_duration,
            )
        return self._tracks[track_id]

    @staticmethod
    def _euclidean_distance(pt1: List[float], pt2: List[float]) -> float:
        """Euclidean distance in 2D/3D coordinate space."""
        dx = pt1[0] - pt2[0]
        dy = pt1[1] - pt2[1]
        dz = (pt1[2] - pt2[2]) if len(pt1) > 2 and len(pt2) > 2 else 0.0
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def extract_measurement(
        self,
        landmarks: DenseFaceLandmarks,
        face_track_id: str,
        timestamp_seconds: float,
    ) -> LipDynamicsMeasurement:
        """
        Compute lip dynamics for a single timestamped facial landmark observation.
        """
        track_state = self._get_track_state(face_track_id)

        # 1. Check validity of landmark observations
        if not landmarks.is_valid or landmarks.confidence < self.min_face_confidence or len(landmarks.points) < 292:
            track_state.reset()
            return LipDynamicsMeasurement(
                timestamp_seconds=timestamp_seconds,
                face_track_id=face_track_id,
                aperture=0.0,
                mouth_width=0.0,
                mar_raw=0.0,
                mar_smooth=0.0,
                mar_velocity=0.0,
                mar_variance=0.0,
                quality_confidence=landmarks.confidence,
                is_valid=False,
            )

        pts = landmarks.points
        p13 = pts[INDEX_UPPER_LIP_INNER]
        p14 = pts[INDEX_LOWER_LIP_INNER]
        p61 = pts[INDEX_MOUTH_LEFT_CORNER]
        p291 = pts[INDEX_MOUTH_RIGHT_CORNER]

        # 2. Compute inner-lip vertical aperture and horizontal mouth width
        aperture = self._euclidean_distance(p13, p14)
        mouth_width = self._euclidean_distance(p61, p291)

        # Sanity check: mouth width must be positive and non-zero
        if mouth_width <= EPSILON_WIDTH:
            track_state.reset()
            return LipDynamicsMeasurement(
                timestamp_seconds=timestamp_seconds,
                face_track_id=face_track_id,
                aperture=round(aperture, 5),
                mouth_width=0.0,
                mar_raw=0.0,
                mar_smooth=0.0,
                mar_velocity=0.0,
                mar_variance=0.0,
                quality_confidence=landmarks.confidence,
                is_valid=False,
            )

        # 3. Compute raw MAR
        mar_raw = aperture / mouth_width

        # Reject implausibly extreme values
        if mar_raw > MAX_PLAUSIBLE_MAR or math.isnan(mar_raw) or math.isinf(mar_raw):
            track_state.reset()
            return LipDynamicsMeasurement(
                timestamp_seconds=timestamp_seconds,
                face_track_id=face_track_id,
                aperture=round(aperture, 5),
                mouth_width=round(mouth_width, 5),
                mar_raw=round(min(mar_raw, MAX_PLAUSIBLE_MAR), 5),
                mar_smooth=round(min(mar_raw, MAX_PLAUSIBLE_MAR), 5),
                mar_velocity=0.0,
                mar_variance=0.0,
                quality_confidence=landmarks.confidence * 0.5,
                is_valid=False,
            )

        # 4. Handle temporal continuity and calculate velocity & smoothing
        is_first_sample = track_state.last_timestamp is None
        dt = (timestamp_seconds - track_state.last_timestamp) if not is_first_sample else 0.0

        # Detect gap / scene cut / backward timestamp
        if is_first_sample or dt <= 0.0 or dt > MAX_OCCLUSION_GAP_SECONDS:
            # Cold start or after occlusion: initialize smoothed MAR directly from raw
            mar_smooth = mar_raw
            mar_velocity = 0.0
            track_state.history.clear()
        else:
            # Check for implausible sudden jitter
            delta_mar = abs(mar_raw - track_state.last_mar_raw)
            if delta_mar > MAX_JITTER_DELTA_MAR and dt < 0.05:
                # Extreme jump in short frame interval: clamp raw to mitigate flicker
                mar_raw = track_state.last_mar_raw + math.copysign(MAX_JITTER_DELTA_MAR, mar_raw - track_state.last_mar_raw)

            # Exponential Moving Average (EMA) smoothing
            alpha = self.smoothing_alpha
            mar_smooth = alpha * mar_raw + (1.0 - alpha) * track_state.last_mar_smooth

            # Temporal velocity dMAR/dt using actual dt
            mar_velocity = abs(mar_raw - track_state.last_mar_raw) / max(dt, EPSILON_TIME)

        # 5. Sliding window variance
        track_state.history.append((timestamp_seconds, mar_raw))
        cutoff_time = timestamp_seconds - self.window_duration
        while track_state.history and track_state.history[0][0] < cutoff_time:
            track_state.history.popleft()

        if len(track_state.history) >= 2:
            vals = [val for _, val in track_state.history]
            mar_variance = float(np.var(vals))
        else:
            mar_variance = 0.0

        # 6. Update track state
        track_state.last_timestamp = timestamp_seconds
        track_state.last_mar_raw = mar_raw
        track_state.last_mar_smooth = mar_smooth

        return LipDynamicsMeasurement(
            timestamp_seconds=round(timestamp_seconds, 4),
            face_track_id=face_track_id,
            aperture=round(aperture, 5),
            mouth_width=round(mouth_width, 5),
            mar_raw=round(mar_raw, 5),
            mar_smooth=round(mar_smooth, 5),
            mar_velocity=round(mar_velocity, 4),
            mar_variance=round(mar_variance, 6),
            quality_confidence=round(landmarks.confidence, 4),
            is_valid=True,
        )
