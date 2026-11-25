"""
ClipForge AI - Phase 9 Stage 5 Test Suite
Multi-Person Layout Engine: split_vertical, split_horizontal, blurred_background,
picture_in_picture, LayoutSelector, and real FFmpeg rendering acceptance.
"""

import os
import subprocess
import tempfile
import pytest
from pathlib import Path

from app.composition.schemas.composition import CompositionSpec
from app.composition.schemas.layout import LayoutConfig
from app.composition.schemas.delivery import get_default_delivery_profile
from app.composition.render.graph.graph_builder import CompositionToGraphBuilder
from app.composition.render.graph.graph_validator import GraphValidator
from app.composition.render.compiler.ffmpeg_compiler import RenderGraphCompiler
from app.composition.render.execution.render_process import RenderProcessRunner
from app.composition.render.validation.output_validator import OutputValidator
from app.composition.layout.layout_selector import LayoutSelector


@pytest.fixture(scope="module")
def sample_test_video(tmp_path_factory) -> str:
    """Generate a real 1.0-second 16:9 test video (1920x1080) with stereo audio."""
    temp_dir = tmp_path_factory.mktemp("media_p9s5")
    video_path = str(temp_dir / "sample_interview.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=1.0:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1.0:sample_rate=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k",
        video_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return video_path


def test_multi_person_layout_graph_compilation_split_vertical():
    spec = CompositionSpec.create_default(
        composition_id="comp_split_v",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=5000000,
        clip_start_us=0,
        clip_end_us=3000000,
    )
    spec.layout.layout_type = "split_vertical"

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path="C:/videos/interview.mp4",
        output_file_path="C:/videos/output_split_v.mp4",
    )

    # Verify nodes
    assert "node_v_split" in graph.nodes
    assert "node_v_crop_0" in graph.nodes
    assert "node_v_scale_0" in graph.nodes
    assert "node_v_crop_1" in graph.nodes
    assert "node_v_scale_1" in graph.nodes
    assert "node_v_stack" in graph.nodes

    # Validate graph
    val_res = GraphValidator.validate(graph)
    assert val_res.is_valid is True, f"Validation errors: {val_res.errors}"

    # Compile execution plan
    delivery = get_default_delivery_profile("9:16")
    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_split_v_01",
    )

    assert "split=2" in plan.filter_complex_string
    assert "vstack=inputs=2" in plan.filter_complex_string
    assert plan.video_encoder in ("libx264", "h264_nvenc")


def test_multi_person_layout_graph_compilation_split_horizontal():
    spec = CompositionSpec.create_default(
        composition_id="comp_split_h",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=5000000,
        clip_start_us=0,
        clip_end_us=3000000,
    )
    spec.layout.layout_type = "split_horizontal"

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path="C:/videos/interview.mp4",
        output_file_path="C:/videos/output_split_h.mp4",
    )

    assert "node_v_split" in graph.nodes
    assert "node_v_stack" in graph.nodes

    val_res = GraphValidator.validate(graph)
    assert val_res.is_valid is True

    delivery = get_default_delivery_profile("9:16")
    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_split_h_01",
    )
    assert "hstack=inputs=2" in plan.filter_complex_string


def test_blurred_background_graph_compilation():
    spec = CompositionSpec.create_default(
        composition_id="comp_blur",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=5000000,
        clip_start_us=0,
        clip_end_us=3000000,
    )
    spec.layout.layout_type = "blurred_background"

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path="C:/videos/landscape.mp4",
        output_file_path="C:/videos/output_blur.mp4",
    )

    assert "node_v_bg_scale" in graph.nodes
    assert "node_v_bg_blur" in graph.nodes
    assert "node_v_fg_scale" in graph.nodes
    assert "node_v_overlay" in graph.nodes

    val_res = GraphValidator.validate(graph)
    assert val_res.is_valid is True

    delivery = get_default_delivery_profile("9:16")
    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_blur_01",
    )
    assert "boxblur" in plan.filter_complex_string
    assert "overlay" in plan.filter_complex_string


def test_picture_in_picture_graph_compilation():
    spec = CompositionSpec.create_default(
        composition_id="comp_pip",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=5000000,
        clip_start_us=0,
        clip_end_us=3000000,
    )
    spec.layout.layout_type = "picture_in_picture"

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path="C:/videos/presentation.mp4",
        output_file_path="C:/videos/output_pip.mp4",
    )

    assert "node_v_main_crop" in graph.nodes
    assert "node_v_pip_crop" in graph.nodes
    assert "node_v_pip_overlay" in graph.nodes

    val_res = GraphValidator.validate(graph)
    assert val_res.is_valid is True

    delivery = get_default_delivery_profile("9:16")
    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_pip_01",
    )
    assert "overlay" in plan.filter_complex_string


def test_layout_selector_intelligence():
    # 1. 0 faces -> blurred_background
    res1 = LayoutSelector.select_optimal_layout(
        face_tracks=[],
        active_speaker_tracks=[],
        speaker_turns_count=0,
    )
    assert res1 == "blurred_background"

    # 2. 2 active speakers with frequent dialogue turns -> split_vertical
    res2 = LayoutSelector.select_optimal_layout(
        face_tracks=[{"id": "f1"}, {"id": "f2"}],
        active_speaker_tracks=["spk_1", "spk_2"],
        speaker_turns_count=4,
    )
    assert res2 == "split_vertical"

    # 3. 1 active speaker -> single_full_frame
    res3 = LayoutSelector.select_optimal_layout(
        face_tracks=[{"id": "f1"}],
        active_speaker_tracks=["spk_1"],
        speaker_turns_count=1,
    )
    assert res3 == "single_full_frame"


@pytest.mark.asyncio
async def test_real_ffmpeg_rendering_split_vertical(sample_test_video: str, tmp_path):
    output_path = str(tmp_path / "rendered_split_vertical.mp4")

    spec = CompositionSpec.create_default(
        composition_id="comp_real_split_v",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=1000000,
        clip_start_us=0,
        clip_end_us=1000000,
    )
    spec.layout.layout_type = "split_vertical"

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=sample_test_video,
        output_file_path=output_path,
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_real_split_v",
    )

    # Execute FFmpeg rendering process
    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_real_split_v", total_duration=1.0)

    assert outcome.success is True, f"FFmpeg failed with return code {outcome.return_code}: {outcome.error_message}"
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 10000

    # Deep output validation via FFprobe
    val = OutputValidator.validate_file(output_path, delivery, expected_duration_seconds=1.0)
    assert val.is_valid is True, f"Output validation failed: {val.errors}"
    assert val.video_width == 1080
    assert val.video_height == 1920
    assert val.video_codec == "h264"


@pytest.mark.asyncio
async def test_real_ffmpeg_rendering_blurred_background(sample_test_video: str, tmp_path):
    output_path = str(tmp_path / "rendered_blurred_bg.mp4")

    spec = CompositionSpec.create_default(
        composition_id="comp_real_blur",
        project_id="proj_01",
        video_id="vid_01",
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=1000000,
        clip_start_us=0,
        clip_end_us=1000000,
    )
    spec.layout.layout_type = "blurred_background"

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=sample_test_video,
        output_file_path=output_path,
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_real_blur",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_real_blur", total_duration=1.0)

    assert outcome.success is True
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 10000

    val = OutputValidator.validate_file(output_path, delivery, expected_duration_seconds=1.0)
    assert val.is_valid is True, f"Output validation failed: {val.errors}"
    assert val.video_width == 1080
    assert val.video_height == 1920
