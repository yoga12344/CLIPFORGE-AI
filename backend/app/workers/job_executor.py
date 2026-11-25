import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..core.config import settings
from ..core.database import async_session_factory
from ..db.models import Job, Video, Clip
from ..video.ffmpeg_manager import FFmpegManager, FFmpegProgress
from ..video.ffprobe_manager import FFprobeManager
from ..video.thumbnail_generator import ThumbnailGenerator
from ..video.audio_extractor import AudioExtractor
from ..video.preview_generator import PreviewGenerator
from ..video.clip_generator import ClipGenerator
from .cancellation import CancellationToken
from .job_events import JobEvent, JobEventBroadcaster

logger = logging.getLogger("clipforge.workers.executor")


def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert value to float, handling None, empty string, and invalid types without throwing."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class JobExecutor:
    @classmethod
    async def execute_job(cls, job_id: str, cancel_token: CancellationToken) -> Dict[str, Any]:
        """
        Execute a queued job with real video processing, live progress tracking,
        and cancellation checks.
        """
        async with async_session_factory() as db:
            res = await db.execute(select(Job).where(Job.id == job_id))
            job = res.scalar_one_or_none()
            if not job:
                raise ValueError(f"Job not found: {job_id}")

            job_type = job.job_type
            project_id = job.project_id
            params: Dict[str, Any] = job.params or {}

            # Mark running
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.progress_percent = 0
            job.stage_description = "Starting video task"
            await db.commit()

        await JobEventBroadcaster.broadcast(JobEvent(
            job_id=job_id,
            project_id=project_id,
            job_type=job_type,
            event_type="started",
            progress_percent=0,
            stage_description="Starting task"
        ))

        # Helper for progress
        async def on_progress(p: FFmpegProgress, stage_desc: str):
            if cancel_token.is_cancelled:
                await FFmpegManager.cancel_process(job_id)
                raise asyncio.CancelledError()

            async with async_session_factory() as prog_db:
                await prog_db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        progress_percent=p.progress_percent,
                        stage_description=stage_desc
                    )
                )
                await prog_db.commit()

            await JobEventBroadcaster.broadcast(JobEvent(
                job_id=job_id,
                project_id=project_id,
                job_type=job_type,
                event_type="progress",
                progress_percent=p.progress_percent,
                stage_description=f"{stage_desc} ({p.progress_percent}%)"
            ))

        result_data: Dict[str, Any] = {}

        try:
            if cancel_token.is_cancelled:
                raise asyncio.CancelledError()

            # Execute specific job type
            if job_type == "thumbnail":
                result_data = await cls._execute_thumbnail(job_id, params, project_id, on_progress)

            elif job_type == "extract_audio":
                result_data = await cls._execute_extract_audio(job_id, params, project_id, on_progress)

            elif job_type == "generate_preview":
                result_data = await cls._execute_preview(job_id, params, project_id, on_progress)

            elif job_type == "generate_clip":
                result_data = await cls._execute_clip_render(job_id, params, project_id, on_progress)

            elif job_type == "inspect":
                result_data = await cls._execute_inspect(job_id, params, project_id)

            elif job_type == "transcribe_video":
                result_data = await cls._execute_transcribe(job_id, params, project_id, cancel_token)

            elif job_type == "analyze_highlights":
                result_data = await cls._execute_analyze_highlights(job_id, params, project_id, cancel_token)

            elif job_type == "visual_analysis":
                result_data = await cls._execute_visual_analysis(job_id, params, project_id, cancel_token)

            elif job_type in ("render_export", "export"):
                result_data = await cls._execute_render_export(job_id, params, project_id, cancel_token)

            elif job_type == "audio_analysis":
                result_data = await cls._execute_audio_analysis(job_id, params, project_id, cancel_token)

            elif job_type == "speaker_diarization":
                result_data = await cls._execute_speaker_diarization(job_id, params, project_id, cancel_token)

            elif job_type == "composition_render":
                result_data = await cls._execute_composition_render(job_id, params, project_id, cancel_token)

            else:
                raise ValueError(f"Unknown job type: {job_type}")

            # Mark completed
            async with async_session_factory() as comp_db:
                await comp_db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status="completed",
                        progress_percent=100,
                        stage_description="Completed successfully",
                        result_data=result_data,
                        completed_at=datetime.utcnow()
                    )
                )
                await comp_db.commit()

            await JobEventBroadcaster.broadcast(JobEvent(
                job_id=job_id,
                project_id=project_id,
                job_type=job_type,
                event_type="completed",
                progress_percent=100,
                stage_description="Completed successfully",
                result_data=result_data
            ))

            return result_data

        except asyncio.CancelledError:
            logger.warning(f"Job {job_id} cancelled.")
            async with async_session_factory() as canc_db:
                await canc_db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status="cancelled",
                        stage_description="Job cancelled by user",
                        completed_at=datetime.utcnow()
                    )
                )
                await canc_db.commit()

            await JobEventBroadcaster.broadcast(JobEvent(
                job_id=job_id,
                project_id=project_id,
                job_type=job_type,
                event_type="cancelled",
                stage_description="Job cancelled by user"
            ))
            raise

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            err_msg = str(e)
            async with async_session_factory() as err_db:
                await err_db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        status="failed",
                        stage_description="Failed",
                        error_message=err_msg,
                        completed_at=datetime.utcnow()
                    )
                )
                await err_db.commit()

            await JobEventBroadcaster.broadcast(JobEvent(
                job_id=job_id,
                project_id=project_id,
                job_type=job_type,
                event_type="failed",
                error_message=err_msg,
                stage_description=f"Error: {err_msg}"
            ))
            raise

    # ---------------- Specific Handlers ----------------

    @classmethod
    async def _execute_thumbnail(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], on_progress
    ) -> Dict[str, Any]:
        video_id = params.get("video_id")
        async with async_session_factory() as db:
            res = await db.execute(select(Video).where(Video.id == video_id))
            video = res.scalar_one_or_none()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            video_file = video.file_path
            p_id = video.project_id

        dest_dir = settings.DATA_DIR / "projects" / p_id / "thumbnails"
        dest_dir.mkdir(parents=True, exist_ok=True)
        poster_file = dest_dir / f"{video_id}_poster.jpg"

        poster_path = await ThumbnailGenerator.generate_poster_thumbnail(
            video_path=video_file,
            output_path=str(poster_file),
            timestamp_seconds=params.get("timestamp_seconds")
        )

        strip_data = []
        if params.get("generate_strip", True):
            strip_dir = dest_dir / "strip"
            strip_data = await ThumbnailGenerator.generate_thumbnail_strip(
                video_path=video_file,
                output_dir=str(strip_dir),
                num_thumbnails=params.get("strip_count", 10)
            )

        # Update video record
        async with async_session_factory() as db:
            await db.execute(
                update(Video)
                .where(Video.id == video_id)
                .values(thumbnail_path=poster_path)
            )
            await db.commit()

        return {
            "poster_path": poster_path,
            "strip_count": len(strip_data),
            "strip": strip_data
        }

    @classmethod
    async def _execute_extract_audio(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], on_progress
    ) -> Dict[str, Any]:
        video_id = params.get("video_id")
        async with async_session_factory() as db:
            res = await db.execute(select(Video).where(Video.id == video_id))
            video = res.scalar_one_or_none()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            video_file = video.file_path
            p_id = video.project_id

        dest_dir = settings.DATA_DIR / "projects" / p_id / "audio"
        dest_dir.mkdir(parents=True, exist_ok=True)
        wav_file = dest_dir / f"{video_id}_16k_mono.wav"

        async def cb(p: FFmpegProgress):
            await on_progress(p, "Extracting audio")

        wav_path = await AudioExtractor.extract_for_transcription(
            video_path=video_file,
            output_wav_path=str(wav_file),
            on_progress=cb,
            process_id=job_id
        )

        return {"audio_path": wav_path}

    @classmethod
    async def _execute_preview(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], on_progress
    ) -> Dict[str, Any]:
        video_id = params.get("video_id")
        async with async_session_factory() as db:
            res = await db.execute(select(Video).where(Video.id == video_id))
            video = res.scalar_one_or_none()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            video_file = video.file_path
            p_id = video.project_id

        dest_dir = settings.DATA_DIR / "projects" / p_id / "previews"
        dest_dir.mkdir(parents=True, exist_ok=True)
        preview_file = dest_dir / f"{video_id}_preview.mp4"

        async def cb(p: FFmpegProgress):
            await on_progress(p, "Rendering 720p preview")

        prev_path = await PreviewGenerator.generate_preview(
            source_path=video_file,
            output_preview_path=str(preview_file),
            max_height=params.get("max_height", 720),
            on_progress=cb,
            process_id=job_id
        )

        # Update video record
        async with async_session_factory() as db:
            await db.execute(
                update(Video)
                .where(Video.id == video_id)
                .values(preview_path=prev_path)
            )
            await db.commit()

        return {"preview_path": prev_path}

    @classmethod
    async def _execute_clip_render(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], on_progress
    ) -> Dict[str, Any]:
        clip_id = params.get("clip_id")
        start_time = safe_float(params.get("start_time"), 0.0) or 0.0
        end_time = safe_float(params.get("end_time"), 0.0) or 0.0
        aspect_ratio = params.get("aspect_ratio", "9:16")
        reframe_mode = params.get("reframe_mode", "center_crop")
        trajectory = params.get("trajectory")

        async with async_session_factory() as db:
            res = await db.execute(select(Clip).where(Clip.id == clip_id))
            clip = res.scalar_one_or_none()
            if not clip:
                raise ValueError(f"Clip {clip_id} not found")
            
            video_res = await db.execute(select(Video).where(Video.id == clip.video_id))
            video = video_res.scalar_one_or_none()
            if not video:
                raise ValueError(f"Video {clip.video_id} for clip not found")
            
            source_file = video.file_path
            p_id = clip.project_id

            if not trajectory and (reframe_mode == "smart_face_track" or params.get("use_vision_tracking")):
                from ..services.vision_service import VisionService
                from ..ai.vision.schemas import ReframeConfig
                latest_analysis = await VisionService.get_latest_analysis_for_video(db, clip.video_id)
                if latest_analysis:
                    reframe_cfg = ReframeConfig(
                        aspect_ratio=aspect_ratio,
                        strategy=params.get("strategy", "largest_face"),
                        selected_track_id=params.get("selected_track_id"),
                        smoothing_strength=safe_float(params.get("smoothing_strength"), 0.85) or 0.85,
                        headroom=safe_float(params.get("headroom"), 0.20) or 0.20,
                    )
                    coords = await VisionService.calculate_trajectory(db, latest_analysis.id, reframe_cfg)
                    trajectory = [c for c in coords if start_time <= c.timestamp_seconds <= end_time]

        dest_dir = settings.DATA_DIR / "projects" / p_id / "clips"
        dest_dir.mkdir(parents=True, exist_ok=True)
        clip_file = dest_dir / f"{clip_id}_{aspect_ratio.replace(':', '_')}.mp4"

        async def cb(p: FFmpegProgress):
            await on_progress(p, f"Rendering clip ({aspect_ratio})")

        rendered_clip_path = await ClipGenerator.generate_clip(
            source_video_path=source_file,
            output_clip_path=str(clip_file),
            start_time=start_time,
            end_time=end_time,
            aspect_ratio=aspect_ratio,
            reframe_mode=reframe_mode,
            trajectory=trajectory,
            on_progress=cb,
            process_id=job_id
        )

        # Generate clip thumbnail
        thumb_file = dest_dir / f"{clip_id}_thumb.jpg"
        clip_thumb_path = await ThumbnailGenerator.generate_poster_thumbnail(
            video_path=rendered_clip_path,
            output_path=str(thumb_file),
            timestamp_seconds=0.5
        )

        # Update clip record
        async with async_session_factory() as db:
            await db.execute(
                update(Clip)
                .where(Clip.id == clip_id)
                .values(
                    file_path=rendered_clip_path,
                    thumbnail_path=clip_thumb_path,
                    status="ready",
                    duration_seconds=end_time - start_time,
                    aspect_ratio=aspect_ratio
                )
            )
            await db.commit()

        return {
            "clip_path": rendered_clip_path,
            "thumbnail_path": clip_thumb_path,
            "duration_seconds": end_time - start_time
        }

    @classmethod
    async def _execute_inspect(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str]
    ) -> Dict[str, Any]:
        video_id = params.get("video_id")
        async with async_session_factory() as db:
            res = await db.execute(select(Video).where(Video.id == video_id))
            video = res.scalar_one_or_none()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            file_path = video.file_path

        meta = FFprobeManager.probe(file_path)
        if not meta.valid:
            raise ValueError(f"FFprobe failed: {meta.error}")

        async with async_session_factory() as db:
            v_update = {
                "duration_seconds": meta.duration_seconds,
                "format": meta.format_name,
            }
            if meta.video_stream:
                v_update.update({
                    "width": meta.video_stream.width,
                    "height": meta.video_stream.height,
                    "fps": meta.video_stream.fps,
                    "video_codec": meta.video_stream.codec_name,
                })
            if meta.audio_stream:
                v_update.update({
                    "has_audio": True,
                    "audio_codec": meta.audio_stream.codec_name,
                    "audio_channels": meta.audio_stream.channels,
                })
            await db.execute(
                update(Video).where(Video.id == video_id).values(**v_update)
            )
            await db.commit()

        return meta.model_dump()

    @classmethod
    async def _execute_transcribe(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], cancel_token: CancellationToken
    ) -> Dict[str, Any]:
        from ..services.transcription_service import TranscriptionService

        video_id = params.get("video_id")
        if not video_id:
            raise ValueError("video_id is required for transcribe_video job")

        async def on_transcribe_progress(percent: int, stage_desc: str):
            if cancel_token.is_cancelled:
                raise asyncio.CancelledError()

            async with async_session_factory() as prog_db:
                await prog_db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        progress_percent=percent,
                        stage_description=stage_desc
                    )
                )
                await prog_db.commit()

            await JobEventBroadcaster.broadcast(JobEvent(
                job_id=job_id,
                project_id=project_id,
                job_type="transcribe_video",
                event_type="progress",
                progress_percent=percent,
                stage_description=stage_desc
            ))

        return await TranscriptionService.process_transcription_job(
            video_id=video_id,
            params=params,
            on_progress=on_transcribe_progress,
            is_cancelled=lambda: cancel_token.is_cancelled
        )

    @classmethod
    async def _execute_analyze_highlights(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], cancel_token: CancellationToken
    ) -> Dict[str, Any]:
        from ..services.transcript_repository import TranscriptRepository
        from ..services.highlight_service import HighlightService
        from ..ai.highlights.highlight_analyzer import HighlightAnalyzer, HighlightAnalysisConfig

        video_id = params.get("video_id")
        if not video_id:
            raise ValueError("video_id is required for analyze_highlights job")

        # 1. Fetch video and transcript from database (with retry)
        video = None
        for attempt in range(3):
            async with async_session_factory() as db:
                v_res = await db.execute(select(Video).where(Video.id == video_id))
                video = v_res.scalar_one_or_none()
                if video:
                    video_duration = video.duration_seconds
                    resolved_project_id = project_id or video.project_id
                    break
            await asyncio.sleep(0.2)

        if not video:
            raise FileNotFoundError(f"Video {video_id} not found")

        async with async_session_factory() as db:
            transcript = await TranscriptRepository.get_by_video_id(db, video_id)
            if not transcript or not transcript.segments:
                # Prerequisite resolution: Auto-run transcription if video has audio
                if video.has_audio:
                    from ..services.transcription_service import TranscriptionService
                    logger.info(f"Video {video_id} has not been transcribed yet. Automatically triggering transcription prerequisite...")
                    try:
                        await TranscriptionService.process_transcription_job(
                            video_id=video_id,
                            params={"video_id": video_id},
                            on_progress=None,
                            is_cancelled=lambda: cancel_token.is_cancelled,
                        )
                        transcript = await TranscriptRepository.get_by_video_id(db, video_id)
                    except Exception as t_err:
                        logger.warning(f"Automatic transcription attempt finished: {t_err}")

            transcript_id = transcript.id if transcript else None
            # Extract segment data if transcript present
            segments = [
                {
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "text": s.text,
                    "words": s.words or []
                }
                for s in (transcript.segments if transcript else [])
            ]

        # 2. Progress callback
        async def on_stage_update(stage_desc: str, percent: int):
            if cancel_token.is_cancelled:
                raise asyncio.CancelledError()

            async with async_session_factory() as prog_db:
                await prog_db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        progress_percent=percent,
                        stage_description=stage_desc
                    )
                )
                await prog_db.commit()

            await JobEventBroadcaster.broadcast(JobEvent(
                job_id=job_id,
                project_id=resolved_project_id,
                job_type="analyze_highlights",
                event_type="progress",
                progress_percent=percent,
                stage_description=f"{stage_desc} ({percent}%)"
            ))

        # 3. Configure analysis
        model_name = params.get("model_name", "qwen-2.5-3b")
        content_type = params.get("content_type", "general")
        target_duration_min = safe_float(params.get("target_duration_min"), 30.0) or 30.0
        target_duration_max = safe_float(params.get("target_duration_max"), 60.0) or 60.0
        max_candidates = int(safe_float(params.get("max_candidates"), 5.0) or 5)

        config = HighlightAnalysisConfig(
            model_name=model_name,
            content_type=content_type,
            target_duration_min=target_duration_min,
            target_duration_max=target_duration_max,
            max_candidates=max_candidates
        )

        # 4. Run highlight analysis pipeline
        candidates = await HighlightAnalyzer.analyze(
            segments=segments,
            total_video_duration=video_duration,
            config=config,
            on_stage_update=on_stage_update
        )

        # 5. Persist candidates
        created_clip_ids = []
        async with async_session_factory() as db:
            saved_records = await HighlightService.save_candidates(
                db=db,
                video_id=video_id,
                project_id=resolved_project_id,
                candidates=candidates,
                transcript_id=transcript_id,
                model_name=model_name
            )

            # Auto-create clips if requested
            if params.get("auto_create_clips", False) and saved_records:
                for cand in saved_records:
                    try:
                        clip = await HighlightService.create_clip_from_candidate(
                            db=db,
                            candidate_id=cand.id,
                            aspect_ratio=params.get("aspect_ratio", "9:16"),
                            reframe_mode=params.get("reframe_mode", "center_crop")
                        )
                        created_clip_ids.append(clip.id)
                    except Exception as clip_err:
                        logger.warning(f"Failed to auto-create clip for candidate {cand.id}: {clip_err}")

        return {
            "video_id": video_id,
            "project_id": resolved_project_id,
            "transcript_id": transcript_id,
            "model_used": model_name,
            "content_type": content_type,
            "candidates_count": len(saved_records),
            "candidate_ids": [r.id for r in saved_records],
            "auto_created_clips": created_clip_ids
        }

    @classmethod
    async def _execute_visual_analysis(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], cancel_token: CancellationToken
    ) -> Dict[str, Any]:
        from ..ai.vision.vision_manager import VisionManager
        from ..services.vision_service import VisionService

        video_id = params.get("video_id")
        if not video_id:
            raise ValueError("video_id is required for visual_analysis job")

        clip_id = params.get("clip_id")
        sampling_fps = safe_float(params.get("sampling_fps"), 4.0) or 4.0
        confidence_threshold = safe_float(params.get("confidence_threshold"), 0.55) or 0.55
        start_time = safe_float(params.get("start_time"), 0.0) or 0.0
        end_time = safe_float(params.get("end_time"), None)

        # 1. Fetch video record (with retry to tolerate async session commit delay)
        video = None
        for attempt in range(3):
            async with async_session_factory() as db:
                v_res = await db.execute(select(Video).where(Video.id == video_id))
                video = v_res.scalar_one_or_none()
                if video:
                    video_path = video.file_path
                    resolved_project_id = project_id or video.project_id
                    break
            await asyncio.sleep(0.2)

        if not video:
            raise FileNotFoundError(f"Video {video_id} not found in database.")

        # 2. Progress callback
        loop = asyncio.get_running_loop()

        def on_stage_update(percent: int, stage_desc: str):
            if cancel_token.is_cancelled:
                raise asyncio.CancelledError()

            async def _persist_and_broadcast():
                async with async_session_factory() as prog_db:
                    await prog_db.execute(
                        update(Job)
                        .where(Job.id == job_id)
                        .values(
                            progress_percent=percent,
                            stage_description=stage_desc,
                        )
                    )
                    await prog_db.commit()

                await JobEventBroadcaster.broadcast(JobEvent(
                    job_id=job_id,
                    project_id=resolved_project_id,
                    job_type="visual_analysis",
                    event_type="progress",
                    progress_percent=percent,
                    stage_description=f"{stage_desc} ({percent}%)",
                ))

            asyncio.run_coroutine_threadsafe(_persist_and_broadcast(), loop)

        # 3. Execute vision analysis
        manager = VisionManager()
        analysis_result = await manager.analyze_video(
            video_path=video_path,
            start_time=start_time,
            end_time=end_time,
            sampling_fps=sampling_fps,
            confidence_threshold=confidence_threshold,
            progress_callback=on_stage_update,
            is_cancelled=lambda: cancel_token.is_cancelled,
        )

        # 4. Persist analysis & face tracks
        async with async_session_factory() as db:
            saved_analysis = await VisionService.save_analysis(
                db=db,
                video_id=video_id,
                result=analysis_result,
                clip_id=clip_id,
            )
            analysis_id = saved_analysis.id

        return {
            "analysis_id": analysis_id,
            "video_id": video_id,
            "project_id": resolved_project_id,
            "clip_id": clip_id,
            "model_used": analysis_result.model_name,
            "total_frames_sampled": analysis_result.total_frames_sampled,
            "frames_with_faces": analysis_result.frames_with_faces,
            "tracks_count": len(analysis_result.tracked_faces),
            "scene_type": analysis_result.composition.scene_type,
            "composition": analysis_result.composition.model_dump(),
        }

    @classmethod
    async def _execute_render_export(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], cancel_token: CancellationToken
    ) -> Dict[str, Any]:
        from ..services.export_service import ExportService
        from ..schemas.subtitle_schemas import RenderExportRequest

        clip_id = params.get("clip_id")
        if not clip_id:
            raise ValueError("clip_id is required for render_export job")

        # Construct request object
        render_req = RenderExportRequest(
            preset_id=params.get("preset_id"),
            resolution=params.get("resolution", "1080x1920"),
            fps=safe_float(params.get("fps"), 30.0) or 30.0,
            bitrate_kbps=int(safe_float(params.get("bitrate_kbps"), 6000.0) or 6000),
            burn_subtitles=bool(params.get("burn_subtitles", True)),
            reframe_mode=params.get("reframe_mode", "smart_face_track"),
            use_vision_tracking=bool(params.get("use_vision_tracking", True)),
            custom_style=params.get("custom_style"),
            codec=params.get("codec"),
        )

        async def on_progress(percent: int, stage_desc: str):
            if cancel_token.is_cancelled:
                raise asyncio.CancelledError()

            async with async_session_factory() as prog_db:
                await prog_db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        progress_percent=percent,
                        stage_description=stage_desc,
                    )
                )
                await prog_db.commit()

            await JobEventBroadcaster.broadcast(JobEvent(
                job_id=job_id,
                project_id=project_id,
                job_type="render_export",
                event_type="progress",
                progress_percent=percent,
                stage_description=f"{stage_desc} ({percent}%)",
            ))

        async with async_session_factory() as db:
            export_rec = await ExportService.render_final_export(
                db=db,
                clip_id=clip_id,
                request=render_req,
                job_id=job_id,
                on_progress=on_progress,
                is_cancelled=lambda: cancel_token.is_cancelled,
            )

            return {
                "export_id": export_rec.id,
                "clip_id": clip_id,
                "output_path": export_rec.output_path,
                "resolution": export_rec.resolution,
                "file_size_bytes": export_rec.file_size_bytes,
                "duration_seconds": export_rec.duration_seconds,
                "codec": export_rec.codec,
            }

    @classmethod
    async def _execute_audio_analysis(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], cancel_token: CancellationToken
    ) -> Dict[str, Any]:
        from ..services.audio_analysis_service import AudioAnalysisService
        from ..schemas.audio_schemas import VADConfigSchema

        video_id = params.get("video_id")
        if not video_id:
            raise ValueError("video_id is required for audio_analysis job")

        # 1. Fetch video record (with retry to tolerate async session commit delay)
        video = None
        for attempt in range(3):
            async with async_session_factory() as db:
                v_res = await db.execute(select(Video).where(Video.id == video_id))
                video = v_res.scalar_one_or_none()
                if video:
                    video_path = video.file_path
                    resolved_project_id = project_id or video.project_id
                    break
            await asyncio.sleep(0.2)

        if not video:
            raise FileNotFoundError(f"Video {video_id} not found in database.")

        # 2. Setup progress callback
        loop = asyncio.get_running_loop()

        def on_stage_update(percent: int, stage_desc: str):
            if cancel_token.is_cancelled:
                raise asyncio.CancelledError()

            async def _persist_and_broadcast():
                async with async_session_factory() as prog_db:
                    await prog_db.execute(
                        update(Job)
                        .where(Job.id == job_id)
                        .values(
                            progress_percent=percent,
                            stage_description=stage_desc,
                        )
                    )
                    await prog_db.commit()

                await JobEventBroadcaster.broadcast(JobEvent(
                    job_id=job_id,
                    project_id=resolved_project_id,
                    job_type="audio_analysis",
                    event_type="progress",
                    progress_percent=percent,
                    stage_description=f"{stage_desc} ({percent}%)",
                ))

            asyncio.run_coroutine_threadsafe(_persist_and_broadcast(), loop)

        # 3. Parse optional config
        raw_cfg = params.get("config")
        vad_config = VADConfigSchema(**raw_cfg) if raw_cfg else VADConfigSchema()

        # 4. Execute pipeline
        analysis_data = await AudioAnalysisService.run_audio_analysis(
            video_path=video_path,
            project_id=resolved_project_id,
            video_id=video_id,
            config=vad_config,
            force_reprocess=params.get("force_reprocess", False),
            progress_callback=on_stage_update,
            is_cancelled=lambda: cancel_token.is_cancelled,
        )

        # 5. Persist AudioAnalysis & SpeechIntervals
        async with async_session_factory() as db:
            saved_analysis = await AudioAnalysisService.save_analysis(
                db=db,
                project_id=resolved_project_id,
                video_id=video_id,
                metadata=analysis_data["metadata"],
                speech_intervals=analysis_data["intervals"],
                config=vad_config,
                processing_duration=analysis_data["processing_duration"],
                vad_model=analysis_data.get("vad_model", "silero-vad-v4"),
                vad_version=analysis_data.get("vad_version", "1.2.1"),
                processing_device=analysis_data.get("device", "cpu"),
            )
            analysis_id = saved_analysis.id

        from ..ai.audio.voice_activity_detector import VoiceActivityDetector
        total_speech = VoiceActivityDetector.calculate_interval_union_duration(analysis_data["intervals"])
        if analysis_data["metadata"].source_duration > 0.0:
            total_speech = min(analysis_data["metadata"].source_duration, total_speech)
        return {
            "analysis_id": analysis_id,
            "video_id": video_id,
            "project_id": resolved_project_id,
            "total_speech_intervals": len(analysis_data["intervals"]),
            "speech_duration_seconds": round(total_speech, 2),
            "audio_available": analysis_data["metadata"].audio_available,
            "audio_is_silent": analysis_data["metadata"].audio_is_silent,
            "vad_model": analysis_data.get("vad_model", "silero-vad-v4"),
            "vad_version": analysis_data.get("vad_version", "1.2.1"),
            "processing_duration": round(analysis_data["processing_duration"], 2),
        }

    @classmethod
    async def _execute_speaker_diarization(
        cls, job_id: str, params: Dict[str, Any], project_id: Optional[str], cancel_token: CancellationToken
    ) -> Dict[str, Any]:
        from ..services.speaker_analysis_service import SpeakerAnalysisService
        from ..schemas.speaker_schemas import DiarizationConfigSchema
        from ..db.models import AudioAnalysis, Video

        analysis_id = params.get("analysis_id")
        if not analysis_id:
            raise ValueError("analysis_id is required for speaker_diarization job")

        # 1. Fetch analysis and video
        async with async_session_factory() as db:
            a_res = await db.execute(
                select(AudioAnalysis)
                .where(AudioAnalysis.id == analysis_id)
                .options(selectinload(AudioAnalysis.speech_intervals))
            )
            analysis = a_res.scalar_one_or_none()
            if not analysis:
                raise FileNotFoundError(f"AudioAnalysis {analysis_id} not found")

            v_res = await db.execute(select(Video).where(Video.id == analysis.video_id))
            video = v_res.scalar_one_or_none()
            if not video:
                raise FileNotFoundError(f"Video {analysis.video_id} not found")

            video_path = video.file_path
            resolved_project_id = project_id or analysis.project_id
            speech_intervals = list(analysis.speech_intervals)

        # 2. Setup progress callback
        loop = asyncio.get_running_loop()

        def on_stage_update(percent: int, stage_desc: str):
            if cancel_token.is_cancelled:
                return

            async def _persist_and_broadcast():
                async with async_session_factory() as p_db:
                    await p_db.execute(
                        update(Job)
                        .where(Job.id == job_id)
                        .values(
                            progress_percent=percent,
                            stage_description=f"{stage_desc} ({percent}%)",
                            updated_at=datetime.utcnow()
                        )
                    )
                    await p_db.commit()

                from ..services.websocket_service import manager
                await manager.broadcast_job_event(JobEvent(
                    job_id=job_id,
                    project_id=resolved_project_id,
                    job_type="speaker_diarization",
                    event_type="progress",
                    progress_percent=percent,
                    stage_description=f"{stage_desc} ({percent}%)",
                ))

            asyncio.run_coroutine_threadsafe(_persist_and_broadcast(), loop)

        # 3. Parse optional config
        raw_cfg = params.get("config")
        diar_config = DiarizationConfigSchema(**raw_cfg) if raw_cfg else DiarizationConfigSchema()

        # 4. Execute diarization pipeline
        diar_result = await SpeakerAnalysisService.run_speaker_diarization(
            audio_path=video_path,
            analysis_id=analysis_id,
            speech_intervals=speech_intervals,
            config=diar_config,
            progress_callback=on_stage_update,
            is_cancelled=lambda: cancel_token.is_cancelled,
        )

        # 5. Persist speakers, turns, embeddings
        async with async_session_factory() as db:
            await SpeakerAnalysisService.save_diarization_results(
                db=db,
                analysis_id=analysis_id,
                project_id=resolved_project_id,
                diarization_result=diar_result,
            )

        return {
            "analysis_id": analysis_id,
            "project_id": resolved_project_id,
            "num_speakers": diar_result.num_speakers,
            "total_speaker_turns": len(diar_result.speaker_turns),
            "total_speech_duration": diar_result.total_speech_duration,
            "silhouette_score": diar_result.silhouette_score,
            "processing_duration": diar_result.processing_duration,
            "rtf": diar_result.rtf,
            "execution_device": diar_result.execution_device,
        }

    @classmethod
    async def _execute_composition_render(
        cls,
        job_id: str,
        params: Dict[str, Any],
        project_id: Optional[str],
        cancel_token: CancellationToken,
    ) -> Dict[str, Any]:
        from ..composition.render.execution.render_executor import RenderExecutor
        from ..db.models import CompositionRender
        render_id = params.get("render_id")
        if not render_id:
            raise ValueError("composition_render job missing 'render_id' in params")

        # Retry fetching render record up to 3 times to tolerate async session commit delay
        for attempt in range(3):
            async with async_session_factory() as chk_db:
                r_chk = await chk_db.execute(select(CompositionRender).where(CompositionRender.id == render_id))
                if r_chk.scalar_one_or_none():
                    break
            await asyncio.sleep(0.2)

        async with async_session_factory() as db:
            result = await RenderExecutor.execute_render(
                render_id=render_id,
                db=db,
                cancel_token=cancel_token,
            )

        if not result.success:
            raise RuntimeError(result.error_message or "Composition render execution failed.")

        return {
            "render_id": result.render_id,
            "output_file_path": result.output_file_path,
            "duration_seconds": result.duration_seconds,
            "validation_status": result.validation_result.status if result.validation_result else "unknown",
        }
