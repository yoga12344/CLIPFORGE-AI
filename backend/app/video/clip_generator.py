import asyncio
import logging
import os
from pathlib import Path
from typing import Callable, Coroutine, Optional

from .aspect_ratio import AspectRatioProcessor
from .capabilities import CapabilityDetector
from .ffmpeg_manager import FFmpegManager, FFmpegProgress
from .ffprobe_manager import FFprobeManager

logger = logging.getLogger("clipforge.video.clips")

class ClipGenerator:
    @classmethod
    async def generate_clip(
        cls,
        source_video_path: str,
        output_clip_path: str,
        start_time: float,
        end_time: float,
        aspect_ratio: str = "9:16",
        reframe_mode: str = "center_crop",
        trajectory: Optional[list] = None,
        crop_box: Optional[tuple] = None,
        subtitle_path: Optional[str] = None,
        on_progress: Optional[Callable[[FFmpegProgress], Coroutine[None, None, None]]] = None,
        process_id: Optional[str] = None
    ) -> str:
        """
        Generate a frame-accurate short clip with aspect ratio reframing.
        Supports static crop, dynamic camera tracking trajectory, or preset filtergraphs.
        Optionally burns in ASS subtitles.
        """
        in_p = Path(source_video_path).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Source video not found: {source_video_path}")

        out_p = Path(output_clip_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if start_time < 0:
            start_time = 0.0
        if end_time <= start_time:
            raise ValueError(f"Invalid clip boundaries: start={start_time}, end={end_time}")

        clip_duration = end_time - start_time
        caps = CapabilityDetector.detect()

        # Build filtergraph for reframing
        if trajectory and len(trajectory) > 0:
            # Trajectory reframing
            first_c = trajectory[0]
            cw = getattr(first_c, "pixel_width", 0) if hasattr(first_c, "pixel_width") else first_c.get("pixel_width", 0)
            ch = getattr(first_c, "pixel_height", 0) if hasattr(first_c, "pixel_height") else first_c.get("pixel_height", 0)

            # If pixel dimensions are not set, derive from normalized coordinates or source dimensions
            if not cw or not ch:
                source_meta = FFprobeManager.probe(str(in_p))
                sw = source_meta.video_stream.width if source_meta.video_stream else 1920
                sh = source_meta.video_stream.height if source_meta.video_stream else 1080

                norm_w = getattr(first_c, "crop_width", 0.0) if hasattr(first_c, "crop_width") else first_c.get("crop_width", 0.0)
                norm_h = getattr(first_c, "crop_height", 0.0) if hasattr(first_c, "crop_height") else first_c.get("crop_height", 0.0)

                if norm_w > 0 and norm_h > 0:
                    cw = int(norm_w * sw)
                    ch = int(norm_h * sh)
                else:
                    tw, th = AspectRatioProcessor.get_target_dimensions(aspect_ratio)
                    ch = sh
                    cw = int(sh * (tw / th))

                cw = max(2, (cw // 2) * 2)
                ch = max(2, (ch // 2) * 2)

                # Ensure pixel_x and pixel_y exist for trajectory interpolation
                for pt in trajectory:
                    nx = getattr(pt, "crop_x", 0.0) if hasattr(pt, "crop_x") else pt.get("crop_x", 0.0)
                    ny = getattr(pt, "crop_y", 0.0) if hasattr(pt, "crop_y") else pt.get("crop_y", 0.0)
                    px = getattr(pt, "pixel_x", 0) if hasattr(pt, "pixel_x") else pt.get("pixel_x", 0)
                    py = getattr(pt, "pixel_y", 0) if hasattr(pt, "pixel_y") else pt.get("pixel_y", 0)

                    if not px:
                        calc_x = int(nx * sw)
                        if hasattr(pt, "pixel_x"):
                            pt.pixel_x = calc_x
                        elif isinstance(pt, dict):
                            pt["pixel_x"] = calc_x
                    if not py:
                        calc_y = int(ny * sh)
                        if hasattr(pt, "pixel_y"):
                            pt.pixel_y = calc_y
                        elif isinstance(pt, dict):
                            pt["pixel_y"] = calc_y

            vf_filter = AspectRatioProcessor.build_trajectory_filtergraph(
                crop_w=cw,
                crop_h=ch,
                trajectory=trajectory,
                aspect_ratio=aspect_ratio,
            )
        elif crop_box and len(crop_box) == 4:
            cw, ch, cx, cy = crop_box
            vf_filter = AspectRatioProcessor.build_smart_crop_filtergraph(
                crop_w=cw,
                crop_h=ch,
                crop_x=cx,
                crop_y=cy,
                aspect_ratio=aspect_ratio,
            )
        else:
            vf_filter = AspectRatioProcessor.build_filtergraph(
                aspect_ratio=aspect_ratio,
                mode=reframe_mode,
            )

        if subtitle_path and os.path.exists(subtitle_path):
            from ..services.subtitle_renderer import format_ffmpeg_ass_path
            clean_sub = format_ffmpeg_ass_path(subtitle_path)
            vf_filter = f"{vf_filter},ass=filename='{clean_sub}'"

        # Encoder selection
        video_encoder = caps.recommended_video_encoder
        if video_encoder == "h264_nvenc" and caps.nvenc_functional:
            enc_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "4000k"]
        else:
            enc_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

        # Accurate seek: put -ss before -i for fast seek, but specify -t for exact slice
        # When precision is paramount, seeking 1-2 seconds early and trimming in filter or using exact seek
        args = [
            "-ss", f"{start_time:.3f}",
            "-i", str(in_p),
            "-t", f"{clip_duration:.3f}",
            "-vf", vf_filter,
            *enc_args,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-movflags", "+faststart",
            str(out_p)
        ]

        logger.info(
            f"Generating clip [{start_time:.2f}s - {end_time:.2f}s, ratio={aspect_ratio}, "
            f"mode={reframe_mode}] -> {out_p.name}..."
        )

        res = await FFmpegManager.run(
            args=args,
            process_id=process_id,
            total_duration=clip_duration,
            on_progress=on_progress,
            output_file_to_verify=str(out_p)
        )

        if not res.success:
            # Fallback to libx264 CPU if GPU failed
            if video_encoder != "libx264":
                logger.warning("GPU clip encoding failed; falling back to CPU libx264...")
                fallback_args = [
                    "-ss", f"{start_time:.3f}",
                    "-i", str(in_p),
                    "-t", f"{clip_duration:.3f}",
                    "-vf", vf_filter,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "22",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ar", "44100",
                    "-ac", "2",
                    "-movflags", "+faststart",
                    str(out_p)
                ]
                res = await FFmpegManager.run(
                    args=fallback_args,
                    process_id=process_id,
                    total_duration=clip_duration,
                    on_progress=on_progress,
                    output_file_to_verify=str(out_p)
                )

        if not res.success:
            raise RuntimeError(f"Clip generation failed: {res.error_message}")

        # Verify output clip with FFprobe
        clip_meta = FFprobeManager.probe(str(out_p))
        if not clip_meta.valid or not clip_meta.has_video:
            raise RuntimeError("Generated clip is corrupt or unreadable.")

        # Check duration is reasonable (within 0.75s of requested)
        if abs(clip_meta.duration_seconds - clip_duration) > 1.5:
            logger.warning(
                f"Generated clip duration ({clip_meta.duration_seconds:.2f}s) differs from "
                f"requested ({clip_duration:.2f}s)"
            )

        logger.info(
            f"Clip generated successfully: {out_p.name} ({out_p.stat().st_size} bytes, "
            f"{clip_meta.duration_seconds:.2f}s, {clip_meta.video_stream.width}x{clip_meta.video_stream.height})"
        )
        return str(out_p)
