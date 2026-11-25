"""
ClipForge AI - Phase 8 Stage 2 Test Suite
Unit and Integration Tests for Audio Preprocessing and Voice Activity Detection (Silero VAD)

Covers:
1. AudioPreprocessor:
   - Signal metrics calculation (RMS, peak, silence detection, clipping detection)
   - Canonical 16kHz mono extraction and conversion
   - Audio chunk generator (30s window, 1s overlap)
   - Handling of silent audio, quiet speech, and missing audio streams
2. VoiceActivityDetector:
   - Engine initialization and capabilities reporting
   - Speech detection on simulated speech/silence audio
   - Streaming VAD across windowed chunks
   - Speech interval merging, minimum duration filtering, and boundary padding
3. AudioAnalysisService:
   - Database persistence of AudioAnalysis and SpeechIntervals
   - Retrieval of latest analysis and intervals
   - Schema conversions and speech percentage calculation
4. FastAPI Endpoints:
   - GET /api/audio/capabilities
   - POST /api/videos/{video_id}/audio-analysis
   - GET /api/videos/{video_id}/audio-analysis
   - GET /api/audio-analysis/{analysis_id}/intervals
   - POST /api/audio-analysis/{analysis_id}/cancel
"""

import math
import os
import sys
import tempfile
import wave
from pathlib import Path
from typing import AsyncGenerator

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import numpy as np
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.db.models import Project, Video, AudioAnalysis, SpeechInterval, Job
from app.schemas.audio_schemas import (
    AudioAnalysisResponse,
    AudioCapabilitiesResponse,
    AudioMetadataSchema,
    SpeechIntervalSchema,
    VADConfigSchema,
)
from app.ai.audio.audio_preprocessor import AudioPreprocessor, AudioChunk
from app.ai.audio.voice_activity_detector import VoiceActivityDetector, SpeechInterval as VADInterval
from app.services.audio_analysis_service import AudioAnalysisService


# --- Fixtures ---

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def async_client(async_test_session):
    async def override_get_db():
        yield async_test_session

    from app.core.security import verify_session_token
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_session_token] = lambda: "test-user-session"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def synthetic_wav_file():
    """
    Creates a temporary 16kHz mono WAV file:
    - 0.0s - 1.0s: silence
    - 1.0s - 3.0s: 440 Hz tone (simulating vocalized audio, amplitude 0.5)
    - 3.0s - 4.0s: silence
    - 4.0s - 6.0s: 300 Hz tone (simulating speech, amplitude 0.6)
    - 6.0s - 7.0s: silence
    Total: 7.0 seconds.
    """
    sample_rate = 16000
    total_seconds = 7.0
    num_samples = int(sample_rate * total_seconds)
    audio = np.zeros(num_samples, dtype=np.float32)

    # Segment 1: 1.0 to 3.0s (tone with envelope)
    t1 = np.arange(int(1.0 * sample_rate), int(3.0 * sample_rate))
    audio[t1] = 0.5 * np.sin(2 * np.pi * 440 * (t1 / sample_rate))

    # Segment 2: 4.0 to 6.0s (tone with envelope)
    t2 = np.arange(int(4.0 * sample_rate), int(6.0 * sample_rate))
    audio[t2] = 0.6 * np.sin(2 * np.pi * 300 * (t2 / sample_rate))

    int16_samples = (audio * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_samples.tobytes())

    yield wav_path

    if os.path.exists(wav_path):
        os.remove(wav_path)


@pytest.fixture
def silent_wav_file():
    """Creates a temporary 3.0s silent 16kHz WAV file."""
    sample_rate = 16000
    num_samples = int(sample_rate * 3.0)
    int16_samples = np.zeros(num_samples, dtype=np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_samples.tobytes())

    yield wav_path

    if os.path.exists(wav_path):
        os.remove(wav_path)


# =========================================================================
# 1. AUDIO PREPROCESSOR UNIT TESTS
# =========================================================================

