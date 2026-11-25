"""
ClipForge AI - Audio Preprocessor Module
Extracts, resamples, inspects, and streams audio chunks for speech intelligence and VAD.
Supports 16kHz mono PCM for speech models, 48kHz stereo for export, silence analysis,
clipping detection, and memory-bounded chunk streaming.
"""

import asyncio
import logging
import math
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, Generator, List, Optional, Tuple

import numpy as np

from ...core.config import settings
from ...schemas.audio_schemas import AudioMetadataSchema
from ...video.ffmpeg_manager import FFmpegManager, FFmpegProgress
from ...video.ffprobe_manager import FFprobeManager

logger = logging.getLogger("clipforge.ai.audio.preprocessor")


class AudioChunk:
    """Represents a bounded slice of audio for streaming VAD/model inference."""

    def __init__(
        self,
        chunk_index: int,
        start_seconds: float,
        end_seconds: float,
        samples: np.ndarray,
        sample_rate: int = 16000,
        is_final: bool = False,
    ):
        self.chunk_index = chunk_index
        self.start_seconds = start_seconds
        self.end_seconds = end_seconds
        self.samples = samples  # 1D float32 numpy array normalized to [-1.0, 1.0]
        self.sample_rate = sample_rate
        self.is_final = is_final

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


class AudioPreprocessor:
    """
    Handles robust extraction, validation, inspection, and chunked streaming of audio signals.
    Never overwrites or mutates source media.
    """

    SILENCE_RMS_THRESHOLD: float = 1e-4  # ~ -80 dBFS
    CLIPPING_THRESHOLD: float = 0.999

    @classmethod
    def inspect_audio_array(
        cls, samples: np.ndarray, sample_rate: int = 16000
    ) -> Tuple[float, float, bool, bool]:
        """
        Analyze audio array samples.
        Returns:
            (peak_amplitude, rms_level, audio_is_silent, clipping_detected)
        """
        if samples is None or len(samples) == 0:
            return 0.0, 0.0, True, False

        float_samples = samples.astype(np.float32)
        if np.max(np.abs(float_samples)) > 1.0:
            float_samples = float_samples / 32768.0

        peak = float(np.max(np.abs(float_samples)))
        rms = float(np.sqrt(np.mean(float_samples**2)))
        is_silent = bool(rms < cls.SILENCE_RMS_THRESHOLD or peak < 1e-5)
        clipping = bool(peak >= cls.CLIPPING_THRESHOLD)

        return round(peak, 5), round(rms, 6), is_silent, clipping

    @classmethod
    async def extract_and_preprocess(
        cls,
        source_media_path: str,
        output_wav_path: Optional[str] = None,
        target_sample_rate: int = 16000,
        channels: int = 1,
        on_progress: Optional[Callable[[FFmpegProgress], Coroutine[None, None, None]]] = None,
        process_id: Optional[str] = None,
        cancel_token: Optional[Any] = None,
    ) -> Tuple[str, AudioMetadataSchema]:
        """
        Extract clean uncompressed WAV audio from source video/audio file.
        Resamples and channels as requested (e.g. 16kHz mono for speech, 48kHz stereo for render).
        Returns:
            (target_wav_path, AudioMetadataSchema)
        """
        in_p = Path(source_media_path).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Source media not found: {source_media_path}")

        t_start = time.perf_counter()

        # Probe source technical metadata
        src_meta = FFprobeManager.probe(str(in_p))
        if not src_meta.valid:
            raise ValueError(f"Unable to probe source media: {src_meta.error or 'Invalid file format'}")

        has_audio = src_meta.has_audio and src_meta.audio_stream is not None

        if not has_audio:
            # Source video has no audio stream
            logger.warning(f"Source video {in_p.name} contains no audio stream.")
            empty_meta = AudioMetadataSchema(
                source_sample_rate=None,
                source_channels=None,
                source_codec=None,
                source_duration=src_meta.duration_seconds,
                processed_sample_rate=target_sample_rate,
                processed_channels=channels,
                sample_format="pcm_s16le",
                audio_available=False,
                audio_is_silent=True,
                peak_amplitude=0.0,
                rms_level=0.0,
                clipping_detected=False,
                processing_duration=round(time.perf_counter() - t_start, 3),
                processing_device="cpu",
            )
            return "", empty_meta

        src_audio = src_meta.audio_stream
        src_sr = src_audio.sample_rate if src_audio else 44100
        src_ch = src_audio.channels if src_audio else 2
        src_codec = src_audio.codec_name if src_audio else "unknown"
        src_duration = src_meta.duration_seconds

        # Determine target output path
        if not output_wav_path:
            cache_dir = settings.DATA_DIR / "cache" / "audio"
            cache_dir.mkdir(parents=True, exist_ok=True)
            output_wav_path = str(cache_dir / f"{in_p.stem}_{target_sample_rate}hz_{channels}ch.wav")

        out_p = Path(output_wav_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if cancel_token and cancel_token.is_cancelled:
            raise asyncio.CancelledError("Audio extraction cancelled before FFmpeg start.")

        # FFmpeg extraction arguments
        # Using aresample=async=1:first_pts=0 preserves timeline alignment for non-zero audio start times
        args = [
            "-i", str(in_p),
            "-vn",
            "-af", "aresample=async=1:first_pts=0",
            "-acodec", "pcm_s16le",
            "-ar", str(target_sample_rate),
            "-ac", str(channels),
            str(out_p),
        ]

        logger.info(
            f"Extracting audio: {in_p.name} -> {out_p.name} ({target_sample_rate}Hz, {channels}ch)"
        )
        res = await FFmpegManager.run(
            args=args,
            process_id=process_id,
            total_duration=src_duration,
            on_progress=on_progress,
            output_file_to_verify=str(out_p),
        )

        if cancel_token and cancel_token.is_cancelled:
            if out_p.exists():
                out_p.unlink(missing_ok=True)
            raise asyncio.CancelledError("Audio extraction cancelled during execution.")

        if not res.success or not out_p.exists():
            raise RuntimeError(f"FFmpeg audio extraction failed: {res.error_message}")

        # Quick sample measurement on initial window
        metrics = cls.sample_file_metrics(str(out_p))
        peak = metrics.get("peak", 0.0)
        rms = metrics.get("rms", 0.0)
        is_silent = metrics.get("is_silent", False)
        clipping = metrics.get("clipping", False)

        metadata = AudioMetadataSchema(
            source_sample_rate=src_sr,
            source_channels=src_ch,
            source_codec=src_codec,
            source_duration=round(src_duration, 3),
            processed_sample_rate=target_sample_rate,
            processed_channels=channels,
            sample_format="pcm_s16le",
            audio_available=True,
            audio_is_silent=is_silent,
            peak_amplitude=peak,
            rms_level=rms,
            clipping_detected=clipping,
            processing_duration=round(time.perf_counter() - t_start, 3),
            processing_device="cpu",
        )

        return str(out_p), metadata

    @classmethod
    def sample_file_metrics(cls, wav_path: str, max_seconds_to_read: float = 60.0) -> Dict[str, Any]:
        """Read sample headers and initial duration to evaluate signal metrics."""
        import wave

        try:
            with wave.open(wav_path, "rb") as wf:
                sr = wf.getframerate()
                ch = wf.getnchannels()
                total_frames = wf.getnframes()
                duration = total_frames / float(sr) if sr > 0 else 0.0
                n_frames = min(int(sr * max_seconds_to_read), total_frames)
                raw_bytes = wf.readframes(n_frames)
                samples = np.frombuffer(raw_bytes, dtype=np.int16)
                if ch > 1:
                    samples = samples[:: ch]
                peak, rms, is_silent, clipping = cls.inspect_audio_array(samples, sr)
                return {
                    "peak": peak,
                    "rms": rms,
                    "is_silent": is_silent,
                    "clipping": clipping,
                    "sample_rate": sr,
                    "channels": ch,
                    "duration": duration,
                }
        except Exception as e:
            logger.warning(f"Error reading WAV metrics from {wav_path}: {e}")
            return {
                "peak": 0.0,
                "rms": 0.0,
                "is_silent": True,
                "clipping": False,
                "sample_rate": 16000,
                "channels": 1,
                "duration": 0.0,
            }

    @classmethod
    def load_wav_as_float32(cls, wav_path: str) -> Tuple[np.ndarray, int]:
        """
        Load standard 16-bit PCM WAV into normalized 1D float32 numpy array [-1.0, 1.0].
        Handles mono and multi-channel downmixing.
        """
        import wave

        p = Path(wav_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"WAV file does not exist: {wav_path}")

        with wave.open(str(p), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        if sample_width == 2:
            raw_int = np.frombuffer(raw_bytes, dtype=np.int16)
            float_data = raw_int.astype(np.float32) / 32768.0
        elif sample_width == 4:
            raw_int = np.frombuffer(raw_bytes, dtype=np.int32)
            float_data = raw_int.astype(np.float32) / 2147483648.0
        elif sample_width == 1:
            raw_int = np.frombuffer(raw_bytes, dtype=np.uint8)
            float_data = (raw_int.astype(np.float32) - 128.0) / 128.0
        else:
            raise ValueError(f"Unsupported sample width: {sample_width} bytes")

        if channels > 1:
            float_data = float_data.reshape(-1, channels).mean(axis=1)

        return float_data, sample_rate

    @classmethod
    def stream_wav_chunks(
        cls,
        wav_path: str,
        chunk_duration_sec: float = 30.0,
        overlap_sec: float = 1.0,
        cancel_token: Optional[Any] = None,
    ) -> Generator[AudioChunk, None, None]:
        """
        Streams audio chunks without loading entire multi-hour audio into RAM.
        Reads consecutive blocks with defined overlap for boundary continuity.
        """
        import wave

        p = Path(wav_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {wav_path}")

        with wave.open(str(p), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            total_frames = wf.getnframes()

            if sample_width != 2:
                # Fallback to load full array if non-16bit
                full_samples, sr = cls.load_wav_as_float32(str(p))
                yield from cls.stream_array_chunks(full_samples, sr, chunk_duration_sec, overlap_sec, cancel_token)
                return

            chunk_frames = int(chunk_duration_sec * sample_rate)
            overlap_frames = int(overlap_sec * sample_rate)
            step_frames = max(1, chunk_frames - overlap_frames)

            current_frame = 0
            chunk_idx = 0

            while current_frame < total_frames:
                if cancel_token and cancel_token.is_cancelled:
                    raise asyncio.CancelledError("Chunk streaming cancelled.")

                wf.setpos(current_frame)
                read_count = min(chunk_frames, total_frames - current_frame)
                raw_bytes = wf.readframes(read_count)
                if not raw_bytes:
                    break

                raw_int = np.frombuffer(raw_bytes, dtype=np.int16)
                if channels > 1:
                    raw_int = raw_int.reshape(-1, channels).mean(axis=1)

                float_samples = raw_int.astype(np.float32) / 32768.0

                start_sec = current_frame / float(sample_rate)
                end_sec = (current_frame + read_count) / float(sample_rate)
                is_final = (current_frame + read_count) >= total_frames

                yield AudioChunk(
                    chunk_index=chunk_idx,
                    start_seconds=round(start_sec, 3),
                    end_seconds=round(end_sec, 3),
                    samples=float_samples,
                    sample_rate=sample_rate,
                    is_final=is_final,
                )

                if is_final:
                    break

                current_frame += step_frames
                chunk_idx += 1

    @classmethod
    def stream_array_chunks(
        cls,
        samples: Optional[np.ndarray] = None,
        sample_rate: int = 16000,
        chunk_duration_sec: float = 30.0,
        overlap_sec: float = 1.0,
        cancel_token: Optional[Any] = None,
        audio: Optional[np.ndarray] = None,
    ) -> Generator[AudioChunk, None, None]:
        """Stream chunks from an in-memory numpy array with temporal windowing."""
        target_samples = samples if samples is not None else audio
        if target_samples is None:
            raise ValueError("samples or audio array must be provided.")

        total_samples = len(target_samples)
        chunk_size = int(chunk_duration_sec * sample_rate)
        overlap_size = int(overlap_sec * sample_rate)
        step_size = max(1, chunk_size - overlap_size)

        current_idx = 0
        chunk_idx = 0

        while current_idx < total_samples:
            if cancel_token and cancel_token.is_cancelled:
                raise asyncio.CancelledError("Chunk streaming cancelled.")

            end_idx = min(current_idx + chunk_size, total_samples)
            slice_samples = target_samples[current_idx:end_idx]
            is_final = end_idx >= total_samples

            start_sec = current_idx / float(sample_rate)
            end_sec = end_idx / float(sample_rate)

            yield AudioChunk(
                chunk_index=chunk_idx,
                start_seconds=round(start_sec, 3),
                end_seconds=round(end_sec, 3),
                samples=slice_samples,
                sample_rate=sample_rate,
                is_final=is_final,
            )

            if is_final:
                break

            current_idx += step_size
            chunk_idx += 1
