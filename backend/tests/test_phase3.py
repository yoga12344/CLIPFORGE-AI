import asyncio
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import async_session_factory, init_db
from app.db.models import Project, Video, Clip, Job
from app.video.capabilities import CapabilityDetector
from app.video.ffmpeg_manager import FFmpegManager
from app.video.ffprobe_manager import FFprobeManager
from app.video.thumbnail_generator import ThumbnailGenerator
from app.video.audio_extractor import AudioExtractor
from app.video.preview_generator import PreviewGenerator
from app.video.clip_generator import ClipGenerator
from app.workers.job_manager import JobManager

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()

@pytest.fixture
async def synthetic_video_path():
    """Generate a clean 4-second synthetic test video with audio."""
    temp_dir = tempfile.gettempdir()
    video_path = os.path.join(temp_dir, "clipforge_test_synthetic.mp4")
    
    args = [
        "-f", "lavfi", "-i", "testsrc=duration=4:size=1280x720:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        video_path
    ]
    res = await FFmpegManager.run(args=args, output_file_to_verify=video_path)
    assert res.success, f"Failed to generate synthetic video: {res.error_message}"
    
    yield video_path

    if os.path.exists(video_path):
        try:
            os.remove(video_path)
        except Exception:
            pass

@pytest.mark.asyncio
async def test_video_capabilities():
    """Verify capability detector accurately identifies FFmpeg, filters, and encoders."""
    caps = CapabilityDetector.detect()
    assert caps.ffmpeg_available is True
    assert caps.ffprobe_available is True
    assert caps.libx264_functional is True
    assert caps.libass_available is True
    assert caps.subtitle_filter_available is True
    assert caps.recommended_video_encoder in ("h264_nvenc", "libx264")

@pytest.mark.asyncio
async def test_ffprobe_detailed_metadata(synthetic_video_path):
    """Verify FFprobe extracts correct streams, codecs, and dimensions."""
    meta = FFprobeManager.probe(synthetic_video_path)
    assert meta.valid is True
    assert meta.has_video is True
    assert meta.has_audio is True
    assert meta.duration_seconds >= 3.8
    assert meta.video_stream is not None
    assert meta.video_stream.width == 1280
    assert meta.video_stream.height == 720
    assert meta.video_stream.fps == 25.0
    assert meta.audio_stream is not None
    assert meta.audio_stream.sample_rate == 44100

@pytest.mark.asyncio
async def test_thumbnail_and_strip_generation(synthetic_video_path):
    """Verify poster thumbnail extraction and multi-frame strip generation."""
    temp_dir = tempfile.gettempdir()
    poster_path = os.path.join(temp_dir, "test_poster.jpg")
    strip_dir = os.path.join(temp_dir, "test_strip")

    out_poster = await ThumbnailGenerator.generate_poster_thumbnail(
        video_path=synthetic_video_path,
        output_path=poster_path,
        timestamp_seconds=1.0,
        width=480
    )
    assert os.path.exists(out_poster)
    assert os.path.getsize(out_poster) > 0

    strip = await ThumbnailGenerator.generate_thumbnail_strip(
        video_path=synthetic_video_path,
        output_dir=strip_dir,
        num_thumbnails=3,
        thumb_width=320
    )
    assert len(strip) == 3
    for s in strip:
        assert os.path.exists(s["file_path"])
        assert os.path.getsize(s["file_path"]) > 0

@pytest.mark.asyncio
async def test_audio_extraction_whisper_spec(synthetic_video_path):
    """Verify audio extraction produces 16kHz mono WAV compliant with Whisper."""
    temp_dir = tempfile.gettempdir()
    wav_path = os.path.join(temp_dir, "test_whisper_spec.wav")

    extracted = await AudioExtractor.extract_for_transcription(
        video_path=synthetic_video_path,
        output_wav_path=wav_path
    )
    assert os.path.exists(extracted)

    wav_meta = FFprobeManager.probe(extracted)
    assert wav_meta.valid is True
    assert wav_meta.audio_stream is not None
    assert wav_meta.audio_stream.sample_rate == 16000
    assert wav_meta.audio_stream.channels == 1
    assert wav_meta.audio_stream.codec_name in ("pcm_s16le", "pcm_s16be")

@pytest.mark.asyncio
async def test_preview_generation(synthetic_video_path):
    """Verify preview generator creates playable 720p H.264 faststart MP4."""
    temp_dir = tempfile.gettempdir()
    preview_path = os.path.join(temp_dir, "test_preview_720p.mp4")

    out_prev = await PreviewGenerator.generate_preview(
        source_path=synthetic_video_path,
        output_preview_path=preview_path,
        max_height=720
    )
    assert os.path.exists(out_prev)

    prev_meta = FFprobeManager.probe(out_prev)
    assert prev_meta.valid is True
    assert prev_meta.video_stream is not None
    assert prev_meta.video_stream.height <= 720
    assert prev_meta.video_stream.codec_name == "h264"