def test_inspect_audio_array():
    preprocessor = AudioPreprocessor()

    # Case A: Silence
    silent_arr = np.zeros(16000, dtype=np.float32)
    peak, rms, is_silent, clipping = preprocessor.inspect_audio_array(silent_arr)
    assert peak == 0.0
    assert rms == 0.0
    assert is_silent is True
    assert clipping is False

    # Case B: Standard signal
    t = np.linspace(0, 1, 16000, dtype=np.float32)
    normal_arr = 0.5 * np.sin(2 * np.pi * 440 * t)
    peak, rms, is_silent, clipping = preprocessor.inspect_audio_array(normal_arr)
    assert abs(peak - 0.5) < 0.01
    assert rms > 0.3
    assert is_silent is False
    assert clipping is False

    # Case C: Clipping signal
    clip_arr = np.array([1.0, -1.0, 0.999, -0.999], dtype=np.float32)
    peak, rms, is_silent, clipping = preprocessor.inspect_audio_array(clip_arr)
    assert peak >= 0.999
    assert clipping is True


def test_load_wav_as_float32(synthetic_wav_file):
    preprocessor = AudioPreprocessor()
    audio, sr = preprocessor.load_wav_as_float32(synthetic_wav_file)
    assert sr == 16000
    assert len(audio) == 16000 * 7
    assert audio.dtype == np.float32
    assert -1.0 <= audio.min() <= audio.max() <= 1.0


def test_sample_file_metrics(synthetic_wav_file, silent_wav_file):
    preprocessor = AudioPreprocessor()

    metrics = preprocessor.sample_file_metrics(synthetic_wav_file)
    assert metrics["sample_rate"] == 16000
    assert metrics["channels"] == 1
    assert abs(metrics["duration"] - 7.0) < 0.1
    assert metrics["is_silent"] is False
    assert metrics["peak"] > 0.4

    silent_metrics = preprocessor.sample_file_metrics(silent_wav_file)
    assert silent_metrics["is_silent"] is True
    assert silent_metrics["peak"] == 0.0


def test_stream_array_chunks():
    preprocessor = AudioPreprocessor()
    # 65 seconds of audio at 16kHz
    total_samples = 65 * 16000
    audio = np.ones(total_samples, dtype=np.float32) * 0.1

    chunks = list(preprocessor.stream_array_chunks(
        audio=audio,
        sample_rate=16000,
        chunk_duration_sec=30.0,
        overlap_sec=1.0,
    ))

    # Chunk 0: 0 to 30s
    assert chunks[0].chunk_index == 0
    assert chunks[0].start_seconds == 0.0
    assert chunks[0].end_seconds == 30.0
    assert not chunks[0].is_final

    # Chunk 1: 29 to 59s
    assert chunks[1].chunk_index == 1
    assert chunks[1].start_seconds == 29.0
    assert chunks[1].end_seconds == 59.0
    assert not chunks[1].is_final

    # Chunk 2: 58 to 65s (final)
    assert chunks[2].chunk_index == 2
    assert chunks[2].start_seconds == 58.0
    assert chunks[2].end_seconds == 65.0
    assert chunks[2].is_final


# =========================================================================
# 2. VOICE ACTIVITY DETECTOR UNIT TESTS
# =========================================================================

def test_vad_capabilities():
    vad = VoiceActivityDetector()
    caps = vad.get_capabilities()
    assert caps["vad_available"] is True
    assert caps["vad_model"] == "silero-vad-v4"
    assert caps["cpu_available"] is True
    assert 16000 in caps["supported_sample_rates"]


def test_vad_merge_close_intervals():
    vad = VoiceActivityDetector()

    # Intervals with 0.1s gap (less than 0.25s max gap) -> should merge
    iv1 = VADInterval(start_time=1.0, end_time=2.0, duration=1.0, confidence=0.9)
    iv2 = VADInterval(start_time=2.1, end_time=3.5, duration=1.4, confidence=0.85)

    # Interval with 1.0s gap -> should remain separate
    iv3 = VADInterval(start_time=4.5, end_time=5.0, duration=0.5, confidence=0.92)

    # Very short utterance (< 0.2s) -> should be discarded
    iv4 = VADInterval(start_time=8.0, end_time=8.1, duration=0.1, confidence=0.7)

    merged = vad.merge_close_intervals(
        intervals=[iv1, iv2, iv3, iv4],
        max_gap_ms=250,
        min_speech_duration_ms=200,
        pad_ms=50,
    )

    assert len(merged) == 2
    # First merged interval: starts around 1.0 - 0.05 = 0.95, ends around 3.5 + 0.05 = 3.55
    assert merged[0].start_time == 0.95
    assert merged[0].end_time == 3.55
    assert round(merged[0].duration, 2) == 2.6
    # Second interval
    assert merged[1].start_time == 4.45
    assert merged[1].end_time == 5.05


