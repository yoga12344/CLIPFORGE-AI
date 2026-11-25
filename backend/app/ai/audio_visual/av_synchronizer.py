"""
ClipForge AI - Audio-Visual Temporal Synchronizer
Aligns decoded video presentation timestamps (PTS) with the canonical 16 kHz mono audio timeline.
Handles Variable Frame Rate (VFR), stream offsets, non-zero start timestamps, and window slicing.
Local-first, CPU-optimized, zero cloud dependencies.
"""

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger("clipforge.ai.audio_visual.sync")

CANONICAL_AUDIO_SAMPLE_RATE = 16000
DEFAULT_AV_WINDOW_DURATION = 0.40  # 400 ms default audio context


@dataclass
class StreamSyncInfo:
    """Detailed timing and synchronization parameters between video and audio streams."""
    video_start_time: float = 0.0        # Source video stream start PTS (seconds)
    audio_start_time: float = 0.0        # Source audio stream start PTS (seconds)
    relative_offset_seconds: float = 0.0 # audio_start_time - video_start_time
    is_vfr: bool = False                 # Whether video uses Variable Frame Rate
    nominal_fps: float = 30.0
    sync_uncertainty_seconds: float = 0.005 # Expected alignment precision margin
    audio_sample_rate: int = CANONICAL_AUDIO_SAMPLE_RATE
    total_audio_samples: int = 0
    total_video_frames: int = 0
    has_audio: bool = True


@dataclass
class SynchronizedAVWindow:
    """A temporal window of audio samples precisely aligned to a video timestamp."""
    center_timestamp: float              # Center video PTS timestamp (seconds)
    window_duration: float               # Duration in seconds (e.g. 0.40s)
    audio_samples: np.ndarray            # 1D float32 normalized PCM [-1.0, 1.0]
    sample_rate: int
    is_padded_left: bool                 # True if window exceeded start of audio stream
    is_padded_right: bool                # True if window exceeded end of audio stream
    sync_confidence: float               # Alignment reliability [0.0, 1.0]


