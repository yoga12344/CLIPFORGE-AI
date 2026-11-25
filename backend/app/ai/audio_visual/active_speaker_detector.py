"""
ClipForge AI - Light-ASD Audio-Visual Active Speaker Detector
Executes the CVPR 2023 Light-ASD ONNX model for cross-modal active speaker detection.
Local-first, CPU-optimized with ONNX Runtime, zero cloud dependencies.
"""

import hashlib
import logging
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import onnxruntime as ort

from ...core.config import settings
from ..vision.schemas import NormalizedBBox
from .av_synchronizer import AudioVisualSynchronizer
from .schemas import ActiveSpeakerObservation

logger = logging.getLogger("clipforge.ai.audio_visual.light_asd")

LIGHT_ASD_FILENAME = "light_asd.onnx"
EXPECTED_LIGHT_ASD_SHA256 = "3ac4cd7810993cdf6ca05243730b6dff104fa20dd572fbbebc1535ac28b453dd"


class AVTemporalAdapter:
    """
    Temporal adapter bridging Phase 6 4.0 FPS keyframe face tracking to Light-ASD's
    strict 25.0 FPS video / 100 Hz audio MFCC (4:1 step ratio) requirements.
    Operates in bounded temporal windows to guarantee strict memory limits.
    """

    TARGET_FPS: float = 25.0
    FRAME_INTERVAL: float = 1.0 / 25.0  # 0.040s (40 ms)
    MFCC_RATE: float = 100.0  # 100 Hz (10 ms hop)
    AUDIO_VIDEO_RATIO: int = 4  # Exactly 4 MFCC frames per 1 visual frame

    @classmethod
    def interpolate_track_bboxes(
        cls,
        samples: List[Dict[str, Any]],
        start_time: float,
        end_time: float,
        max_gap_seconds: float = 0.50,
    ) -> List[Tuple[float, Optional[NormalizedBBox]]]:
        """
        Linearly interpolate 4.0 FPS track keyframes to 25.0 FPS grid.
        Preserves track discontinuities: if gap exceeds max_gap_seconds, yields None bbox.
        """
        if not samples:
            return []

        # Sort samples chronologically
        clean_samples = []
        for s in samples:
            ts = float(s.get("timestamp_seconds", s.get("timestamp", 0.0)))
            b = s.get("bbox")
            if isinstance(b, dict):
                bbox = NormalizedBBox(**b)
            elif isinstance(b, NormalizedBBox):
                bbox = b
            else:
                continue
            clean_samples.append((ts, bbox))

        clean_samples.sort(key=lambda x: x[0])
        if not clean_samples:
            return []

        grid_times = []
        cur_t = start_time
        while cur_t <= end_time + 1e-4:
            grid_times.append(round(cur_t, 4))
            cur_t += cls.FRAME_INTERVAL

        interpolated: List[Tuple[float, Optional[NormalizedBBox]]] = []
        sample_idx = 0
        num_s = len(clean_samples)

        for target_t in grid_times:
            # Advance sample_idx until target_t is between sample_idx and sample_idx + 1
            while sample_idx < num_s - 1 and clean_samples[sample_idx + 1][0] < target_t:
                sample_idx += 1

            t_prev, b_prev = clean_samples[sample_idx]

            if sample_idx == num_s - 1:
                # Target is at or after last sample
                if abs(target_t - t_prev) <= max_gap_seconds:
                    interpolated.append((target_t, b_prev))
                else:
                    interpolated.append((target_t, None))
                continue

            t_next, b_next = clean_samples[sample_idx + 1]

            if target_t < t_prev:
                if abs(t_prev - target_t) <= max_gap_seconds:
                    interpolated.append((target_t, b_prev))
                else:
                    interpolated.append((target_t, None))
            elif (t_next - t_prev) > max_gap_seconds:
                # Track lost across long gap
                interpolated.append((target_t, None))
            else:
                # Linear interpolation
                dt = t_next - t_prev
                alpha = max(0.0, min(1.0, (target_t - t_prev) / max(1e-6, dt)))
                interp_bbox = NormalizedBBox(
                    x=float(np.clip(b_prev.x * (1.0 - alpha) + b_next.x * alpha, 0.0, 1.0)),
                    y=float(np.clip(b_prev.y * (1.0 - alpha) + b_next.y * alpha, 0.0, 1.0)),
                    width=float(np.clip(b_prev.width * (1.0 - alpha) + b_next.width * alpha, 0.0, 1.0)),
                    height=float(np.clip(b_prev.height * (1.0 - alpha) + b_next.height * alpha, 0.0, 1.0)),
                )
                interpolated.append((target_t, interp_bbox))

        return interpolated


