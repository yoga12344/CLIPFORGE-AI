import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from ..config import settings

class VideoDownloader:
    @staticmethod
    def probe_video(file_path: str) -> Dict[str, Any]:
        """Use ffprobe or basic file stats to determine video metadata."""
        ffmpeg_bin = settings.get_ffmpeg_executable()
        ffprobe_bin = ffmpeg_bin.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
        
        info = {
            "duration": 0.0,
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "title": Path(file_path).stem
        }
        
        try:
            cmd = [
                ffprobe_bin,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            if "format" in data and "duration" in data["format"]:
                info["duration"] = float(data["format"]["duration"])
            
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    info["width"] = int(stream.get("width", 1920))
                    info["height"] = int(stream.get("height", 1080))
                    if "r_frame_rate" in stream:
                        parts = stream["r_frame_rate"].split('/')
                        if len(parts) == 2 and float(parts[1]) != 0:
                            info["fps"] = float(parts[0]) / float(parts[1])
                    break
        except Exception as e:
            print(f"Warning: ffprobe failed ({e}), using default probe stats.")
            
        return info

    @staticmethod
    async def download_from_url(url: str, output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Download a video using yt-dlp."""
        import yt_dlp

        out_dir = output_dir or settings.UPLOAD_DIR
        out_template = str(out_dir / "%(id)s.%(ext)s")

        ffmpeg_bin = settings.get_ffmpeg_executable()
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": out_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": ffmpeg_bin,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(meta)
            
            # If yt-dlp merges into .mp4
            if not os.path.exists(filename):
                stem = Path(filename).stem
                for f in out_dir.glob(f"{stem}.*"):
                    filename = str(f)
                    break

            probe_info = VideoDownloader.probe_video(filename)
            return {
                "file_path": filename,
                "title": meta.get("title", Path(filename).stem),
                "duration": float(meta.get("duration", probe_info["duration"])),
                "width": probe_info["width"],
                "height": probe_info["height"],
                "fps": probe_info["fps"],
            }

    @staticmethod
    async def save_uploaded_file(file_content: bytes, original_filename: str) -> Dict[str, Any]:
        """Save an uploaded file to the upload directory and probe it."""
        import uuid
        ext = Path(original_filename).suffix or ".mp4"
        file_id = str(uuid.uuid4())[:8]
        dest_filename = f"{file_id}_{original_filename}"
        dest_path = settings.UPLOAD_DIR / dest_filename
        
        with open(dest_path, "wb") as f:
            f.write(file_content)
            
        probe_info = VideoDownloader.probe_video(str(dest_path))
        return {
            "file_path": str(dest_path),
            "title": Path(original_filename).stem,
            "duration": probe_info["duration"],
            "width": probe_info["width"],
            "height": probe_info["height"],
            "fps": probe_info["fps"],
        }
