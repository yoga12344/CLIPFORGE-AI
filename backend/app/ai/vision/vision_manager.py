"""
ClipForge AI - Vision Analysis Manager & Orchestrator
Coordinates frame sampling, face detection, multi-face tracking, and scene analysis.
Enforces sequential AI resource locking, memory safety, and cancellation responsiveness.
"""

import asyncio
import os
import time
from typing import Callable, Dict, List, Optional
import cv2
from pydantic import BaseModel

from app.ai.vision.face_detector import BaseFaceDetector, get_face_detector
from app.ai.vision.face_tracker import FaceTracker
from app.ai.vision.scene_analyzer import SceneAnalyzer
from app.ai.vision.schemas import FaceDetection, SceneComposition, TrackedFace


class VisionAnalysisResult(BaseModel):
    """Complete visual analysis output for a video or clip."""
    video_path: str
    duration_seconds: float
    total_frames_sampled: int
    frames_with_faces: int
    model_name: str
    sampling_fps: float
    composition: SceneComposition
    tracked_faces: List[TrackedFace]
    frame_detections: Dict[float, List[FaceDetection]] # timestamp -> detections


class VisionManager:
    """
    Singleton orchestrator for visual computer vision tasks.
    Enforces sequential model execution to prevent system RAM / CPU saturation.
    """

    _instance: Optional["VisionManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> "VisionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._detector = None
        return cls._instance

    def get_detector(self) -> BaseFaceDetector:
        if self._detector is None:
            self._detector = get_face_detector()
        return self._detector

    async def analyze_video(
        self,
        video_path: str,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        sampling_fps: float = 4.0,
        confidence_threshold: float = 0.55,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> VisionAnalysisResult:
        """
        Execute visual analysis over a video segment with sequential lock.
        """
        async with self._lock:
            return await asyncio.to_thread(
                self._analyze_video_sync,
                video_path,
                start_time,
                end_time,
                sampling_fps,
                confidence_threshold,
                progress_callback,
                is_cancelled,
            )

    def _analyze_video_sync(
        self,
        video_path: str,
        start_time: float,
        end_time: Optional[float],
        sampling_fps: float,
        confidence_threshold: float,
        progress_callback: Optional[Callable[[int, str], None]],
        is_cancelled: Optional[Callable[[], bool]],
    ) -> VisionAnalysisResult:
        """Synchronous frame sampling loop running in background thread."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        detector = self.get_detector()
        detector.confidence_threshold = confidence_threshold

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video file for visual analysis: {video_path}")

        try:
            total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_fps = float(cap.get(cv2.CAP_PROP_FPS))
            if video_fps <= 0:
                video_fps = 30.0
            video_duration = total_video_frames / video_fps if total_video_frames > 0 else 0.0

            seg_start = max(0.0, start_time)
            seg_end = min(video_duration, end_time) if end_time and end_time > 0 else video_duration
            if seg_end <= seg_start:
                seg_end = video_duration

            target_duration = max(0.1, seg_end - seg_start)
            step_seconds = 1.0 / max(0.5, sampling_fps)

            tracker = FaceTracker(
                iou_threshold=0.25,
                max_centroid_distance=0.25,
                max_missed_frames=int(sampling_fps * 1.5), # ~1.5 seconds tolerance
            )

            frame_detections: Dict[float, List[FaceDetection]] = {}
            current_time = seg_start
            sampled_count = 0
            frames_with_faces = 0

            if progress_callback:
                progress_callback(5, "Initialized computer vision detector")

            while current_time <= seg_end:
                if is_cancelled and is_cancelled():
                    raise asyncio.CancelledError("Visual analysis cancelled by user")

                current_msec = current_time * 1000.0
                cap.set(cv2.CAP_PROP_POS_MSEC, current_msec)
                ret, frame = cap.read()

                if not ret or frame is None:
                    # End of stream or decode error
                    break

                # Downscale frame for fast CPU inference (e.g. 640px width)
                orig_h, orig_w = frame.shape[:2]
                target_w = 640
                if orig_w > target_w:
                    target_h = int(round(orig_h * (target_w / float(orig_w))))
                    detect_frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
                else:
                    detect_frame = frame

                # Run detector
                detections = detector.detect(
                    frame=detect_frame,
                    timestamp_seconds=round(current_time, 3),
                    frame_index=sampled_count,
                )

                if detections:
                    frames_with_faces += 1

                # Update spatial-temporal tracker
                updated_detections = tracker.update(
                    detections=detections,
                    frame_index=sampled_count,
                    timestamp_seconds=round(current_time, 3),
                )

                frame_detections[round(current_time, 3)] = updated_detections
                sampled_count += 1
                current_time += step_seconds

                # Report progress
                if progress_callback and sampled_count % 4 == 0:
                    pct = 5 + int(85.0 * min(1.0, (current_time - seg_start) / target_duration))
                    progress_callback(min(90, pct), f"Analyzing visual frames ({sampled_count} sampled)")

            # Finalize tracking & scene composition
            if progress_callback:
                progress_callback(92, "Aggregating face trajectories and scene composition")

            tracked_faces = tracker.finalize()

            composition = SceneAnalyzer.analyze_composition(
                total_frames_sampled=sampled_count,
                frame_detections={idx: frame_detections[ts] for idx, ts in enumerate(frame_detections.keys())},
                tracked_faces=tracked_faces,
            )

            if progress_callback:
                progress_callback(100, "Visual analysis complete")

            return VisionAnalysisResult(
                video_path=video_path,
                duration_seconds=round(target_duration, 3),
                total_frames_sampled=sampled_count,
                frames_with_faces=frames_with_faces,
                model_name=detector.model_name,
                sampling_fps=sampling_fps,
                composition=composition,
                tracked_faces=tracked_faces,
                frame_detections=frame_detections,
            )
        finally:
            cap.release()
