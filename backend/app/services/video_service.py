import os
import shutil
import subprocess
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.config import settings
from ..db.models import Video, Project
from ..schemas.api_schemas import VideoProbeResponse

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

class VideoService:
    @staticmethod
    def probe_video(file_path: str) -> VideoProbeResponse:
        """Inspect video file metadata using FFprobe without loading the file into memory."""
        path_obj = Path(file_path)

        if not path_obj.exists() or not path_obj.is_file():
            return VideoProbeResponse(
                valid=False,
                error=f"File not found: {file_path}",
                filename=path_obj.name,
                file_path=file_path,
                file_size_bytes=0
            )

        if path_obj.suffix.lower() not in ALLOWED_EXTENSIONS:
            return VideoProbeResponse(
                valid=False,
                error=f"Unsupported video format: {path_obj.suffix}. Supported: {', '.join(ALLOWED_EXTENSIONS)}",
                filename=path_obj.name,
                file_path=file_path,
                file_size_bytes=path_obj.stat().st_size
            )

        ffprobe_bin = settings.get_ffprobe_binary()
        file_size = path_obj.stat().st_size

        cmd = [
            ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path_obj.resolve())
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
        except Exception as e:
            return VideoProbeResponse(
                valid=False,
                error=f"FFprobe extraction failed: {str(e)}",
                filename=path_obj.name,
                file_path=file_path,
                file_size_bytes=file_size
            )

        format_info = data.get("format", {})
        duration = float(format_info.get("duration", 0.0))
        format_name = format_info.get("format_name", "")

        width = 0
        height = 0
        fps = 30.0
        video_codec = None
        audio_codec = None
        has_audio = False
        audio_channels = 0

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            if codec_type == "video" and not video_codec:
                video_codec = stream.get("codec_name")
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                r_frame_rate = stream.get("r_frame_rate", "30/1")
                try:
                    num, den = r_frame_rate.split("/")
                    if float(den) > 0:
                        fps = round(float(num) / float(den), 2)
                except Exception:
                    fps = 30.0
            elif codec_type == "audio" and not audio_codec:
                has_audio = True
                audio_codec = stream.get("codec_name")
                audio_channels = int(stream.get("channels", 2))

        return VideoProbeResponse(
            valid=True,
            filename=path_obj.name,
            file_path=str(path_obj.resolve()),
            file_size_bytes=file_size,
            format_name=format_name,
            duration_seconds=round(duration, 2),
            width=width,
            height=height,
            fps=fps,
            video_codec=video_codec,
            audio_codec=audio_codec,
            has_audio=has_audio,
            audio_channels=audio_channels
        )

    @staticmethod
    def generate_thumbnail(video_path: str, output_path: str, timestamp_sec: float = 1.0) -> bool:
        """Extract a single representative frame as thumbnail."""
        ffmpeg_bin = settings.get_ffmpeg_binary()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", f"{timestamp_sec:.2f}",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return os.path.exists(output_path)
        except Exception:
            return False

    @staticmethod
    async def import_video(
        db: AsyncSession,
        project_id: str,
        source_file_path: str,
        copy_to_storage: bool = True
    ) -> Video:
        """Import video into project and persist metadata in SQLite."""
        # 1. Check Project exists
        p_res = await db.execute(select(Project).where(Project.id == project_id))
        project = p_res.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project with ID '{project_id}' not found.")

        # 2. Probe metadata
        probe = VideoService.probe_video(source_file_path)
        if not probe.valid:
            raise ValueError(probe.error or "Invalid video file.")

        src_path = Path(source_file_path)
        video_id = str(uuid.uuid4())

        # 3. Storage destination
        if copy_to_storage:
            dest_filename = f"{video_id[:8]}_{src_path.name}"
            dest_path = settings.UPLOADS_DIR / dest_filename
            shutil.copy2(src_path, dest_path)
            stored_file_path = str(dest_path.resolve())
        else:
            stored_file_path = str(src_path.resolve())

        # 4. Generate Thumbnail
        thumb_filename = f"{video_id[:8]}_thumb.jpg"
        thumb_path = settings.THUMBNAILS_DIR / thumb_filename
        VideoService.generate_thumbnail(stored_file_path, str(thumb_path), timestamp_sec=min(2.0, probe.duration_seconds / 2))

        # 5. Persist record in SQLite
        video = Video(
            id=video_id,
            project_id=project_id,
            filename=src_path.name,
            file_path=stored_file_path,
            file_size_bytes=probe.file_size_bytes,
            format=probe.format_name,
            duration_seconds=probe.duration_seconds,
            width=probe.width,
            height=probe.height,
            fps=probe.fps,
            video_codec=probe.video_codec,
            audio_codec=probe.audio_codec,
            has_audio=probe.has_audio,
            audio_channels=probe.audio_channels,
            thumbnail_path=str(thumb_path) if thumb_path.exists() else None
        )

        db.add(video)
        await db.commit()
        await db.refresh(video)
        return video
