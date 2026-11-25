import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

from ..core.config import settings

logger = logging.getLogger("clipforge.video.capabilities")

class VideoCapabilities(BaseModel):
    ffmpeg_available: bool = False
    ffprobe_available: bool = False
    ffmpeg_path: str = ""
    ffprobe_path: str = ""
    ffmpeg_version: str = "Unknown"
    ffprobe_version: str = "Unknown"
    h264_nvenc_available: bool = False
    hevc_nvenc_available: bool = False
    libx264_available: bool = False
    libx265_available: bool = False
    nvenc_functional: bool = False
    libx264_functional: bool = False
    libass_available: bool = False
    subtitle_filter_available: bool = False
    supported_audio_encoders: List[str] = []
    recommended_video_encoder: str = "libx264"
    diagnostic_notes: List[str] = []

_cached_capabilities: Optional[VideoCapabilities] = None

class CapabilityDetector:
    @classmethod
    def detect(cls, force_refresh: bool = False) -> VideoCapabilities:
        global _cached_capabilities
        if _cached_capabilities is not None and not force_refresh:
            return _cached_capabilities

        caps = VideoCapabilities()
        ffmpeg_bin = settings.get_ffmpeg_binary()
        ffprobe_bin = settings.get_ffprobe_binary()

        # 1. Check binaries
        if ffmpeg_bin and os.path.isfile(ffmpeg_bin):
            caps.ffmpeg_available = True
            caps.ffmpeg_path = str(Path(ffmpeg_bin).resolve())
        else:
            caps.diagnostic_notes.append(f"FFmpeg binary not found at: {ffmpeg_bin}")

        if ffprobe_bin and os.path.isfile(ffprobe_bin):
            caps.ffprobe_available = True
            caps.ffprobe_path = str(Path(ffprobe_bin).resolve())
        else:
            caps.diagnostic_notes.append(f"FFprobe binary not found at: {ffprobe_bin}")

        if not caps.ffmpeg_available:
            _cached_capabilities = caps
            return caps

        # 2. Check version
        try:
            p = subprocess.run([caps.ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)
            if p.returncode == 0 and p.stdout:
                first_line = p.stdout.splitlines()[0]
                caps.ffmpeg_version = first_line.strip()
        except Exception as e:
            caps.diagnostic_notes.append(f"Failed to query FFmpeg version: {e}")

        if caps.ffprobe_available:
            try:
                p = subprocess.run([caps.ffprobe_path, "-version"], capture_output=True, text=True, timeout=5)
                if p.returncode == 0 and p.stdout:
                    first_line = p.stdout.splitlines()[0]
                    caps.ffprobe_version = first_line.strip()
            except Exception as e:
                caps.diagnostic_notes.append(f"Failed to query FFprobe version: {e}")

        # 3. Check encoders
        try:
            p = subprocess.run([caps.ffmpeg_path, "-encoders"], capture_output=True, text=True, timeout=5)
            stdout = p.stdout or ""
            caps.h264_nvenc_available = "h264_nvenc" in stdout
            caps.hevc_nvenc_available = "hevc_nvenc" in stdout
            caps.libx264_available = "libx264" in stdout
            caps.libx265_available = "libx265" in stdout

            audio_candidates = ["aac", "libmp3lame", "pcm_s16le", "libopus", "flac"]
            for a_cand in audio_candidates:
                if a_cand in stdout:
                    caps.supported_audio_encoders.append(a_cand)
        except Exception as e:
            caps.diagnostic_notes.append(f"Failed to query FFmpeg encoders: {e}")

        # 4. Check filters (libass / subtitles)
        try:
            p = subprocess.run([caps.ffmpeg_path, "-filters"], capture_output=True, text=True, timeout=5)
            stdout = p.stdout or ""
            caps.libass_available = " ass " in stdout or "\tass " in stdout or " ass\n" in stdout
            caps.subtitle_filter_available = "subtitles" in stdout
        except Exception as e:
            caps.diagnostic_notes.append(f"Failed to query FFmpeg filters: {e}")

        # 5. Actively test libx264 CPU encoder
        if caps.libx264_available:
            try:
                test_cmd = [
                    caps.ffmpeg_path, "-y",
                    "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=15",
                    "-pix_fmt", "yuv420p",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-f", "null", "NUL" if os.name == "nt" else "/dev/null"
                ]
                res = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    caps.libx264_functional = True
                else:
                    caps.diagnostic_notes.append(f"libx264 test failed: {res.stderr[-200:].strip()}")
            except Exception as e:
                caps.diagnostic_notes.append(f"libx264 test exception: {e}")

        # 6. Actively test h264_nvenc GPU encoder
        if caps.h264_nvenc_available:
            try:
                test_cmd = [
                    caps.ffmpeg_path, "-y",
                    "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=15",
                    "-pix_fmt", "yuv420p",
                    "-c:v", "h264_nvenc",
                    "-f", "null", "NUL" if os.name == "nt" else "/dev/null"
                ]
                res = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    caps.nvenc_functional = True
                    caps.recommended_video_encoder = "h264_nvenc"
                else:
                    err_lines = [l.strip() for l in res.stderr.splitlines() if "nvenc" in l.lower() or "driver" in l.lower()]
                    err_msg = "; ".join(err_lines) if err_lines else res.stderr[-200:].strip()
                    caps.nvenc_functional = False
                    caps.diagnostic_notes.append(f"NVENC not functional on current driver: {err_msg}")
                    caps.recommended_video_encoder = "libx264"
            except Exception as e:
                caps.nvenc_functional = False
                caps.diagnostic_notes.append(f"NVENC test exception: {e}")
                caps.recommended_video_encoder = "libx264"
        else:
            caps.recommended_video_encoder = "libx264"

        _cached_capabilities = caps
        logger.info(
            f"Video capabilities detected: ffmpeg={caps.ffmpeg_available}, "
            f"nvenc={caps.nvenc_functional}, libx264={caps.libx264_functional}, "
            f"recommended={caps.recommended_video_encoder}"
        )
        return caps