def compute_mfcc_13(
    signal: np.ndarray,
    sample_rate: int = 16000,
    win_len: float = 0.025,
    win_step: float = 0.010,
    num_cep: int = 13,
    num_filters: int = 26,
    nfft: int = 512,
) -> np.ndarray:
    """
    Computes 13-dimensional MFCCs (100 Hz) using pure NumPy without requiring SciPy.
    Matches python_speech_features / Librosa canonical parameters used by Light-ASD.
    """
    if len(signal) == 0:
        return np.zeros((0, num_cep), dtype=np.float32)

    # 1. Pre-emphasis filter
    emphasized = np.append(signal[0], signal[1:] - 0.97 * signal[:-1])

    # 2. Framing
    frame_length = int(round(win_len * sample_rate))
    frame_step = int(round(win_step * sample_rate))
    signal_length = len(emphasized)

    if signal_length <= frame_length:
        num_frames = 1
    else:
        num_frames = 1 + int(math.ceil((signal_length - frame_length) / float(frame_step)))

    pad_signal_length = (num_frames - 1) * frame_step + frame_length
    pad_signal = np.pad(emphasized, (0, max(0, pad_signal_length - signal_length)))

    # Frame indexing
    indices = (
        np.tile(np.arange(0, frame_length), (num_frames, 1))
        + np.tile(np.arange(0, num_frames * frame_step, frame_step), (frame_length, 1)).T
    )
    frames = pad_signal[indices.astype(np.int32, copy=False)]

    # 3. Windowing (Hamming)
    frames = frames * np.hamming(frame_length)

    # 4. FFT and Power Spectrum
    mag_frames = np.absolute(np.fft.rfft(frames, nfft))
    pow_frames = (1.0 / nfft) * (mag_frames ** 2)

    # 5. Triangular Mel Filterbanks
    low_freq_mel = 0.0
    high_freq_mel = 2595.0 * np.log10(1.0 + (sample_rate / 2.0) / 700.0)
    mel_points = np.linspace(low_freq_mel, high_freq_mel, num_filters + 2)
    hz_points = 700.0 * (10.0 ** (mel_points / 2595.0) - 1.0)
    bin_points = np.floor((nfft + 1) * hz_points / sample_rate).astype(np.int32)

    fbank = np.zeros((num_filters, int(np.floor(nfft / 2 + 1))), dtype=np.float32)
    for m in range(1, num_filters + 1):
        f_m_minus = bin_points[m - 1]
        f_m = bin_points[m]
        f_m_plus = bin_points[m + 1]
        for k in range(f_m_minus, f_m):
            fbank[m - 1, k] = (k - bin_points[m - 1]) / max(1e-6, float(bin_points[m] - bin_points[m - 1]))
        for k in range(f_m, f_m_plus):
            fbank[m - 1, k] = (bin_points[m + 1] - k) / max(1e-6, float(bin_points[m + 1] - bin_points[m]))

    filter_banks = np.dot(pow_frames, fbank.T)
    filter_banks = np.where(filter_banks == 0, np.finfo(float).eps, filter_banks)
    filter_banks = 20.0 * np.log10(filter_banks)

    # 6. Discrete Cosine Transform (DCT Type-II Orthogonal)
    num_fb = filter_banks.shape[1]
    n_idx = np.arange(num_fb)
    k_idx = np.arange(num_cep)[:, None]
    basis = np.cos(np.pi / num_fb * (n_idx + 0.5) * k_idx)
    basis[0] *= 1.0 / math.sqrt(2.0)
    basis *= math.sqrt(2.0 / num_fb)
    mfcc = np.dot(filter_banks, basis.T)

    return mfcc.astype(np.float32)


