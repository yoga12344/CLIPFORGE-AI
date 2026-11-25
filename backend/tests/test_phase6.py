"""
ClipForge AI - Phase 6 Test Suite: Visual AI, Face Tracking & Smart Reframing
Tests for detection, tracking, scene analysis, subject selection, smoothing, boundary clamping,
database persistence, and API endpoints.
"""

import math
import sys
from pathlib import Path

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
from app.db.models import Project, Video, VisionAnalysis, FaceTrack, ManualCropCorrection
from app.ai.vision.schemas import (
    NormalizedBBox,
    FaceDetection,
    TrackSample,
    TrackedFace,
    SceneComposition,
    CropCoordinate,
    ReframeConfig,
    ManualCropInput,
)
from app.ai.vision.face_detector import YuNetFaceDetector, HaarCascadeFaceDetector, get_face_detector
from app.ai.vision.face_tracker import FaceTracker, calculate_iou, calculate_centroid_distance
from app.ai.vision.scene_analyzer import SceneAnalyzer
from app.ai.vision.subject_selector import SubjectSelector
from app.ai.vision.reframe_engine import ReframeEngine
from app.video.aspect_ratio import AspectRatioProcessor
from app.services.vision_service import VisionService


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

    await engine.dispose()


@pytest_asyncio.fixture
async def test_client(async_test_session):
    async def override_get_db():
        yield async_test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# --- Unit Tests: Schemas & Geometry ---

def test_normalized_bbox_geometry():
    box = NormalizedBBox(x=0.2, y=0.3, width=0.4, height=0.4)
    assert math.isclose(box.center_x, 0.4)
    assert math.isclose(box.center_y, 0.5)
    assert math.isclose(box.area, 0.16)


def test_iou_calculation():
    # Identical boxes -> IoU = 1.0
    b1 = NormalizedBBox(x=0.2, y=0.2, width=0.2, height=0.2)
    b2 = NormalizedBBox(x=0.2, y=0.2, width=0.2, height=0.2)
    assert math.isclose(calculate_iou(b1, b2), 1.0)

    # Disjoint boxes -> IoU = 0.0
    b3 = NormalizedBBox(x=0.6, y=0.6, width=0.2, height=0.2)
    assert calculate_iou(b1, b3) == 0.0

    # 50% overlap horizontally
    b4 = NormalizedBBox(x=0.3, y=0.2, width=0.2, height=0.2)
    iou = calculate_iou(b1, b4)
    assert 0.3 < iou < 0.4


# --- Unit Tests: Face Tracking ---

def test_face_tracker_association():
    tracker = FaceTracker(iou_threshold=0.2, max_missed_frames=3)

    # Frame 0: detection at x=0.3
    d0 = [FaceDetection(bbox=NormalizedBBox(x=0.3, y=0.2, width=0.15, height=0.2), confidence=0.9, frame_index=0, timestamp_seconds=0.0)]
    updated0 = tracker.update(d0, frame_index=0, timestamp_seconds=0.0)
    assert len(updated0) == 1
    track_id = updated0[0].track_id
    assert track_id == "track_1"

    # Frame 1: slight movement to x=0.32
    d1 = [FaceDetection(bbox=NormalizedBBox(x=0.32, y=0.21, width=0.15, height=0.2), confidence=0.88, frame_index=1, timestamp_seconds=0.25)]
    updated1 = tracker.update(d1, frame_index=1, timestamp_seconds=0.25)
    assert updated1[0].track_id == track_id

    # Frame 2: new second person appears at x=0.75
    d2 = [
        FaceDetection(bbox=NormalizedBBox(x=0.33, y=0.2, width=0.15, height=0.2), confidence=0.85, frame_index=2, timestamp_seconds=0.5),
        FaceDetection(bbox=NormalizedBBox(x=0.75, y=0.3, width=0.12, height=0.18), confidence=0.92, frame_index=2, timestamp_seconds=0.5),
    ]
    updated2 = tracker.update(d2, frame_index=2, timestamp_seconds=0.5)
    assert len(updated2) == 2
    assert updated2[0].track_id == track_id
    assert updated2[1].track_id == "track_2"

    # Finalize tracks
    tracks = tracker.finalize()
    assert len(tracks) >= 1
    assert tracks[0].track_id == "track_1"
    assert tracks[0].detection_count == 3


