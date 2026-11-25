"""
ClipForge AI - Phase 9 Stage 8 Test Suite
Audio Mixing, Dynamic Sidechain Ducking, High-Pass Filtering, and Broadcast EBU R128 Loudness Mastering.
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
    LoudnessMasteringConfig
)
from app.composition.schemas.delivery import get_default_delivery_profile
from app.composition.audio.audio_mixer import db_to_linear, linear_to_db, AudioMixPlanner
from app.composition.audio.loudness_master import LoudnessMaster
from app.composition.render.graph.nodes import (
    AudioMixNode,
    SidechainCompressNode,
    HighPassFilterNode,
    LoudnessNormalizeNode
)
from app.composition.render.compiler.filter_compiler import FilterCompiler
from app.composition.render.graph.graph_builder import CompositionToGraphBuilder
from app.composition.render.compiler.ffmpeg_compiler import RenderGraphCompiler
from app.composition.render.execution.render_process import RenderProcessRunner
from app.composition.render.validation.output_validator import OutputValidator


def generate_synthetic_mp4(output_path: str, duration_sec: int = 2, width: int = 1280, height: int = 720) -> str:
    """Generate a clean synthetic MP4 with audio tone for testing."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_sec}:size={width}x{height}:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_sec}:sample_rate=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_path


def generate_synthetic_audio(output_path: str, duration_sec: int = 2, freq: int = 880) -> str:
    """Generate a clean synthetic AAC or MP3 audio file."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration_sec}:sample_rate=48000",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_path


def test_decibel_linear_conversions():
    """Verify decibel to linear multiplier conversion formulas."""
    assert db_to_linear(0.0) == 1.0
    assert abs(db_to_linear(-6.02) - 0.5) < 0.01
    assert abs(db_to_linear(-20.0) - 0.1) < 0.01
    assert linear_to_db(1.0) == 0.0
    assert abs(linear_to_db(0.5) - (-6.02)) < 0.1


def test_ducking_parameters_calculation():
    """Verify dynamic ducking parameter transformation for sidechaincompress."""
    duck_cfg = AudioDuckingConfig(
        enabled=True,
        duck_attenuation_db=-14.0,
        attack_ms=40,
        release_ms=300,
        threshold_db=-26.0,
        ratio=5.0,
    )
    params = AudioMixPlanner.calculate_ducking_parameters(duck_cfg)
    assert abs(params["threshold"] - db_to_linear(-26.0)) < 0.001
    assert params["attack"] == 40.0
    assert params["release"] == 300.0
    assert params["ratio"] == 5.0


def test_platform_loudness_presets():
    """Verify standard broadcast loudness targets."""
    yt = LoudnessMaster.get_preset("youtube_shorts")
    assert yt.integrated_lufs == -14.0
    assert yt.true_peak_dbtp == -1.0
    assert yt.loudness_range_lu == 7.0

    podcast = LoudnessMaster.get_preset("podcast")
    assert podcast.integrated_lufs == -16.0
    assert podcast.loudness_range_lu == 8.0


def test_audio_filter_nodes_compilation():
    """Verify filter expressions for audio mixing, sidechain compression, and loudness mastering."""
    mix_node = AudioMixNode(id="mix1", params={"inputs_count": 2, "duration": "first"})
    mix_expr = FilterCompiler.compile_node_filter(mix_node)
    assert "amix=inputs=2:duration=first" in mix_expr

    duck_node = SidechainCompressNode(
        id="sc1",
        params={"threshold": 0.05, "ratio": 4.0, "attack": 50.0, "release": 350.0}
    )
    duck_expr = FilterCompiler.compile_node_filter(duck_node)
    assert "sidechaincompress=" in duck_expr
    assert "ratio=4.0" in duck_expr
    assert "attack=50.0" in duck_expr

    hp_node = HighPassFilterNode(id="hp1", params={"frequency": 80})
    hp_expr = FilterCompiler.compile_node_filter(hp_node)
    assert hp_expr == "highpass=f=80"

    loud_node = LoudnessNormalizeNode(
        id="ln1",
        params={"target_lufs": -14.0, "max_true_peak_dbtp": -1.0, "lra": 7.0}
    )
    loud_expr = FilterCompiler.compile_node_filter(loud_node)
    assert "loudnorm=I=-14.0:TP=-1.0:LRA=7.0" in loud_expr


@pytest.mark.asyncio
async def test_real_ffmpeg_rendering_with_voice_and_music_ducking(tmp_path):
    """Verify real FFmpeg execution rendering video with voice dialogue, BGM, and sidechain ducking."""
    main_video = str(tmp_path / "main.mp4")
    music_audio = str(tmp_path / "bgm.aac")
    out_video = str(tmp_path / "output_ducked.mp4")

    generate_synthetic_mp4(main_video, duration_sec=2, width=1280, height=720)
    generate_synthetic_audio(music_audio, duration_sec=2, freq=220)

    spec = CompositionSpec.create_default(
        composition_id="comp_audio_duck",
        project_id="proj_audio",
        video_id="vid_audio",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=2000000,
        clip_start_us=0,
        clip_end_us=2000000,
    )

    spec.audio.voice = VoiceDialogueConfig(gain_db=2.0, high_pass_filter_hz=80)
    spec.audio.music = BackgroundMusicConfig(
        asset_uri="asset://audio/music_track",
        gain_db=-12.0,
    )
    spec.audio.ducking = AudioDuckingConfig(
        enabled=True,
        threshold_db=-24.0,
        ratio=4.0,
        attack_ms=50,
        release_ms=300,
    )
    spec.audio.master_loudness = LoudnessMasteringConfig(
        enabled=True,
        integrated_lufs=-14.0,
        true_peak_dbtp=-1.0,
        loudness_range_lu=7.0,
    )

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=main_video,
        output_file_path=out_video,
        asset_resolver={"asset://audio/music_track": music_audio},
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_ducked_audio",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_ducked_audio", total_duration=2.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=2.0)
    assert val.is_valid is True, f"Validation errors: {val.errors}"
    assert val.audio_channels == 2
    assert val.audio_sample_rate == 48000


@pytest.mark.asyncio
async def test_real_ffmpeg_rendering_with_loudness_mastering(tmp_path):
    """Verify EBU R128 loudness mastering in real rendering pipeline."""
    main_video = str(tmp_path / "main_loud.mp4")
    out_video = str(tmp_path / "output_mastered.mp4")

    generate_synthetic_mp4(main_video, duration_sec=1, width=1280, height=720)

    spec = CompositionSpec.create_default(
        composition_id="comp_loud_master",
        project_id="proj_audio",
        video_id="vid_audio",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=1000000,
        clip_start_us=0,
        clip_end_us=1000000,
    )

    spec.audio.master_loudness = LoudnessMasteringConfig(
        enabled=True,
        integrated_lufs=-16.0,
        true_peak_dbtp=-1.5,
        loudness_range_lu=8.0,
    )

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=main_video,
        output_file_path=out_video,
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_loudness_master",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_loudness_master", total_duration=1.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=1.0)
    assert val.is_valid is True, f"Validation errors: {val.errors}"
