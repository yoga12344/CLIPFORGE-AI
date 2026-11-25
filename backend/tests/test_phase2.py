import pytest
import os
import sys
import subprocess
from pathlib import Path
from sqlalchemy import select

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.db.models import Project, Video
from app.schemas.api_schemas import ProjectCreate, ProjectUpdate
from app.services.project_service import ProjectService
from app.services.settings_service import SettingsService
from app.services.video_service import VideoService

# Tests for Phase 2: Projects, Dashboard Stats, Settings, Video Probe & Import

@pytest.mark.asyncio
async def test_project_lifecycle():
    await init_db()
    async with AsyncSessionLocal() as session:
        # 1. Create
        p_data = ProjectCreate(name="Podcast Interview #42", description="Joe Rogan style discussion")
        project = await ProjectService.create_project(session, p_data)
        assert project.id is not None
        assert project.name == "Podcast Interview #42"

        # 2. List & Search
        projects = await ProjectService.list_projects(session, search="Podcast")
        assert len(projects) >= 1
        assert any(p["id"] == project.id for p in projects)

        # 3. Update / Rename
        u_data = ProjectUpdate(name="Renamed Podcast Ep 42")
        updated = await ProjectService.update_project(session, project.id, u_data)
        assert updated.name == "Renamed Podcast Ep 42"

        # 4. Get
        fetched = await ProjectService.get_project(session, project.id)
        assert fetched["name"] == "Renamed Podcast Ep 42"

        # 5. Delete
        del_success = await ProjectService.delete_project(session, project.id)
        assert del_success is True

        # Verify gone
        gone = await ProjectService.get_project(session, project.id)
        assert gone is None

@pytest.mark.asyncio
async def test_dashboard_statistics():
    async with AsyncSessionLocal() as session:
        stats = await ProjectService.get_dashboard_stats(session)
        assert stats.total_projects >= 0
        assert stats.total_videos >= 0
        assert stats.total_clips >= 0
        assert stats.total_exports >= 0
        assert isinstance(stats.recent_projects, list)

@pytest.mark.asyncio
async def test_settings_persistence():
    async with AsyncSessionLocal() as session:
        # Fetch defaults
        settings_dict = await SettingsService.get_all_settings(session)
        assert "gpu_acceleration" in settings_dict
        assert settings_dict["gpu_acceleration"] is True
        assert settings_dict["theme"] == "dark"

        # Update
        updated = await SettingsService.update_settings(session, {"theme": "dark", "vram_budget_mb": 7000})
        assert updated["vram_budget_mb"] == 7000

        # Verify persistent
        refetched = await SettingsService.get_all_settings(session)
        assert refetched["vram_budget_mb"] == 7000

@pytest.mark.asyncio
async def test_video_probe_and_import():
    # 1. Generate a small synthetic 3-second 1080p MP4 test file with FFmpeg
    temp_dir = settings.CACHE_DIR / "test_media"
    temp_dir.mkdir(parents=True, exist_ok=True)
    test_video = str(temp_dir / "sample_probe_test.mp4")

    ffmpeg_bin = settings.get_ffmpeg_binary()
    cmd = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=3:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        test_video
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    assert os.path.exists(test_video)

    # 2. Test Probe
    probe = VideoService.probe_video(test_video)
    assert probe.valid is True
    assert probe.width == 1920
    assert probe.height == 1080
    assert probe.has_audio is True
    assert probe.duration_seconds >= 2.5
    assert probe.video_codec == "h264"

    # 3. Test Import to Project
    async with AsyncSessionLocal() as session:
        proj = await ProjectService.create_project(session, ProjectCreate(name="Video Test Project"))
        
        imported_video = await VideoService.import_video(
            db=session,
            project_id=proj.id,
            source_file_path=test_video,
            copy_to_storage=True
        )

        assert imported_video.id is not None
        assert imported_video.project_id == proj.id
        assert imported_video.width == 1920
        assert imported_video.thumbnail_path is not None
        assert os.path.exists(imported_video.thumbnail_path)

        # Clean up project
        await ProjectService.delete_project(session, proj.id)
