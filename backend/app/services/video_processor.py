import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from ..config import settings

def escape_ffmpeg_filter_path(file_path: str) -> str:
    """Escape Windows file paths for FFmpeg filter arguments (colons and backslashes)."""
    # Replace backslashes with forward slashes
    p = file_path.replace("\\", "/")
    # Escape colon (e.g., C: -> C\:)
    if len(p) > 1 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p

class VideoProcessor:
    @staticmethod
    def render_clip(
        source_video: str,
        start_time: float,
        end_time: float,
        output_path: str,
        crop_box: Optional[Tuple[int, int, int, int]] = None,
        ass_subtitle_path: Optional[str] = None,
        target_resolution: Tuple[int, int] = (1080, 1920),
        normalize_audio: bool = True
    ) -> str:
        """
        Cut, crop, burn subtitles, normalize audio, and encode to high-quality vertical MP4.
        """
        ffmpeg_bin = settings.get_ffmpeg_executable()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        filter_complex = []

        # 1. Video Cropping & Scaling
        if crop_box:
            x, y, w, h = crop_box
            filter_complex.append(f"crop={w}:{h}:{x}:{y}")
        else:
            # Default center crop to 9:16
            filter_complex.append("crop=ih*9/16:ih")
            
        filter_complex.append(f"scale={target_resolution[0]}:{target_resolution[1]}")

        # 2. Burn Animated Subtitles (libass)
        if ass_subtitle_path and os.path.exists(ass_subtitle_path):
            escaped_sub = escape_ffmpeg_filter_path(ass_subtitle_path)
            filter_complex.append(f"ass='{escaped_sub}'")

        vf_str = ",".join(filter_complex)

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", f"{start_time:.2f}",
            "-to", f"{end_time:.2f}",
            "-i", source_video,
            "-vf", vf_str,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
        ]

        if normalize_audio:
            cmd.extend([
                "-af", "loudnorm=I=-14:LRA=7:tp=-1.5",
                "-c:a", "aac",
                "-b:a", "192k",
            ])
        else:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        cmd.extend([
            "-movflags", "+faststart",
            output_path
        ])

        print(f"Executing FFmpeg render: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            # If libass failed due to font cache or missing library, retry without subtitle filter
            if "ass" in vf_str:
                print("Retrying render without subtitle burn-in...")
                fallback_vf = f"crop=ih*9/16:ih,scale={target_resolution[0]}:{target_resolution[1]}"
                fallback_cmd = [
                    ffmpeg_bin, "-y",
                    "-ss", f"{start_time:.2f}", "-to", f"{end_time:.2f}",
                    "-i", source_video,
                    "-vf", fallback_vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    output_path
                ]
                subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)
            else:
                raise RuntimeError(f"FFmpeg render failed: {result.stderr}")

        return output_path

    @staticmethod
    def generate_thumbnail(video_path: str, output_thumb_path: str, timestamp: float = 1.0) -> str:
        """Extract a single frame as a JPG thumbnail."""
        ffmpeg_bin = settings.get_ffmpeg_executable()
        Path(output_thumb_path).parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", f"{timestamp:.2f}",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_thumb_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        return output_thumb_path
