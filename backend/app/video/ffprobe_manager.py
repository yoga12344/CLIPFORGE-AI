import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from .capabilities import CapabilityDetector

logger = logging.getLogger("clipforge.video.ffprobe")

class AudioStreamInfo(BaseModel):
    codec_name: str
    sample_rate: int = 44100
    channels: int = 2
    channel_layout: Optional[str] = None
    bit_rate: Optional[int] = None
    duration_seconds: Optional[float] = None

class VideoStreamInfo(BaseModel):
    codec_name: str
    profile: Optional[str] = None
    width: int
    height: int
    fps: float = 30.0
    aspect_ratio: str = "16:9"
    pix_fmt: Optional[str] = None
    color_space: Optional[str] = None
    rotation: int = 0
    duration_seconds: Optional[float] = None
    nb_frames: Optional[int] = None

class SubtitleStreamInfo(BaseModel):
    index: int
    codec_name: str
    language: Optional[str] = None
    title: Optional[str] = None

class DetailedVideoMetadata(BaseModel):
    valid: bool
    error: Optional[str] = None
    file_path: str
    filename: str
    file_size_bytes: int = 0
    format_name: str = ""
    duration_seconds: float = 0.0
    bit_rate: int = 0
    video_stream: Optional[VideoStreamInfo] = None
    audio_stream: Optional[AudioStreamInfo] = None
    subtitles: List[SubtitleStreamInfo] = []
    has_video: bool = False
    has_audio: bool = False
    tags: Dict[str, Any] = {}

class FFprobeManager:
    @classmethod
    def probe(cls, file_path: str) -> DetailedVideoMetadata:
        """Extract deep technical metadata from video using FFprobe."""
        path_obj = Path(file_path).resolve()
        
        if not path_obj.exists() or not path_obj.is_file():
            return DetailedVideoMetadata(
                valid=False,
                error=f"File does not exist: {file_path}",
                file_path=str(path_obj),
                filename=path_obj.name,
                file_size_bytes=0
            )

        file_size = path_obj.stat().st_size
        if file_size == 0:
            return DetailedVideoMetadata(
                valid=False,
                error="Video file is empty (0 bytes).",
                file_path=str(path_obj),
                filename=path_obj.name,
                file_size_bytes=0
            )

        caps = CapabilityDetector.detect()
        if not caps.ffprobe_available:
            return DetailedVideoMetadata(
                valid=False,
                error="FFprobe binary is not available on this system.",
                file_path=str(path_obj),
                filename=path_obj.name,
                file_size_bytes=file_size
            )

        cmd = [
            caps.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path_obj)
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return DetailedVideoMetadata(
                    valid=False,
                    error=f"FFprobe inspection failed (exit code {res.returncode}): {res.stderr.strip()}",
                    file_path=str(path_obj),
                    filename=path_obj.name,
                    file_size_bytes=file_size
                )
            
            data = json.loads(res.stdout)
        except subprocess.TimeoutExpired:
            return DetailedVideoMetadata(
                valid=False,
                error="FFprobe inspection timed out after 15 seconds.",
                file_path=str(path_obj),
                filename=path_obj.name,
                file_size_bytes=file_size
            )
        except Exception as e:
            return DetailedVideoMetadata(
                valid=False,
                error=f"Failed to inspect media file: {str(e)}",
                file_path=str(path_obj),
                filename=path_obj.name,
                file_size_bytes=file_size
            )

        format_info = data.get("format", {})
        streams = data.get("streams", [])

        try:
            duration = float(format_info.get("duration", 0.0))
        except (ValueError, TypeError):
            duration = 0.0

        try:
            bit_rate = int(format_info.get("bit_rate", 0))
        except (ValueError, TypeError):
            bit_rate = 0

        format_name = format_info.get("format_name", "")
        tags = format_info.get("tags", {})

        video_info: Optional[VideoStreamInfo] = None
        audio_info: Optional[AudioStreamInfo] = None
        subtitles: List[SubtitleStreamInfo] = []

        for stream in streams:
            codec_type = stream.get("codec_type")

            if codec_type == "video" and video_info is None:
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))

                # Parse frame rate
                fps = 30.0
                r_frame_rate = stream.get("r_frame_rate", "30/1")
                try:
                    num, den = r_frame_rate.split("/")
                    if float(den) > 0:
                        fps = round(float(num) / float(den), 2)
                except Exception:
                    pass

                # Parse aspect ratio
                dar = stream.get("display_aspect_ratio")
                if not dar and width > 0 and height > 0:
                    dar = f"{width}:{height}"

                # Parse rotation from stream tags or side data
                rotation = 0
                st_tags = stream.get("tags", {})
                if "rotate" in st_tags:
                    try:
                        rotation = int(st_tags["rotate"])
                    except ValueError:
                        pass
                
                for side_data in stream.get("side_data_list", []):
                    if "rotation" in side_data:
                        try:
                            rotation = int(side_data["rotation"])
                        except ValueError:
                            pass

                stream_duration = None
                try:
                    if "duration" in stream:
                        stream_duration = float(stream["duration"])
                except Exception:
                    pass

                nb_frames = None
                try:
                    if "nb_frames" in stream:
                        nb_frames = int(stream["nb_frames"])
                except Exception:
                    pass

                video_info = VideoStreamInfo(
                    codec_name=stream.get("codec_name", "unknown"),
                    profile=stream.get("profile"),
                    width=width,
                    height=height,
                    fps=fps,
                    aspect_ratio=dar or "16:9",
                    pix_fmt=stream.get("pix_fmt"),
                    color_space=stream.get("color_space"),
                    rotation=rotation,
                    duration_seconds=stream_duration or duration,
                    nb_frames=nb_frames
                )

            elif codec_type == "audio" and audio_info is None:
                sample_rate = 44100
                try:
                    sample_rate = int(stream.get("sample_rate", 44100))
                except Exception:
                    pass

                channels = 2
                try:
                    channels = int(stream.get("channels", 2))
                except Exception:
                    pass

                audio_bitrate = None
                try:
                    if "bit_rate" in stream:
                        audio_bitrate = int(stream["bit_rate"])
                except Exception:
                    pass

                a_dur = None
                try:
                    if "duration" in stream:
                        a_dur = float(stream["duration"])
                except Exception:
                    pass

                audio_info = AudioStreamInfo(
                    codec_name=stream.get("codec_name", "unknown"),
                    sample_rate=sample_rate,
                    channels=channels,
                    channel_layout=stream.get("channel_layout"),
                    bit_rate=audio_bitrate,
                    duration_seconds=a_dur
                )

            elif codec_type == "subtitle":
                st_tags = stream.get("tags", {})
                subtitles.append(SubtitleStreamInfo(
                    index=int(stream.get("index", 0)),
                    codec_name=stream.get("codec_name", "unknown"),
                    language=st_tags.get("language"),
                    title=st_tags.get("title")
                ))

        if not video_info and not audio_info:
            return DetailedVideoMetadata(
                valid=False,
                error="No valid video or audio stream found in media file.",
                file_path=str(path_obj),
                filename=path_obj.name,
                file_size_bytes=file_size
            )

        return DetailedVideoMetadata(
            valid=True,
            file_path=str(path_obj),
            filename=path_obj.name,
            file_size_bytes=file_size,
            format_name=format_name,
            duration_seconds=duration or (video_info.duration_seconds if video_info else 0.0),
            bit_rate=bit_rate,
            video_stream=video_info,
            audio_stream=audio_info,
            subtitles=subtitles,
            has_video=video_info is not None,
            has_audio=audio_info is not None,
            tags=tags
        )