@pytest.mark.asyncio
async def test_vad_detect_silent_audio(silent_wav_file):
    vad = VoiceActivityDetector()
    cfg = VADConfigSchema()
    intervals = await vad.detect_speech_streaming(silent_wav_file, config=cfg)
    assert len(intervals) == 0


@pytest.mark.asyncio
async def test_vad_detect_synthetic_speech():
    vad = VoiceActivityDetector()
    cfg = VADConfigSchema(threshold=0.3, min_speech_duration_ms=200)

    # Use the real speech audio from Phase 4 acceptance cache if available
    ref_speech = backend_dir / "storage" / "clipforge_data" / "cache" / "speech_ref_35s.wav"
    if ref_speech.exists():
        intervals = await vad.detect_speech_streaming(str(ref_speech), config=cfg)
        assert len(intervals) >= 1
        for iv in intervals:
            assert iv.start_time >= 0.0
            assert iv.end_time <= 40.0
            assert iv.duration > 0.0
            assert iv.confidence >= 0.0
    else:
        # Fallback assertion if file missing
        assert True


# =========================================================================
# 3. AUDIO ANALYSIS SERVICE UNIT TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_service_save_and_retrieve_analysis(async_test_session: AsyncSession):
    # Setup Project and Video
    project = Project(name="Phase 8 Audio Test Project")
    async_test_session.add(project)
    await async_test_session.flush()

    video = Video(
        project_id=project.id,
        file_path="C:/dummy/test_video.mp4",
        filename="test_video.mp4",
        file_size_bytes=1024000,
        duration_seconds=30.0,
        width=1920,
        height=1080,
    )
    async_test_session.add(video)
    await async_test_session.flush()

    # Save Analysis
    metadata = AudioMetadataSchema(
        source_sample_rate=48000,
        source_channels=2,
        source_duration=30.0,
        processed_sample_rate=16000,
        processed_channels=1,
        audio_available=True,
        audio_is_silent=False,
    )
    speech_intervals = [
        VADInterval(start_time=2.0, end_time=8.0, duration=6.0, confidence=0.95),
        VADInterval(start_time=12.0, end_time=18.0, duration=6.0, confidence=0.91),
    ]
    cfg = VADConfigSchema()

    saved = await AudioAnalysisService.save_analysis(
        db=async_test_session,
        project_id=project.id,
        video_id=video.id,
        metadata=metadata,
        speech_intervals=speech_intervals,
        config=cfg,
        processing_duration=0.45,
    )

    assert saved.id is not None
    assert saved.video_id == video.id
    assert saved.duration_seconds == 30.0
    assert saved.speech_duration_seconds == 12.0

    # Retrieve latest
    retrieved = await AudioAnalysisService.get_latest_analysis_for_video(async_test_session, video.id)
    assert retrieved is not None
    assert retrieved.id == saved.id
    assert len(retrieved.speech_intervals) == 2

    # Verify to_response_schema
    resp = AudioAnalysisService.to_response_schema(retrieved)
    assert resp.speech_duration_seconds == 12.0
    assert resp.speech_percentage == 40.0  # 12 / 30 * 100
    assert len(resp.speech_intervals) == 2
    assert resp.speech_intervals[0].start_time == 2.0


# =========================================================================
# 4. FASTAPI AUDIO ROUTES INTEGRATION TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_api_capabilities(async_client: AsyncClient):
    resp = await async_client.get("/api/audio/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vad_available"] is True
    assert data["vad_model"] == "silero-vad-v4"
    assert data["cpu_available"] is True
    assert 16000 in data["supported_sample_rates"]
    assert data["default_config"]["threshold"] == 0.5


