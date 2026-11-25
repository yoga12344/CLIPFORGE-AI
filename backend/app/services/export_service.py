"""
ClipForge AI - Coordinated Final Video Export Pipeline
Renders approved clips with accurate source slicing, dynamic camera tracking crop trajectories,
karaoke ASS subtitle burn-in, hardware-accelerated/CPU H.264 encoding, FFprobe verification,
and persistent export tracking.
"""

import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import settings
from app.db.models import Clip, Export, Job, Video, CaptionPreset, SubtitleTrack
from app.schemas.subtitle_schemas import CaptionPresetSchema, RenderExportRequest, SubtitleSegment
from app.services.subtitle_renderer import SubtitleRenderer, DEFAULT_PRESETS, format_ffmpeg_ass_path
from app.services.subtitle_service import SubtitleService
from app.services.vision_service import VisionService
from app.ai.vision.schemas import ReframeConfig
from app.video.aspect_ratio import AspectRatioProcessor, TARGET_DIMENSIONS
from app.video.capabilities import CapabilityDetector
from app.video.ffmpeg_manager import FFmpegManager, FFmpegProgress
from app.video.ffprobe_manager import FFprobeManager
from app.workers.job_events import JobEvent, JobEventBroadcaster

logger = logging.getLogger("clipforge.services.export")