def test_face_tracker_occlusion_tolerance():
    tracker = FaceTracker(max_missed_frames=3, min_detections_for_valid_track=2)

    # Frame 0: present
    d0 = [FaceDetection(bbox=NormalizedBBox(x=0.4, y=0.2, width=0.2, height=0.2), confidence=0.9, frame_index=0, timestamp_seconds=0.0)]
    tracker.update(d0, 0, 0.0)

    # Frame 1: occluded (no detection)
    tracker.update([], 1, 0.25)

    # Frame 2: reappears nearby
    d2 = [FaceDetection(bbox=NormalizedBBox(x=0.42, y=0.2, width=0.2, height=0.2), confidence=0.88, frame_index=2, timestamp_seconds=0.5)]
    updated2 = tracker.update(d2, 2, 0.5)
    assert len(updated2) == 1
    assert updated2[0].track_id == "track_1"


# --- Unit Tests: Scene Composition ---

def test_scene_analyzer_classifications():
    # 1. B-roll: 0 faces
    comp_broll = SceneAnalyzer.analyze_composition(10, {}, [])
    assert comp_broll.scene_type == "b_roll"
    assert comp_broll.has_no_faces is True

    # 2. Single subject
    dets_single = {
        0: [FaceDetection(bbox=NormalizedBBox(x=0.4, y=0.2, width=0.2, height=0.2), confidence=0.9, frame_index=0, timestamp_seconds=0.0)],
        1: [FaceDetection(bbox=NormalizedBBox(x=0.4, y=0.2, width=0.2, height=0.2), confidence=0.9, frame_index=1, timestamp_seconds=0.25)],
    }
    trk_single = [TrackedFace(track_id="track_1", start_time=0.0, end_time=0.25, detection_count=2, average_confidence=0.9, average_bbox=NormalizedBBox(x=0.4, y=0.2, width=0.2, height=0.2))]
    comp_single = SceneAnalyzer.analyze_composition(2, dets_single, trk_single)
    assert comp_single.scene_type == "single_subject"
    assert comp_single.primary_track_id == "track_1"

    # 3. Multi-person
    dets_multi = {
        0: [
            FaceDetection(bbox=NormalizedBBox(x=0.2, y=0.2, width=0.15, height=0.2), confidence=0.9, frame_index=0, timestamp_seconds=0.0),
            FaceDetection(bbox=NormalizedBBox(x=0.7, y=0.2, width=0.15, height=0.2), confidence=0.9, frame_index=0, timestamp_seconds=0.0),
        ]
    }
    comp_multi = SceneAnalyzer.analyze_composition(1, dets_multi, [])
    assert comp_multi.scene_type == "multi_person"
    assert comp_multi.has_multiple_subjects is True


# --- Unit Tests: Subject Selector ---

def test_subject_selector_strategies():
    small_face = FaceDetection(bbox=NormalizedBBox(x=0.1, y=0.2, width=0.1, height=0.1), confidence=0.9, frame_index=0, timestamp_seconds=0.0, track_id="track_1")
    large_face = FaceDetection(bbox=NormalizedBBox(x=0.7, y=0.2, width=0.3, height=0.3), confidence=0.9, frame_index=0, timestamp_seconds=0.0, track_id="track_2")
    center_face = FaceDetection(bbox=NormalizedBBox(x=0.45, y=0.2, width=0.15, height=0.15), confidence=0.9, frame_index=0, timestamp_seconds=0.0, track_id="track_3")

    dets = [small_face, large_face, center_face]

    # Largest face strategy
    target_largest = SubjectSelector.select_target(dets, strategy="largest_face")
    assert target_largest == large_face.bbox

    # Center face strategy
    target_center = SubjectSelector.select_target(dets, strategy="center_face")
    assert target_center == center_face.bbox

    # Manual track strategy
    target_manual = SubjectSelector.select_target(dets, strategy="manual_track", selected_track_id="track_1")
    assert target_manual == small_face.bbox

    # Group framing strategy (union of all)
    target_group = SubjectSelector.select_target(dets, strategy="group")
    assert target_group.x == 0.1
    assert math.isclose(target_group.x + target_group.width, 1.0)