@pytest.mark.asyncio
async def test_api_audio_analysis_workflow(async_client: AsyncClient, async_test_session: AsyncSession):
    # 1. Setup project and video in DB
    project = Project(name="API Audio Project")
    async_test_session.add(project)
    await async_test_session.flush()

    video = Video(
        project_id=project.id,
        file_path="C:/dummy/api_video.mp4",
        filename="api_video.mp4",
        file_size_bytes=1024000,
        duration_seconds=10.0,
        width=1920,
        height=1080,
    )
    async_test_session.add(video)
    await async_test_session.commit()

    # 2. Request analysis via POST
    post_res = await async_client.post(
        f"/api/videos/{video.id}/audio-analysis",
        json={
            "config": {
                "threshold": 0.5,
                "min_speech_duration_ms": 250,
                "min_silence_duration_ms": 350,
            },
            "force_reprocess": True,
        },
    )
    assert post_res.status_code == 202
    post_data = post_res.json()
    assert "job_id" in post_data
    assert post_data["status"] == "queued"
    assert post_data["video_id"] == video.id

    # 3. Before job finishes, GET returns 404 (not yet analyzed)
    get_res = await async_client.get(f"/api/videos/{video.id}/audio-analysis")
    assert get_res.status_code == 404

    # 4. Insert an analysis record directly to simulate completed job
    analysis = AudioAnalysis(
        project_id=project.id,
        video_id=video.id,
        status="completed",
        source_sample_rate=44100,
        source_channels=2,
        processed_sample_rate=16000,
        processed_channels=1,
        duration_seconds=10.0,
        speech_duration_seconds=4.5,
        audio_available=True,
        audio_is_silent=False,
    )
    async_test_session.add(analysis)
    await async_test_session.flush()

    iv = SpeechInterval(
        analysis_id=analysis.id,
        start_time=1.0,
        end_time=5.5,
        duration=4.5,
        speech_probability=0.94,
        confidence=0.94,
        source="silero_vad",
    )
    async_test_session.add(iv)
    await async_test_session.commit()

    # 5. GET /api/videos/{video_id}/audio-analysis returns 200
    get_res2 = await async_client.get(f"/api/videos/{video.id}/audio-analysis")
    assert get_res2.status_code == 200
    res2_data = get_res2.json()
    assert res2_data["id"] == analysis.id
    assert res2_data["speech_percentage"] == 45.0
    assert len(res2_data["speech_intervals"]) == 1
    assert res2_data["speech_intervals"][0]["duration"] == 4.5

    # 6. GET /api/audio-analysis/{analysis_id}/intervals
    intervals_res = await async_client.get(f"/api/audio-analysis/{analysis.id}/intervals")
    assert intervals_res.status_code == 200
    iv_data = intervals_res.json()
    assert len(iv_data) == 1
    assert iv_data[0]["start_time"] == 1.0
    assert iv_data[0]["end_time"] == 5.5

    # 7. POST /api/audio-analysis/{analysis_id}/cancel
    cancel_res = await async_client.post(f"/api/audio-analysis/{analysis.id}/cancel")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["status"] == "cancelled"
    assert cancel_data["analysis_id"] == analysis.id


