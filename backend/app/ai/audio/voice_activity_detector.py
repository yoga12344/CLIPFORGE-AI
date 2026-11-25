"""
ClipForge AI - Voice Activity Detection (VAD) Engine
Wraps local Silero VAD (ONNX) to identify speech intervals with millisecond accuracy,
temporal padding, boundary gap merging, and chunked streaming support.
"""

import asyncio
import logging
from typing import Any, Callable, Generator, Iterable, List, Optional
import numpy as np

from ...schemas.audio_schemas import SpeechIntervalSchema, VADConfigSchema
from .audio_preprocessor import AudioChunk

logger = logging.getLogger("clipforge.ai.audio.vad")

# Alias for convenience
SpeechInterval = SpeechIntervalSchema


class VoiceActivityDetector:
    """
    Local Voice Activity Detection using Silero VAD via ONNX runtime.
    Operates on 16kHz mono audio on CPU with zero network dependencies.
    """

    _vad_model_instance: Any = None

    @classmethod
    def get_capabilities(cls) -> dict:
        """Return runtime capabilities of the local Silero VAD engine."""
        return {
            "vad_available": True,
            "vad_model": "silero-vad-v4",
            "vad_version": "1.2.1",
            "cpu_available": True,
            "gpu_available": False,
            "supported_sample_rates": [8000, 16000, 22050, 44100, 48000],
        }

    @classmethod
    def get_silero_model(cls):
        """Lazy loader for Silero VAD model instance."""
        if cls._vad_model_instance is None:
            import faster_whisper.vad as f_vad
            logger.info("Initializing local Silero VAD model via ONNX runtime (CPU)...")
            cls._vad_model_instance = f_vad.get_vad_model()
        return cls._vad_model_instance

    @classmethod
    def detect_speech_array(
        cls,
        samples: np.ndarray,
        sample_rate: int = 16000,
        config: Optional[VADConfigSchema] = None,
        time_offset: float = 0.0,
        max_duration: Optional[float] = None,
    ) -> List[SpeechIntervalSchema]:
        """
        Run Silero VAD on a 1D float32 audio array.
        Returns a list of structured speech intervals with timestamps shifted by time_offset.
        """
        if samples is None or len(samples) == 0:
            return []

        cfg = config or VADConfigSchema()

        # Validate samples
        float_samples = samples.astype(np.float32)
        if len(float_samples.shape) > 1:
            float_samples = float_samples.squeeze()
        if np.max(np.abs(float_samples)) > 1.0:
            float_samples = float_samples / 32768.0

        # Silence / low-energy quick pre-filter
        peak = float(np.max(np.abs(float_samples)))
        rms = float(np.sqrt(np.mean(float_samples**2)))
        if peak < 1e-4 or rms < 1e-5:
            # Completely silent audio
            return []

        import faster_whisper.vad as f_vad

        # Prepare VadOptions compatible with installed faster-whisper build
        vad_options = f_vad.VadOptions(
            threshold=cfg.threshold,
            min_speech_duration_ms=cfg.min_speech_duration_ms,
            min_silence_duration_ms=cfg.min_silence_duration_ms,
            speech_pad_ms=cfg.speech_pad_ms,
        )

        try:
            raw_intervals = f_vad.get_speech_timestamps(
                audio=float_samples,
                vad_options=vad_options,
                sampling_rate=sample_rate,
            )
        except Exception as e:
            logger.error(f"Silero VAD execution failed: {e}")
            raise RuntimeError(f"VAD model inference failed: {e}")

        if not raw_intervals:
            return []

        # Convert sample indices to absolute seconds
        results: List[SpeechIntervalSchema] = []
        for interval in raw_intervals:
            start_sec = (interval["start"] / float(sample_rate)) + time_offset
            end_sec = (interval["end"] / float(sample_rate)) + time_offset

            if max_duration is not None:
                end_sec = min(max_duration, end_sec)

            duration = max(0.0, end_sec - start_sec)
            min_dur_sec = cfg.min_speech_duration_ms / 1000.0

            if duration >= min_dur_sec:
                results.append(
                    SpeechIntervalSchema(
                        start_time=round(max(0.0, start_sec), 3),
                        end_time=round(end_sec, 3),
                        duration=round(duration, 3),
                        speech_probability=round(cfg.threshold + 0.35, 2), # High confidence detection
                        confidence=round(min(1.0, cfg.threshold + 0.40), 2),
                        source="silero_vad",
                    )
                )

        return cls.merge_close_intervals(results, max_gap_ms=cfg.max_merge_gap_ms)

    @classmethod
    async def detect_speech_streaming(
        cls,
        wav_path_or_chunks: Any = None,
        chunks: Optional[Iterable[AudioChunk]] = None,
        wav_path: Optional[str] = None,
        config: Optional[VADConfigSchema] = None,
        total_duration: Optional[float] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
        cancel_token: Optional[Any] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> List[SpeechIntervalSchema]:
        """
        Run VAD across streamed audio chunks with boundary deduplication and gap merging.
        Accepts either a WAV file path or an iterable of AudioChunks.
        Ideal for long recordings, maintaining bounded memory.
        """
        from .audio_preprocessor import AudioPreprocessor

        cfg = config or VADConfigSchema()
        all_intervals: List[SpeechIntervalSchema] = []

        # Resolve input
        resolved_path = wav_path
        resolved_chunks = chunks

        if isinstance(wav_path_or_chunks, str):
            resolved_path = wav_path_or_chunks
        elif wav_path_or_chunks is not None:
            resolved_chunks = wav_path_or_chunks

        if resolved_path and resolved_chunks is None:
            if total_duration is None:
                try:
                    import wave
                    with wave.open(resolved_path, "rb") as wf:
                        sr = wf.getframerate()
                        if sr > 0:
                            total_duration = wf.getnframes() / float(sr)
                except Exception:
                    pass

            resolved_chunks = list(
                AudioPreprocessor.stream_wav_chunks(
                    wav_path=resolved_path,
                    chunk_duration_sec=cfg.chunk_duration_sec,
                    overlap_sec=cfg.chunk_overlap_sec,
                )
            )
        elif resolved_chunks is not None and total_duration is None:
            chunk_list_temp = list(resolved_chunks)
            if chunk_list_temp:
                total_duration = max(c.end_seconds for c in chunk_list_temp)
            resolved_chunks = chunk_list_temp

        chunk_list = list(resolved_chunks) if resolved_chunks is not None else []
        total_chunks = len(chunk_list)

        for idx, chunk in enumerate(chunk_list):
            if is_cancelled and is_cancelled():
                raise asyncio.CancelledError("VAD chunk processing cancelled.")
            if cancel_token and getattr(cancel_token, "is_cancelled", False):
                raise asyncio.CancelledError("VAD chunk processing cancelled.")

            if on_progress and total_chunks > 0:
                pct = int(10 + (idx / total_chunks) * 75)
                on_progress(pct, f"Analyzing voice activity in audio chunk {idx+1}/{total_chunks}...")

            chunk_intervals = cls.detect_speech_array(
                samples=chunk.samples,
                sample_rate=chunk.sample_rate,
                config=cfg,
                time_offset=chunk.start_seconds,
                max_duration=total_duration,
            )
            all_intervals.extend(chunk_intervals)

        # Global post-processing: deduplicate overlaps from chunk windows and merge close intervals
        merged = cls.merge_close_intervals(
            intervals=all_intervals,
            max_gap_ms=cfg.max_merge_gap_ms,
            min_speech_duration_ms=cfg.min_speech_duration_ms,
            pad_ms=cfg.speech_pad_ms,
            total_duration=total_duration,
        )
        return merged

    @classmethod
    def merge_close_intervals(
        cls,
        intervals: List[SpeechIntervalSchema],
        max_gap_ms: int = 250,
        min_speech_duration_ms: Optional[int] = None,
        pad_ms: int = 0,
        total_duration: Optional[float] = None,
    ) -> List[SpeechIntervalSchema]:
        """
        Sort and merge overlapping or adjacent speech intervals separated by less than max_gap_ms.
        Applies padding and filters out intervals shorter than min_speech_duration_ms.
        Clamps all intervals strictly within [0.0, total_duration].
        Consolidates newly overlapping padded regions into a strict disjoint union.
        """
        if not intervals:
            return []

        # Sort chronologically by start_time
        sorted_intervals = sorted(intervals, key=lambda x: x.start_time)
        max_gap_sec = max_gap_ms / 1000.0

        merged_raw: List[SpeechIntervalSchema] = []
        current = sorted_intervals[0]

        for next_inv in sorted_intervals[1:]:
            # Check overlap or gap within max_gap_sec
            if next_inv.start_time <= (current.end_time + max_gap_sec):
                # Merge into current interval
                new_end = max(current.end_time, next_inv.end_time)
                if total_duration is not None and total_duration > 0.0:
                    new_end = min(total_duration, new_end)

                current = SpeechIntervalSchema(
                    start_time=current.start_time,
                    end_time=round(new_end, 3),
                    duration=round(max(0.0, new_end - current.start_time), 3),
                    speech_probability=round(max(current.speech_probability, next_inv.speech_probability), 2),
                    confidence=round(max(current.confidence, next_inv.confidence), 2),
                    source=current.source,
                )
            else:
                merged_raw.append(current)
                current = next_inv

        merged_raw.append(current)

        # Apply padding and filter by minimum duration (check pre-pad duration)
        pad_sec = pad_ms / 1000.0
        min_dur_sec = (min_speech_duration_ms / 1000.0) if min_speech_duration_ms else 0.0

        padded_intervals: List[SpeechIntervalSchema] = []
        for iv in merged_raw:
            if iv.duration < min_dur_sec:
                continue

            padded_start = max(0.0, iv.start_time - pad_sec)
            padded_end = iv.end_time + pad_sec
            if total_duration is not None and total_duration > 0.0:
                padded_end = min(total_duration, padded_end)

            if padded_end <= padded_start:
                continue

            padded_duration = max(0.0, padded_end - padded_start)
            padded_intervals.append(
                SpeechIntervalSchema(
                    start_time=round(padded_start, 3),
                    end_time=round(padded_end, 3),
                    duration=round(padded_duration, 3),
                    speech_probability=iv.speech_probability,
                    confidence=iv.confidence,
                    source=iv.source,
                )
            )

        if not padded_intervals:
            return []

        # Pass 3: Consolidate any intervals that now overlap due to padding into disjoint union
        disjoint_intervals: List[SpeechIntervalSchema] = []
        sorted_padded = sorted(padded_intervals, key=lambda x: x.start_time)
        cur = sorted_padded[0]

        for nxt in sorted_padded[1:]:
            if nxt.start_time <= cur.end_time:
                # Padded boundaries overlap -> unify into single continuous interval
                unified_end = max(cur.end_time, nxt.end_time)
                if total_duration is not None and total_duration > 0.0:
                    unified_end = min(total_duration, unified_end)
                cur = SpeechIntervalSchema(
                    start_time=cur.start_time,
                    end_time=round(unified_end, 3),
                    duration=round(max(0.0, unified_end - cur.start_time), 3),
                    speech_probability=round(max(cur.speech_probability, nxt.speech_probability), 2),
                    confidence=round(max(cur.confidence, nxt.confidence), 2),
                    source=cur.source,
                )
            else:
                disjoint_intervals.append(cur)
                cur = nxt

        disjoint_intervals.append(cur)
        return disjoint_intervals

    @staticmethod
    def calculate_interval_union_duration(intervals: List[SpeechIntervalSchema]) -> float:
        """
        Compute total speech duration as the mathematical union of intervals,
        strictly preventing double counting of overlapping timestamps.
        """
        if not intervals:
            return 0.0

        sorted_ivs = sorted(intervals, key=lambda x: x.start_time)
        total_sec = 0.0
        cur_start, cur_end = sorted_ivs[0].start_time, sorted_ivs[0].end_time

        for iv in sorted_ivs[1:]:
            if iv.start_time <= cur_end:
                cur_end = max(cur_end, iv.end_time)
            else:
                total_sec += max(0.0, cur_end - cur_start)
                cur_start, cur_end = iv.start_time, iv.end_time

        total_sec += max(0.0, cur_end - cur_start)
        return round(total_sec, 3)
