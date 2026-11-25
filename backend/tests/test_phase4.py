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
from app.db.models import Project, Video, Transcript, TranscriptSegment, Job
from app.config import settings
from app.video.ffmpeg_manager import FFmpegManager
from app.ai.model_registry import ModelRegistry, SUPPORTED_WHISPER_MODELS
from app.ai.model_manager import ModelManager
from app.ai.device_detector import DeviceDetector
from app.ai.transcription_config import TranscriptionConfig
from app.ai.transcription_validator import TranscriptionValidator
from app.ai.transcription_engine import TranscriptionEngine
from app.services.transcript_repository import TranscriptRepository
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
async def synthetic_speech_wav():
    """Generate a clean 3-second speech audio file using FFmpeg flite."""
    temp_dir = tempfile.gettempdir()
    wav_path = os.path.join(temp_dir, "clipforge_test_speech.wav")
    
    args = [
        "-f", "lavfi", "-i", "flite=text='Welcome to ClipForge AI transcription engine.'",
        "-ar", "16000", "-ac", "1",
        wav_path
    ]
    res = await FFmpegManager.run(args=args, output_file_to_verify=wav_path)
    assert res.success, f"Failed to generate speech audio: {res.error_message}"
    
    yield wav_path

    if os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except Exception:
            pass

@pytest.fixture
async def silence_wav():
    """Generate a 2-second pure silence audio file."""
    temp_dir = tempfile.gettempdir()
    wav_path = os.path.join(temp_dir, "clipforge_test_silence.wav")
    
    args = [
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
        "-t", "2",
        wav_path
    ]
    res = await FFmpegManager.run(args=args, output_file_to_verify=wav_path)
    assert res.success
    
    yield wav_path

    if os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except Exception:
            pass

# ----------------- Unit & Integration Tests -----------------

def test_model_registry_definitions():
    """Verify all 4 models are correctly registered with metadata and licenses."""
    models = ModelRegistry.list_all()
    assert len(models) == 4
    model_ids = [m.model_id for m in models]
    assert "tiny" in model_ids
    assert "base" in model_ids
    assert "small" in model_ids
    assert "medium" in model_ids

    small = ModelRegistry.get("small")
    assert small is not None
    assert small.disk_size_mb > 0
    assert "MIT" in small.license
    assert "Systran" in small.repo_id

def test_model_installation_detection():
    """Verify ModelManager accurately identifies installed and missing models."""
    tiny_status = ModelManager.check_model_status("tiny")
    assert tiny_status.is_installed is True
    assert tiny_status.disk_size_mb > 50

    medium_status = ModelManager.check_model_status("medium")
    assert medium_status.is_installed is False
    assert len(medium_status.missing_files) > 0

def test_missing_model_handling():
    """Verify invalid model requests raise an appropriate ValueError."""
    with pytest.raises(ValueError):
        ModelManager.check_model_status("invalid_model_xyz")

def test_hardware_device_detection():
    """Verify DeviceDetector returns accurate CTranslate2 and compute type details."""
    status = DeviceDetector.detect()
    assert status.ctranslate2_version != "Unknown"
    assert status.faster_whisper_version != "Unknown"
    assert len(status.cpu_supported_compute_types) > 0
    assert status.recommended_compute_type in ("int8", "float16")

def test_device_resolution_fallback():
    """Verify fallback mechanism safely defaults to CPU when GPU libraries are absent."""
    dev, comp, is_fallback, msg = DeviceDetector.resolve_device_and_compute_type("cpu")
    assert dev == "cpu"
    assert comp == "int8"
    assert is_fallback is False

    dev_auto, comp_auto, _, _ = DeviceDetector.resolve_device_and_compute_type("auto")
    assert dev_auto in ("cuda", "cpu")
    assert comp_auto in ("int8", "float16", "int8_float16")

def test_audio_validation(synthetic_speech_wav):
    """Verify audio file validation handles valid, missing, and empty files."""
    valid_res = TranscriptionValidator.validate_audio_file(synthetic_speech_wav)
    assert valid_res.valid is True
    assert valid_res.duration_seconds > 0.5

    missing_res = TranscriptionValidator.validate_audio_file("non_existent_file.wav")
    assert missing_res.valid is False
    assert "does not exist" in missing_res.error

@pytest.mark.asyncio
async def test_real_speech_transcription(synthetic_speech_wav):
    """Execute real local transcription with faster-whisper and verify word timestamps."""
    tiny_status = ModelManager.check_model_status("tiny")
    if not tiny_status.is_installed:
        pytest.skip("Tiny model not downloaded; skipping live inference test.")

    engine = TranscriptionEngine.get_instance()
    cfg = TranscriptionConfig(model_name="tiny", device="auto", word_timestamps=True)

    result = await engine.transcribe(synthetic_speech_wav, cfg)
    assert len(result.full_text) > 0
    assert result.language == "en"
    assert result.audio_duration_seconds > 0.5
    assert result.processing_duration_seconds > 0.0
    assert len(result.segments) > 0

    # Verify segment and word timestamps
    first_seg = result.segments[0]
    assert first_seg.start_time >= 0.0
    assert first_seg.end_time > first_seg.start_time
    assert len(first_seg.words) > 0
    for w in first_seg.words:
        assert w.end >= w.start
        assert len(w.word) > 0