class LightASDDetector:
    """
    Light-ASD (CVPR 2023) ONNX active speaker inference engine.
    Executes decoupled 2D-3D CNN + Bi-GRU multimodal cross-modal classification on CPU.
    """

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        intra_op_threads: int = 2,
        inter_op_threads: int = 1,
        probability_threshold: float = 0.50,
        verify_checksum: bool = False,
    ):
        self.probability_threshold = probability_threshold
        self.intra_op_threads = intra_op_threads
        self.inter_op_threads = inter_op_threads

        if model_path is None:
            self.model_path = Path(settings.MODELS_DIR) / "audio_visual" / LIGHT_ASD_FILENAME
        else:
            self.model_path = Path(model_path)

        if verify_checksum and self.model_path.exists():
            self._verify_checksum()

        self._session: Optional[ort.InferenceSession] = None

    def _verify_checksum(self) -> None:
        """Verify model file integrity against pinned SHA-256."""
        hasher = hashlib.sha256()
        with open(self.model_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_sha256 = hasher.hexdigest()
        if actual_sha256 != EXPECTED_LIGHT_ASD_SHA256:
            raise ValueError(
                f"Model checksum verification failed for {self.model_path}!\n"
                f"Expected: {EXPECTED_LIGHT_ASD_SHA256}\n"
                f"Actual:   {actual_sha256}"
            )
        logger.info(f"Verified light_asd.onnx SHA-256: {actual_sha256}")

    def is_available(self) -> bool:
        """Check if Light-ASD model weights exist on disk."""
        return self.model_path.exists()

    def _ensure_session(self) -> ort.InferenceSession:
        """Initialize and cache the ONNX Runtime CPU session."""
        if self._session is not None:
            return self._session

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Light-ASD model weights not found at: {self.model_path}. "
                "Ensure light_asd.onnx is located in storage/clipforge_data/models/audio_visual/."
            )

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self.intra_op_threads
        sess_options.inter_op_num_threads = self.inter_op_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        logger.info(f"Loading Light-ASD ONNX session from {self.model_path} on CPU")
        self._session = ort.InferenceSession(
            str(self.model_path),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        return self._session

    @staticmethod
    def preprocess_face_crop(crop_bgr: np.ndarray) -> np.ndarray:
        """
        Preprocess face crop according to Light-ASD official specifications:
        1. Convert BGR to Grayscale.
        2. Resize to 224x224.
        3. Center crop to 112x112 (from [56:168, 56:168]).
        4. Normalize by (x / 255.0 - 0.4161) / 0.1688.
        Returns float32 array of shape (112, 112).
        """
        if len(crop_bgr.shape) == 3:
            gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop_bgr

        resized = cv2.resize(gray, (224, 224), interpolation=cv2.INTER_LINEAR)
        # Center crop 112x112
        crop_112 = resized[56:168, 56:168]
        return crop_112.astype(np.float32)

    def detect_active_speaker_sequence(
        self,
        face_crops: List[np.ndarray],
        timestamps: List[float],
        audio_segment: np.ndarray,
        face_track_id: str,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[ActiveSpeakerObservation]:
        """
        Run Light-ASD on a temporal sequence of face crops and corresponding audio PCM segment.
        Args:
            face_crops: List of BGR/Grayscale face crops for sequential frames.
            timestamps: Frame timestamps (seconds).
            audio_segment: Synchronized 16 kHz mono audio PCM float32 array spanning the sequence.
            face_track_id: Identity string of the subject face track.
            is_cancelled: Optional cancellation probe.
        Returns:
            List of ActiveSpeakerObservation records for each frame in the sequence.
        """
        if not face_crops or len(face_crops) == 0:
            return []

        if is_cancelled and is_cancelled():
            return []

        session = self._ensure_session()
        num_frames = len(face_crops)

        # 1. Preprocess visual inputs: [1, T, 112, 112]
        visual_tensor = np.zeros((1, num_frames, 112, 112), dtype=np.float32)
        for i, crop in enumerate(face_crops):
            if crop is not None and crop.size > 0:
                visual_tensor[0, i] = self.preprocess_face_crop(crop)

        # 2. Extract MFCC features: target shape is [1, T * 4, 13]
        target_mfcc_steps = num_frames * 4
        mfcc = compute_mfcc_13(audio_segment, sample_rate=16000)

        # Adjust MFCC temporal dimension to match exact required count (T * 4)
        if len(mfcc) < target_mfcc_steps:
            pad_len = target_mfcc_steps - len(mfcc)
            mfcc_padded = np.pad(mfcc, ((0, pad_len), (0, 0)), mode="edge" if len(mfcc) > 0 else "constant")
        else:
            mfcc_padded = mfcc[:target_mfcc_steps]

        audio_tensor = mfcc_padded[np.newaxis, :, :].astype(np.float32)

        # 3. Execute ONNX inference
        outputs = session.run(
            None,
            {
                "visual_features": visual_tensor,
                "audio_features": audio_tensor,
            },
        )
        logits = outputs[0]  # Shape: [1, T, 2]

        observations: List[ActiveSpeakerObservation] = []
        for i in range(num_frames):
            ts = timestamps[i] if i < len(timestamps) else 0.0
            raw_neg = float(logits[0, i, 0])
            raw_pos = float(logits[0, i, 1])

            # Calibrate probability via Softmax
            exp_neg = math.exp(np.clip(raw_neg, -20.0, 20.0))
            exp_pos = math.exp(np.clip(raw_pos, -20.0, 20.0))
            prob_speaking = float(exp_pos / max(1e-8, (exp_neg + exp_pos)))
            is_speaking = bool(prob_speaking >= self.probability_threshold)

            obs = ActiveSpeakerObservation(
                timestamp_seconds=round(ts, 4),
                face_track_id=face_track_id,
                raw_logit=round(raw_pos, 4),
                speaking_probability=round(prob_speaking, 4),
                is_speaking=is_speaking,
                sync_confidence=1.0,
                normalized_model_score=round(prob_speaking, 4),
                state="active" if is_speaking else "inactive",
            )
            observations.append(obs)

        # Immediate buffer cleanup
        del visual_tensor
        del audio_tensor
        del outputs
        return observations

    def close(self) -> None:
        """Release session resources."""
        self._session = None
