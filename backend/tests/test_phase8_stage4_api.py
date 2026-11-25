"""
ClipForge AI - Phase 8 Stage 4 API Test Suite
Tests active speaker capabilities, intervals, manual associations, and deletion endpoints.
"""

from pathlib import Path
import sys
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
from app.db.models import ActiveSpeakerInterval, Project, Speaker, SpeakerFaceAssociation, Video

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
    app.dependency_overrides[verify_session_token] = lambda: "test-session"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_active_speaker_capabilities(async_client):
    """Test the GET /api/active-speakers/capabilities endpoint."""
    resp = await async_client.get("/api/active-speakers/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["face_mesh_points"] == 478
    assert "Light-ASD" in data["model_name"]
    assert data["offline_only"] is True


@pytest.mark.asyncio
async def test_get_video_active_speakers_empty(async_client, async_test_session):
    """Test fetching active speakers when none exist yet."""
    proj = Project(name="Test Project")
    async_test_session.add(proj)
    await async_test_session.flush()

    video = Video(
        project_id=proj.id,
        filename="test.mp4",
        file_path="/tmp/test.mp4",
        file_size_bytes=1024,
        duration_seconds=10.0,
    )
    async_test_session.add(video)
    await async_test_session.commit()

    resp = await async_client.get(f"/api/videos/{video.id}/active-speakers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["video_id"] == video.id
    assert len(data["active_segments"]) == 0
    assert len(data["associations"]) == 0


@pytest.mark.asyncio
async def test_manual_speaker_face_association(async_client, async_test_session):
    """Test manual speaker-face association override via PUT endpoint."""
    proj = Project(name="Test Project")
    async_test_session.add(proj)
    await async_test_session.flush()

    video = Video(
        project_id=proj.id,
        filename="test.mp4",
        file_path="/tmp/test.mp4",
        file_size_bytes=1024,
        duration_seconds=10.0,
    )
    async_test_session.add(video)
    await async_test_session.flush()

    spk = Speaker(
        project_id=proj.id,
        speaker_identifier="SPEAKER_00",
        label="Speaker 1",
    )
    async_test_session.add(spk)
    await async_test_session.commit()

    # Call PUT endpoint to manually associate SPEAKER_00 with track_manual_1
    resp = await async_client.put(
        f"/api/videos/{video.id}/speakers/{spk.id}/associate",
        json={"face_track_id": "track_manual_1", "is_off_screen": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["speaker_id"] == spk.id
    assert data["face_track_id"] == "track_manual_1"
    assert data["is_manual"] is True
    assert data["is_off_screen"] is False

    # Fetch active speakers to verify persistent storage
    fetch_resp = await async_client.get(f"/api/videos/{video.id}/active-speakers")
    assert fetch_resp.status_code == 200
    fetch_data = fetch_resp.json()
    assert len(fetch_data["associations"]) == 1
    assert fetch_data["associations"][0]["face_track_id"] == "track_manual_1"


@pytest.mark.asyncio
async def test_delete_active_speaker_analysis(async_client, async_test_session):
    """Test DELETE /api/videos/{video_id}/active-speakers."""
    proj = Project(name="Test Project")
    async_test_session.add(proj)
    await async_test_session.flush()

    video = Video(
        project_id=proj.id,
        filename="test.mp4",
        file_path="/tmp/test.mp4",
        file_size_bytes=1024,
        duration_seconds=10.0,
    )
    async_test_session.add(video)
    await async_test_session.flush()

    # Add an interval
    interval = ActiveSpeakerInterval(
        video_id=video.id,
        start_time=1.0,
        end_time=3.0,
        duration=2.0,
        confidence=0.9,
    )
    async_test_session.add(interval)
    await async_test_session.commit()

    # Delete
    del_resp = await async_client.delete(f"/api/videos/{video.id}/active-speakers")
    assert del_resp.status_code == 204

    # Verify interval deleted but video remains
    fetch_resp = await async_client.get(f"/api/videos/{video.id}/active-speakers")
    assert len(fetch_resp.json()["active_segments"]) == 0
