import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ffmpeg_manager import FFmpegManager
from .ffprobe_manager import FFprobeManager

logger = logging.getLogger("clipforge.video.thumbnails")

class ThumbnailGenerator:
    @classmethod
    async def generate_poster_thumbnail(
        cls,
        video_path: str,
        output_path: str,
        timestamp_seconds: Optional[float] = None,
        width: int = 640
    ) -> str:
        """
        Extract a single high-quality poster thumbnail from video,
        avoiding initial black frame by default.
        """
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if timestamp_seconds is None:
            # Probe duration
            meta = FFprobeManager.probe(video_path)
            dur = meta.duration_seconds if meta.valid else 10.0
            # Target ~10% into video or at least 1.0s
            timestamp_seconds = min(dur * 0.1, 5.0) if dur > 2.0 else 0.5

        # Fast seek before input, then single frame extraction
        args = [
            "-ss", f"{timestamp_seconds:.3f}",
            "-i", str(Path(video_path).resolve()),
            "-vframes", "1",
            "-vf", f"scale={width}:-1:force_original_aspect_ratio=decrease",
            "-q:v", "2",
            str(out_p.resolve())
        ]

        res = await FFmpegManager.run(
            args=args,
            output_file_to_verify=str(out_p.resolve())
        )

        if not res.success:
            # Fallback seek without fast seek if needed
            fallback_args = [
                "-i", str(Path(video_path).resolve()),
                "-ss", f"{timestamp_seconds:.3f}",
                "-vframes", "1",
                "-vf", f"scale={width}:-1:force_original_aspect_ratio=decrease",
                "-q:v", "3",
                str(out_p.resolve())
            ]
            res = await FFmpegManager.run(
                args=fallback_args,
                output_file_to_verify=str(out_p.resolve())
            )
            if not res.success:
                raise RuntimeError(f"Failed to extract poster thumbnail: {res.error_message}")

        return str(out_p.resolve())

    @classmethod
    async def generate_thumbnail_strip(
        cls,
        video_path: str,
        output_dir: str,
        num_thumbnails: int = 10,
        thumb_width: int = 320
    ) -> List[Dict[str, Any]]:
        """
        Generate evenly-spaced timeline strip thumbnails across video duration.
        """
        out_dir_path = Path(output_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)

        meta = FFprobeManager.probe(video_path)
        if not meta.valid or meta.duration_seconds <= 0.1:
            raise ValueError(f"Cannot generate strip: invalid video or duration ({meta.error})")

        duration = meta.duration_seconds
        step = duration / (num_thumbnails + 1)
        timestamps = [step * (i + 1) for i in range(num_thumbnails)]

        results: List[Dict[str, Any]] = []

        for idx, ts in enumerate(timestamps):
            out_file = out_dir_path / f"thumb_{idx:03d}_{int(ts*1000)}ms.jpg"
            args = [
                "-ss", f"{ts:.3f}",
                "-i", str(Path(video_path).resolve()),
                "-vframes", "1",
                "-vf", f"scale={thumb_width}:-1:force_original_aspect_ratio=decrease",
                "-q:v", "4",
                str(out_file.resolve())
            ]

            res = await FFmpegManager.run(
                args=args,
                output_file_to_verify=str(out_file.resolve())
            )

            if res.success:
                results.append({
                    "index": idx,
                    "timestamp": round(ts, 3),
                    "file_path": str(out_file.resolve()),
                    "filename": out_file.name
                })
            else:
                logger.warning(f"Failed to generate thumbnail at {ts:.2f}s: {res.error_message}")

        return results