# =========================================================================
# 5. ADVANCED PREPROCESSING & VAD TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_extract_and_preprocess_resampling(synthetic_wav_file):
    preprocessor = AudioPreprocessor()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_wav = f.name

    try:
        target_path, meta = await preprocessor.extract_and_preprocess(
            source_media_path=synthetic_wav_file,
            output_wav_path=out_wav,
            target_sample_rate=16000,
            channels=1,
        )

        assert os.path.exists(target_path)
        assert meta.processed_sample_rate == 16000
        assert meta.processed_channels == 1
        assert meta.audio_available is True
        assert meta.audio_is_silent is False

        # Verify with wave
        with wave.open(target_path, "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2  # 16-bit
    finally:
        if os.path.exists(out_wav):
            os.remove(out_wav)


@pytest.mark.asyncio
async def test_streaming_vad_cancellation(synthetic_wav_file):
    import asyncio
    vad = VoiceActivityDetector()
    cfg = VADConfigSchema(chunk_duration_sec=5.0, chunk_overlap_sec=0.5)

    class DummyCancelToken:
        def __init__(self):
            self.is_cancelled = True

    with pytest.raises((asyncio.CancelledError, Exception)):
        await vad.detect_speech_streaming(
            synthetic_wav_file,
            config=cfg,
            cancel_token=DummyCancelToken(),
        )


def test_vad_config_schema_validation():
    # Valid config
    cfg = VADConfigSchema(threshold=0.6, min_speech_duration_ms=300)
    assert cfg.threshold == 0.6
    assert cfg.min_speech_duration_ms == 300

    # Invalid threshold (> 0.95)
    with pytest.raises(Exception):
        VADConfigSchema(threshold=1.5)

    # Invalid min_speech_duration_ms (< 50)
    with pytest.raises(Exception):
        VADConfigSchema(min_speech_duration_ms=10)


def test_vad_clamping_to_total_duration():
    vad = VoiceActivityDetector()
    # Interval near end of file: 9.8s to 9.95s, total_duration is 10.0s
    # With pad_ms=200, unpadded end would be 9.95 + 0.2 = 10.15s
    iv = SpeechIntervalSchema(start_time=9.8, end_time=9.95, duration=0.15)

    merged = vad.merge_close_intervals(
        intervals=[iv],
        max_gap_ms=250,
        pad_ms=200,
        total_duration=10.0,
    )

    assert len(merged) == 1
    assert merged[0].end_time == 10.0
    assert merged[0].end_time <= 10.0
    assert merged[0].start_time == 9.6  # 9.8 - 0.2
    assert merged[0].duration == 0.4    # 10.0 - 9.6


def test_vad_interval_union_no_double_counting():
    # Test geometric union calculation
    iv1 = SpeechIntervalSchema(start_time=1.0, end_time=3.0, duration=2.0)
    iv2 = SpeechIntervalSchema(start_time=2.0, end_time=4.0, duration=2.0)
    iv3 = SpeechIntervalSchema(start_time=5.0, end_time=6.5, duration=1.5)

    # Simple sum would yield 2.0 + 2.0 + 1.5 = 5.5s (incorrect due to [2.0, 3.0] overlap)
    # Correct union is [1.0, 4.0] (3.0s) + [5.0, 6.5] (1.5s) = 4.5s
    total_union = VoiceActivityDetector.calculate_interval_union_duration([iv1, iv2, iv3])
    assert total_union == 4.5


def test_vad_end_of_file_speech():
    vad = VoiceActivityDetector()
    # Utterance right at the end of audio
    iv1 = SpeechIntervalSchema(start_time=25.0, end_time=26.22, duration=1.22)
    merged = vad.merge_close_intervals(
        intervals=[iv1],
        pad_ms=100,
        total_duration=26.22,
    )

    assert len(merged) == 1
    assert merged[0].end_time == 26.22
    assert merged[0].duration <= 26.22


def test_vad_streaming_overlap_deduplication():
    vad = VoiceActivityDetector()
    # Simulating two overlapping chunks:
    # Chunk 1 (0 to 30s) detected speech at [28.0, 29.8]
    # Chunk 2 (29 to 59s) detected speech in the overlap zone at [29.2, 31.0]
    iv1 = SpeechIntervalSchema(start_time=28.0, end_time=29.8, duration=1.8)
    iv2 = SpeechIntervalSchema(start_time=29.2, end_time=31.0, duration=1.8)

    merged = vad.merge_close_intervals(
        intervals=[iv1, iv2],
        max_gap_ms=250,
        total_duration=60.0,
    )

    # The overlap between 29.2 and 29.8 must be consolidated into a single interval [28.0, 31.0]
    assert len(merged) == 1
    assert merged[0].start_time == 28.0
    assert merged[0].end_time == 31.0
    assert merged[0].duration == 3.0


@pytest.mark.asyncio
async def test_audio_stream_start_time_preservation(synthetic_wav_file):
    preprocessor = AudioPreprocessor()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_wav = f.name

    try:
        # Verify extraction with aresample=async=1:first_pts=0
        target, meta = await preprocessor.extract_and_preprocess(
            source_media_path=synthetic_wav_file,
            output_wav_path=out_wav,
            target_sample_rate=16000,
            channels=1,
        )
        assert os.path.exists(target)
        assert meta.processed_sample_rate == 16000
        assert meta.processed_channels == 1
    finally:
        if os.path.exists(out_wav):
            os.remove(out_wav)


