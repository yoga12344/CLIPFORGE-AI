"""
ClipForge AI - Master Release 1.0 Real-Media Acceptance & Performance Test Suite
Validates real synthetic video and audio rendering across multiple aspect ratios,
layouts, audio ducking, EBU R128 loudness mastering, unicode filenames, and path spaces.
"""

import os
import subprocess
import pytest
from pathlib import Path

from app.composition.schemas.composition import CompositionSpec
from app.composition.schemas.audio import (
    AudioCompositionConfig,
    VoiceDialogueConfig,
    BackgroundMusicConfig,
    AudioDuckingConfig,
    LoudnessMasteringConfig,
)
from app.composition.schemas.delivery import get_default_delivery_profile
from app.composition.render.graph.graph_builder import CompositionToGraphBuilder
from app.composition.render.compiler.ffmpeg_compiler import RenderGraphCompiler
from app.composition.render.execution.render_process import RenderProcessRunner
from app.composition.render.validation.output_validator import OutputValidator


def create_test_video(path: str, duration_sec: int = 2, width: int = 1280, height: int = 720) -> str:
    """Generate real MP4 test video with video pattern and stereo audio tone."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_sec}:size={width}x{height}:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_sec}:sample_rate=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac",
        path,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert res.returncode == 0, f"FFmpeg failed to create test video: {res.stderr.decode()}"
    return path


def create_test_audio(path: str, duration_sec: int = 2, freq: int = 880) -> str:
    """Generate real stereo audio file."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration_sec}:sample_rate=48000",
        "-c:a", "aac",
        path,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert res.returncode == 0, f"FFmpeg failed to create test audio: {res.stderr.decode()}"
    return path


@pytest.mark.asyncio
async def test_real_media_landscape_16x9_to_vertical_9x16_render(tmp_path: Path):
    """Test 1: Render 16:9 1280x720 video into 1080x1920 9:16 portrait reframe with valid MP4 output."""
    raw_video = str(tmp_path / "source_16x9.mp4")
    out_video = str(tmp_path / "rendered_9x16_master.mp4")
    create_test_video(raw_video, duration_sec=2, width=1280, height=720)

    spec = CompositionSpec.create_default(
        composition_id="comp_landscape_9x16",
        project_id="proj_acc",
        video_id="vid_raw",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=2_000_000,
        clip_start_us=0,
        clip_end_us=2_000_000,
        title="Landscape to Portrait Reframe",
    )

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=raw_video,
        output_file_path=out_video,
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_test_16x9_to_9x16",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_test_16x9_to_9x16", total_duration=2.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)
    assert os.path.getsize(out_video) > 5000

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=2.0)
    assert val.is_valid is True, f"Validation failed: {val.errors}"
    assert val.video_width == 1080
    assert val.video_height == 1920


@pytest.mark.asyncio
async def test_real_media_split_vertical_layout_render(tmp_path: Path):
    """Test 2: Render 2-person split vertical layout into 1080x1920 9:16."""
    raw_video = str(tmp_path / "source_interview.mp4")
    out_video = str(tmp_path / "rendered_split_vertical.mp4")
    create_test_video(raw_video, duration_sec=2, width=1280, height=720)

    spec = CompositionSpec.create_default(
        composition_id="comp_split_vert",
        project_id="proj_acc",
        video_id="vid_raw",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=2_000_000,
        clip_start_us=0,
        clip_end_us=2_000_000,
        title="Split Vertical 2-Person Interview",
    )
    spec.layout.layout_type = "split_vertical"

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=raw_video,
        output_file_path=out_video,
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_test_split_vert",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_test_split_vert", total_duration=2.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=2.0)
    assert val.is_valid is True, f"Validation failed: {val.errors}"
    assert val.video_width == 1080
    assert val.video_height == 1920


