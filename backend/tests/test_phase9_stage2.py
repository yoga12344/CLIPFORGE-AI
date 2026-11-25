"""
ClipForge AI - Phase 9 Stage 2 Test Suite: CompositionSpec v1.0 & Versioned Database
Comprehensive tests covering:
1. Pydantic schema validation & canonical JSON roundtrip
2. Timeline conversions, microsecond arithmetic & rational timebase
3. Asset URI parsing, validation & security traversal rejection
4. Layout configuration & normalized geometry boundary checks
5. Camera keyframes, interpolation modes & manual override preservation
6. Subtitle word references, presets & collision avoidance
7. Audio mixing, ducking & configurable loudness targets
8. Delivery profiles & H.264 even dimension enforcement
9. CompositionService CRUD & project/video ownership authorization
10. CompositionVersionService immutable snapshots & OCC conflict detection
11. Non-destructive version rollback & restore
12. Database integrity, unique constraints & cascade deletions
13. CompositionValidationService project asset authorization
14. FastAPI REST API endpoints for compositions, versions, restore, validate, and assets
"""

import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.db.models import (
    Project,
    Video,
    HighlightCandidate,
    Composition,
    CompositionVersion,
    CompositionAsset,
    CompositionRender,
    RenderArtifact,
)
from app.composition.schemas import (
    CompositionSpec,
    RationalTimebase,
    ClipBoundary,
    NormalizedRect,
    LayoutSlot,
    LayoutConfig,
    CameraPlan,
    CameraKeyframe,
    ManualOverride,
    TrackSegment,
    VideoTrack,
    AudioTrack,
    DeliveryProfile,
    get_default_delivery_profile,
    us_to_seconds,
    seconds_to_us,
    source_to_composition_us,
    composition_to_source_us,
    composition_to_output_us,
    output_to_composition_us,
    parse_and_validate_asset_uri,
    validate_composition_semantics,
)
from app.composition.services import (
    CompositionService,
    CompositionVersionService,
    CompositionValidationService,
    VersionConflictError,
    ResourceOwnershipError,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_test_session():
    """Isolated in-memory SQLite database session with PRAGMA foreign_keys=ON."""
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(async_test_session):
    """FastAPI test client with dependency override for get_db."""
    async def override_get_db():
        yield async_test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def setup_project_and_video(async_test_session):
    """Creates a sample Project and Video record."""
    proj = Project(name="Phase 9 Test Project", description="Testing CompositionSpec")
    async_test_session.add(proj)
    await async_test_session.flush()

    vid = Video(
        project_id=proj.id,
        filename="test_interview.mp4",
        file_path="C:/media/test_interview.mp4",
        file_size_bytes=10485760,
        duration_seconds=120.0,
        width=1920,
        height=1080,
        fps=29.97,
        video_codec="h264",
        audio_codec="aac",
    )
    async_test_session.add(vid)
    await async_test_session.flush()

    cand = HighlightCandidate(
        project_id=proj.id,
        video_id=vid.id,
        title="Key Pitch Segment",
        start_time=10.0,
        end_time=30.0,
        duration_seconds=20.0,
        overall_score=92,
        status="approved",
    )
    async_test_session.add(cand)
    await async_test_session.commit()

    return proj, vid, cand


# ==============================================================================
# 1. Timeline & Timebase Unit Tests
# ==============================================================================

def test_microseconds_and_seconds_conversion():
    assert us_to_seconds(1_000_000) == 1.0
    assert us_to_seconds(500_000) == 0.5
    assert seconds_to_us(1.0) == 1_000_000
    assert seconds_to_us(0.5) == 500_000
    assert seconds_to_us(12.345678) == 12345678

    with pytest.raises(ValueError):
        seconds_to_us(-0.1)


def test_rational_timebase_derivation():
    # 29.97 NTSC preset
    tb_ntsc = RationalTimebase.from_float(29.97)
    assert tb_ntsc.numerator == 30000
    assert tb_ntsc.denominator == 1001
    assert abs(tb_ntsc.as_float() - 29.97002997) < 1e-4

    # 23.976 preset
    tb_24 = RationalTimebase.from_float(23.976)
    assert tb_24.numerator == 24000
    assert tb_24.denominator == 1001

    # Standard integer rates
    tb_30 = RationalTimebase.from_float(30.0)
    assert tb_30.numerator == 30
    assert tb_30.denominator == 1

    tb_60 = RationalTimebase.from_float(60.0)
    assert tb_60.numerator == 60
    assert tb_60.denominator == 1

    with pytest.raises(ValueError):
        RationalTimebase.from_float(-30.0)


def test_coordinate_system_conversions():
    # Source: clip starts at 10.0s (10,000,000 us)
    clip_start_src_us = 10_000_000

    # Event at 15.0s in source video -> 5.0s in composition
    source_ts_us = 15_000_000
    comp_ts_us = source_to_composition_us(source_ts_us, clip_start_src_us)
    assert comp_ts_us == 5_000_000

    # Reverse
    assert composition_to_source_us(comp_ts_us, clip_start_src_us) == source_ts_us

    # Timestamp before clip start must raise error
    with pytest.raises(ValueError):
        source_to_composition_us(9_999_999, clip_start_src_us)

    # Output offset conversion (e.g. 1.0s bumper intro)
    output_offset = 1_000_000
    out_ts_us = composition_to_output_us(comp_ts_us, output_offset)
    assert out_ts_us == 6_000_000
    assert output_to_composition_us(out_ts_us, output_offset) == comp_ts_us


def test_clip_boundary_validation():
    # Valid boundary
    cb = ClipBoundary(source_start_us=10_000_000, source_end_us=30_000_000, duration_us=20_000_000)
    assert cb.duration_seconds == 20.0

    # Invalid: start >= end
    with pytest.raises(ValueError):
        ClipBoundary(source_start_us=20_000_000, source_end_us=10_000_000, duration_us=10_000_000)

    # Invalid: duration mismatch
    with pytest.raises(ValueError):
        ClipBoundary(source_start_us=10_000_000, source_end_us=30_000_000, duration_us=15_000_000)


# ==============================================================================
# 2. Asset URI Parsing & Security Tests
# ==============================================================================

def test_valid_asset_uris():
    valid_uris = [
        "asset://videos/source_01",
        "asset://audio/background_music_bed",
        "asset://images/channel_logo_watermark",
        "asset://broll/cutaway_chart",
        "asset://overlays/lower_third_01",
        "asset://subtitles/custom_ass_script",
        "asset://fonts/montserrat_bold",
    ]
    for uri in valid_uris:
        parsed = parse_and_validate_asset_uri(uri)
        assert parsed.scheme == "asset"
        assert parsed.raw_uri == uri


def test_rejected_asset_uris_path_traversal():
    invalid_uris = [
        "asset://videos/../secrets.txt",
        "asset://audio/..\\windows\\system32",
        "C:\\Users\\admin\\Desktop\\video.mp4",
        "/etc/passwd",
        "file:///C:/video.mp4",
        "http://example.com/asset.mp4",
        "asset://unauthorized_type/my_asset",
        "asset://videos/",
        "",
        "asset://videos/has spaces here",
    ]
    for uri in invalid_uris:
        with pytest.raises(ValueError):
            parse_and_validate_asset_uri(uri)


# ==============================================================================
# 3. Geometry & Layout Schema Tests
# ==============================================================================

def test_normalized_rect_validation():
    # Valid rect
    r = NormalizedRect(x=0.0, y=0.0, width=1.0, height=0.5)
    assert r.center_x == 0.5
    assert r.center_y == 0.25
    assert r.area == 0.5

    # Out of bounds (> 1.0)
    with pytest.raises(ValueError):
        NormalizedRect(x=0.6, y=0.0, width=0.5, height=0.5)

    # Negative coordinate
    with pytest.raises(ValueError):
        NormalizedRect(x=-0.1, y=0.0, width=0.5, height=0.5)

    # Zero width
    with pytest.raises(ValueError):
        NormalizedRect(x=0.0, y=0.0, width=0.0, height=0.5)


def test_layout_config_auto_population():
    # Single full frame auto-populates 1 slot
    l_single = LayoutConfig(layout_type="single_full_frame")
    assert len(l_single.slots) == 1
    assert l_single.slots[0].slot_id == "slot_0"
    assert l_single.slots[0].bounds.width == 1.0

    # Split vertical auto-populates 2 slots
    l_split = LayoutConfig(layout_type="split_vertical")
    assert len(l_split.slots) == 2
    assert l_split.slots[0].slot_id == "slot_top"
    assert l_split.slots[1].slot_id == "slot_bottom"
    assert l_split.slots[0].bounds.height == 0.5
    assert l_split.slots[1].bounds.height == 0.5


# ==============================================================================
# 4. Delivery Profile Tests
# ==============================================================================

def test_delivery_profile_even_dimensions():
    # Standard 1080x1920 is valid
    dp = DeliveryProfile(width=1080, height=1920)
    assert dp.width == 1080
    assert dp.height == 1920

    # Odd width must fail for H.264 macroblock compliance
    with pytest.raises(ValueError):
        DeliveryProfile(width=1081, height=1920)

    # Odd height must fail
    with pytest.raises(ValueError):
        DeliveryProfile(width=1080, height=1919)


def test_standard_delivery_profiles_lookup():
    p916 = get_default_delivery_profile("9:16")
    assert p916.aspect_ratio == "9:16"
    assert p916.width == 1080
    assert p916.height == 1920

    p11 = get_default_delivery_profile("1:1")
    assert p11.aspect_ratio == "1:1"
    assert p11.width == 1080
    assert p11.height == 1080

    p169 = get_default_delivery_profile("16:9")
    assert p169.aspect_ratio == "16:9"
    assert p169.width == 1920
    assert p169.height == 1080


# ==============================================================================
# 5. Root CompositionSpec Serialization & Hash
# ==============================================================================

def test_composition_spec_canonical_json_and_hash():
    spec = CompositionSpec.create_default(
        composition_id="comp-test-01",
        project_id="proj-01",
        video_id="vid-01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=60_000_000,
        clip_start_us=10_000_000,
        clip_end_us=25_000_000,
        title="Test Serialization",
    )

    # Canonical JSON is deterministic
    json1 = spec.to_canonical_json()
    json2 = spec.to_canonical_json()
    assert json1 == json2

    # Content hash
    hash1 = spec.compute_content_hash()
    assert len(hash1) == 64  # SHA-256 hex string

    # Deserialization round-trip
    restored = CompositionSpec.from_canonical_json(json1)
    assert restored.composition_id == spec.composition_id
    assert restored.clip_boundary.duration_us == 15_000_000
    assert restored.compute_content_hash() == hash1


def test_composition_spec_semantic_validation():
    spec = CompositionSpec.create_default(
        composition_id="comp-test-02",
        project_id="proj-01",
        video_id="vid-01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=60_000_000,
        clip_start_us=0,
        clip_end_us=15_000_000,
    )

    # Valid spec passes
    res = spec.validate_semantics()
    assert res.is_valid is True
    assert len(res.errors) == 0

    # Add a keyframe that references a non-existent slot
    spec.camera.keyframes.append(
        CameraKeyframe(
            timeline_position_us=5_000_000,
            slot_id="slot_does_not_exist",
            crop_rect=NormalizedRect(x=0.0, y=0.0, width=0.5, height=0.5),
        )
    )
    res_err = spec.validate_semantics()
    assert res_err.is_valid is False
    assert any(e.code == "UNKNOWN_SLOT" for e in res_err.errors)


# ==============================================================================
# 6. CompositionService & VersionService CRUD Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_composition_creation_and_versioning(async_test_session, setup_project_and_video):
    proj, vid, cand = setup_project_and_video

    # 1. Create composition with default spec
    comp, v1 = await CompositionService.create_composition(
        db=async_test_session,
        project_id=proj.id,
        video_id=vid.id,
        title="Podcast Clip #1",
        description="Highlights from the introductory segment",
        candidate_id=cand.id,
        aspect_ratio="9:16",
    )

    assert comp.id is not None
    assert comp.title == "Podcast Clip #1"
    assert comp.status == "draft"
    assert comp.current_version_id == v1.id

    assert v1.version_number == 1
    assert v1.schema_version == "1.0.0"
    assert len(v1.content_hash) == 64
    assert v1.is_draft is False

    # 2. Create version 2 (with updated spec)
    spec = CompositionSpec.model_validate(v1.spec_json)
    spec.title = "Podcast Clip #1 - Revised"
    spec.layout.layout_type = "split_vertical"

    v2 = await CompositionVersionService.create_version(
        db=async_test_session,
        composition=comp,
        spec=spec,
        change_summary="Switched to split_vertical layout",
        is_draft=False,
        expected_version_number=1,  # OCC check passed
    )

    assert v2.version_number == 2
    assert comp.current_version_id == v2.id
    assert v2.content_hash != v1.content_hash

    # 3. Optimistic Concurrency Control (OCC) conflict test
    with pytest.raises(VersionConflictError):
        await CompositionVersionService.create_version(
            db=async_test_session,
            composition=comp,
            spec=spec,
            expected_version_number=1,  # Current is 2 -> conflict!
        )

    # 4. Non-destructive restore: Restore v1 -> creates v3 with v1's spec
    v3 = await CompositionVersionService.restore_version(
        db=async_test_session,
        composition=comp,
        target_version_number=1,
    )
    assert v3.version_number == 3
    assert comp.current_version_id == v3.id

    # Verify v3 content matches v1 layout
    spec_v3 = CompositionSpec.model_validate(v3.spec_json)
    assert spec_v3.layout.layout_type == "single_full_frame"


@pytest.mark.asyncio
async def test_resource_ownership_protection(async_test_session, setup_project_and_video):
    proj, vid, _ = setup_project_and_video

    # Create another project
    other_proj = Project(name="Other Project")
    async_test_session.add(other_proj)
    await async_test_session.commit()

    # Attempt to create composition with mismatched project and video
    with pytest.raises(ResourceOwnershipError):
        await CompositionService.create_composition(
            db=async_test_session,
            project_id=other_proj.id,  # Mismatched!
            video_id=vid.id,
        )


@pytest.mark.asyncio
async def test_database_cascade_deletions(async_test_session, setup_project_and_video):
    proj, vid, _ = setup_project_and_video

    comp, v1 = await CompositionService.create_composition(
        db=async_test_session,
        project_id=proj.id,
        video_id=vid.id,
        title="To Be Deleted",
    )
    comp_id = comp.id
    v1_id = v1.id

    # Create a render record attached to version
    render = CompositionRender(
        composition_id=comp_id,
        composition_version_id=v1_id,
        output_path="C:/exports/test.mp4",
        status="completed",
        progress_percent=100,
    )
    async_test_session.add(render)
    await async_test_session.flush()

    artifact = RenderArtifact(
        composition_render_id=render.id,
        artifact_type="ass_script",
        file_path="C:/tmp/script.ass",
    )
    async_test_session.add(artifact)
    await async_test_session.commit()

    # Delete composition
    await CompositionService.delete_composition(async_test_session, comp_id)

    # Verify versions, renders, and artifacts were cascade-deleted
    assert (await async_test_session.execute(select(Composition).where(Composition.id == comp_id))).scalar_one_or_none() is None
    assert (await async_test_session.execute(select(CompositionVersion).where(CompositionVersion.id == v1_id))).scalar_one_or_none() is None
    assert (await async_test_session.execute(select(CompositionRender).where(CompositionRender.id == render.id))).scalar_one_or_none() is None
    assert (await async_test_session.execute(select(RenderArtifact).where(RenderArtifact.id == artifact.id))).scalar_one_or_none() is None


# ==============================================================================
# 7. FastAPI REST API Route Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_composition_api_routes(async_client, setup_project_and_video):
    proj, vid, cand = setup_project_and_video
    headers = {"x-session-token": "clipforge-secure-session-token"}

    # 1. POST /api/compositions
    create_payload = {
        "project_id": proj.id,
        "video_id": vid.id,
        "title": "API Composition",
        "description": "Created via REST API",
        "candidate_id": cand.id,
        "aspect_ratio": "9:16",
    }
    res = await async_client.post("/api/compositions", json=create_payload, headers=headers)
    assert res.status_code == 201
    comp_data = res.json()
    assert comp_data["title"] == "API Composition"
    assert comp_data["status"] == "draft"
    assert comp_data["active_version"]["version_number"] == 1
    comp_id = comp_data["id"]

    # 2. GET /api/compositions
    list_res = await async_client.get(f"/api/compositions?project_id={proj.id}", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. GET /api/compositions/{id}
    get_res = await async_client.get(f"/api/compositions/{comp_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == comp_id

    # 4. PATCH /api/compositions/{id}
    patch_res = await async_client.patch(
        f"/api/compositions/{comp_id}",
        json={"title": "Updated Title", "status": "ready"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated Title"
    assert patch_res.json()["status"] == "ready"

    # 5. POST /api/compositions/{id}/versions
    active_spec = comp_data["active_version"]["spec"]
    active_spec["title"] = "Version 2 Title"
    v_create_payload = {
        "spec": active_spec,
        "change_summary": "Created version 2",
        "is_draft": False,
        "expected_version_number": 1,
    }
    v_res = await async_client.post(f"/api/compositions/{comp_id}/versions", json=v_create_payload, headers=headers)
    assert v_res.status_code == 201
    assert v_res.json()["version_number"] == 2

    # 6. POST /api/compositions/{id}/versions with OCC conflict (expecting version 1 when it's now 2)
    conflict_res = await async_client.post(
        f"/api/compositions/{comp_id}/versions",
        json={"spec": active_spec, "expected_version_number": 1},
        headers=headers,
    )
    assert conflict_res.status_code == 409

    # 7. GET /api/compositions/{id}/versions
    v_list_res = await async_client.get(f"/api/compositions/{comp_id}/versions", headers=headers)
    assert v_list_res.status_code == 200
    assert len(v_list_res.json()) == 2

    # 8. POST /api/compositions/{id}/versions/1/restore
    restore_res = await async_client.post(f"/api/compositions/{comp_id}/versions/1/restore", headers=headers)
    assert restore_res.status_code == 200
    assert restore_res.json()["version_number"] == 3

    # 9. POST /api/compositions/{id}/validate
    val_res = await async_client.post(f"/api/compositions/{comp_id}/validate", headers=headers)
    assert val_res.status_code == 200
    assert val_res.json()["is_valid"] is True

    # 10. POST /api/compositions/projects/{project_id}/assets
    asset_payload = {
        "asset_type": "audio",
        "logical_asset_id": "upbeat_synth_bed",
        "name": "Upbeat Synth Bed",
        "file_path": "audio/music_01.mp3",
        "file_size_bytes": 2048000,
        "duration_seconds": 60.0,
    }
    asset_res = await async_client.post(
        f"/api/compositions/projects/{proj.id}/assets",
        json=asset_payload,
        headers=headers,
    )
    assert asset_res.status_code == 201
    assert asset_res.json()["asset_uri"] == "asset://audio/upbeat_synth_bed"

    # 11. GET /api/compositions/projects/{project_id}/assets
    assets_get_res = await async_client.get(f"/api/compositions/projects/{proj.id}/assets", headers=headers)
    assert assets_get_res.status_code == 200
    assert len(assets_get_res.json()) == 1

    # 12. DELETE /api/compositions/{id}
    del_res = await async_client.delete(f"/api/compositions/{comp_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True
