"""
ClipForge AI - Composition Render Executor
Phase 9 Stage 3: Orchestrates full render lifecycle, atomic publishing, validation, and persistence.
"""

import asyncio
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.config import settings
from ....db.models import Composition, CompositionVersion, CompositionRender, RenderArtifact, CompositionAsset, Video
from ...schemas.composition import CompositionSpec
from ...schemas.delivery import DeliveryProfile
from ..graph.graph_builder import CompositionToGraphBuilder
from ..compiler.ffmpeg_compiler import RenderGraphCompiler, FFmpegExecutionPlan
from ..validation.output_validator import OutputValidator, OutputValidationResult
from .render_process import RenderProcessRunner
from .render_progress import RenderProgressTracker
from ....workers.cancellation import CancellationToken
from ....services.subtitle_renderer import SubtitleRenderer, DEFAULT_PRESETS, CaptionPresetSchema, SubtitleSegment

logger = logging.getLogger("clipforge.composition.render.executor")


class RenderExecutionResult:
    def __init__(
        self,
        success: bool,
        render_id: str,
        output_file_path: Optional[str] = None,
        error_message: Optional[str] = None,
        validation_result: Optional[OutputValidationResult] = None,
        duration_seconds: float = 0.0,
    ):
        self.success = success
        self.render_id = render_id
        self.output_file_path = output_file_path
        self.error_message = error_message
        self.validation_result = validation_result
        self.duration_seconds = duration_seconds