class AudioVisualSynchronizer:
    """
    Synchronizes video frame timestamps with 16 kHz mono audio PCM buffers.
    Never relies on naive frame_idx / fps on VFR video.
    """

    def __init__(
        self,
        audio_samples: Optional[np.ndarray] = None,
        sync_info: Optional[StreamSyncInfo] = None,
        default_window_duration: float = DEFAULT_AV_WINDOW_DURATION,
        sample_rate: int = CANONICAL_AUDIO_SAMPLE_RATE,
    ):
        """
        Args:
            audio_samples: Pre-loaded 16 kHz mono float32 waveform, or None.
            sync_info: Stream offset and timing metadata.
            default_window_duration: Temporal duration in seconds for audio slicing.
            sample_rate: Audio sample rate (default 16000 Hz).
        """
        self.sample_rate = sample_rate
        self.default_window_duration = default_window_duration
        self.sync_info = sync_info or StreamSyncInfo(audio_sample_rate=sample_rate)

        if audio_samples is not None:
            self.set_audio_samples(audio_samples)
        else:
            self._audio = np.zeros(0, dtype=np.float32)

    def set_audio_samples(self, samples: np.ndarray) -> None:
        """Set or update the audio PCM buffer."""
        if samples.ndim > 1:
            # Flatten or average multi-channel to mono
            samples = np.mean(samples, axis=1) if samples.shape[1] > 1 else samples.squeeze()
        self._audio = np.ascontiguousarray(samples, dtype=np.float32)
        self.sync_info.total_audio_samples = len(self._audio)
        self.sync_info.has_audio = len(self._audio) > 0

    @classmethod
    def from_wav_file(
        cls,
        wav_path: Union[str, Path],
        sync_info: Optional[StreamSyncInfo] = None,
        default_window_duration: float = DEFAULT_AV_WINDOW_DURATION,
    ) -> "AudioVisualSynchronizer":
        """Load from a 16 kHz WAV file."""
        import wave
        p = Path(wav_path)
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {wav_path}")

        with wave.open(str(p), "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        if sample_width == 2:
            data = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            data = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
        elif sample_width == 1:
            data = (np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            raise ValueError(f"Unsupported WAV sample width: {sample_width}")

        if n_channels > 1:
            data = data.reshape(-1, n_channels).mean(axis=1)

        info = sync_info or StreamSyncInfo()
        info.audio_sample_rate = framerate
        info.total_audio_samples = len(data)
        return cls(
            audio_samples=data,
            sync_info=info,
            default_window_duration=default_window_duration,
            sample_rate=framerate,
        )

    def video_pts_to_audio_time(self, video_pts: float) -> float:
        """
        Map video Presentation Timestamp (seconds) to corresponding audio timeline position.
        Accounts for relative stream start offset.
        """
        # If audio stream starts after video (positive offset), audio time = video_pts - relative_offset
        return video_pts - self.sync_info.relative_offset_seconds

    def extract_audio_window(
        self,
        video_pts: float,
        window_duration: Optional[float] = None,
    ) -> SynchronizedAVWindow:
        """
        Extract an audio window of duration W centered symmetrically around video_pts.
        Window spans [video_pts - W/2, video_pts + W/2].
        Boundary conditions outside audio stream are zero-padded.
        """
        w_dur = window_duration or self.default_window_duration
        target_sample_count = int(round(w_dur * self.sample_rate))

        if not self.sync_info.has_audio or len(self._audio) == 0:
            return SynchronizedAVWindow(
                center_timestamp=video_pts,
                window_duration=w_dur,
                audio_samples=np.zeros(target_sample_count, dtype=np.float32),
                sample_rate=self.sample_rate,
                is_padded_left=True,
                is_padded_right=True,
                sync_confidence=0.0,
            )

        audio_center_time = self.video_pts_to_audio_time(video_pts)
        t_start = audio_center_time - (w_dur / 2.0)
        t_end = t_start + w_dur

        idx_start = int(round(t_start * self.sample_rate))
        idx_end = idx_start + target_sample_count

        total_samples = len(self._audio)
        is_padded_left = False
        is_padded_right = False

        # Compute valid overlap bounds with available audio buffer
        buf_start = max(0, idx_start)
        buf_end = min(total_samples, idx_end)

        pad_left = 0
        if idx_start < 0:
            pad_left = -idx_start
            is_padded_left = True

        pad_right = 0
        if idx_end > total_samples:
            pad_right = idx_end - total_samples
            is_padded_right = True

        # Extract available slice
        if buf_end > buf_start:
            valid_slice = self._audio[buf_start:buf_end]
        else:
            valid_slice = np.zeros(0, dtype=np.float32)

        # Assemble full padded window
        if pad_left > 0 or pad_right > 0:
            parts = []
            if pad_left > 0:
                parts.append(np.zeros(pad_left, dtype=np.float32))
            if len(valid_slice) > 0:
                parts.append(valid_slice)
            if pad_right > 0:
                parts.append(np.zeros(pad_right, dtype=np.float32))
            window_samples = np.concatenate(parts)
        else:
            window_samples = valid_slice.copy()

        # Enforce exact length
        if len(window_samples) != target_sample_count:
            if len(window_samples) < target_sample_count:
                window_samples = np.pad(window_samples, (0, target_sample_count - len(window_samples)))
            else:
                window_samples = window_samples[:target_sample_count]

        # Confidence decays if significant padding was needed
        valid_fraction = max(0.0, (len(valid_slice) / float(target_sample_count)))
        sync_confidence = round(float(valid_fraction), 3)

        return SynchronizedAVWindow(
            center_timestamp=round(video_pts, 4),
            window_duration=w_dur,
            audio_samples=window_samples,
            sample_rate=self.sample_rate,
            is_padded_left=is_padded_left,
            is_padded_right=is_padded_right,
            sync_confidence=sync_confidence,
        )

    def extract_audio_windows_for_timestamps(
        self,
        video_timestamps: List[float],
        window_duration: Optional[float] = None,
    ) -> List[SynchronizedAVWindow]:
        """Batch extract synchronized audio windows for a sequence of video timestamps."""
        return [self.extract_audio_window(t, window_duration) for t in video_timestamps]