# --- Unit Tests: Reframe Engine ---

def test_reframe_crop_dimensions():
    # 1920x1080 source, 9:16 target
    dims_9_16 = ReframeEngine.calculate_crop_dimensions(1920, 1080, "9:16")
    assert dims_9_16["pixel_height"] == 1080
    assert dims_9_16["pixel_width"] == 608 # 1080 * 9/16 = 607.5 -> rounded to 608 (even)
    assert dims_9_16["pixel_width"] % 2 == 0
    assert dims_9_16["norm_height"] == 1.0
    assert 0.31 < dims_9_16["norm_width"] < 0.32

    # 1920x1080 source, 1:1 target
    dims_1_1 = ReframeEngine.calculate_crop_dimensions(1920, 1080, "1:1")
    assert dims_1_1["pixel_height"] == 1080
    assert dims_1_1["pixel_width"] == 1080


def test_reframe_boundary_clamping():
    # Video 1920x1080, face on the extreme right edge (x=0.95)
    dets = {
        0.0: [FaceDetection(bbox=NormalizedBBox(x=0.95, y=0.3, width=0.04, height=0.1), confidence=0.9, frame_index=0, timestamp_seconds=0.0)]
    }
    traj = ReframeEngine.generate_trajectory(
        source_width=1920,
        source_height=1080,
        frame_detections=dets,
        config=ReframeConfig(aspect_ratio="9:16", smoothing_strength=0.0), # 0 smoothing for instant response
    )
    assert len(traj) == 1
    c = traj[0]
    # Crop right edge must not exceed 1.0 or source width
    assert c.crop_x + c.crop_width <= 1.0 + 1e-4
    assert c.pixel_x + c.pixel_width <= 1920
    assert c.crop_x >= 0.0
    assert c.pixel_x >= 0


def test_reframe_temporal_smoothing():
    # Sudden jump from x=0.2 to x=0.8
    dets = {
        0.0: [FaceDetection(bbox=NormalizedBBox(x=0.2, y=0.3, width=0.1, height=0.1), confidence=0.9, frame_index=0, timestamp_seconds=0.0)],
        0.25: [FaceDetection(bbox=NormalizedBBox(x=0.8, y=0.3, width=0.1, height=0.1), confidence=0.9, frame_index=1, timestamp_seconds=0.25)],
    }
    traj = ReframeEngine.generate_trajectory(
        source_width=1920,
        source_height=1080,
        frame_detections=dets,
        config=ReframeConfig(aspect_ratio="9:16", smoothing_strength=0.85, max_crop_velocity_per_sec=0.5),
    )
    assert len(traj) == 2
    # At t=0.25, the crop_x should not jump immediately to 0.8 because of smoothing + velocity clamp
    assert traj[1].crop_x < 0.6
    assert traj[1].crop_x > traj[0].crop_x


# --- Unit Tests: FFmpeg Trajectory Expression ---

def test_ffmpeg_trajectory_filtergraph():
    coords = [
        CropCoordinate(timestamp_seconds=0.0, crop_x=0.1, crop_y=0.0, crop_width=0.316, crop_height=1.0, pixel_x=192, pixel_y=0, pixel_width=608, pixel_height=1080),
        CropCoordinate(timestamp_seconds=1.0, crop_x=0.2, crop_y=0.0, crop_width=0.316, crop_height=1.0, pixel_x=384, pixel_y=0, pixel_width=608, pixel_height=1080),
    ]
    vf = AspectRatioProcessor.build_trajectory_filtergraph(
        crop_w=608,
        crop_h=1080,
        trajectory=coords,
        aspect_ratio="9:16",
    )
    assert "crop=608:1080:" in vf
    assert "scale=1080:1920" in vf
    assert "if(lt(t," in vf


# --- Integration Tests: Database Persistence & VisionService ---