class RenderExecutor:
    """Executes the complete rendering workflow for a CompositionRender."""

    DEFAULT_OUTPUT_DIR = settings.EXPORTS_DIR

    @classmethod
    async def execute_render(
        cls,
        render_id: str,
        db: AsyncSession,
        cancel_token: Optional[CancellationToken] = None,
        custom_output_dir: Optional[Path] = None,
    ) -> RenderExecutionResult:
        start_time = time.time()
        
        # 1. Fetch Render and Version
        r_query = await db.execute(select(CompositionRender).where(CompositionRender.id == render_id))
        render = r_query.scalar_one_or_none()
        if not render:
            raise ValueError(f"CompositionRender '{render_id}' not found.")

        v_query = await db.execute(select(CompositionVersion).where(CompositionVersion.id == render.composition_version_id))
        version = v_query.scalar_one_or_none()
        if not version:
            raise ValueError(f"CompositionVersion '{render.composition_version_id}' not found.")

        c_query = await db.execute(select(Composition).where(Composition.id == render.composition_id))
        composition = c_query.scalar_one_or_none()

        spec = CompositionSpec.model_validate(version.spec_json) if isinstance(version.spec_json, dict) else CompositionSpec.from_canonical_json(version.spec_json)
        delivery = getattr(spec, "delivery_profile", None) or getattr(spec, "delivery", None)

        # 2. Update Status: Preparing
        render.status = "preparing"
        render.progress_percent = 5
        await db.commit()

        tracker = RenderProgressTracker(job_id=render_id, project_id=composition.project_id if composition else None)
        await tracker.update_stage("Preparing render workspace", 5)

        temp_dir = (settings.CACHE_DIR / "render_tmp" / render_id).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)

        final_dir = (custom_output_dir or settings.EXPORTS_DIR).resolve()
        final_dir.mkdir(parents=True, exist_ok=True)
        final_output_file = final_dir / f"composition_{composition.id if composition else 'clip'}_{render_id[:8]}.mp4"
        tmp_output_file = temp_dir / f"render_{render_id[:8]}.tmp.mp4"

        try:
            if cancel_token and cancel_token.is_cancelled:
                raise asyncio.CancelledError()

            # 3. Resolve Source Media Path
            source_path: Optional[str] = None
            if spec.source_media.asset_uri and composition:
                try:
                    from ...schemas.assets import parse_asset_uri
                    parsed = parse_asset_uri(spec.source_media.asset_uri)
                    a_res = await db.execute(
                        select(CompositionAsset).where(
                            CompositionAsset.project_id == composition.project_id,
                            CompositionAsset.asset_type == parsed.asset_type,
                            CompositionAsset.logical_asset_id == parsed.asset_id,
                        )
                    )
                    asset = a_res.scalar_one_or_none()
                    if asset and Path(asset.file_path).exists():
                        source_path = asset.file_path
                except Exception:
                    pass

            if not source_path and composition and composition.source_video_id:
                # Fallback to Video entity
                v_res = await db.execute(select(Video).where(Video.id == composition.source_video_id))
                vid = v_res.scalar_one_or_none()
                if vid and Path(vid.file_path).exists():
                    source_path = vid.file_path

            if not source_path:
                raise FileNotFoundError(f"Could not resolve physical media for '{spec.source_media.asset_uri}'")

            # 4. Handle Subtitles (if enabled)
            ass_path_str: Optional[str] = None
            if spec.subtitles.segments:
                # Build ASS subtitle file
                ass_file = temp_dir / f"subtitles_{render_id[:8]}.ass"
                preset = DEFAULT_PRESETS[1]  # Bold Creator default
                
                # Convert subtitle segment refs
                sub_segments: List[SubtitleSegment] = []
                for s_ref in spec.subtitles.segments:
                    sub_segments.append(SubtitleSegment(
                        start_time=s_ref.start_us / 1_000_000.0,
                        end_time=s_ref.end_us / 1_000_000.0,
                        text=s_ref.text,
                        words=[],
                    ))

                SubtitleRenderer.write_ass_file(
                    segments=sub_segments,
                    preset=preset,
                    output_file_path=str(ass_file),
                    canvas_width=delivery.width,
                    canvas_height=delivery.height,
                )
                ass_path_str = str(ass_file.resolve())

                # Add ASS script artifact
                db.add(RenderArtifact(
                    composition_render_id=render.id,
                    artifact_type="ass_script",
                    file_path=ass_path_str,
                    file_size_bytes=ass_file.stat().st_size if ass_file.exists() else 0,
                ))

            # 5. Build Graph & Compile Plan
            await tracker.update_stage("Compiling render graph", 15)
            render.status = "compiling"
            render.progress_percent = 15
            await db.commit()

            boundary = getattr(spec, "clip_boundary", None) or getattr(getattr(spec, "timeline", None), "composition_boundary", None)
            start_us = getattr(boundary, "source_start_us", getattr(boundary, "in_point_us", 0)) if boundary else 0
            end_us = getattr(boundary, "source_end_us", getattr(boundary, "out_point_us", 1000000)) if boundary else getattr(getattr(spec, "timeline", None), "total_duration_us", 1000000)
            est_dur_s = (end_us - start_us) / 1_000_000.0

            graph = CompositionToGraphBuilder.build_graph(
                spec=spec,
                source_media_path=source_path,
                output_file_path=str(tmp_output_file),
                ass_subtitle_path=ass_path_str,
                graph_id=f"g_{render_id[:8]}",
            )

            plan = RenderGraphCompiler.compile(
                graph=graph,
                delivery=delivery,
                render_id=render_id,
                estimated_duration_seconds=est_dur_s,
                custom_script_dir=temp_dir,
            )

            if plan.filter_script_path:
                db.add(RenderArtifact(
                    composition_render_id=render.id,
                    artifact_type="ffscript",
                    file_path=plan.filter_script_path,
                    file_size_bytes=Path(plan.filter_script_path).stat().st_size if Path(plan.filter_script_path).exists() else 0,
                ))

            if cancel_token and cancel_token.is_cancelled:
                raise asyncio.CancelledError()

            # 6. Execute FFmpeg Rendering
            await tracker.update_stage("Rendering video", 20)
            render.status = "rendering"
            render.progress_percent = 20
            await db.commit()

            proc_result = await RenderProcessRunner.run_plan(
                plan=plan,
                process_id=f"proc_{render_id}",
                progress_tracker=tracker,
                total_duration=est_dur_s,
            )

            if not proc_result.success:
                err_msg = proc_result.error_message or "FFmpeg process failed with non-zero exit code."
                logger.error(f"Render {render_id} failed: {err_msg}")
                render.status = "failed"
                render.error_message = err_msg
                render.completed_at = datetime.utcnow()
                await db.commit()
                if tmp_output_file.exists():
                    tmp_output_file.unlink()
                return RenderExecutionResult(
                    success=False,
                    render_id=render_id,
                    error_message=err_msg,
                    duration_seconds=time.time() - start_time,
                )

            # 7. Post-Flight Output Validation
            await tracker.update_stage("Validating rendered output", 92)
            render.status = "validating"
            render.progress_percent = 92
            await db.commit()

            val_result = OutputValidator.validate_file(
                file_path=str(tmp_output_file),
                expected_delivery=delivery,
                expected_duration_seconds=est_dur_s,
            )

            if not val_result.is_valid:
                err_summary = "; ".join(val_result.errors)
                logger.error(f"Render {render_id} validation failed: {err_summary}")
                render.status = "failed"
                render.error_message = f"Output validation failed: {err_summary}"
                render.completed_at = datetime.utcnow()
                await db.commit()
                if tmp_output_file.exists():
                    tmp_output_file.unlink()
                return RenderExecutionResult(
                    success=False,
                    render_id=render_id,
                    error_message=err_summary,
                    validation_result=val_result,
                    duration_seconds=time.time() - start_time,
                )

            # 8. Atomic Publication with Windows File Lock Tolerance
            if final_output_file.exists():
                try:
                    final_output_file.unlink()
                except Exception:
                    pass

            moved = False
            for attempt in range(10):
                try:
                    shutil.move(str(tmp_output_file), str(final_output_file))
                    moved = True
                    break
                except (PermissionError, OSError):
                    await asyncio.sleep(0.15 * (attempt + 1))

            if not moved:
                shutil.copy2(str(tmp_output_file), str(final_output_file))
                try:
                    tmp_output_file.unlink()
                except Exception:
                    pass

            # 9. Update Database Record as Completed
            total_elapsed = time.time() - start_time
            render.status = "completed"
            render.progress_percent = 100
            render.output_path = str(final_output_file.resolve())
            render.render_duration_seconds = round(total_elapsed, 2)
            render.file_size_bytes = val_result.file_size_bytes
            render.validation_metrics = val_result.model_dump()
            render.completed_at = datetime.utcnow()
            await db.commit()

            await tracker.update_stage("Render completed successfully", 100)

            return RenderExecutionResult(
                success=True,
                render_id=render_id,
                output_file_path=str(final_output_file.resolve()),
                validation_result=val_result,
                duration_seconds=total_elapsed,
            )

        except asyncio.CancelledError:
            logger.warning(f"Render {render_id} was cancelled.")
            try:
                await db.rollback()
            except Exception:
                pass
            try:
                r_stmt = select(CompositionRender).where(CompositionRender.id == render_id)
                res = await db.execute(r_stmt)
                ren = res.scalar_one_or_none()
                if ren:
                    ren.status = "cancelled"
                    ren.error_message = "Cancelled by user."
                    ren.completed_at = datetime.utcnow()
                    await db.commit()
            except Exception as commit_err:
                logger.warning(f"Failed to record cancelled render status: {commit_err}")
            if tmp_output_file.exists():
                try:
                    tmp_output_file.unlink()
                except Exception:
                    pass
            raise

        except Exception as e:
            logger.exception(f"Unhandled exception during render {render_id}: {e}")
            try:
                await db.rollback()
            except Exception:
                pass
            try:
                r_stmt = select(CompositionRender).where(CompositionRender.id == render_id)
                res = await db.execute(r_stmt)
                ren = res.scalar_one_or_none()
                if ren:
                    ren.status = "failed"
                    ren.error_message = str(e)
                    ren.completed_at = datetime.utcnow()
                    await db.commit()
            except Exception as commit_err:
                logger.warning(f"Failed to record failed render status: {commit_err}")
            if tmp_output_file.exists():
                try:
                    tmp_output_file.unlink()
                except Exception:
                    pass
            return RenderExecutionResult(
                success=False,
                render_id=render_id,
                error_message=str(e),
                duration_seconds=time.time() - start_time,
            )
        finally:
            # Clean up temporary dir if empty or partial files remain
            try:
                if temp_dir.exists():
                    shutil.rmtree(str(temp_dir), ignore_errors=True)
            except Exception:
                pass
