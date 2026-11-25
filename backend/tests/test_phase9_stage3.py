"""
ClipForge AI - Phase 9 Stage 3 Test Suite: Render Graph Compiler & Modular FFmpeg Execution Harness
Tests for DAG nodes, stream compatibility, cycle detection, topological sorting,
graph validation, FFmpeg compiler, script generation, output validation, real FFmpeg rendering,
cancellation recovery, and REST API endpoints.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.db.models import Project, Video, Composition, CompositionVersion, CompositionRender, RenderArtifact
from app.composition.schemas.composition import CompositionSpec, SourceMediaMetadata
from app.composition.schemas.timeline import TimelineSpec, RationalTimebase, ClipBoundary
from app.composition.schemas.layout import LayoutConfig
from app.composition.schemas.camera import CameraPlan, CameraKeyframe, NormalizedRect
from app.composition.schemas.delivery import DeliveryProfile
from app.composition.render.graph import (
    StreamType,
    PortDirection,
    Port,
    are_stream_types_compatible,
    BaseNode,
    VideoInputNode,
    AudioInputNode,
    VideoTrimNode,
    AudioTrimNode,
    SetPTSNode,
    FPSNormalizeNode,
    CropNode,
    ScaleNode,
    SARNormalizeNode,
    PixelFormatConvertNode,
    SubtitleBurnNode,
    VideoOutputNode,
    AudioResampleNode,
    AudioGainNode,
    LoudnessNormalizeNode,
    AudioOutputNode,
    VideoAudioMuxNode,
    OutputContainerNode,
    RenderGraph,
    topological_sort,
    GraphCycleError,
    GraphValidator,
    CompositionToGraphBuilder,
    UnsupportedCompositionFeatureError,
    UnsupportedNodeError,
    create_node,
)
from app.composition.render.compiler import (
    FilterCompiler,
    format_ffmpeg_filter_path,
    FilterScriptWriter,
    ArgumentBuilder,
    RenderGraphCompiler,
)
from app.composition.render.validation import (
    OutputValidator,
    SynchronizationValidator,
)
from app.composition.render.execution import (
    RenderExecutor,
    RenderRecoveryService,
)
from app.composition.render.services import (
    RenderPlanService,
    RenderService,
)

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


# =============================================================================
# 1. NODE REGISTRY & UNSUPPORTED NODES
# =============================================================================

def test_node_instantiation_and_ports():
    v_in = VideoInputNode(id="v0", params={"file_path": "test.mp4"})
    assert v_in.id == "v0"
    assert len(v_in.outputs) == 1
    assert v_in.outputs[0].stream_type == StreamType.VIDEO

    crop = CropNode(id="c0", params={"width": 1080, "height": 1920, "x": 0, "y": 0})
    assert crop.get_input_port("in") is not None
    assert crop.get_output_port("out") is not None
    assert len(crop.validate_parameters()) == 0


def test_unsupported_nodes_rejected():
    with pytest.raises(UnsupportedNodeError) as exc_info:
        create_node("Transition", id="tr0")
    assert "Transition" in str(exc_info.value)

    with pytest.raises(UnsupportedNodeError):
        create_node("SidechainDucking", id="sc0")


# =============================================================================
# 2. STREAM COMPATIBILITY & VALIDATION
# =============================================================================

def test_stream_type_compatibility():
    assert are_stream_types_compatible(StreamType.VIDEO, StreamType.VIDEO) is True
    assert are_stream_types_compatible(StreamType.AUDIO, StreamType.AUDIO) is True
    assert are_stream_types_compatible(StreamType.IMAGE, StreamType.VIDEO) is True
    assert are_stream_types_compatible(StreamType.VIDEO, StreamType.AUDIO) is False
    assert are_stream_types_compatible(StreamType.AUDIO, StreamType.VIDEO) is False


def test_graph_cycle_detection():
    graph = RenderGraph(id="cycle_test")
    n1 = CropNode(id="n1", params={"width": 100, "height": 100})
    n2 = ScaleNode(id="n2", params={"width": 100, "height": 100})
    n3 = SARNormalizeNode(id="n3", params={})
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)

    # Create cycle n1 -> n2 -> n3 -> n1
    graph.add_edge("n1", "out", "n2", "in")
    graph.add_edge("n2", "out", "n3", "in")
    graph.add_edge("n3", "out", "n1", "in")

    with pytest.raises(GraphCycleError):
        topological_sort(graph)

    val_res = GraphValidator.validate(graph)
    assert val_res.is_valid is False
    assert any(e.error_category == "cycle" for e in val_res.errors)


def test_graph_type_mismatch_detection():
    graph = RenderGraph(id="type_mismatch_test")
    v_node = VideoInputNode(id="v_in", params={"file_path": "dummy.mp4"})
    a_trim = AudioTrimNode(id="a_trim", params={"start_us": 0, "end_us": 1000000})
    container = OutputContainerNode(id="out", params={"output_path": "out.mp4"})
    graph.add_node(v_node)
    graph.add_node(a_trim)
    graph.add_node(container)

    # Connect video output to audio input
    graph.add_edge("v_in", "out", "a_trim", "in")
    graph.add_edge("a_trim", "out", "out", "in")

    val_res = GraphValidator.validate(graph)
    assert val_res.is_valid is False
    assert any(e.error_category == "type_mismatch" for e in val_res.errors)


# =============================================================================
# 3. COMPOSITION TO GRAPH BUILDER
# =============================================================================

def test_graph_builder_single_full_frame():
    spec = CompositionSpec.create_default(
        composition_id="comp_bld_01",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=10000000,
        clip_start_us=0,
        clip_end_us=5000000,
    )

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path="C:/videos/input.mp4",
        output_file_path="C:/videos/output.mp4",
    )

    assert "node_v_in" in graph.nodes
    assert "node_v_crop" in graph.nodes
    assert "node_v_scale" in graph.nodes
    assert "node_container" in graph.nodes

    val_res = GraphValidator.validate(graph)
    assert val_res.is_valid is True


def test_graph_builder_rejects_unsupported_topology():
    spec = CompositionSpec.create_default(
        composition_id="comp_bld_02",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=10000000,
        clip_start_us=0,
        clip_end_us=5000000,
    )
    # Alter layout to three_person_grid (unsupported complex topology)
    spec.layout.layout_type = "three_person_grid"

    with pytest.raises(UnsupportedCompositionFeatureError) as exc_info:
        CompositionToGraphBuilder.build_graph(
            spec=spec,
            source_media_path="dummy.mp4",
            output_file_path="out.mp4",
        )
    assert "three_person_grid" in str(exc_info.value)


# =============================================================================
# 4. COMPILER & FILTER SCRIPT
# =============================================================================

def test_ffmpeg_filter_path_escaping():
    win_path = r"C:\Users\yogac\AppData\Local\Temp\subtitles_01.ass"
    escaped = format_ffmpeg_filter_path(win_path)
    assert escaped.startswith("C\\:/")
    assert "\\" not in escaped[4:]


def test_render_graph_compilation_and_script():
    spec = CompositionSpec.create_default(
        composition_id="comp_cmp_01",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=5000000,
        clip_start_us=0,
        clip_end_us=3000000,
    )

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        graph = CompositionToGraphBuilder.build_graph(
            spec=spec,
            source_media_path="C:/media/test.mp4",
            output_file_path="C:/media/out.mp4",
        )

        # Force script file generation
        delivery = getattr(spec, "delivery_profile", None) or getattr(spec, "delivery", None)
        plan = RenderGraphCompiler.compile(
            graph=graph,
            delivery=delivery,
            render_id="test_render_01",
            force_script_file=True,
            custom_script_dir=temp_dir,
        )

        assert plan.is_script_file is True
        assert plan.filter_script_path is not None
        assert Path(plan.filter_script_path).exists()
        assert "-filter_complex_script" in plan.command_args
        assert "[v_out]" in plan.filter_complex_string
        assert "[a_out]" in plan.filter_complex_string


# =============================================================================
# 5. REAL FFMPEG EXECUTION & OUTPUT VALIDATION ACCEPTANCE TEST
# =============================================================================

@pytest.mark.asyncio
async def test_real_ffmpeg_rendering_acceptance(async_test_session: AsyncSession):
    """
    Generate synthetic 2s 16:9 media, build CompositionSpec for 9:16 portrait export,
    execute full render via RenderExecutor, and deeply validate output via FFprobe.
    """
    from app.video.capabilities import CapabilityDetector
    caps = CapabilityDetector.detect()
    if not caps.ffmpeg_available:
        pytest.skip("FFmpeg is not installed on this system.")

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        source_mp4 = temp_dir / "synthetic_source.mp4"
        export_dir = temp_dir / "exports"
        export_dir.mkdir()

        # 1. Generate 2s 1920x1080 synthetic media with sine audio
        cmd = [
            caps.ffmpeg_path, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(source_mp4)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        assert source_mp4.exists()

        # 2. Setup DB entities
        project = Project(name="Render Acceptance Project")
        async_test_session.add(project)
        await async_test_session.flush()

        video = Video(
            project_id=project.id,
            filename="synthetic_source.mp4",
            file_path=str(source_mp4),
            file_size_bytes=source_mp4.stat().st_size,
            width=1920,
            height=1080,
            duration_seconds=2.0,
        )
        async_test_session.add(video)
        await async_test_session.flush()

        spec = CompositionSpec.create_default(
            composition_id="comp_acc_01",
            project_id=project.id,
            video_id=video.id,
            source_width=1920,
            source_height=1080,
            source_fps=30.0,
            source_duration_us=2000000,
            clip_start_us=0,
            clip_end_us=1000000,
        )

        comp = Composition(
            id="comp_acc_01",
            project_id=project.id,
            source_video_id=video.id,
            title="Acceptance Composition",
        )
        async_test_session.add(comp)
        await async_test_session.flush()

        version = CompositionVersion(
            id="ver_acc_01",
            composition_id=comp.id,
            version_number=1,
            spec_json=spec.model_dump(mode="json"),
            content_hash=spec.compute_content_hash(),
            is_draft=False,
        )
        async_test_session.add(version)
        await async_test_session.flush()

        render = CompositionRender(
            id="rnd_acc_01",
            composition_id=comp.id,
            composition_version_id=version.id,
            output_path=str(export_dir / "final_output.mp4"),
            status="queued",
            progress_percent=0,
        )
        async_test_session.add(render)
        await async_test_session.commit()

        # 3. Execute Render
        result = await RenderExecutor.execute_render(
            render_id=render.id,
            db=async_test_session,
            custom_output_dir=export_dir,
        )

        assert result.success is True
        assert Path(result.output_file_path).exists()
        assert result.validation_result is not None
        assert result.validation_result.is_valid is True
        assert result.validation_result.video_width == 1080
        assert result.validation_result.video_height == 1920

        # Check DB update
        await async_test_session.refresh(render)
        assert render.status == "completed"
        assert render.progress_percent == 100
        assert render.render_duration_seconds > 0


# =============================================================================
# 6. CRASH RECOVERY & REST API ENDPOINTS
# =============================================================================

@pytest.mark.asyncio
async def test_render_crash_recovery(async_test_session: AsyncSession):
    project = Project(name="Crash Recovery Project")
    async_test_session.add(project)
    await async_test_session.flush()

    video = Video(
        project_id=project.id,
        filename="dummy.mp4",
        file_path="dummy.mp4",
        file_size_bytes=1000,
        width=1920,
        height=1080,
    )
    async_test_session.add(video)
    await async_test_session.flush()

    comp = Composition(id="comp_crash", project_id=project.id, source_video_id=video.id, title="Crash Comp")
    async_test_session.add(comp)
    await async_test_session.flush()

    ver = CompositionVersion(id="ver_crash", composition_id=comp.id, version_number=1, spec_json={}, content_hash="h")
    async_test_session.add(ver)
    await async_test_session.flush()

    # Create stale rendering record
    stale_render = CompositionRender(
        id="rnd_stale",
        composition_id=comp.id,
        composition_version_id=ver.id,
        output_path="storage/clipforge_data/exports/stale.mp4",
        status="rendering",
        progress_percent=45,
    )
    async_test_session.add(stale_render)
    await async_test_session.commit()

    recovered_count = await RenderRecoveryService.recover_interrupted_renders(async_test_session)
    assert recovered_count == 1

    await async_test_session.refresh(stale_render)
    assert stale_render.status == "failed"
    assert "Interrupted" in stale_render.error_message


@pytest.mark.asyncio
async def test_render_api_endpoints(test_client: AsyncClient, async_test_session: AsyncSession):
    project = Project(name="API Render Project")
    async_test_session.add(project)
    await async_test_session.flush()

    video = Video(
        project_id=project.id,
        filename="api_vid.mp4",
        file_path="dummy.mp4",
        file_size_bytes=1000,
        width=1920,
        height=1080,
        duration_seconds=10.0,
    )
    async_test_session.add(video)
    await async_test_session.flush()

    spec = CompositionSpec.create_default(
        composition_id="comp_api_01",
        project_id=project.id,
        video_id=video.id,
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=10000000,
        clip_start_us=0,
        clip_end_us=5000000,
    )

    comp = Composition(
        id="comp_api_01",
        project_id=project.id,
        source_video_id=video.id,
        title="API Comp",
    )
    async_test_session.add(comp)
    await async_test_session.flush()

    ver = CompositionVersion(
        id="ver_api_01",
        composition_id=comp.id,
        version_number=1,
        spec_json=spec.model_dump(mode="json"),
        content_hash=spec.compute_content_hash(),
        is_draft=False,
    )
    async_test_session.add(ver)
    await async_test_session.commit()

    headers = {"x-session-token": "clipforge-secure-session-token"}

    # 1. Compile Plan Endpoint
    compile_res = await test_client.post(
        f"/api/compositions/{comp.id}/versions/{ver.id}/compile",
        json={"preferred_encoder": "libx264"},
        headers=headers,
    )
    assert compile_res.status_code == 200
    plan_data = compile_res.json()
    assert plan_data["composition_id"] == comp.id
    assert plan_data["video_encoder"] == "libx264"
    assert "command_args" in plan_data
    assert plan_data["node_count"] > 0

    # 2. Queue Render Endpoint
    render_res = await test_client.post(
        f"/api/compositions/{comp.id}/versions/{ver.id}/renders",
        json={},
        headers=headers,
    )
    assert render_res.status_code == 202
    render_data = render_res.json()
    assert render_data["status"] == "queued"
    render_id = render_data["id"]

    # 3. List Renders Endpoint
    list_res = await test_client.get(f"/api/compositions/{comp.id}/renders", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Get Render Endpoint
    get_res = await test_client.get(f"/api/compositions/{comp.id}/renders/{render_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == render_id

    # 5. Cancel Render Endpoint
    cancel_res = await test_client.post(f"/api/compositions/{comp.id}/renders/{render_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["render_id"] == render_id