@pytest.mark.asyncio
async def test_clip_generation_and_aspect_ratios(synthetic_video_path):
    """Verify clip cutting and 9:16 reframing (center_crop and blur_background)."""
    temp_dir = tempfile.gettempdir()

    # 1. Center crop to 9:16 (1080x1920)
    clip_crop_path = os.path.join(temp_dir, "test_clip_crop.mp4")
    out_crop = await ClipGenerator.generate_clip(
        source_video_path=synthetic_video_path,
        output_clip_path=clip_crop_path,
        start_time=1.0,
        end_time=3.0,
        aspect_ratio="9:16",
        reframe_mode="center_crop"
    )
    assert os.path.exists(out_crop)
    meta_crop = FFprobeManager.probe(out_crop)
    assert meta_crop.video_stream.width == 1080
    assert meta_crop.video_stream.height == 1920
    assert abs(meta_crop.duration_seconds - 2.0) < 1.0

    # 2. Blur background to 9:16 (1080x1920)
    clip_blur_path = os.path.join(temp_dir, "test_clip_blur.mp4")
    out_blur = await ClipGenerator.generate_clip(
        source_video_path=synthetic_video_path,
        output_clip_path=clip_blur_path,
        start_time=0.5,
        end_time=2.5,
        aspect_ratio="9:16",
        reframe_mode="blur_background"
    )
    assert os.path.exists(out_blur)
    meta_blur = FFprobeManager.probe(out_blur)
    assert meta_blur.video_stream.width == 1080
    assert meta_blur.video_stream.height == 1920

@pytest.mark.asyncio
async def test_job_manager_queue_and_execution(synthetic_video_path):
    """Verify background job manager executes queued video processing tasks."""
    jm = JobManager.get_instance()
    await jm.start()

    # Create dummy project and video in DB
    async with async_session_factory() as db:
        proj = Project(name="Test Video Project")
        db.add(proj)
        await db.commit()
        await db.refresh(proj)

        vid = Video(
            project_id=proj.id,
            filename="synthetic.mp4",
            file_path=synthetic_video_path,
            file_size_bytes=os.path.getsize(synthetic_video_path),
            duration_seconds=4.0
        )
        db.add(vid)
        await db.commit()
        await db.refresh(vid)
        video_id = vid.id
        project_id = proj.id

    # Enqueue thumbnail job
    job = await jm.enqueue_job(
        job_type="thumbnail",
        project_id=project_id,
        params={"video_id": video_id, "generate_strip": False}
    )
    assert job.status == "queued"

    # Wait for worker to process
    for _ in range(30):
        await asyncio.sleep(0.5)
        async with async_session_factory() as db:
            from sqlalchemy import select
            res = await db.execute(select(Job).where(Job.id == job.id))
            updated_job = res.scalar_one_or_none()
            if updated_job and updated_job.status in ("completed", "failed"):
                break

    assert updated_job is not None
    assert updated_job.status == "completed"
    assert updated_job.progress_percent == 100

@pytest.mark.asyncio
async def test_phase3_api_endpoints(synthetic_video_path):
    """Verify Phase 3 REST endpoints and HTTP range video streaming."""
    # Create project and video in DB
    async with async_session_factory() as db:
        proj = Project(name="API Phase 3 Project")
        db.add(proj)
        await db.commit()
        await db.refresh(proj)

        vid = Video(
            project_id=proj.id,
            filename="api_test.mp4",
            file_path=synthetic_video_path,
            file_size_bytes=os.path.getsize(synthetic_video_path),
            duration_seconds=4.0
        )
        db.add(vid)
        await db.commit()
        await db.refresh(vid)
        vid_id = vid.id
        proj_id = proj.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Video capabilities
        r = await client.get("/api/system/video-capabilities")
        assert r.status_code == 200
        assert r.json()["ffmpeg_available"] is True

        # 2. Enqueue thumbnail job
        r = await client.post(f"/api/videos/{vid_id}/thumbnail")
        assert r.status_code == 200
        assert "job_id" in r.json()

        # 3. Enqueue extract audio job
        r = await client.post(f"/api/videos/{vid_id}/extract-audio")
        assert r.status_code == 200
        assert "job_id" in r.json()

        # 4. Enqueue preview generation
        r = await client.post(f"/api/videos/{vid_id}/generate-preview")
        assert r.status_code == 200
        assert "job_id" in r.json()

        # 5. Generate Clip endpoint
        clip_payload = {
            "project_id": proj_id,
            "video_id": vid_id,
            "title": "Highlight 1",
            "start_time": 1.0,
            "end_time": 3.0,
            "aspect_ratio": "9:16",
            "reframe_mode": "center_crop"
        }
        r = await client.post("/api/clips/generate", json=clip_payload)
        assert r.status_code == 201
        clip_data = r.json()
        assert clip_data["title"] == "Highlight 1"
        assert clip_data["status"] == "rendering"

        # 6. Stream video with HTTP Range header (Partial Content 206)
        r = await client.get(
            f"/api/videos/{vid_id}/preview",
            headers={"Range": "bytes=0-1024"}
        )
        assert r.status_code == 206
        assert "Content-Range" in r.headers
        assert len(r.content) == 1025

        # 7. List jobs
        r = await client.get("/api/jobs")
        assert r.status_code == 200
        assert len(r.json()) > 0