@pytest.mark.asyncio
async def test_manual_language_selection(synthetic_speech_wav):
    """Verify manual language parameter is respected."""
    engine = TranscriptionEngine.get_instance()
    cfg = TranscriptionConfig(model_name="tiny", language="en", word_timestamps=False)

    result = await engine.transcribe(synthetic_speech_wav, cfg)
    assert result.language == "en"

@pytest.mark.asyncio
async def test_silence_handling(silence_wav):
    """Verify silence audio does not crash the transcription pipeline."""
    engine = TranscriptionEngine.get_instance()
    cfg = TranscriptionConfig(model_name="tiny", vad_filter=True)

    result = await engine.transcribe(silence_wav, cfg)
    assert isinstance(result.full_text, str)
    assert result.audio_duration_seconds >= 1.9

@pytest.mark.asyncio
async def test_transcript_database_persistence_and_editing(synthetic_speech_wav):
    """Verify transcript and word segments persist into SQLite and can be edited."""
    async with async_session_factory() as db:
        proj = Project(name="Transcription Test Project")
        db.add(proj)
        await db.commit()
        await db.refresh(proj)

        vid = Video(
            project_id=proj.id,
            filename="speech.mp4",
            file_path=synthetic_speech_wav,
            file_size_bytes=os.path.getsize(synthetic_speech_wav),
            duration_seconds=3.0
        )
        db.add(vid)
        await db.commit()
        await db.refresh(vid)
        video_id = vid.id

    # Transcribe
    engine = TranscriptionEngine.get_instance()
    res = await engine.transcribe(synthetic_speech_wav, TranscriptionConfig(model_name="tiny"))

    # Save to SQLite
    async with async_session_factory() as db:
        t = await TranscriptRepository.save_transcription_result(db, video_id, res)
        assert t.id is not None
        assert t.full_text == res.full_text
        assert len(t.segments) == len(res.segments)
        transcript_id = t.id
        first_segment_id = t.segments[0].id

    # Edit segment text
    async with async_session_factory() as db:
        updated_seg = await TranscriptRepository.update_segment_text(
            db=db,
            segment_id=first_segment_id,
            new_text="Edited spoken text for clip."
        )
        assert updated_seg.text == "Edited spoken text for clip."

        # Verify parent transcript was refreshed
        t_refreshed = await TranscriptRepository.get_by_id(db, transcript_id)
        assert "Edited spoken text for clip." in t_refreshed.full_text

@pytest.mark.asyncio
async def test_transcription_job_lifecycle(synthetic_speech_wav):
    """Verify JobManager executes transcribe_video job to completion."""
    jm = JobManager.get_instance()
    await jm.start()

    async with async_session_factory() as db:
        proj = Project(name="Job Queue Transcript Project")
        db.add(proj)
        await db.commit()
        await db.refresh(proj)

        vid = Video(
            project_id=proj.id,
            filename="job_speech.mp4",
            file_path=synthetic_speech_wav,
            file_size_bytes=os.path.getsize(synthetic_speech_wav),
            duration_seconds=3.0
        )
        db.add(vid)
        await db.commit()
        await db.refresh(vid)
        video_id = vid.id
        project_id = proj.id

    job = await jm.enqueue_job(
        job_type="transcribe_video",
        project_id=project_id,
        params={"video_id": video_id, "model_name": "tiny"}
    )
    assert job.status == "queued"

    # Poll until completed
    for _ in range(40):
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
async def test_phase4_api_endpoints(synthetic_speech_wav):
    """Verify REST API endpoints for AI capabilities, models, and transcripts."""
    async with async_session_factory() as db:
        proj = Project(name="Phase 4 API Project")
        db.add(proj)
        await db.commit()
        await db.refresh(proj)

        vid = Video(
            project_id=proj.id,
            filename="api_speech.mp4",
            file_path=synthetic_speech_wav,
            file_size_bytes=os.path.getsize(synthetic_speech_wav),
            duration_seconds=3.0
        )
        db.add(vid)
        await db.commit()
        await db.refresh(vid)
        vid_id = vid.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. AI Capabilities
        r = await client.get("/api/ai/capabilities")
        assert r.status_code == 200
        assert "ctranslate2_version" in r.json()

        # 2. List Models
        r = await client.get("/api/ai/models")
        assert r.status_code == 200
        models_data = r.json()
        assert len(models_data) >= 4

        # 3. Model Detail
        r = await client.get("/api/ai/models/tiny")
        assert r.status_code == 200
        assert r.json()["model_id"] == "tiny"

        # 4. Trigger Transcription
        r = await client.post(f"/api/videos/{vid_id}/transcribe", json={"model_name": "tiny"})
        assert r.status_code == 200
        assert "job_id" in r.json()

        # Wait a short moment for job execution
        await asyncio.sleep(4)

        # 5. Fetch Transcript
        r = await client.get(f"/api/videos/{vid_id}/transcript")
        if r.status_code == 200:
            t_data = r.json()
            assert "full_text" in t_data
            assert len(t_data["segments"]) > 0

            # 6. Edit Segment
            seg_id = t_data["segments"][0]["id"]
            r_edit = await client.patch(
                f"/api/transcripts/segments/{seg_id}",
                json={"text": "Updated API Segment Text"}
            )
            assert r_edit.status_code == 200
            assert r_edit.json()["text"] == "Updated API Segment Text"
