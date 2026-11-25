import asyncio
import gc
import logging
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel

from .device_detector import DeviceDetector
from .model_manager import ModelManager
from .transcription_config import TranscriptionConfig
from .transcription_validator import TranscriptionValidator

logger = logging.getLogger("clipforge.ai.engine")

class WordTimestampResult(BaseModel):
    word: str
    start: float
    end: float
    prob: float

class TranscriptionSegmentResult(BaseModel):
    segment_index: int
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    words: List[WordTimestampResult] = []

class TranscriptionResult(BaseModel):
    full_text: str
    language: str
    language_probability: float = 1.0
    audio_duration_seconds: float = 0.0
    processing_duration_seconds: float = 0.0
    model_used: str
    device_used: str
    segments: List[TranscriptionSegmentResult] = []

class TranscriptionEngine:
    _instance: Optional["TranscriptionEngine"] = None
    _loaded_model: Any = None
    _loaded_model_id: Optional[str] = None
    _loaded_device: Optional[str] = None
    _loaded_compute_type: Optional[str] = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "TranscriptionEngine":
        if cls._instance is None:
            cls._instance = TranscriptionEngine()
        return cls._instance

    def unload_model(self):
        """Release currently cached model from RAM/VRAM."""
        if self._loaded_model is not None:
            logger.info(f"Unloading Whisper model '{self._loaded_model_id}' from {self._loaded_device}...")
            del self._loaded_model
            self._loaded_model = None
            self._loaded_model_id = None
            self._loaded_device = None
            self._loaded_compute_type = None
            gc.collect()

    def _load_model(
        self,
        model_id: str,
        target_device: str,
        target_compute_type: str
    ) -> Any:
        from faster_whisper import WhisperModel

        model_status = ModelManager.check_model_status(model_id)
        if not model_status.is_installed:
            raise FileNotFoundError(
                f"Whisper model '{model_id}' is not installed locally. Missing: {model_status.missing_files}"
            )

        model_dir = model_status.local_path

        # If already loaded with identical settings, reuse it!
        if (
            self._loaded_model is not None
            and self._loaded_model_id == model_id
            and self._loaded_device == target_device
            and self._loaded_compute_type == target_compute_type
        ):
            logger.info(f"Reusing already loaded Whisper model '{model_id}' on {target_device}")
            return self._loaded_model

        # Otherwise unload prior model
        self.unload_model()

        logger.info(
            f"Loading Whisper model '{model_id}' from {model_dir} onto {target_device} ({target_compute_type})..."
        )

        try:
            model = WhisperModel(
                model_size_or_path=str(model_dir),
                device=target_device,
                compute_type=target_compute_type,
                local_files_only=True
            )
            self._loaded_model = model
            self._loaded_model_id = model_id
            self._loaded_device = target_device
            self._loaded_compute_type = target_compute_type
            return model
        except Exception as load_err:
            if target_device == "cuda":
                logger.warning(
                    f"CUDA model loading failed ({load_err}). Automatically falling back to CPU int8..."
                )
                model = WhisperModel(
                    model_size_or_path=str(model_dir),
                    device="cpu",
                    compute_type="int8",
                    local_files_only=True
                )
                self._loaded_model = model
                self._loaded_model_id = model_id
                self._loaded_device = "cpu (fallback)"
                self._loaded_compute_type = "int8"
                return model
            else:
                raise

    async def transcribe(
        self,
        audio_file_path: str,
        config: Optional[TranscriptionConfig] = None,
        on_progress: Optional[Callable[[int, str], Coroutine[None, None, None]]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> TranscriptionResult:
        """
        Execute speech-to-text transcription with word-level timestamps,
        streaming progress, and cancellation checks.
        """
        cfg = config or TranscriptionConfig()

        # 1. Validate audio file
        validation = TranscriptionValidator.validate_audio_file(audio_file_path)
        if not validation.valid:
            raise ValueError(f"Audio validation failed: {validation.error}")

        total_audio_duration = validation.duration_seconds

        # 2. Resolve hardware target
        target_device, target_compute, is_fallback, diag = DeviceDetector.resolve_device_and_compute_type(
            requested_device=cfg.device,
            requested_compute_type=cfg.compute_type
        )

        # 3. Ensure single heavy AI task concurrency
        async with self._lock:
            if is_cancelled and is_cancelled():
                raise asyncio.CancelledError()

            # Ensure model is installed locally
            model_status = ModelManager.check_model_status(cfg.model_name)
            if not model_status.is_installed:
                if on_progress:
                    await on_progress(5, f"Downloading Whisper model '{cfg.model_name}' on demand...")
                await ModelManager.download_model(cfg.model_name)

            if on_progress:
                await on_progress(10, f"Initializing Whisper model '{cfg.model_name}' on {target_device}...")

            # Load model (CPU/GPU)
            loop = asyncio.get_running_loop()
            model = await loop.run_in_executor(
                None,
                self._load_model,
                cfg.model_name,
                target_device,
                target_compute
            )

            actual_device_used = self._loaded_device or target_device

            if on_progress:
                await on_progress(15, f"Transcribing audio ({actual_device_used})...")

            start_clock = time.time()

            # Define generator consumer in thread
            def do_transcribe():
                vad_params = dict(threshold=cfg.vad_threshold) if cfg.vad_filter else None
                segments_gen, info = model.transcribe(
                    audio_file_path,
                    language=cfg.language,
                    beam_size=cfg.beam_size,
                    vad_filter=cfg.vad_filter,
                    vad_parameters=vad_params,
                    word_timestamps=cfg.word_timestamps,
                    temperature=cfg.temperature,
                    initial_prompt=cfg.initial_prompt
                )
                return segments_gen, info

            try:
                segments_gen, info = await loop.run_in_executor(None, do_transcribe)
            except Exception as inf_err:
                if "cuda" in str(actual_device_used).lower():
                    logger.warning(
                        f"GPU inference failed ({inf_err}). Gracefully falling back to CPU int8..."
                    )
                    self.unload_model()
                    model = await loop.run_in_executor(
                        None,
                        self._load_model,
                        cfg.model_name,
                        "cpu",
                        "int8"
                    )
                    actual_device_used = "cpu (fallback)"
                    if on_progress:
                        await on_progress(15, "Retrying on CPU int8 (fallback)...")
                    segments_gen, info = await loop.run_in_executor(None, do_transcribe)
                else:
                    raise

            # Consume segments while reporting progress and checking cancellation
            collected_segments: List[TranscriptionSegmentResult] = []
            segment_idx = 0

            # Helper to fetch next segment in executor without blocking loop
            iterator = iter(segments_gen)

            def get_next_segment():
                try:
                    return next(iterator)
                except StopIteration:
                    return None

            while True:
                if is_cancelled and is_cancelled():
                    raise asyncio.CancelledError()

                seg = await loop.run_in_executor(None, get_next_segment)
                if seg is None:
                    break

                words_data: List[WordTimestampResult] = []
                if hasattr(seg, "words") and seg.words:
                    for w in seg.words:
                        words_data.append(WordTimestampResult(
                            word=w.word,
                            start=round(w.start, 3),
                            end=round(w.end, 3),
                            prob=round(w.probability, 3)
                        ))

                confidence_val = None
                if hasattr(seg, "avg_logprob"):
                    import math
                    try:
                        confidence_val = round(math.exp(seg.avg_logprob), 3)
                    except Exception:
                        confidence_val = 0.85

                collected_segments.append(TranscriptionSegmentResult(
                    segment_index=segment_idx,
                    start_time=round(seg.start, 3),
                    end_time=round(seg.end, 3),
                    text=seg.text.strip(),
                    confidence=confidence_val,
                    words=words_data
                ))
                segment_idx += 1

                # Calculate progress based on segment end time
                if total_audio_duration > 0.1:
                    pct = min(98, max(15, int((seg.end / total_audio_duration) * 100)))
                    if on_progress:
                        await on_progress(
                            pct,
                            f"Transcribing: {round(seg.end, 1)}s / {round(total_audio_duration, 1)}s ({len(collected_segments)} segments)"
                        )

            elapsed = round(time.time() - start_clock, 2)
            full_text = " ".join(s.text for s in collected_segments).strip()

            detected_lang = getattr(info, "language", cfg.language or "en")
            lang_prob = round(getattr(info, "language_probability", 1.0), 3)

            if on_progress:
                await on_progress(100, f"Transcription completed ({len(collected_segments)} segments)")

            logger.info(
                f"Transcription complete: {len(collected_segments)} segments in {elapsed}s "
                f"using {cfg.model_name} on {actual_device_used} (Lang: {detected_lang} {lang_prob})"
            )

            return TranscriptionResult(
                full_text=full_text,
                language=detected_lang,
                language_probability=lang_prob,
                audio_duration_seconds=total_audio_duration,
                processing_duration_seconds=elapsed,
                model_used=f"whisper-{cfg.model_name}-{target_compute}",
                device_used=actual_device_used,
                segments=collected_segments
            )