class ExportService:

    @classmethod
    async def render_final_export(
        cls,
        db: AsyncSession,
        clip_id: str,
        request: RenderExportRequest,
        job_id: Optional[str] = None,
        on_progress: Optional[Callable[[int, str], Coroutine[None, None, None]]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Export:
        """
        Execute full render pipeline:
        Source Cut -> Smart Crop Trajectory -> Scale -> Burn ASS Subtitles -> Encode -> Verify -> Persist.
        """
        # 1. Fetch Clip and Video records
        c_res = await db.execute(select(Clip).where(Clip.id == clip_id))
        clip = c_res.scalars().first()
        if not clip:
            raise ValueError(f"Clip {clip_id} not found")

        v_res = await db.execute(select(Video).where(Video.id == clip.video_id))
        video = v_res.scalars().first()
        if not video:
            raise ValueError(f"Parent Video {clip.video_id} not found")

        source_video_path = Path(video.file_path).resolve()
        if not source_video_path.exists():
            raise FileNotFoundError(f"Source video file not found: {source_video_path}")

        start_time = max(0.0, clip.start_time)
        end_time = max(start_time + 0.5, clip.end_time)
        clip_duration = end_time - start_time

        # 2. Determine Output Resolution and Aspect Ratio
        res_str = request.resolution
        tw, th = 1080, 1920
        if "x" in res_str:
            parts = res_str.split("x")
            try:
                tw, th = int(parts[0]), int(parts[1])
            except Exception:
                tw, th = 1080, 1920

        # Determine ratio key (e.g. 9:16, 1:1, etc.)
        if tw == 1080 and th == 1920:
            aspect_ratio_key = "9:16"
        elif tw == 1080 and th == 1080:
            aspect_ratio_key = "1:1"
        elif tw == 1080 and th == 1350:
            aspect_ratio_key = "4:5"
        elif tw == 1920 and th == 1080:
            aspect_ratio_key = "16:9"
        else:
            aspect_ratio_key = f"{tw}:{th}"

        # 3. Destination File Path
        export_dir = settings.DATA_DIR / "projects" / clip.project_id / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        export_filename = f"{clip_id}_{res_str}_{int(datetime.utcnow().timestamp())}.mp4"
        final_output_path = export_dir / export_filename

        if on_progress:
            await on_progress(5, "Preparing render filters and trajectories")

        # 4. Trajectory and Cropping Filtergraph
        vf_base = ""
        trajectory = None

        if request.use_vision_tracking:
            latest_analysis = await VisionService.get_latest_analysis_for_video(db, clip.video_id)
            if latest_analysis:
                reframe_cfg = ReframeConfig(
                    aspect_ratio=aspect_ratio_key,
                    strategy="largest_face",
                    smoothing_strength=0.85,
                    headroom=0.20,
                )
                coords = await VisionService.calculate_trajectory(db, latest_analysis.id, reframe_cfg)
                trajectory = [c for c in coords if start_time <= c.timestamp_seconds <= end_time]

        if trajectory and len(trajectory) > 0:
            first_c = trajectory[0]
            cw = getattr(first_c, "pixel_width", 0) if hasattr(first_c, "pixel_width") else first_c.get("pixel_width", 0)
            ch = getattr(first_c, "pixel_height", 0) if hasattr(first_c, "pixel_height") else first_c.get("pixel_height", 0)
            vf_base = AspectRatioProcessor.build_trajectory_filtergraph(
                crop_w=cw,
                crop_h=ch,
                trajectory=trajectory,
                aspect_ratio=aspect_ratio_key,
            )
        else:
            vf_base = AspectRatioProcessor.build_filtergraph(
                aspect_ratio=aspect_ratio_key,
                mode=request.reframe_mode if request.reframe_mode in ("fit_pad", "blur_background") else "center_crop",
            )

        # 5. Subtitle Burn-In Preparation (ASS)
        temp_ass_path: Optional[str] = None
        subtitle_snapshot: Optional[Dict[str, Any]] = None

        if request.burn_subtitles:
            track = await SubtitleService.get_or_create_subtitle_track(db, clip.id)
            if track and track.is_enabled and track.segments:
                # Load or resolve preset
                preset_schema = None
                if request.custom_style:
                    preset_schema = CaptionPresetSchema(**request.custom_style)
                elif track.preset_id:
                    p_res = await db.execute(select(CaptionPreset).where(CaptionPreset.id == track.preset_id))
                    db_p = p_res.scalars().first()
                    if db_p:
                        preset_schema = CaptionPresetSchema(
                            id=db_p.id,
                            name=db_p.name,
                            font_family=db_p.font_family,
                            font_size=db_p.font_size,
                            primary_color=db_p.primary_color,
                            highlight_color=db_p.highlight_color,
                            outline_color=db_p.outline_color,
                            outline_width=db_p.outline_width,
                            shadow_width=db_p.shadow_width,
                            bold=db_p.bold,
                            italic=db_p.italic,
                            alignment=db_p.alignment,
                            margin_v=db_p.margin_v,
                            margin_l=db_p.margin_l,
                            margin_r=db_p.margin_r,
                            max_words_per_line=db_p.max_words_per_line,
                            max_lines=db_p.max_lines,
                            bg_color=db_p.bg_color,
                            bg_padding=db_p.bg_padding,
                            animation_style=db_p.animation_style,
                            is_default=db_p.is_default,
                        )

                if not preset_schema:
                    preset_schema = DEFAULT_PRESETS[1]  # Bold Creator default

                subtitle_snapshot = preset_schema.model_dump()

                # Generate ASS file in temp
                parsed_segments = [SubtitleSegment(**s) for s in track.segments]
                temp_ass_file = Path(tempfile.gettempdir()) / f"clipforge_sub_{clip.id}_{uuid.uuid4().hex[:6]}.ass"
                SubtitleRenderer.write_ass_file(
                    segments=parsed_segments,
                    preset=preset_schema,
                    output_file_path=str(temp_ass_file),
                    canvas_width=tw,
                    canvas_height=th,
                )
                temp_ass_path = str(temp_ass_file)

                # Append ASS filter to video filter chain
                clean_ass_path = format_ffmpeg_ass_path(temp_ass_path)
                vf_full = f"{vf_base},ass=filename='{clean_ass_path}'"
            else:
                vf_full = vf_base
        else:
            vf_full = vf_base

        # 6. Encoder Configuration & Hardware Capability Check
        caps = CapabilityDetector.detect()
        video_encoder = request.codec or caps.recommended_video_encoder

        if video_encoder == "h264_nvenc" and caps.nvenc_functional:
            enc_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-b:v", f"{request.bitrate_kbps}k"]
        else:
            video_encoder = "libx264"
            enc_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

        # 7. Construct FFmpeg command arguments
        args = [
            "-y",
            "-ss", f"{start_time:.3f}",
            "-i", str(source_video_path),
            "-t", f"{clip_duration:.3f}",
            "-vf", vf_full,
            *enc_args,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-movflags", "+faststart",
            str(final_output_path),
        ]

        logger.info(f"Starting Final Render for Clip {clip_id}: {res_str} via {video_encoder} -> {final_output_path.name}")

        async def ffmpeg_progress(p: FFmpegProgress):
            if is_cancelled and is_cancelled():
                raise asyncio.CancelledError()
            pct = 10 + int(p.progress_percent * 0.85)
            if on_progress:
                await on_progress(min(95, pct), f"Encoding {res_str} ({p.progress_percent}%)")

        try:
            res = await FFmpegManager.run(
                args=args,
                process_id=job_id or f"render_{clip_id}",
                total_duration=clip_duration,
                on_progress=ffmpeg_progress,
                output_file_to_verify=str(final_output_path),
            )

            if not res.success:
                # If GPU encoding failed, fallback to CPU libx264
                if video_encoder != "libx264":
                    logger.warning("GPU render failed, falling back to CPU libx264...")
                    video_encoder = "libx264"
                    fallback_args = [
                        "-y",
                        "-ss", f"{start_time:.3f}",
                        "-i", str(source_video_path),
                        "-t", f"{clip_duration:.3f}",
                        "-vf", vf_full,
                        "-c:v", "libx264",
                        "-preset", "ultrafast",
                        "-crf", "22",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-ar", "44100",
                        "-ac", "2",
                        "-movflags", "+faststart",
                        str(final_output_path),
                    ]
                    res = await FFmpegManager.run(
                        args=fallback_args,
                        process_id=job_id or f"render_{clip_id}",
                        total_duration=clip_duration,
                        on_progress=ffmpeg_progress,
                        output_file_to_verify=str(final_output_path),
                    )

            if not res.success or not final_output_path.exists():
                raise RuntimeError(f"FFmpeg render failed: {res.stderr[-300:] if res.stderr else 'Unknown error'}")

            # 8. Probe & Validate Final Render with FFprobe
            probe_meta = FFprobeManager.probe(str(final_output_path))
            if not probe_meta.valid or not probe_meta.video_stream:
                raise RuntimeError("Rendered output file failed FFprobe validation")

            file_size = final_output_path.stat().st_size
            rendered_duration = probe_meta.duration_seconds

            # 9. Persist Export Record
            export_record = Export(
                clip_id=clip.id,
                preset_id=request.preset_id,
                output_path=str(final_output_path),
                resolution=f"{probe_meta.video_stream.width}x{probe_meta.video_stream.height}",
                fps=probe_meta.video_stream.fps,
                bitrate_kbps=request.bitrate_kbps,
                codec=video_encoder,
                file_size_bytes=file_size,
                duration_seconds=round(rendered_duration, 2),
                burn_subtitles=request.burn_subtitles,
                subtitle_settings=subtitle_snapshot,
                status="completed",
                error_message=None,
                created_at=datetime.utcnow(),
            )
            db.add(export_record)

            # Update Clip status
            clip.status = "exported"
            clip.file_path = str(final_output_path)
            await db.commit()
            await db.refresh(export_record)

            if on_progress:
                await on_progress(100, f"Render completed ({file_size // 1024} KB)")

            return export_record

        except asyncio.CancelledError:
            logger.warning(f"Render job cancelled for clip {clip_id}. Cleaning up partial files...")
            if final_output_path.exists():
                try:
                    os.remove(final_output_path)
                except Exception:
                    pass
            raise

        except Exception as e:
            logger.error(f"Render job failed for clip {clip_id}: {e}")
            if final_output_path.exists():
                try:
                    os.remove(final_output_path)
                except Exception:
                    pass
            raise

        finally:
            # Clean up temp ASS file
            if temp_ass_path and os.path.exists(temp_ass_path):
                try:
                    os.remove(temp_ass_path)
                except Exception:
                    pass
