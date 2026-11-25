"""
ClipForge AI - Phase 8 Stage 3 API and Service Test Suite
Tests SpeakerAnalysisService, API endpoints, persistence, and manual editing.
"""

from datetime import datetime
from pathlib import Path
import sys
import numpy as np
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.core.database import Base, get_db
from app.core.security import verify_session_token
from app.db.models import AudioAnalysis, Project, Speaker, SpeakerEmbedding, SpeakerTurn, SpeechInterval, Video
from app.schemas.speaker_schemas import (
    DiarizationConfigSchema,
    UpdateSpeakerRequest,
    UpdateSpeakerTurnRequest,
)
from app.services.speaker_analysis_service import SpeakerAnalysisService
from app.ai.audio.speaker_diarizer import DiarizationResult, DiarizedSpeaker, SpeakerTurnData, SpeakerEmbeddingData

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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_session_token] = lambda: "test-user-session"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_data(async_test_session):
    """Seed test project, video, and audio analysis."""
    proj = Project(name="Diarization Test Project")
    async_test_session.add(proj)
    await async_test_session.flush()

    vid = Video(
        project_id=proj.id,
        filename="interview.mp4",
        file_path="storage/test/interview.mp4",
        file_size_bytes=1024 * 1024,
        duration_seconds=30.0,
        has_audio=True,
    )
    async_test_session.add(vid)
    await async_test_session.flush()

    analysis = AudioAnalysis(
        project_id=proj.id,
        video_id=vid.id,
        status="completed",
        duration_seconds=30.0,
        speech_duration_seconds=20.0,
        audio_available=True,
    )
    async_test_session.add(analysis)
    await async_test_session.flush()

    # Seed mock diarization result
    diar_result = DiarizationResult(
        speakers=[
            DiarizedSpeaker(0, "SPEAKER_00", "Speaker 1", 12.0, 2, np.zeros(512, dtype=np.float32), "#6366f1"),
            DiarizedSpeaker(1, "SPEAKER_01", "Speaker 2", 8.0, 1, np.zeros(512, dtype=np.float32), "#10b981"),
        ],
        speaker_turns=[
            SpeakerTurnData(0, "SPEAKER_00", "Speaker 1", 0.0, 6.0, 6.0, 0.95),
            SpeakerTurnData(1, "SPEAKER_01", "Speaker 2", 6.0, 14.0, 8.0, 0.92),
            SpeakerTurnData(0, "SPEAKER_00", "Speaker 1", 14.0, 20.0, 6.0, 0.96),
        ],
        embeddings=[
            SpeakerEmbeddingData(0.0, 1.5, np.zeros(512, dtype=np.float32), 0.9, 0),
            SpeakerEmbeddingData(6.0, 7.5, np.zeros(512, dtype=np.float32), 0.9, 1),
        ],
        num_speakers=2,
        total_speech_duration=20.0,
        silhouette_score=0.75,
        processing_duration=1.2,
        rtf=0.04,
        execution_device="cpu",
    )

    await SpeakerAnalysisService.save_diarization_results(
        db=async_test_session,
        analysis_id=analysis.id,
        project_id=proj.id,
        diarization_result=diar_result,
    )

    return {"project": proj, "video": vid, "analysis": analysis}


class TestSpeakerDiarizationAPI:
    """Integration tests for Speaker Diarization API routes."""

    @pytest.mark.asyncio
    async def test_get_capabilities(self, async_client):
        res = await async_client.get("/api/speakers/capabilities")
        assert res.status_code == 200
        data = res.json()
        assert data["diarization_available"] is True
        assert data["embedding_dimension"] == 512
        assert data["execution_device"] == "cpu"
        assert "default_config" in data

    @pytest.mark.asyncio
    async def test_get_speakers_for_analysis(self, async_client, seeded_data):
        analysis_id = seeded_data["analysis"].id
        res = await async_client.get(f"/api/audio-analysis/{analysis_id}/speakers")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        assert data[0]["speaker_identifier"] == "SPEAKER_00"
        assert data[0]["display_name"] == "Speaker 1"
        assert data[1]["speaker_identifier"] == "SPEAKER_01"

    @pytest.mark.asyncio
    async def test_get_speaker_turns_for_analysis(self, async_client, seeded_data):
        analysis_id = seeded_data["analysis"].id
        res = await async_client.get(f"/api/audio-analysis/{analysis_id}/speaker-turns")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 3
        assert data[0]["start_time"] == 0.0
        assert data[0]["end_time"] == 6.0
        assert data[1]["start_time"] == 6.0
        assert data[1]["end_time"] == 14.0

    @pytest.mark.asyncio
    async def test_get_diarization_summary(self, async_client, seeded_data):
        analysis_id = seeded_data["analysis"].id
        res = await async_client.get(f"/api/audio-analysis/{analysis_id}/diarization")
        assert res.status_code == 200
        data = res.json()
        assert data["num_speakers"] == 2
        assert len(data["speakers"]) == 2
        assert len(data["speaker_turns"]) == 3
        assert data["total_speech_duration"] == 20.0

    @pytest.mark.asyncio
    async def test_update_speaker_metadata(self, async_client, seeded_data):
        analysis_id = seeded_data["analysis"].id
        speakers_res = await async_client.get(f"/api/audio-analysis/{analysis_id}/speakers")
        spk_id = speakers_res.json()[0]["id"]

        patch_res = await async_client.patch(
            f"/api/speakers/{spk_id}",
            json={"display_name": "Dr. Sarah Connor", "color": "#ff007f"},
        )
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["display_name"] == "Dr. Sarah Connor"
        assert updated["color"] == "#ff007f"

    @pytest.mark.asyncio
    async def test_update_speaker_turn_reassignment(self, async_client, seeded_data):
        analysis_id = seeded_data["analysis"].id
        turns_res = await async_client.get(f"/api/audio-analysis/{analysis_id}/speaker-turns")
        turn_id = turns_res.json()[0]["id"]
        speakers_res = await async_client.get(f"/api/audio-analysis/{analysis_id}/speakers")
        spk2_id = speakers_res.json()[1]["id"]

        patch_res = await async_client.patch(
            f"/api/speaker-turns/{turn_id}",
            json={"speaker_id": spk2_id},
        )
        assert patch_res.status_code == 200
        updated_turn = patch_res.json()
        assert updated_turn["speaker_id"] == spk2_id
        assert updated_turn["assignment_status"] == "manual"

    @pytest.mark.asyncio
    async def test_delete_diarization(self, async_client, seeded_data):
        analysis_id = seeded_data["analysis"].id
        del_res = await async_client.delete(f"/api/audio-analysis/{analysis_id}/speakers")
        assert del_res.status_code == 200

        # Verify speakers and turns are cleared
        spk_res = await async_client.get(f"/api/audio-analysis/{analysis_id}/speakers")
        assert len(spk_res.json()) == 0
        turn_res = await async_client.get(f"/api/audio-analysis/{analysis_id}/speaker-turns")
        assert len(turn_res.json()) == 0
