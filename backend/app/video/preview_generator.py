import asyncio
import logging
import os
from pathlib import Path
from typing import Callable, Coroutine, Optional

from .capabilities import CapabilityDetector
from .ffmpeg_manager import FFmpegManager, FFmpegProgress
from .ffprobe_manager import FFprobeManager

logger = logging.getLogger("clipforge.video.preview")

class PreviewGenerator:
    @classmethod
    async def generate_preview(
        cls,
        source_path: str,
        output_preview_path: str,
        max_height: int = 720,
        on_progress: Optional[Callable[[FFmpegProgress], Coroutine[None, None, None]]] = None,
        process_id: Optional[str] = None
    ) -> str:
        """
        Generate an optimized 720p H.264 faststart MP4 preview for smooth
        streaming and seeking in Electron and React.
        """
        in_p = Path(source_path).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Source video not found: {source_path}")

        out_p = Path(output_preview_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        meta = FFprobeManager.probe(str(in_p))
        if not meta.valid or not meta.has_video:
            raise ValueError(f"Invalid video source for preview: {meta.error}")

        total_duration = meta.duration_seconds
        caps = CapabilityDetector.detect()

        # Decide encoder
        video_encoder = caps.recommended_video_encoder
        encoder_args: list[str] = []

        if video_encoder == "h264_nvenc" and caps.nvenc_functional:
            encoder_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "2500k"]
        else:
            encoder_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]

        # Ensure dimensions are even and height <= max_height
        scale_filter = f"scale=-2:'min({max_height},ih)':flags=bicubic"

        args = [
            "-i", str(in_p),
            "-vf", scale_filter,
            *encoder_args,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-ac", "2",
            "-movflags", "+faststart",
            str(out_p)
        ]

        logger.info(f"Generating preview MP4 for {in_p.name} using {video_encoder}...")
        res = await FFmpegManager.run(
            args=args,
            process_id=process_id,
            total_duration=total_duration,
            on_progress=on_progress,
            output_file_to_verify=str(out_p)
        )

        if not res.success:
            # Fallback to pure CPU libx264 if nvenc failed mid-stream
            if video_encoder != "libx264":
                logger.warning("GPU preview generation failed; retrying with CPU libx264 fallback...")
                args_fallback = [
                    "-i", str(in_p),
                    "-vf", scale_filter,
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "24",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-ar", "44100",
                    "-ac", "2",
                    "-movflags", "+faststart",
                    str(out_p)
                ]
                res = await FFmpegManager.run(
                    args=args_fallback,
                    process_id=process_id,
                    total_duration=total_duration,
                    on_progress=on_progress,
                    output_file_to_verify=str(out_p)
                )

        if not res.success:
            raise RuntimeError(f"Preview generation failed: {res.error_message}")

        logger.info(f"Preview successfully generated: {out_p.name} ({out_p.stat().st_size} bytes)")
        return str(out_p)