@pytest.mark.asyncio
async def test_vision_service_persistence(async_test_session: AsyncSession):
    # Setup Project and Video
    project = Project(name="Vision Test Project")
    async_test_session.add(project)
    await async_test_session.flush()

    video = Video(
        project_id=project.id,
        filename="test_video.mp4",
        file_path="dummy.mp4",
        file_size_bytes=1000,
        width=1920,
        height=1080,
    )
    async_test_session.add(video)
    await async_test_session.commit()

    # Create dummy analysis result
    from app.ai.vision.vision_manager import VisionAnalysisResult
    result = VisionAnalysisResult(
        video_path="dummy.mp4",
        duration_seconds=5.0,
        total_frames_sampled=20,
        frames_with_faces=18,
        model_name="yunet",
        sampling_fps=4.0,
        composition=SceneComposition(
            total_frames_sampled=20,
            frames_with_faces=18,
            max_simultaneous_faces=1,
            average_face_count=0.9,
            primary_track_id="track_1",
            has_multiple_subjects=False,
            has_no_faces=False,
            scene_type="single_subject",
        ),
        tracked_faces=[
            TrackedFace(
                track_id="track_1",
                start_time=0.0,
                end_time=4.5,
                detection_count=18,
                average_confidence=0.92,
                average_bbox=NormalizedBBox(x=0.4, y=0.2, width=0.2, height=0.2),
                samples=[
                    TrackSample(timestamp_seconds=0.0, frame_index=0, bbox=NormalizedBBox(x=0.4, y=0.2, width=0.2, height=0.2), confidence=0.92),
                    TrackSample(timestamp_seconds=0.25, frame_index=1, bbox=NormalizedBBox(x=0.41, y=0.2, width=0.2, height=0.2), confidence=0.91),
                ],
            )
        ],
        frame_detections={},
    )

    # Save via service
    analysis = await VisionService.save_analysis(async_test_session, video.id, result)
    assert analysis.id is not None
    assert analysis.scene_type == "single_subject"

    # Fetch latest
    fetched = await VisionService.get_latest_analysis_for_video(async_test_session, video.id)
    assert fetched is not None
    assert len(fetched.tracks) == 1
    assert fetched.tracks[0].track_id == "track_1"

    # Add manual crop
    mc = await VisionService.add_manual_crop(
        async_test_session,
        analysis.id,
        ManualCropInput(timestamp_seconds=1.5, crop_x=0.25, crop_y=0.0, crop_width=0.316, crop_height=1.0),
    )
    assert mc.id is not None

    # Calculate trajectory
    traj = await VisionService.calculate_trajectory(
        async_test_session,
        analysis.id,
        ReframeConfig(aspect_ratio="9:16"),
    )
    assert len(traj) > 0


# --- Integration Tests: API Endpoints ---

@pytest.mark.asyncio
async def test_api_vision_workflow(test_client: AsyncClient, async_test_session: AsyncSession):
    # Setup Project and Video
    project = Project(name="API Vision Project")
    async_test_session.add(project)
    await async_test_session.flush()

    video = Video(
        project_id=project.id,
        filename="api_test.mp4",
        file_path="dummy.mp4",
        file_size_bytes=1000,
        width=1920,
        height=1080,
    )
    async_test_session.add(video)
    await async_test_session.commit()

    # 1. Enqueue visual analysis job
    res = await test_client.post(
        f"/api/videos/{video.id}/vision/analyze",
        json={"sampling_fps": 4.0, "confidence_threshold": 0.55},
        headers={"x-session-token": "clipforge-secure-session-token"},
    )
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    assert data["status"] == "queued"

    # 2. Query empty analysis (since job hasn't run in background during this unit test)
    res_get = await test_client.get(
        f"/api/videos/{video.id}/vision/analysis",
        headers={"x-session-token": "clipforge-secure-session-token"},
    )
    assert res_get.status_code == 200
    assert res_get.json() is None

    # 3. Create preset
    res_preset = await test_client.post(
        "/api/vision/presets",
        json={"name": "Cinematic 9:16", "aspect_ratio": "9:16", "strategy": "largest_face", "smoothing_strength": 0.9},
        headers={"x-session-token": "clipforge-secure-session-token"},
    )
    assert res_preset.status_code == 200
    preset_data = res_preset.json()
    assert preset_data["name"] == "Cinematic 9:16"
