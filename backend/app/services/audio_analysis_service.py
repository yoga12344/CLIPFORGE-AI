"""
ClipForge AI - Audio Analysis Service Layer
Orchestrates audio extraction, preprocessing, Silero VAD analysis, and database persistence.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.audio.audio_preprocessor import AudioPreprocessor
from app.ai.audio.voice_activity_detector import VoiceActivityDetector, SpeechInterval as VADSpeechInterval
from app.db.models import AudioAnalysis, SpeechInterval, Video, Project
from app.schemas.audio_schemas import (
    AudioAnalysisResponse,
    AudioCapabilitiesResponse,
    AudioMetadataSchema,
    SpeechIntervalSchema,
    VADConfigSchema,
)

logger = logging.getLogger("clipforge.services.audio_analysis")


class AudioAnalysisService:
    """
    High-level service coordinating audio preprocessing, Voice Activity Detection (VAD),
    and SQLite persistence.
    """

    @classmethod
    def get_capabilities(cls) -> AudioCapabilitiesResponse:
        """
        Return the capabilities and default configuration of the local audio engine.
        """
        vad = VoiceActivityDetector()
        caps = vad.get_capabilities()
        return AudioCapabilitiesResponse(
            vad_available=caps["vad_available"],
            vad_model=caps["vad_model"],
            vad_version=caps["vad_version"],
            cpu_available=caps["cpu_available"],
            gpu_available=caps["gpu_available"],
            supported_sample_rates=caps["supported_sample_rates"],
            default_config=VADConfigSchema(),
        )

    @classmethod
    async def save_analysis(
        cls,
        db: AsyncSession,
        project_id: str,
        video_id: str,
        metadata: AudioMetadataSchema,
        speech_intervals: List[VADSpeechInterval],
        config: Optional[VADConfigSchema] = None,
        processing_duration: float = 0.0,
        vad_model: str = "silero-vad-v4",
        vad_version: str = "1.2.1",
        processing_device: str = "cpu",
        status: str = "completed",
        error_message: Optional[str] = None,
    ) -> AudioAnalysis:
        """
        Persist an AudioAnalysis record and its associated SpeechIntervals into SQLite.
        """
        total_speech_sec = VoiceActivityDetector.calculate_interval_union_duration(speech_intervals)
        if metadata.source_duration > 0.0:
            total_speech_sec = min(metadata.source_duration, total_speech_sec)
        config_dict = config.model_dump() if config and hasattr(config, "model_dump") else (config or {})

        analysis = AudioAnalysis(
            project_id=project_id,
            video_id=video_id,
            status=status,
            source_sample_rate=metadata.source_sample_rate,
            source_channels=metadata.source_channels,
            processed_sample_rate=metadata.processed_sample_rate,
            processed_channels=metadata.processed_channels,
            duration_seconds=metadata.source_duration,
            speech_duration_seconds=total_speech_sec,
            audio_available=metadata.audio_available,
            audio_is_silent=metadata.audio_is_silent,
            vad_model=vad_model,
            vad_version=vad_version,
            processing_device=processing_device,
            processing_duration_seconds=processing_duration,
            configuration=config_dict,
            error_message=error_message,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(analysis)
        await db.flush()

        for iv in speech_intervals:
            interval_record = SpeechInterval(
                analysis_id=analysis.id,
                start_time=iv.start_time,
                end_time=iv.end_time,
                duration=iv.duration,
                speech_probability=iv.speech_probability,
                confidence=iv.confidence,
                source=iv.source,
                created_at=datetime.utcnow(),
            )
            db.add(interval_record)

        await db.commit()
        await db.refresh(analysis)
        return analysis

    @classmethod
    async def get_latest_analysis_for_video(
        cls,
        db: AsyncSession,
        video_id: str,
    ) -> Optional[AudioAnalysis]:
        """
        Retrieve the latest completed audio analysis for a video, including its speech intervals.
        """
        stmt = (
            select(AudioAnalysis)
            .where(AudioAnalysis.video_id == video_id)
            .options(selectinload(AudioAnalysis.speech_intervals))
            .order_by(desc(AudioAnalysis.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def get_analysis_by_id(
        cls,
        db: AsyncSession,
        analysis_id: str,
    ) -> Optional[AudioAnalysis]:
        """
        Retrieve a specific AudioAnalysis record by ID.
        """
        stmt = (
            select(AudioAnalysis)
            .where(AudioAnalysis.id == analysis_id)
            .options(selectinload(AudioAnalysis.speech_intervals))
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def get_intervals_for_analysis(
        cls,
        db: AsyncSession,
        analysis_id: str,
    ) -> List[SpeechInterval]:
        """
        Retrieve all speech intervals for a given analysis ID, ordered by start time.
        """
        stmt = (
            select(SpeechInterval)
            .where(SpeechInterval.analysis_id == analysis_id)
            .order_by(SpeechInterval.start_time.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    def to_response_schema(cls, analysis: AudioAnalysis) -> AudioAnalysisResponse:
        """
        Convert an SQLAlchemy AudioAnalysis model into an AudioAnalysisResponse Pydantic schema.
        """
        speech_intervals = [
            SpeechIntervalSchema(
                id=iv.id,
                analysis_id=iv.analysis_id,
                start_time=iv.start_time,
                end_time=iv.end_time,
                duration=iv.duration,
                speech_probability=iv.speech_probability,
                confidence=iv.confidence,
                source=iv.source,
                created_at=iv.created_at,
            )
            for iv in (analysis.speech_intervals or [])
        ]

        speech_pct = 0.0
        if analysis.duration_seconds > 0.0:
            speech_pct = round(min(100.0, (analysis.speech_duration_seconds / analysis.duration_seconds) * 100.0), 2)

        return AudioAnalysisResponse(
            id=analysis.id,
            project_id=analysis.project_id,
            video_id=analysis.video_id,
            status=analysis.status,
            source_sample_rate=analysis.source_sample_rate,
            source_channels=analysis.source_channels,
            processed_sample_rate=analysis.processed_sample_rate or 16000,
            processed_channels=analysis.processed_channels or 1,
            duration_seconds=analysis.duration_seconds or 0.0,
            speech_duration_seconds=analysis.speech_duration_seconds or 0.0,
            speech_percentage=speech_pct,
            audio_available=analysis.audio_available if analysis.audio_available is not None else True,
            audio_is_silent=analysis.audio_is_silent if analysis.audio_is_silent is not None else False,
            vad_model=analysis.vad_model or "silero-vad-v4",
            vad_version=analysis.vad_version or "1.2.1",
            processing_device=analysis.processing_device or "cpu",
            processing_duration_seconds=analysis.processing_duration_seconds or 0.0,
            configuration=analysis.configuration or {},
            error_message=analysis.error_message,
            speech_intervals=speech_intervals,
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
        )

    @classmethod
    async def run_audio_analysis(
        cls,
        video_path: str,
        project_id: str,
        video_id: str,
        config: Optional[VADConfigSchema] = None,
        force_reprocess: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full audio preprocessing and VAD pipeline with 8 distinct stages.
        """
        t_start = time.perf_counter()
        config = config or VADConfigSchema()

        def _update_progress(percent: int, stage_desc: str):
            if is_cancelled and is_cancelled():
                raise asyncio.CancelledError("Audio analysis cancelled by user.")
            if progress_callback:
                progress_callback(percent, stage_desc)

        # Stage 1: Validate source audio
        _update_progress(5, "Validating source audio media")
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at {video_path}")

        # Determine audio storage directory
        # Store in project audio cache: storage/clipforge_data/projects/{project_id}/audio/{video_id}_16k.wav
        project_audio_dir = Path("storage/clipforge_data/projects") / project_id / "audio"
        project_audio_dir.mkdir(parents=True, exist_ok=True)
        cached_wav_path = str(project_audio_dir / f"{video_id}_16k.wav")

        preprocessor = AudioPreprocessor()

        # Stage 2: Extract canonical 16kHz mono audio
        _update_progress(15, "Extracting canonical 16kHz mono audio")
        if force_reprocess or not os.path.exists(cached_wav_path) or os.path.getsize(cached_wav_path) == 0:
            target_wav, metadata = await preprocessor.extract_and_preprocess(
                source_media_path=video_path,
                output_wav_path=cached_wav_path,
                target_sample_rate=16000,
                channels=1,
            )
        else:
            # Quick inspection of cached WAV
            meta_dict = preprocessor.sample_file_metrics(cached_wav_path)
            metadata = AudioMetadataSchema(
                source_sample_rate=16000,
                source_channels=1,
                source_codec="pcm_s16le",
                source_duration=meta_dict.get("duration", 0.0),
                processed_sample_rate=16000,
                processed_channels=1,
                audio_available=True,
                audio_is_silent=meta_dict.get("is_silent", False),
                peak_amplitude=meta_dict.get("peak", 0.0),
                rms_level=meta_dict.get("rms", 0.0),
                clipping_detected=meta_dict.get("clipping", False),
                processing_duration=0.0,
                processing_device="cpu",
            )
            target_wav = cached_wav_path

        # Stage 3: Inspecting signal health
        _update_progress(35, "Inspecting audio signal health")
        if not metadata.audio_available or metadata.audio_is_silent:
            logger.warning(f"Audio for video {video_id} is unavailable or silent.")
            t_end = time.perf_counter()
            return {
                "metadata": metadata,
                "intervals": [],
                "processing_duration": t_end - t_start,
                "vad_model": "silero-vad-v4",
                "vad_version": "1.2.1",
                "device": "cpu",
            }

        # Stage 4: Initializing local Silero VAD
        _update_progress(45, "Initializing local Silero VAD engine")
        vad = VoiceActivityDetector()

        # Stage 5: Streaming voice activity detection
        _update_progress(55, "Detecting voice activity across audio chunks")
        raw_intervals = await vad.detect_speech_streaming(
            wav_path=target_wav,
            config=config,
            total_duration=metadata.source_duration,
            is_cancelled=is_cancelled,
        )

        # Stage 6: Merging speech intervals & padding
        _update_progress(80, "Merging speech intervals and applying padding")
        merged_intervals = vad.merge_close_intervals(
            intervals=raw_intervals,
            max_gap_ms=config.max_merge_gap_ms,
            min_speech_duration_ms=config.min_speech_duration_ms,
            pad_ms=config.speech_pad_ms,
            total_duration=metadata.source_duration,
        )

        _update_progress(90, "Finalizing audio intelligence results")
        t_end = time.perf_counter()
        processing_duration = t_end - t_start

        return {
            "metadata": metadata,
            "intervals": merged_intervals,
            "processing_duration": processing_duration,
            "vad_model": "silero-vad-v4",
            "vad_version": "1.2.1",
            "device": "cpu",
        }
