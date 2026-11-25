"""
ClipForge AI - MediaPipe Face Mesh V2 Dense Landmark Detector
Executes Google MediaPipe Face Mesh V2 ONNX for dense 478-point 3D facial landmark regression.
Local-first, CPU-optimized with ONNX Runtime, zero cloud dependencies.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

import cv2
import numpy as np
import onnxruntime as ort

from ...core.config import settings
from .schemas import DenseFaceLandmarks, NormalizedBBox

logger = logging.getLogger("clipforge.ai.vision.landmarks")

LANDMARKS_MODEL_FILENAME = "face_landmarks.onnx"
EXPECTED_LANDMARKS_SHA256 = "f38c3321ceffbc9e95103480ad38cc3f52e7e1bde2bcee7cd9355d0b9138ac0c"

# Canonical MediaPipe Face Mesh Landmark Indices
INDEX_UPPER_LIP_INNER = 13
INDEX_LOWER_LIP_INNER = 14
INDEX_MOUTH_LEFT_CORNER = 61
INDEX_MOUTH_RIGHT_CORNER = 291
INDEX_MOUTH_LEFT_INNER = 78
INDEX_MOUTH_RIGHT_INNER = 308
INDEX_UPPER_LIP_OUTER = 0
INDEX_LOWER_LIP_OUTER = 17


class MediaPipeFaceLandmarkDetector:
    """
    Inference service for MediaPipe Face Mesh V2 ONNX (478 3D keypoints).
    Runs strictly on CPU via ONNX Runtime CPUExecutionProvider with controlled threading.
    """

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        intra_op_threads: int = 2,
        inter_op_threads: int = 1,
        confidence_threshold: float = 0.50,
        verify_checksum: bool = False,
    ):
        self.confidence_threshold = confidence_threshold
        self.intra_op_threads = intra_op_threads
        self.inter_op_threads = inter_op_threads

        if model_path is None:
            self.model_path = Path(settings.MODELS_DIR) / "vision" / LANDMARKS_MODEL_FILENAME
        else:
            self.model_path = Path(model_path)

        if verify_checksum and self.model_path.exists():
            self._verify_checksum()

        self._session: Optional[ort.InferenceSession] = None
        self._input_name: Optional[str] = None
        self._output_names: List[str] = []

    def _verify_checksum(self) -> None:
        """Verify model file integrity against pinned SHA-256."""
        hasher = hashlib.sha256()
        with open(self.model_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_sha256 = hasher.hexdigest()
        if actual_sha256 != EXPECTED_LANDMARKS_SHA256:
            raise ValueError(
                f"Model checksum verification failed for {self.model_path}!\n"
                f"Expected: {EXPECTED_LANDMARKS_SHA256}\n"
                f"Actual:   {actual_sha256}"
            )
        logger.info(f"Verified face_landmarks.onnx SHA-256: {actual_sha256}")

    def is_available(self) -> bool:
        """Check if landmark model weights exist on disk."""
        return self.model_path.exists()

    def _ensure_session(self) -> ort.InferenceSession:
        """Initialize and cache the ONNX Runtime CPU session."""
        if self._session is not None:
            return self._session

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Face landmark model weights not found at: {self.model_path}. "
                "Ensure face_landmarks.onnx is downloaded to storage/clipforge_data/models/vision/."
            )

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self.intra_op_threads
        sess_options.inter_op_num_threads = self.inter_op_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        logger.info(f"Loading Face Landmark ONNX session from {self.model_path} on CPU")
        self._session = ort.InferenceSession(
            str(self.model_path),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name
        self._output_names = [out.name for out in self._session.get_outputs()]
        return self._session

    def detect_landmarks_from_crop(
        self,
        face_crop_bgr: np.ndarray,
        bbox: Optional[NormalizedBBox] = None,
    ) -> DenseFaceLandmarks:
        """
        Run landmark inference on a single cropped face image.
        If bbox is provided, landmarks are mapped to normalized coordinates [0, 1] relative to the source frame.
        Otherwise, landmarks are in normalized crop coordinates [0, 1].
        """
        results = self.detect_landmarks_batch([(face_crop_bgr, bbox)])
        return results[0]

    def detect_landmarks_batch(
        self,
        crops_with_bboxes: List[Tuple[np.ndarray, Optional[NormalizedBBox]]],
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[DenseFaceLandmarks]:
        """
        Batch landmark inference across multiple face crops.
        Releases intermediate buffers immediately to maintain strict memory bounds.
        """
        if not crops_with_bboxes:
            return []

        if is_cancelled and is_cancelled():
            logger.info("Face landmark detection cancelled by caller.")
            return []

        session = self._ensure_session()
        batch_size = len(crops_with_bboxes)
        input_tensor = np.zeros((batch_size, 256, 256, 3), dtype=np.float32)

        valid_indices = []
        for i, (crop, _) in enumerate(crops_with_bboxes):
            if crop is None or crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
                continue

            # Convert BGR to RGB
            if len(crop.shape) == 2:
                crop_rgb = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
            elif crop.shape[2] == 4:
                crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGRA2RGB)
            else:
                crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

            # Resize to 256x256 required by MediaPipe FaceMesh V2
            resized = cv2.resize(crop_rgb, (256, 256), interpolation=cv2.INTER_LINEAR)
            # Normalize to [0.0, 1.0]
            input_tensor[i] = resized.astype(np.float32) / 255.0
            valid_indices.append(i)

        if not valid_indices:
            return [DenseFaceLandmarks(confidence=0.0, is_valid=False) for _ in crops_with_bboxes]

        # Run ONNX inference
        outputs = session.run(self._output_names, {self._input_name: input_tensor})
        raw_landmarks = outputs[0]  # Shape: [N, 1, 1, 1434]
        raw_presence = outputs[1]   # Shape: [N, 1, 1, 1]

        # Reshape to [N, 478, 3]
        landmarks_reshaped = raw_landmarks.reshape(batch_size, 478, 3)

        results: List[DenseFaceLandmarks] = []
        for i, (_, bbox) in enumerate(crops_with_bboxes):
            if i not in valid_indices:
                results.append(DenseFaceLandmarks(confidence=0.0, is_valid=False))
                continue

            # Calculate presence confidence via Sigmoid
            logit = float(raw_presence[i].flatten()[0])
            confidence = float(1.0 / (1.0 + np.exp(-np.clip(logit, -15.0, 15.0))))

            if confidence < self.confidence_threshold:
                results.append(DenseFaceLandmarks(confidence=confidence, is_valid=False))
                continue

            face_pts = landmarks_reshaped[i]  # [478, 3] in [0, 256] crop pixel space

            # Map coordinates to normalized space [0.0, 1.0]
            if bbox is not None:
                # Transform from crop pixel space [0, 256] to normalized source frame [0, 1]
                norm_x = bbox.x + (face_pts[:, 0] / 256.0) * bbox.width
                norm_y = bbox.y + (face_pts[:, 1] / 256.0) * bbox.height
                norm_z = (face_pts[:, 2] / 256.0) * max(bbox.width, bbox.height)
                normalized_points = np.column_stack([norm_x, norm_y, norm_z]).tolist()
            else:
                # Relative to crop [0.0, 1.0]
                norm_x = face_pts[:, 0] / 256.0
                norm_y = face_pts[:, 1] / 256.0
                norm_z = face_pts[:, 2] / 256.0
                normalized_points = np.column_stack([norm_x, norm_y, norm_z]).tolist()

            def get_point(idx: int) -> List[float]:
                return normalized_points[idx]

            landmarks_obj = DenseFaceLandmarks(
                points=normalized_points,
                confidence=round(confidence, 4),
                is_valid=True,
                upper_lip_inner=get_point(INDEX_UPPER_LIP_INNER),
                lower_lip_inner=get_point(INDEX_LOWER_LIP_INNER),
                mouth_left_corner=get_point(INDEX_MOUTH_LEFT_CORNER),
                mouth_right_corner=get_point(INDEX_MOUTH_RIGHT_CORNER),
                upper_lip_outer=get_point(INDEX_UPPER_LIP_OUTER),
                lower_lip_outer=get_point(INDEX_LOWER_LIP_OUTER),
            )
            results.append(landmarks_obj)

        # Explicitly delete temporary tensors to free memory immediately
        del input_tensor
        del outputs
        return results

    def extract_face_crop(
        self,
        frame: np.ndarray,
        bbox: NormalizedBBox,
        padding_ratio: float = 0.20,
    ) -> Tuple[np.ndarray, NormalizedBBox]:
        """
        Extract a padded face crop from a source video frame while handling frame boundary clamping.
        Returns the cropped BGR image and the adjusted padded NormalizedBBox.
        """
        h_frame, w_frame = frame.shape[:2]

        pad_x = bbox.width * padding_ratio
        pad_y = bbox.height * padding_ratio

        x1 = max(0.0, bbox.x - pad_x)
        y1 = max(0.0, bbox.y - pad_y)
        x2 = min(1.0, bbox.x + bbox.width + pad_x)
        y2 = min(1.0, bbox.y + bbox.height + pad_y)

        padded_bbox = NormalizedBBox(
            x=x1,
            y=y1,
            width=x2 - x1,
            height=y2 - y1,
        )

        px1 = int(round(x1 * w_frame))
        py1 = int(round(y1 * h_frame))
        px2 = int(round(x2 * w_frame))
        py2 = int(round(y2 * h_frame))

        px1 = max(0, min(w_frame - 1, px1))
        py1 = max(0, min(h_frame - 1, py1))
        px2 = max(px1 + 1, min(w_frame, px2))
        py2 = max(py1 + 1, min(h_frame, py2))

        crop = frame[py1:py2, px1:px2].copy()
        return crop, padded_bbox

    def close(self) -> None:
        """Release ONNX session resources."""
        self._session = None
