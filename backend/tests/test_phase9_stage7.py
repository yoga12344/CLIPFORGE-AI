"""
ClipForge AI - Phase 9 Stage 7 Test Suite
B-Roll Cutaways, Graphic Watermarks, Semantic B-Roll Matching, and Real FFmpeg Composite Rendering.
"""

import os
import subprocess
import pytest
from pathlib import Path

from app.composition.schemas.composition import CompositionSpec
from app.composition.schemas.layout import NormalizedRect
from app.composition.schemas.overlays import (
    OverlayCompositionConfig,
    BRollItemSpec,
    GraphicOverlaySpec
)
from app.composition.schemas.subtitles import (
    SubtitleCompositionConfig,
    SubtitleSegmentRef,
    SubtitleWordRef
)
from app.composition.schemas.delivery import get_default_delivery_profile
from app.composition.overlays.broll_matcher import BRollAsset, BRollMatcher
from app.composition.overlays.overlay_planner import OverlayPlanner
from app.composition.subtitles.subtitle_service import SubtitleCompositionService
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


def generate_synthetic_png(output_path: str, width: int = 200, height: int = 100) -> str:
    """Generate a simple PNG image for watermark testing."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=red@0.8:size={width}x{height}:duration=1",
        "-vframes", "1",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return output_path


def test_broll_matcher_keyword_overlap():
    """Verify transcript token extraction and automatic B-roll asset scheduling."""
    assets = [
        BRollAsset(
            asset_id="tech_01",
            asset_uri="asset://broll/tech_01",
            file_path="C:/media/tech.mp4",
            duration_us=5_000_000,
            tags=["artificial", "intelligence", "technology", "coding"],
            description="Futuristic technology and coding screens"
        ),
        BRollAsset(
            asset_id="city_01",
            asset_uri="asset://broll/city_01",
            file_path="C:/media/city.mp4",
            duration_us=4_000_000,
            tags=["city", "skyline", "urban", "traffic"],
            description="Aerial view of city traffic"
        ),
    ]

    segments = [
        SubtitleSegmentRef(
            segment_id="s1",
            start_us=0,
            end_us=3_000_000,
            text="Today we discuss artificial intelligence and the future.",
        ),
        SubtitleSegmentRef(
            segment_id="s2",
            start_us=6_000_000,
            end_us=9_000_000,
            text="Walking through the busy city center at night.",
        ),
    ]

    planned = BRollMatcher.match_transcript_to_broll(
        segments=segments,
        available_assets=assets,
        min_broll_duration_us=2_000_000,
        max_broll_duration_us=3_000_000,
        min_gap_between_brolls_us=2_000_000,
    )

    assert len(planned) == 2
    assert planned[0].asset_uri == "asset://broll/tech_01"
    assert planned[0].timeline_start_us == 0
    assert planned[0].duration_us == 3_000_000
    assert planned[1].asset_uri == "asset://broll/city_01"
    assert planned[1].timeline_start_us == 6_000_000


def test_overlay_planner_coordinates():
    """Verify pixel translation and enable expressions for graphic watermarks and B-roll."""
    graphic = GraphicOverlaySpec(
        graphic_id="logo_main",
        asset_uri="asset://images/logo_main",
        timeline_start_us=500_000,  # 0.5s
        duration_us=2_000_000,      # 2.0s -> ends 2.5s
        bounds=NormalizedRect(x=0.05, y=0.05, width=0.20, height=0.10),
        opacity=0.9
    )

    resolved = OverlayPlanner.resolve_graphic_placement(graphic, canvas_width=1080, canvas_height=1920)
    assert resolved.target_width == int(1080 * 0.20)
    assert resolved.target_height == int(1920 * 0.10)
    assert resolved.x_expr == str(int(1080 * 0.05))
    assert resolved.y_expr == str(int(1920 * 0.05))
    assert "between(t,0.500,2.500)" in resolved.enable_expr

    broll = BRollItemSpec(
        item_id="br1",
        asset_uri="asset://broll/cutaway_01",
        timeline_start_us=1_000_000,
        duration_us=2_000_000,
        display_mode="full_frame_cutaway"
    )
    res_broll = OverlayPlanner.resolve_broll_placement(broll, canvas_width=1080, canvas_height=1920)
    assert res_broll.target_width == 1080
    assert res_broll.target_height == 1920
    assert res_broll.x_expr == "0"
    assert res_broll.y_expr == "0"
    assert "between(t,1.000,3.000)" in res_broll.enable_expr


@pytest.mark.asyncio
async def test_render_with_broll_cutaway_real_ffmpeg(tmp_path):
    """Verify real FFmpeg execution rendering a composition with a B-roll cutaway insert."""
    main_video = str(tmp_path / "main.mp4")
    broll_video = str(tmp_path / "broll.mp4")
    out_video = str(tmp_path / "output_broll.mp4")

    generate_synthetic_mp4(main_video, duration_sec=2, width=1280, height=720)
    generate_synthetic_mp4(broll_video, duration_sec=1, width=1280, height=720)

    spec = CompositionSpec.create_default(
        composition_id="comp_broll_test",
        project_id="proj_broll",
        video_id="vid_broll",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=2000000,
        clip_start_us=0,
        clip_end_us=2000000,
    )

    spec.overlays.b_roll_items = [
        BRollItemSpec(
            item_id="broll_item_1",
            asset_uri="asset://broll/cutaway_clip",
            timeline_start_us=500_000,  # 0.5s to 1.5s
            duration_us=1_000_000,
            source_offset_us=0,
            display_mode="full_frame_cutaway",
            opacity=1.0,
        )
    ]

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=main_video,
        output_file_path=out_video,
        asset_resolver={"asset://broll/cutaway_clip": broll_video},
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_broll_cutaway",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_broll_cutaway", total_duration=2.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=2.0)
    assert val.is_valid is True, f"Validation errors: {val.errors}"
    assert val.video_width == 1080
    assert val.video_height == 1920


@pytest.mark.asyncio
async def test_render_with_graphic_watermark_real_ffmpeg(tmp_path):
    """Verify real FFmpeg execution rendering a composition with an image watermark."""
    main_video = str(tmp_path / "main.mp4")
    logo_img = str(tmp_path / "logo.png")
    out_video = str(tmp_path / "output_watermark.mp4")

    generate_synthetic_mp4(main_video, duration_sec=1, width=1280, height=720)
    generate_synthetic_png(logo_img, width=200, height=100)

    spec = CompositionSpec.create_default(
        composition_id="comp_wm_test",
        project_id="proj_wm",
        video_id="vid_wm",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=1000000,
        clip_start_us=0,
        clip_end_us=1000000,
    )

    spec.overlays.graphic_items = [
        GraphicOverlaySpec(
            graphic_id="logo_wm",
            asset_uri="asset://images/channel_badge",
            timeline_start_us=0,
            duration_us=1_000_000,
            bounds=NormalizedRect(x=0.75, y=0.03, width=0.20, height=0.06),
            opacity=1.0,
        )
    ]

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=main_video,
        output_file_path=out_video,
        asset_resolver={"asset://images/channel_badge": logo_img},
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_watermark",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_watermark", total_duration=1.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=1.0)
    assert val.is_valid is True, f"Validation errors: {val.errors}"


@pytest.mark.asyncio
async def test_render_composite_broll_watermark_and_subtitles(tmp_path):
    """Verify complex composition with video, B-roll cutaway, watermark, and subtitles combined."""
    main_video = str(tmp_path / "main.mp4")
    broll_video = str(tmp_path / "broll.mp4")
    logo_img = str(tmp_path / "logo.png")
    out_video = str(tmp_path / "output_all_in_one.mp4")

    generate_synthetic_mp4(main_video, duration_sec=2, width=1280, height=720)
    generate_synthetic_mp4(broll_video, duration_sec=1, width=1280, height=720)
    generate_synthetic_png(logo_img, width=200, height=100)

    # Subtitles
    sub_cfg = SubtitleCompositionConfig(
        enabled=True,
        preset_id="preset_bold_creator",
        segments=[
            SubtitleSegmentRef(
                segment_id="s1",
                start_us=0,
                end_us=2_000_000,
                text="All in One Composite Test",
                words=[
                    SubtitleWordRef(word="All", start_us=0, end_us=500_000),
                    SubtitleWordRef(word="in", start_us=500_000, end_us=1_000_000),
                    SubtitleWordRef(word="One", start_us=1_000_000, end_us=1_500_000),
                    SubtitleWordRef(word="Test", start_us=1_500_000, end_us=2_000_000),
                ],
            )
        ]
    )

    ass_path = SubtitleCompositionService.generate_subtitles_for_composition(
        subtitle_config=sub_cfg,
        output_dir=str(tmp_path),
        composition_id="comp_all",
        version_number=1,
    )

    spec = CompositionSpec.create_default(
        composition_id="comp_all_test",
        project_id="proj_all",
        video_id="vid_all",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=2000000,
        clip_start_us=0,
        clip_end_us=2000000,
    )

    spec.overlays.b_roll_items = [
        BRollItemSpec(
            item_id="br_1",
            asset_uri="asset://broll/cutaway_insert",
            timeline_start_us=500_000,
            duration_us=1_000_000,
            display_mode="full_frame_cutaway",
        )
    ]
    spec.overlays.graphic_items = [
        GraphicOverlaySpec(
            graphic_id="logo_1",
            asset_uri="asset://images/logo_watermark",
            timeline_start_us=0,
            duration_us=2_000_000,
            bounds=NormalizedRect(x=0.05, y=0.03, width=0.15, height=0.05),
        )
    ]

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=main_video,
        output_file_path=out_video,
        ass_subtitle_path=ass_path,
        asset_resolver={
            "asset://broll/cutaway_insert": broll_video,
            "asset://images/logo_watermark": logo_img,
        }
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_all_in_one",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_all_in_one", total_duration=2.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=2.0)
    assert val.is_valid is True, f"Validation errors: {val.errors}"
    assert val.video_width == 1080
    assert val.video_height == 1920
