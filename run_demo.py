"""
Quick test script to verify that FFmpeg, cropping, and subtitle generation work end-to-end.
"""
import os
import sys
import subprocess
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.config import settings
from app.services.video_processor import VideoProcessor
from app.services.subtitles import SubtitleGenerator
from app.models.schemas import TranscriptSegment, WordTimestamp

def create_synthetic_test_video(output_mp4: str, duration: int = 20):
    """Generate a clean synthetic 16:9 test video using FFmpeg testsrc and sine audio."""
    ffmpeg_bin = settings.get_ffmpeg_executable()
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_mp4
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"Generated synthetic test video: {output_mp4}")

def main():
    print("Testing ClipsMaster Engine...")
    print(f"FFmpeg Path: {settings.get_ffmpeg_executable()}")
    
    test_dir = settings.TEMP_DIR / "demo_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    source_video = str(test_dir / "sample_source.mp4")
    create_synthetic_test_video(source_video, duration=15)
    
    # Create sample segments
    sample_segments = [
        TranscriptSegment(
            id=0,
            start=1.0,
            end=7.0,
            text="THE SECRET TO VIRAL SHORTS IS HOOK RETENTION",
            words=[
                WordTimestamp(word="THE", start=1.0, end=1.5),
                WordTimestamp(word="SECRET", start=1.5, end=2.2),
                WordTimestamp(word="TO", start=2.2, end=2.5),
                WordTimestamp(word="VIRAL", start=2.5, end=3.2),
                WordTimestamp(word="SHORTS", start=3.2, end=4.0),
                WordTimestamp(word="IS", start=4.0, end=4.3),
                WordTimestamp(word="HOOK", start=4.3, end=5.2),
                WordTimestamp(word="RETENTION", start=5.2, end=6.5),
            ]
        ),
        TranscriptSegment(
            id=1,
            start=7.0,
            end=13.0,
            text="ANIMATED KARAOKE SUBTITLES DOUBLE WATCH TIME",
            words=[
                WordTimestamp(word="ANIMATED", start=7.0, end=7.8),
                WordTimestamp(word="KARAOKE", start=7.8, end=8.7),
                WordTimestamp(word="SUBTITLES", start=8.7, end=9.8),
                WordTimestamp(word="DOUBLE", start=9.8, end=10.6),
                WordTimestamp(word="WATCH", start=10.6, end=11.4),
                WordTimestamp(word="TIME", start=11.4, end=12.5),
            ]
        )
    ]
    
    # 1. Generate Subtitles
    ass_path = str(test_dir / "sample_subs.ass")
    SubtitleGenerator.generate_ass(
        segments=sample_segments,
        clip_start=0.0,
        clip_end=14.0,
        output_file=ass_path,
        style_preset="karaoke_yellow"
    )
    print(f"Generated ASS subtitles: {ass_path}")
    
    # 2. Render 9:16 clip with face crop / center crop
    output_clip = str(settings.OUTPUT_DIR / "demo_output_clip.mp4")
    thumb_clip = str(settings.OUTPUT_DIR / "demo_output_thumb.jpg")
    
    VideoProcessor.render_clip(
        source_video=source_video,
        start_time=0.0,
        end_time=13.0,
        output_path=output_clip,
        crop_box=None, # auto 9:16 center crop
        ass_subtitle_path=ass_path,
        target_resolution=(1080, 1920),
        normalize_audio=False
    )
    print(f"Rendered vertical clip: {output_clip}")
    
    VideoProcessor.generate_thumbnail(output_clip, thumb_clip, timestamp=2.0)
    print(f"Generated thumbnail: {thumb_clip}")
    print("DEMO TEST COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
