"""
ClipForge AI - Face Detector Module
Implements robust local face detection using OpenCV YuNet (ONNX) and Haar Cascade fallback.
Outputs normalized bounding boxes and facial landmarks with zero cloud dependencies.
"""

import logging
import os
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ...core.config import settings
from .schemas import FacialLandmarks, FaceDetection, NormalizedBBox

logger = logging.getLogger("clipforge.ai.vision.detector")

YUNET_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
YUNET_FILE_NAME = "face_detection_yunet_2023mar.onnx"


class BaseFaceDetector(ABC):
    """Abstract interface for local face detection."""

    @abstractmethod
    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_seconds: float = 0.0
    ) -> List[FaceDetection]:
        """Detect all faces in an RGB/BGR video frame."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if detector weights/assets are loaded."""
        pass


class YuNetFaceDetector(BaseFaceDetector):
    """
    Primary face detector utilizing OpenCV's official YuNet ONNX deep learning model.
    Lightweight (~232 KB), fast (3-10ms per frame on CPU), outputs bounding boxes and 5 facial landmarks.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.55,
        nms_threshold: float = 0.30
    ):
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.model_path = Path(model_path) if model_path else self.get_default_model_path()
        self.model_name = "yunet"
        self._detector: Optional[cv2.FaceDetectorYN] = None
        self._current_input_size: Tuple[int, int] = (320, 320)

    @classmethod
    def get_models_dir(cls) -> Path:
        vision_dir = settings.DATA_DIR / "models" / "vision"
        vision_dir.mkdir(parents=True, exist_ok=True)
        return vision_dir

    @classmethod
    def get_default_model_path(cls) -> Path:
        return cls.get_models_dir() / YUNET_FILE_NAME

    def ensure_model_file(self) -> Path:
        """Verify model file exists on disk, downloading on demand if absent."""
        target = self.model_path
        if not target.exists() or target.stat().st_size < 10000:
            logger.info(f"Downloading YuNet face detection model from {YUNET_MODEL_URL}...")
            temp_target = target.with_suffix(".tmp")
            try:
                req = urllib.request.Request(YUNET_MODEL_URL, headers={"User-Agent": "ClipForge-AI/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp, open(temp_target, "wb") as f:
                    f.write(resp.read())
                temp_target.replace(target)
                logger.info(f"YuNet model downloaded successfully to {target} ({target.stat().st_size} bytes).")
            except Exception as e:
                if temp_target.exists():
                    temp_target.unlink()
                raise RuntimeError(f"Failed to download YuNet face detection model: {e}")
        return target

    def _init_detector(self, width: int, height: int):
        model_file = self.ensure_model_file()
        self._current_input_size = (width, height)
        self._detector = cv2.FaceDetectorYN.create(
            model=str(model_file),
            config="",
            input_size=(width, height),
            score_threshold=self.confidence_threshold,
            nms_threshold=self.nms_threshold,
            top_k=5000,
            backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
            target_id=cv2.dnn.DNN_TARGET_CPU
        )

    def is_available(self) -> bool:
        try:
            return self.model_path.exists() and self.model_path.stat().st_size > 10000
        except Exception:
            return False

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_seconds: float = 0.0
    ) -> List[FaceDetection]:
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        if w < 10 or h < 10:
            return []

        # Initialize or resize detector input size if frame dimensions change
        if self._detector is None or self._current_input_size != (w, h):
            try:
                if self._detector is None:
                    self._init_detector(w, h)
                else:
                    self._detector.setInputSize((w, h))
                    self._current_input_size = (w, h)
            except Exception as e:
                logger.error(f"Error initializing YuNet face detector: {e}")
                return []

        try:
            # YuNet expects 3-channel BGR image
            if len(frame.shape) == 2:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif frame.shape[2] == 4:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            else:
                frame_bgr = frame

            retval, faces = self._detector.detect(frame_bgr)
            if faces is None or len(faces) == 0:
                return []

            results: List[FaceDetection] = []
            for face in faces:
                # YuNet output layout:
                # [0:4] = x, y, width, height (pixel values)
                # [4:14] = 5 landmarks (x, y for right eye, left eye, nose tip, right mouth, left mouth)
                # [14] = confidence score
                x_px = float(face[0])
                y_px = float(face[1])
                w_px = float(face[2])
                h_px = float(face[3])
                conf = float(face[14])

                # Clamp to valid bounds
                norm_x = max(0.0, min(1.0, x_px / w))
                norm_y = max(0.0, min(1.0, y_px / h))
                norm_w = max(0.0, min(1.0 - norm_x, w_px / w))
                norm_h = max(0.0, min(1.0 - norm_y, h_px / h))

                if norm_w <= 0.005 or norm_h <= 0.005:
                    continue

                # Parse landmarks
                landmarks = FacialLandmarks(
                    right_eye=[float(face[4]) / w, float(face[5]) / h],
                    left_eye=[float(face[6]) / w, float(face[7]) / h],
                    nose_tip=[float(face[8]) / w, float(face[9]) / h],
                    right_mouth=[float(face[10]) / w, float(face[11]) / h],
                    left_mouth=[float(face[12]) / w, float(face[13]) / h]
                )

                results.append(FaceDetection(
                    bbox=NormalizedBBox(x=norm_x, y=norm_y, width=norm_w, height=norm_h),
                    confidence=round(conf, 4),
                    frame_index=frame_index,
                    timestamp_seconds=round(timestamp_seconds, 3),
                    landmarks=landmarks
                ))

            return results
        except Exception as e:
            logger.error(f"YuNet detection error on frame {frame_index}: {e}")
            return []


class HaarCascadeFaceDetector(BaseFaceDetector):
    """
    Fallback face detector using OpenCV's built-in frontal face Haar Cascade.
    100% offline with zero download dependencies.
    """

    def __init__(self, confidence: float = 0.60):
        self.confidence = confidence
        self.model_name = "haar_cascade"
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(cascade_path)

    def is_available(self) -> bool:
        return self.cascade is not None and not self.cascade.empty()

    def detect(
        self,
        frame: np.ndarray,
        frame_index: int = 0,
        timestamp_seconds: float = 0.0
    ) -> List[FaceDetection]:
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        if w < 10 or h < 10 or not self.is_available():
            return []

        try:
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            faces = self.cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=4,
                minSize=(24, 24)
            )

            results: List[FaceDetection] = []
            for (x_px, y_px, w_px, h_px) in faces:
                norm_x = max(0.0, min(1.0, float(x_px) / w))
                norm_y = max(0.0, min(1.0, float(y_px) / h))
                norm_w = max(0.0, min(1.0 - norm_x, float(w_px) / w))
                norm_h = max(0.0, min(1.0 - norm_y, float(h_px) / h))

                if norm_w <= 0.005 or norm_h <= 0.005:
                    continue

                results.append(FaceDetection(
                    bbox=NormalizedBBox(x=norm_x, y=norm_y, width=norm_w, height=norm_h),
                    confidence=self.confidence,
                    frame_index=frame_index,
                    timestamp_seconds=round(timestamp_seconds, 3),
                    landmarks=None
                ))

            return results
        except Exception as e:
            logger.error(f"Haar cascade detection error on frame {frame_index}: {e}")
            return []


class FaceDetectorFactory:
    """Factory providing the best available local face detector."""

    @classmethod
    def create(cls, prefer_yunet: bool = True) -> BaseFaceDetector:
        if prefer_yunet:
            try:
                yunet = YuNetFaceDetector()
                yunet.ensure_model_file()
                if yunet.is_available():
                    return yunet
            except Exception as e:
                logger.warning(f"YuNet detector initialization failed, falling back to Haar Cascade: {e}")

        return HaarCascadeFaceDetector()


def get_face_detector(prefer_yunet: bool = True) -> BaseFaceDetector:
    """Convenience accessor for the preferred local face detector."""
    return FaceDetectorFactory.create(prefer_yunet=prefer_yunet)
