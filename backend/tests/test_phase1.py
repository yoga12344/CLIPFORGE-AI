import pytest
import os
import sys
from pathlib import Path
from sqlalchemy import text, select

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.database import engine, AsyncSessionLocal, init_db, Base
from app.db.models import Project, Video, Job, CaptionPreset
from app.services.hardware import HardwareMonitor

@pytest.mark.asyncio
async def test_database_initialization():
    """Verify that all required tables are properly created in SQLite."""
    await init_db()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = [row[0] for row in result.fetchall()]

    required_tables = [
        "projects",
        "videos",
        "transcripts",
        "transcript_segments",
        "speakers",
        "clips",
        "clip_scores",
        "jobs",
        "exports",
        "caption_presets",
        "app_settings"
    ]

    for req in required_tables:
        assert req in tables, f"Table '{req}' was not found in SQLite schema!"

@pytest.mark.asyncio
async def test_project_crud():
    """Verify CRUD transactions on Project model."""
    async with AsyncSessionLocal() as session:
        # Create
        project = Project(name="Phase 1 Test Project", description="Testing SQLite persistence")
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project_id = project.id
        assert project_id is not None

        # Read
        res = await session.execute(select(Project).where(Project.id == project_id))
        fetched = res.scalar_one_or_none()
        assert fetched is not None
        assert fetched.name == "Phase 1 Test Project"

        # Update
        fetched.name = "Updated Project Name"
        await session.commit()

        # Re-fetch
        res2 = await session.execute(select(Project).where(Project.id == project_id))
        updated = res2.scalar_one_or_none()
        assert updated.name == "Updated Project Name"

        # Delete
        await session.delete(updated)
        await session.commit()

        res3 = await session.execute(select(Project).where(Project.id == project_id))
        assert res3.scalar_one_or_none() is None

def test_hardware_monitoring():
    """Verify hardware probe returns non-mock values for GPU, CPU, RAM, and Disk."""
    metrics = HardwareMonitor.get_system_metrics()
    
    assert "cpu" in metrics
    assert "ram" in metrics
    assert "disk" in metrics
    assert "gpu" in metrics
    assert "ffmpeg" in metrics

    # CPU metrics validation
    assert metrics["cpu"]["cores_logical"] > 0
    assert 0.0 <= metrics["cpu"]["utilization_percent"] <= 100.0

    # RAM metrics validation
    assert metrics["ram"]["total_gb"] > 0
    assert 0.0 <= metrics["ram"]["percent"] <= 100.0

    # Storage metrics validation
    assert metrics["disk"]["total_gb"] > 0
    assert 0.0 <= metrics["disk"]["percent"] <= 100.0

    # GPU presence
    assert "has_gpu" in metrics["gpu"]
    if metrics["gpu"]["has_gpu"]:
        assert "RTX" in metrics["gpu"]["gpu_name"] or len(metrics["gpu"]["gpu_name"]) > 0
        assert metrics["gpu"]["vram_total_mb"] > 0

    # FFmpeg presence
    assert metrics["ffmpeg"]["available"] is True