@pytest.mark.asyncio
async def test_real_media_audio_sidechain_ducking_mastering(tmp_path: Path):
    """Test 3: Render composition with Voice Dialogue + Background Music ducking + EBU R128 mastering."""
    raw_video = str(tmp_path / "source_voice.mp4")
    bgm_audio = str(tmp_path / "music_bgm.aac")
    out_video = str(tmp_path / "rendered_ducked_audio.mp4")

    create_test_video(raw_video, duration_sec=2, width=1280, height=720)
    create_test_audio(bgm_audio, duration_sec=2, freq=220)

    spec = CompositionSpec.create_default(
        composition_id="comp_ducked_audio",
        project_id="proj_acc",
        video_id="vid_raw",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=2_000_000,
        clip_start_us=0,
        clip_end_us=2_000_000,
        title="Ducked Audio Composition",
    )

    spec.audio.voice = VoiceDialogueConfig(gain_db=1.0, high_pass_filter_hz=80)
    spec.audio.music = BackgroundMusicConfig(
        asset_uri="asset://audio/music_track",
        gain_db=-14.0,
    )
    spec.audio.ducking = AudioDuckingConfig(
        enabled=True,
        threshold_db=-24.0,
        ratio=4.0,
        attack_ms=30,
        release_ms=250,
    )
    spec.audio.master_loudness = LoudnessMasteringConfig(
        enabled=True,
        integrated_lufs=-14.0,
        true_peak_dbtp=-1.5,
        loudness_range_lu=7.0,
    )

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=raw_video,
        output_file_path=out_video,
        asset_resolver={"asset://audio/music_track": bgm_audio},
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_ducked_audio_test",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_ducked_audio_test", total_duration=2.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=2.0)
    assert val.is_valid is True, f"Validation failed: {val.errors}"
    assert val.audio_channels == 2
    assert val.audio_sample_rate == 48000


@pytest.mark.asyncio
async def test_real_media_unicode_filename_and_spaces(tmp_path: Path):
    """Test 4: Handle paths with spaces and Unicode characters (Japanese, Cyrillic) safely."""
    unicode_dir = tmp_path / "My Videos" / "Пользователь 2026"
    unicode_dir.mkdir(parents=True, exist_ok=True)

    raw_video = str(unicode_dir / "исходник 日本語 clip.mp4")
    out_video = str(unicode_dir / "выход 9x16 clip.mp4")

    create_test_video(raw_video, duration_sec=2, width=1280, height=720)

    spec = CompositionSpec.create_default(
        composition_id="comp_unicode_space",
        project_id="proj_acc",
        video_id="vid_raw",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=2_000_000,
        clip_start_us=0,
        clip_end_us=2_000_000,
        title="Unicode & Space Path Test",
    )

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=raw_video,
        output_file_path=out_video,
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_unicode_test",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_unicode_test", total_duration=2.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)
    assert os.path.getsize(out_video) > 5000

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=2.0)
    assert val.is_valid is True, f"Validation failed: {val.errors}"


def test_real_media_deterministic_render_graph_hash(tmp_path: Path):
    """Test 5: Ensure identical CompositionSpec versions compile to identical filtergraph strings."""
    raw_video = str(tmp_path / "source_hash.mp4")
    out_video1 = str(tmp_path / "out1.mp4")
    out_video2 = str(tmp_path / "out2.mp4")
    create_test_video(raw_video, duration_sec=2, width=1280, height=720)

    spec = CompositionSpec.create_default(
        composition_id="comp_hash_check",
        project_id="proj_acc",
        video_id="vid_raw",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=2_000_000,
        clip_start_us=0,
        clip_end_us=2_000_000,
        title="Hash Check",
    )

    graph1 = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=raw_video,
        output_file_path=out_video1,
    )
    graph2 = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=raw_video,
        output_file_path=out_video2,
    )

    delivery = get_default_delivery_profile("9:16")
    plan1 = RenderGraphCompiler.compile(graph=graph1, delivery=delivery, render_id="r1")
    plan2 = RenderGraphCompiler.compile(graph=graph2, delivery=delivery, render_id="r2")

    # Command filter complex strings must be identical
    assert plan1.filter_complex_string == plan2.filter_complex_string
    assert len(plan1.filter_complex_string) > 20
