"""
ClipForge AI - Local Speaker Embedding Extraction Engine
Extracts 512-dimensional speaker embeddings using the 3D-Speaker CAM++ ONNX model.
Fully local, CPU-optimized, zero cloud dependencies.
"""

from dataclasses import dataclass
import logging
import math
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Union
import numpy as np

from ...core.config import settings

logger = logging.getLogger("clipforge.ai.audio.embeddings")

DEFAULT_MODEL_NAME = "3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx"
EXPECTED_EMBEDDING_DIM = 512
TARGET_SAMPLE_RATE = 16000


@dataclass
class FBankConfig:
    """Kaldi-compliant filterbank configuration for 3D-Speaker CAM++."""
    sample_rate: int = 16000
    num_mel_bins: int = 80
    frame_length_ms: float = 25.0
    frame_shift_ms: float = 10.0
    preemphasis_coefficient: float = 0.97
    low_freq: float = 20.0
    high_freq: float = 7600.0
    dither: float = 0.0
    remove_dc_offset: bool = True
    window_type: str = "povey"
    use_energy: bool = False
    use_cmn: bool = True  # Cepstral Mean Normalization


class FBankExtractor:
    """
    Pure NumPy implementation of Kaldi-compliant 80-bin Mel Filterbank feature extractor.
    Matches standard Kaldi / torchaudio.compliance.kaldi.fbank output format.
    """

    def __init__(self, config: Optional[FBankConfig] = None) -> None:
        self.config = config or FBankConfig()
        self.sample_rate = self.config.sample_rate
        self.num_mel_bins = self.config.num_mel_bins
        self.frame_length = int(round(self.config.frame_length_ms * self.sample_rate / 1000.0))
        self.frame_shift = int(round(self.config.frame_shift_ms * self.sample_rate / 1000.0))

        # FFT size: next power of 2 >= frame_length
        self.n_fft = 1
        while self.n_fft < self.frame_length:
            self.n_fft <<= 1  # 512 for frame_length 400

        # Precompute window
        self._window = self._build_window()

        # Precompute Mel filterbank matrix (shape: n_fft // 2 + 1, num_mel_bins)
        self._filterbank = self._build_mel_filterbank()

    def _build_window(self) -> np.ndarray:
        """Povey window: (0.5 - 0.5 * cos(2 * pi * i / (N - 1))) ^ 0.85"""
        n = self.frame_length
        indices = np.arange(n, dtype=np.float32)
        if self.config.window_type == "povey":
            hann = 0.5 - 0.5 * np.cos(2.0 * np.pi * indices / (n - 1))
            return np.power(hann, 0.85).astype(np.float32)
        elif self.config.window_type == "hamming":
            return (0.54 - 0.46 * np.cos(2.0 * np.pi * indices / (n - 1))).astype(np.float32)
        elif self.config.window_type == "hanning":
            return (0.5 - 0.5 * np.cos(2.0 * np.pi * indices / (n - 1))).astype(np.float32)
        else:
            return np.ones(n, dtype=np.float32)

    @staticmethod
    def _hz_to_mel(hz: float) -> float:
        """Kaldi Mel conversion: 1127.0 * ln(1.0 + hz / 700.0)"""
        return 1127.0 * math.log(1.0 + hz / 700.0)

    @staticmethod
    def _mel_to_hz(mel: float) -> float:
        """Kaldi inverse Mel conversion: 700.0 * (exp(mel / 1127.0) - 1.0)"""
        return 700.0 * (math.exp(mel / 1127.0) - 1.0)

    def _build_mel_filterbank(self) -> np.ndarray:
        """Construct triangular Mel filterbank matrix matching Kaldi."""
        num_bins = self.num_mel_bins
        n_fft = self.n_fft
        nyquist = self.sample_rate / 2.0
        high_freq = min(self.config.high_freq, nyquist)
        low_freq = max(self.config.low_freq, 0.0)

        low_mel = self._hz_to_mel(low_freq)
        high_mel = self._hz_to_mel(high_freq)
        mel_points = np.linspace(low_mel, high_mel, num_bins + 2)
        hz_points = np.array([self._mel_to_hz(m) for m in mel_points])

        # Convert Hz to FFT bin indices (float)
        bin_points = hz_points * (n_fft + 1) / self.sample_rate

        num_fft_bins = n_fft // 2 + 1
        weights = np.zeros((num_fft_bins, num_bins), dtype=np.float32)

        for i in range(num_bins):
            left = bin_points[i]
            center = bin_points[i + 1]
            right = bin_points[i + 2]

            for j in range(num_fft_bins):
                if left < j < center:
                    weights[j, i] = (j - left) / (center - left)
                elif center <= j < right:
                    weights[j, i] = (right - j) / (right - center)

        return weights

    def compute_fbank(self, samples: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """
        Extract 80-bin Mel filterbank features from 1D audio waveform.
        
        Args:
            samples: 1D numpy array of audio samples (float32 in [-1, 1] or int16).
            sample_rate: sampling frequency in Hz (must be 16000).
            
        Returns:
            np.ndarray of shape (T, 80) where T is the number of frames.
        """
        if samples is None or len(samples) == 0:
            return np.zeros((0, self.num_mel_bins), dtype=np.float32)

        audio = np.asarray(samples, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.flatten()

        # Kaldi scaling: audio waveform values are scaled to [-32768, 32767]
        max_val = np.max(np.abs(audio))
        if max_val <= 1.01:
            audio = audio * 32768.0

        num_samples = len(audio)

        # Pad if audio is shorter than a single frame
        if num_samples < self.frame_length:
            pad_width = self.frame_length - num_samples
            audio = np.pad(audio, (0, pad_width), mode="reflect" if num_samples > 1 else "constant")
            num_samples = len(audio)

        # Calculate number of frames
        num_frames = 1 + (num_samples - self.frame_length) // self.frame_shift
        if num_frames <= 0:
            num_frames = 1

        # Vectorized frame extraction
        indices = (
            np.arange(0, self.frame_length)[None, :]
            + np.arange(0, num_frames)[:, None] * self.frame_shift
        )
        indices = np.clip(indices, 0, num_samples - 1)
        frames = audio[indices].copy()  # (num_frames, frame_length)

        # Remove DC offset per frame if requested
        if self.config.remove_dc_offset:
            frames -= np.mean(frames, axis=1, keepdims=True)

        # Pre-emphasis: s[t] - preemph * s[t-1]
        preemph = self.config.preemphasis_coefficient
        if preemph > 0:
            first_col = frames[:, 0:1] * (1.0 - preemph)
            rest_cols = frames[:, 1:] - preemph * frames[:, :-1]
            frames = np.concatenate([first_col, rest_cols], axis=1)

        # Apply window
        frames *= self._window[None, :]

        # RFFT and power spectrum
        spectra = np.fft.rfft(frames, n=self.n_fft, axis=1)  # (num_frames, 257)
        power_spectra = np.abs(spectra) ** 2

        # Apply mel filterbank
        mel_energies = np.matmul(power_spectra, self._filterbank)  # (num_frames, num_mel_bins)

        # Floor energy to avoid log(0)
        mel_energies = np.maximum(mel_energies, 1.0)
        log_mel = np.log(mel_energies)

        # Cepstral Mean Normalization (CMN) across time
        if self.config.use_cmn and num_frames > 1:
            log_mel -= np.mean(log_mel, axis=0, keepdims=True)

        return log_mel.astype(np.float32)


class SpeakerEmbeddingExtractor:
    """
    Local-first speaker embedding extractor using 3D-Speaker CAM++ ONNX model.
    Generates 512-dimensional, L2-normalized speaker representation vectors on CPU.
    Thread-safe with singleton session caching.
    """

    _instance: Optional["SpeakerEmbeddingExtractor"] = None
    _lock = threading.Lock()

    def __init__(self, model_path: Optional[Union[str, Path]] = None) -> None:
        self.model_path = Path(model_path) if model_path else self._default_model_path()
        self._session: Any = None
        self._session_lock = threading.Lock()
        self.fbank_extractor = FBankExtractor()
        self.embedding_dim = EXPECTED_EMBEDDING_DIM
        self.sample_rate = TARGET_SAMPLE_RATE

    @classmethod
    def get_instance(cls, model_path: Optional[Union[str, Path]] = None) -> "SpeakerEmbeddingExtractor":
        """Singleton accessor ensuring only one ONNX session is resident in RAM."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(model_path)
            return cls._instance

    @staticmethod
    def _default_model_path() -> Path:
        """Resolve model path from application settings."""
        return settings.MODELS_DIR / "audio" / DEFAULT_MODEL_NAME

    def is_model_available(self) -> bool:
        """Check if the ONNX model binary exists and is readable."""
        try:
            return self.model_path.is_file() and self.model_path.stat().st_size > 10_000_000
        except Exception:
            return False

    def get_capabilities(self) -> Dict[str, Any]:
        """Return runtime diagnostic and model capability information."""
        return {
            "model_name": "3D-Speaker CAM++ (VoxCeleb 16k)",
            "model_file": self.model_path.name,
            "model_path": str(self.model_path),
            "model_available": self.is_model_available(),
            "model_size_bytes": self.model_path.stat().st_size if self.is_model_available() else 0,
            "embedding_dimension": self.embedding_dim,
            "sample_rate": self.sample_rate,
            "feature_type": "Kaldi-compliant 80-bin FBank with CMN",
            "execution_provider": "CPUExecutionProvider",
            "l2_normalized": True,
        }

    def _get_session(self) -> Any:
        """Lazy loader for ONNX Runtime inference session with CPU provider."""
        if self._session is not None:
            return self._session

        with self._session_lock:
            if self._session is not None:
                return self._session

            if not self.is_model_available():
                raise FileNotFoundError(
                    f"CAM++ ONNX model file not found at: {self.model_path}. "
                    "Ensure Phase 8 Stage 3 model assets are downloaded."
                )

            import onnxruntime as ort

            logger.info("Initializing 3D-Speaker CAM++ ONNX session on CPU: %s", self.model_path)
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = 2
            sess_options.inter_op_num_threads = 1
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            providers = ["CPUExecutionProvider"]
            self._session = ort.InferenceSession(
                str(self.model_path),
                sess_options=sess_options,
                providers=providers,
            )
            logger.info("CAM++ ONNX session successfully loaded.")
            return self._session

    def extract_embedding(
        self,
        audio_segment: np.ndarray,
        sample_rate: int = 16000,
        min_duration_sec: float = 0.25,
    ) -> Optional[np.ndarray]:
        """
        Extract a 512-dimensional L2-normalized speaker embedding from audio.
        
        Args:
            audio_segment: 1D numpy array of audio samples (float32 [-1, 1] or int16).
            sample_rate: audio sample rate in Hz (16000 expected).
            min_duration_sec: minimum required speech duration (default 0.25s).
            
        Returns:
            np.ndarray of shape (512,) float32 normalized vector, or None if too short/silent.
        """
        if audio_segment is None or len(audio_segment) == 0:
            return None

        # Check minimum duration threshold (e.g. 0.25s = 4000 samples @ 16kHz)
        min_samples = int(min_duration_sec * sample_rate)
        if len(audio_segment) < min_samples:
            logger.debug(
                "Audio segment too short for embedding extraction (%d < %d samples)",
                len(audio_segment),
                min_samples,
            )
            return None

        # Check for absolute silence
        peak = float(np.max(np.abs(audio_segment)))
        if peak < 1e-4:
            logger.debug("Audio segment is silent; skipping embedding extraction.")
            return None

        # Extract Kaldi 80-bin FBank features
        fbank = self.fbank_extractor.compute_fbank(audio_segment, sample_rate)
        if len(fbank) == 0:
            return None

        # Shape required by ONNX model: (batch_size, time_steps, 80)
        x = np.expand_dims(fbank, axis=0).astype(np.float32)

        session = self._get_session()
        with self._session_lock:
            input_name = session.get_inputs()[0].name
            raw_output = session.run(None, {input_name: x})[0]

        # raw_output shape is (1, 512)
        embedding = raw_output.squeeze().astype(np.float32)

        # L2 Normalization: v / (||v||_2 + eps)
        norm = float(np.linalg.norm(embedding))
        if norm > 1e-12:
            embedding = embedding / norm
        else:
            return None

        return embedding

    def extract_embeddings_batch(
        self,
        audio_segments: List[np.ndarray],
        sample_rate: int = 16000,
        min_duration_sec: float = 0.25,
    ) -> List[Optional[np.ndarray]]:
        """
        Extract embeddings for a list of audio segments sequentially.
        
        Returns:
            List of 512-dim normalized vectors (or None for segments failing validation).
        """
        results: List[Optional[np.ndarray]] = []
        for segment in audio_segments:
            emb = self.extract_embedding(segment, sample_rate, min_duration_sec)
            results.append(emb)
        return results

    @staticmethod
    def compute_cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Compute cosine similarity between two normalized embeddings in [-1.0, 1.0].
        For unit vectors, dot product equals cosine similarity.
        """
        if emb1 is None or emb2 is None:
            return 0.0
        v1 = emb1.flatten()
        v2 = emb2.flatten()
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-12 or norm2 < 1e-12:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    @staticmethod
    def compute_cosine_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Compute cosine distance: 1.0 - cosine_similarity.
        Bounded in [0.0, 2.0].
        """
        sim = SpeakerEmbeddingExtractor.compute_cosine_similarity(emb1, emb2)
        return float(np.clip(1.0 - sim, 0.0, 2.0))

    def close(self) -> None:
        """Release ONNX session resources."""
        with self._session_lock:
            self._session = None
