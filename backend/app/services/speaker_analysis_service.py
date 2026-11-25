"""
ClipForge AI - Speaker Analysis Service Layer
Coordinates audio feature extraction, speaker diarization, database persistence,
manual turn reassignments, and speaker profile updates.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import numpy as np

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.audio.audio_preprocessor import AudioPreprocessor
from app.ai.audio.speaker_diarizer import (
    DiarizationConfig,
    DiarizationResult,
    DiarizedSpeaker,
    SpeakerDiarizer,
    SpeakerEmbeddingData,
    SpeakerTurnData,
)
from app.ai.audio.voice_activity_detector import SpeechInterval as VADSpeechInterval
from app.db.models import AudioAnalysis, Job, Project, Speaker, SpeakerEmbedding, SpeakerTurn, SpeechInterval, Video
from app.schemas.speaker_schemas import (
    DiarizationConfigSchema,
    DiarizationSummaryResponse,
    SpeakerCapabilitiesResponse,
    SpeakerEmbeddingSchema,
    SpeakerSchema,
    SpeakerTurnSchema,
    StartDiarizationRequest,
    UpdateSpeakerRequest,
    UpdateSpeakerTurnRequest,
)

logger = logging.getLogger("clipforge.services.speaker_analysis")


class SpeakerAnalysisService:
    """
    High-level service coordinating offline speaker diarization,
    persistence in SQLite, and REST / JobExecutor handlers.
    """

    @classmethod
    def get_capabilities(cls) -> SpeakerCapabilitiesResponse:
        """Return runtime capabilities and default config of local speaker diarizer."""
        diarizer = SpeakerDiarizer()
        caps = diarizer.get_capabilities()
        return SpeakerCapabilitiesResponse(
            diarization_available=caps["diarization_available"],
            model_name=caps["model_name"],
            embedding_dimension=caps["embedding_dimension"],
            sample_rate=caps["sample_rate"],
            execution_device=caps["execution_device"],
            clustering_algorithm=caps["clustering_algorithm"],
            default_config=DiarizationConfigSchema(),
        )

    @classmethod
    async def run_speaker_diarization(
        cls,
        audio_path: Union[str, Path],
        analysis_id: str,
        speech_intervals: Optional[List[SpeechInterval]] = None,
        config: Optional[DiarizationConfigSchema] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> DiarizationResult:
        """
        Execute the offline speaker diarization pipeline on an extracted audio file.
        """
        def update_progress(pct: int, msg: str):
            if progress_callback:
                progress_callback(pct, msg)

        if is_cancelled and is_cancelled():
            raise asyncio.CancelledError("Diarization cancelled before start")

        update_progress(5, "Loading 16kHz audio for speaker analysis")
        path_str = str(audio_path)
        if not os.path.exists(path_str):
            raise FileNotFoundError(f"Audio file not found: {path_str}")

        # Extract audio waveform using AudioPreprocessor
        audio_samples, meta = AudioPreprocessor.extract_canonical_audio(
            source_path=path_str,
            target_sample_rate=16000,
        )

        if is_cancelled and is_cancelled():
            raise asyncio.CancelledError("Diarization cancelled after audio load")

        update_progress(20, "Preparing speech intervals for windowing")

        # Convert ORM SpeechIntervals to VADSpeechInterval objects if provided
        vad_intervals: Optional[List[VADSpeechInterval]] = None
        if speech_intervals:
            vad_intervals = [
                VADSpeechInterval(
                    start_time=iv.start_time,
                    end_time=iv.end_time,
                    duration=iv.duration,
                    speech_probability=iv.speech_probability,
                    confidence=iv.confidence,
                    source=iv.source,
                )
                for iv in speech_intervals
            ]

        # Convert Pydantic config to domain DiarizationConfig
        diar_cfg = DiarizationConfig()
        if config:
            diar_cfg.distance_threshold = config.distance_threshold
            diar_cfg.expected_speakers = config.expected_speakers
            diar_cfg.min_speakers = config.min_speakers
            diar_cfg.max_speakers = config.max_speakers
            diar_cfg.window_duration_sec = config.window_duration_sec
            diar_cfg.step_duration_sec = config.step_duration_sec
            diar_cfg.collar_sec = config.collar_sec

        update_progress(40, "Extracting 3D-Speaker CAM++ embeddings on CPU")

        diarizer = SpeakerDiarizer()
        result = diarizer.diarize(
            samples=audio_samples,
            sample_rate=16000,
            speech_intervals=vad_intervals,
            config=diar_cfg,
        )

        if is_cancelled and is_cancelled():
            raise asyncio.CancelledError("Diarization cancelled after model inference")

        update_progress(85, "Consolidating speaker turns and temporal boundaries")
        logger.info(
            "Diarization finished for %s: %d speakers, %d turns, total speech %.2fs, RTF %.4f",
            analysis_id,
            result.num_speakers,
            len(result.speaker_turns),
            result.total_speech_duration,
            result.rtf,
        )

        update_progress(100, "Speaker diarization completed")
        return result

    @classmethod
    async def save_diarization_results(
        cls,
        db: AsyncSession,
        analysis_id: str,
        project_id: str,
        diarization_result: DiarizationResult,
    ) -> DiarizationSummaryResponse:
        """
        Persist diarization output (speakers, turns, embeddings) to SQLite in a single transaction.
        Replaces any prior diarization records for this analysis.
        """
        # 1. Clean existing records for this analysis
        await db.execute(delete(SpeakerEmbedding).where(SpeakerEmbedding.analysis_id == analysis_id))
        await db.execute(delete(SpeakerTurn).where(SpeakerTurn.analysis_id == analysis_id))
        await db.execute(delete(Speaker).where(Speaker.analysis_id == analysis_id))
        await db.flush()

        # 2. Persist Speaker records
        created_speakers: Dict[int, Speaker] = {}
        speaker_schemas: List[SpeakerSchema] = []

        for spk in diarization_result.speakers:
            spk_record = Speaker(
                project_id=project_id,
                analysis_id=analysis_id,
                speaker_identifier=spk.speaker_identifier,
                label=spk.display_name,
                display_name=spk.display_name,
                color=spk.color,
                total_speech_duration=spk.total_speech_duration,
                turn_count=spk.turn_count,
                model_name="3dspeaker_campplus",
                model_version="1.0.0",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(spk_record)
            await db.flush()
            created_speakers[spk.speaker_index] = spk_record

            speaker_schemas.append(
                SpeakerSchema(
                    id=spk_record.id,
                    project_id=project_id,
                    analysis_id=analysis_id,
                    speaker_identifier=spk.speaker_identifier,
                    label=spk.display_name,
                    display_name=spk.display_name,
                    color=spk.color,
                    total_speech_duration=spk.total_speech_duration,
                    turn_count=spk.turn_count,
                    model_name="3dspeaker_campplus",
                    model_version="1.0.0",
                    created_at=spk_record.created_at,
                    updated_at=spk_record.updated_at,
                )
            )

        # 3. Persist SpeakerTurns
        turn_schemas: List[SpeakerTurnSchema] = []
        for turn in diarization_result.speaker_turns:
            spk_obj = created_speakers.get(turn.speaker_index)
            turn_record = SpeakerTurn(
                analysis_id=analysis_id,
                speaker_id=spk_obj.id if spk_obj else None,
                start_time=turn.start_time,
                end_time=turn.end_time,
                duration=turn.duration,
                confidence=turn.confidence,
                assignment_status=turn.assignment_status,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(turn_record)
            await db.flush()

            turn_schemas.append(
                SpeakerTurnSchema(
                    id=turn_record.id,
                    analysis_id=analysis_id,
                    speaker_id=spk_obj.id if spk_obj else None,
                    speaker_identifier=spk_obj.speaker_identifier if spk_obj else turn.speaker_identifier,
                    display_name=spk_obj.display_name if spk_obj else turn.display_name,
                    color=spk_obj.color if spk_obj else None,
                    start_time=turn.start_time,
                    end_time=turn.end_time,
                    duration=turn.duration,
                    confidence=turn.confidence,
                    assignment_status=turn.assignment_status,
                    created_at=turn_record.created_at,
                    updated_at=turn_record.updated_at,
                )
            )

        # 4. Persist window SpeakerEmbeddings
        for emb_data in diarization_result.embeddings:
            spk_obj = created_speakers.get(emb_data.speaker_index) if emb_data.speaker_index is not None else None
            # Store embedding vector as float list in JSON column for future querying / similarity
            emb_list = emb_data.embedding.tolist() if isinstance(emb_data.embedding, np.ndarray) else None
            emb_record = SpeakerEmbedding(
                analysis_id=analysis_id,
                speaker_id=spk_obj.id if spk_obj else None,
                segment_start_time=emb_data.segment_start_time,
                segment_end_time=emb_data.segment_end_time,
                embedding_dimension=512,
                embedding_data=emb_list,
                quality_score=emb_data.quality_score,
                model_version="1.0.0",
                created_at=datetime.utcnow(),
            )
            db.add(emb_record)

        await db.commit()

        return DiarizationSummaryResponse(
            analysis_id=analysis_id,
            status="completed",
            num_speakers=diarization_result.num_speakers,
            total_speech_duration=diarization_result.total_speech_duration,
            speakers=speaker_schemas,
            speaker_turns=turn_schemas,
            silhouette_score=diarization_result.silhouette_score,
            processing_duration_seconds=diarization_result.processing_duration,
            processing_device=diarization_result.execution_device,
        )

    @classmethod
    async def get_diarization_summary(
        cls,
        db: AsyncSession,
        analysis_id: str,
    ) -> Optional[DiarizationSummaryResponse]:
        """
        Fetch full diarization summary for an audio analysis.
        """
        analysis_res = await db.execute(select(AudioAnalysis).where(AudioAnalysis.id == analysis_id))
        analysis = analysis_res.scalar_one_or_none()
        if not analysis:
            return None

        # Fetch speakers
        spk_res = await db.execute(
            select(Speaker)
            .where(Speaker.analysis_id == analysis_id)
            .order_by(Speaker.speaker_identifier)
        )
        speakers = spk_res.scalars().all()
        speaker_map = {s.id: s for s in speakers}

        spk_schemas = [
            SpeakerSchema(
                id=s.id,
                project_id=s.project_id,
                analysis_id=s.analysis_id,
                speaker_identifier=s.speaker_identifier,
                label=s.label,
                display_name=s.display_name or s.label,
                color=s.color,
                total_speech_duration=s.total_speech_duration or 0.0,
                turn_count=s.turn_count or 0,
                model_name=s.model_name or "3dspeaker_campplus",
                model_version=s.model_version or "1.0.0",
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in speakers
        ]

        # Fetch turns
        turn_res = await db.execute(
            select(SpeakerTurn)
            .where(SpeakerTurn.analysis_id == analysis_id)
            .order_by(SpeakerTurn.start_time)
        )
        turns = turn_res.scalars().all()

        turn_schemas = []
        for t in turns:
            spk = speaker_map.get(t.speaker_id)
            turn_schemas.append(
                SpeakerTurnSchema(
                    id=t.id,
                    analysis_id=t.analysis_id,
                    speaker_id=t.speaker_id,
                    speaker_identifier=spk.speaker_identifier if spk else None,
                    display_name=spk.display_name if spk else (spk.label if spk else None),
                    color=spk.color if spk else None,
                    start_time=t.start_time,
                    end_time=t.end_time,
                    duration=t.duration,
                    confidence=t.confidence,
                    assignment_status=t.assignment_status,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                )
            )

        total_speech = sum(t.duration for t in turns)

        return DiarizationSummaryResponse(
            analysis_id=analysis_id,
            status=analysis.status,
            num_speakers=len(speakers),
            total_speech_duration=round(total_speech, 3),
            speakers=spk_schemas,
            speaker_turns=turn_schemas,
            processing_duration_seconds=analysis.processing_duration_seconds or 0.0,
            processing_device=analysis.processing_device or "cpu",
        )

    @classmethod
    async def get_speakers_for_analysis(
        cls,
        db: AsyncSession,
        analysis_id: str,
    ) -> List[SpeakerSchema]:
        """Fetch all recognized speakers for an analysis."""
        stmt = (
            select(Speaker)
            .where(Speaker.analysis_id == analysis_id)
            .order_by(Speaker.speaker_identifier)
        )
        res = await db.execute(stmt)
        speakers = res.scalars().all()
        return [
            SpeakerSchema(
                id=s.id,
                project_id=s.project_id,
                analysis_id=s.analysis_id,
                speaker_identifier=s.speaker_identifier,
                label=s.label,
                display_name=s.display_name or s.label,
                color=s.color,
                total_speech_duration=s.total_speech_duration or 0.0,
                turn_count=s.turn_count or 0,
                model_name=s.model_name or "3dspeaker_campplus",
                model_version=s.model_version or "1.0.0",
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in speakers
        ]

    @classmethod
    async def get_speaker_turns_for_analysis(
        cls,
        db: AsyncSession,
        analysis_id: str,
    ) -> List[SpeakerTurnSchema]:
        """Fetch all speaker turns with speaker identities."""
        # Join speaker info
        turn_stmt = (
            select(SpeakerTurn)
            .where(SpeakerTurn.analysis_id == analysis_id)
            .order_by(SpeakerTurn.start_time)
        )
        res = await db.execute(turn_stmt)
        turns = res.scalars().all()

        spk_res = await db.execute(select(Speaker).where(Speaker.analysis_id == analysis_id))
        spk_map = {s.id: s for s in spk_res.scalars().all()}

        turn_schemas = []
        for t in turns:
            spk = spk_map.get(t.speaker_id)
            turn_schemas.append(
                SpeakerTurnSchema(
                    id=t.id,
                    analysis_id=t.analysis_id,
                    speaker_id=t.speaker_id,
                    speaker_identifier=spk.speaker_identifier if spk else None,
                    display_name=spk.display_name if spk else (spk.label if spk else None),
                    color=spk.color if spk else None,
                    start_time=t.start_time,
                    end_time=t.end_time,
                    duration=t.duration,
                    confidence=t.confidence,
                    assignment_status=t.assignment_status,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                )
            )
        return turn_schemas

    @classmethod
    async def update_speaker_turn(
        cls,
        db: AsyncSession,
        turn_id: str,
        req: UpdateSpeakerTurnRequest,
    ) -> Optional[SpeakerTurnSchema]:
        """
        Update an individual turn assignment or boundary and reconcile speaker totals.
        """
        turn_res = await db.execute(select(SpeakerTurn).where(SpeakerTurn.id == turn_id))
        turn = turn_res.scalar_one_or_none()
        if not turn:
            return None

        old_speaker_id = turn.speaker_id

        if req.speaker_id is not None:
            turn.speaker_id = req.speaker_id
            turn.assignment_status = "manual"
        if req.start_time is not None:
            turn.start_time = req.start_time
        if req.end_time is not None:
            turn.end_time = req.end_time
        if req.assignment_status is not None:
            turn.assignment_status = req.assignment_status

        turn.duration = max(0.0, turn.end_time - turn.start_time)
        turn.updated_at = datetime.utcnow()
        await db.flush()

        # Reconcile turn counts and total durations for affected speakers
        affected_speaker_ids = {old_speaker_id, turn.speaker_id}
        for spk_id in affected_speaker_ids:
            if not spk_id:
                continue
            spk_turns_res = await db.execute(
                select(SpeakerTurn).where(SpeakerTurn.speaker_id == spk_id)
            )
            spk_turns = spk_turns_res.scalars().all()
            total_dur = sum(t.duration for t in spk_turns)
            await db.execute(
                update(Speaker)
                .where(Speaker.id == spk_id)
                .values(
                    turn_count=len(spk_turns),
                    total_speech_duration=round(total_dur, 3),
                    updated_at=datetime.utcnow(),
                )
            )

        await db.commit()
        await db.refresh(turn)

        # Load speaker for response
        spk = None
        if turn.speaker_id:
            spk_res = await db.execute(select(Speaker).where(Speaker.id == turn.speaker_id))
            spk = spk_res.scalar_one_or_none()

        return SpeakerTurnSchema(
            id=turn.id,
            analysis_id=turn.analysis_id,
            speaker_id=turn.speaker_id,
            speaker_identifier=spk.speaker_identifier if spk else None,
            display_name=spk.display_name if spk else (spk.label if spk else None),
            color=spk.color if spk else None,
            start_time=turn.start_time,
            end_time=turn.end_time,
            duration=turn.duration,
            confidence=turn.confidence,
            assignment_status=turn.assignment_status,
            created_at=turn.created_at,
            updated_at=turn.updated_at,
        )

    @classmethod
    async def update_speaker(
        cls,
        db: AsyncSession,
        speaker_id: str,
        req: UpdateSpeakerRequest,
    ) -> Optional[SpeakerSchema]:
        """Update speaker display name and color."""
        spk_res = await db.execute(select(Speaker).where(Speaker.id == speaker_id))
        spk = spk_res.scalar_one_or_none()
        if not spk:
            return None

        if req.display_name is not None:
            spk.display_name = req.display_name
            spk.label = req.display_name
        if req.color is not None:
            spk.color = req.color

        spk.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(spk)

        return SpeakerSchema(
            id=spk.id,
            project_id=spk.project_id,
            analysis_id=spk.analysis_id,
            speaker_identifier=spk.speaker_identifier,
            label=spk.label,
            display_name=spk.display_name,
            color=spk.color,
            total_speech_duration=spk.total_speech_duration or 0.0,
            turn_count=spk.turn_count or 0,
            model_name=spk.model_name or "3dspeaker_campplus",
            model_version=spk.model_version or "1.0.0",
            created_at=spk.created_at,
            updated_at=spk.updated_at,
        )

    @classmethod
    async def delete_diarization_results(
        cls,
        db: AsyncSession,
        analysis_id: str,
    ) -> bool:
        """Clear all diarization records for an analysis."""
        await db.execute(delete(SpeakerEmbedding).where(SpeakerEmbedding.analysis_id == analysis_id))
        await db.execute(delete(SpeakerTurn).where(SpeakerTurn.analysis_id == analysis_id))
        await db.execute(delete(Speaker).where(Speaker.analysis_id == analysis_id))
        await db.commit()
        return True
