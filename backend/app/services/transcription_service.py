import asyncio
import logging
import os
from pathlib import Path
from typing import Callable, Coroutine, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.config import settings
from ..core.database import async_session_factory
from ..db.models import Video, Transcript, Job
from ..video.audio_extractor import AudioExtractor
from ..ai.transcription_config import TranscriptionConfig
from ..ai.transcription_engine import TranscriptionEngine, TranscriptionResult
from .transcript_repository import TranscriptRepository
from ..workers.job_manager import JobManager

logger = logging.getLogger("clipforge.services.transcription")

class TranscriptionService:
    @classmethod
    async def enqueue_transcription(
        cls,
        video_id: str,
        config: Optional[TranscriptionConfig] = None
    ) -> Job:
        """Enqueue a background transcription job."""
        cfg = config or TranscriptionConfig()

        async with async_session_factory() as db:
            res = await db.execute(select(Video).where(Video.id == video_id))
            video = res.scalar_one_or_none()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            project_id = video.project_id

        job = await JobManager.get_instance().enqueue_job(
            job_type="transcribe_video",
            project_id=project_id,
            params={
                "video_id": video_id,
                "model_name": cfg.model_name,
                "language": cfg.language,
                "device": cfg.device,
                "compute_type": cfg.compute_type,
                "vad_filter": cfg.vad_filter,
                "vad_threshold": cfg.vad_threshold,
                "beam_size": cfg.beam_size,
                "word_timestamps": cfg.word_timestamps,
                "temperature": cfg.temperature,
                "initial_prompt": cfg.initial_prompt
            }
        )
        return job

    @classmethod
    async def process_transcription_job(
        cls,
        video_id: str,
        params: Dict[str, Any],
        on_progress: Optional[Callable[[int, str], Coroutine[None, None, None]]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Execute end-to-end transcription:
        1. Resolve audio track (or extract 16kHz mono WAV if not present)
        2. Transcribe with WhisperModel
        3. Persist transcript & word-level segments into SQLite
        """
        async with async_session_factory() as db:
            res = await db.execute(select(Video).where(Video.id == video_id))
            video = res.scalar_one_or_none()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            video_file = video.file_path
            project_id = video.project_id

        # Check existing audio or extract
        dest_dir = settings.DATA_DIR / "projects" / project_id / "audio"
        dest_dir.mkdir(parents=True, exist_ok=True)
        wav_file = dest_dir / f"{video_id}_16k_mono.wav"

        if not video.has_audio:
            logger.info(f"Video {video_id} has no audio stream. Storing empty transcript record.")
            result = TranscriptionResult(
                full_text="",
                language=params.get("language") or "en",
                audio_duration_seconds=float(video.duration_seconds or 0.0),
                processing_duration_seconds=0.0,
                model_used="none",
                device_used="none",
                segments=[],
            )
        else:
            if not wav_file.exists() or wav_file.stat().st_size == 0:
                if on_progress:
                    await on_progress(5, "Extracting 16kHz mono speech audio...")
                await AudioExtractor.extract_for_transcription(
                    video_path=video_file,
                    output_wav_path=str(wav_file)
                )

            if not wav_file.exists() or wav_file.stat().st_size == 0:
                logger.info(f"Audio file for video {video_id} is empty. Storing empty transcript.")
                result = TranscriptionResult(
                    full_text="",
                    language=params.get("language") or "en",
                    audio_duration_seconds=float(video.duration_seconds or 0.0),
                    processing_duration_seconds=0.0,
                    model_used="none",
                    device_used="none",
                    segments=[],
                )
            else:
                if is_cancelled and is_cancelled():
                    raise asyncio.CancelledError()

                # Parse config
                cfg = TranscriptionConfig(
                    model_name=params.get("model_name", "small"),
                    language=params.get("language"),
                    device=params.get("device", "auto"),
                    compute_type=params.get("compute_type"),
                    vad_filter=params.get("vad_filter", True),
                    vad_threshold=float(params.get("vad_threshold", 0.5)),
                    beam_size=int(params.get("beam_size", 5)),
                    word_timestamps=bool(params.get("word_timestamps", True)),
                    temperature=float(params.get("temperature", 0.0)),
                    initial_prompt=params.get("initial_prompt")
                )

                engine = TranscriptionEngine.get_instance()
                result = await engine.transcribe(
                    audio_file_path=str(wav_file),
                    config=cfg,
                    on_progress=on_progress,
                    is_cancelled=is_cancelled
                )

        # Persist into database
        if on_progress:
            await on_progress(99, "Persisting transcript and word timestamps...")

        async with async_session_factory() as db:
            transcript = await TranscriptRepository.save_transcription_result(
                db=db,
                video_id=video_id,
                result=result
            )

        logger.info(
            f"Successfully stored transcript {transcript.id} with {len(transcript.segments)} segments for video {video_id}"
        )

        return {
            "transcript_id": transcript.id,
            "segment_count": len(transcript.segments),
            "language": transcript.language,
            "device_used": transcript.device_used,
            "processing_duration_seconds": transcript.processing_duration_seconds,
            "full_text_preview": transcript.full_text[:200]
        }
