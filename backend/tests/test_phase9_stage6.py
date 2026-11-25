"""
ClipForge AI - Phase 9 Stage 6 Tests
Professional Subtitle Composition: Presets, Overrides, Karaoke, Collision Avoidance & FFmpeg Burn.
"""

import os
import subprocess
import tempfile
import pytest
from pathlib import Path

from app.composition.schemas.subtitles import (
    SubtitleCompositionConfig,
    SubtitleSegmentRef,
    SubtitleWordRef,
    SubtitleStyleOverrides,
    SubtitleCollisionConfig,
)
from app.composition.schemas.composition import CompositionSpec
from app.composition.schemas.delivery import get_default_delivery_profile
from app.composition.subtitles.subtitle_presets import SubtitlePresetRegistry
from app.composition.subtitles.collision_avoidance import (
    CollisionAvoidancePlanner,
    FaceBoxSample,
    SubtitlePlacementDirective,
)
from app.composition.subtitles.karaoke_generator import (
    SubtitleKaraokeGenerator,
    us_to_ass_timestamp,
)
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
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"FFmpeg failed: {res.stderr}"
    return output_path


def test_preset_registry_and_overrides():
    """Verify built-in presets and style override application."""
    presets = SubtitlePresetRegistry.list_presets()
    assert "preset_bold_creator" in presets
    assert "preset_clean_minimal" in presets
    assert "preset_podcast_highlight" in presets
    assert "preset_cinematic" in presets
    assert "preset_gaming" in presets
    assert "preset_educational" in presets
    assert "preset_classic_subtitles" in presets
    assert "preset_high_contrast" in presets

    base = SubtitlePresetRegistry.get_preset("preset_bold_creator")
    assert base.font_family == "Arial Black"
    assert base.font_size == 72

    overrides = SubtitleStyleOverrides(
        font_family="Roboto",
        font_size=80,
        highlight_color="#FF00FF",
        bold=False,
    )
    custom = SubtitlePresetRegistry.apply_overrides(base, overrides)
    assert custom.font_family == "Roboto"
    assert custom.font_size == 80
    assert custom.highlight_color == "#FF00FF"
    assert custom.bold is False


def test_speaker_specific_styling():
    """Verify distinct styles per speaker are properly registered in ASS header."""
    config = SubtitleCompositionConfig(
        enabled=True,
        preset_id="preset_bold_creator",
        segments=[
            SubtitleSegmentRef(
                segment_id="seg1",
                start_us=0,
                end_us=1_000_000,
                text="Hello from speaker one",
                speaker_id="SPEAKER_00",
                words=[
                    SubtitleWordRef(word="Hello", start_us=0, end_us=500_000),
                    SubtitleWordRef(word="there", start_us=500_000, end_us=1_000_000),
                ],
            ),
            SubtitleSegmentRef(
                segment_id="seg2",
                start_us=1_000_000,
                end_us=2_000_000,
                text="And I am speaker two",
                speaker_id="SPEAKER_01",
                words=[
                    SubtitleWordRef(word="And", start_us=1_000_000, end_us=1_500_000),
                    SubtitleWordRef(word="I", start_us=1_500_000, end_us=2_000_000),
                ],
            ),
        ],
        speaker_styles={
            "SPEAKER_01": SubtitleStyleOverrides(highlight_color="#00FFFF")
        }
    )

    gen = SubtitleKaraokeGenerator(config)
    script = gen.generate_ass_script()

    # Verify both speaker styles appear in [V4+ Styles]
    assert "Style: SPEAKER_00" in script
    assert "Style: SPEAKER_01" in script
    # Verify dialogue lines use their speaker style names
    assert ",SPEAKER_00," in script
    assert ",SPEAKER_01," in script


def test_karaoke_pop_word_timing():
    """Verify word-level timing and karaoke pop scale tags."""
    config = SubtitleCompositionConfig(
        enabled=True,
        preset_id="preset_bold_creator",
        segments=[
            SubtitleSegmentRef(
                segment_id="seg1",
                start_us=500_000,  # 0.5s
                end_us=1_500_000,  # 1.5s
                text="Viral video clips",
                words=[
                    SubtitleWordRef(word="Viral", start_us=500_000, end_us=800_000),
                    SubtitleWordRef(word="video", start_us=800_000, end_us=1_200_000),
                    SubtitleWordRef(word="clips", start_us=1_200_000, end_us=1_500_000),
                ],
            )
        ]
    )

    gen = SubtitleKaraokeGenerator(config)
    script = gen.generate_ass_script()

    # Active word pop tag should be present
    assert r"\fscx110\fscy110" in script
    # Timestamp checks
    assert "0:00:00.50" in script
    assert "0:00:01.50" in script


def test_animation_styles_variants():
    """Verify word_by_word, phrase_fade, and static animation styles."""
    for style in ["word_by_word", "phrase_fade", "static"]:
        config = SubtitleCompositionConfig(
            enabled=True,
            preset_id="preset_bold_creator",
            style_overrides=SubtitleStyleOverrides(animation_style=style),
            segments=[
                SubtitleSegmentRef(
                    segment_id="seg1",
                    start_us=0,
                    end_us=1_000_000,
                    text="Testing styles",
                    words=[
                        SubtitleWordRef(word="Testing", start_us=0, end_us=500_000),
                        SubtitleWordRef(word="styles", start_us=500_000, end_us=1_000_000),
                    ],
                )
            ]
        )
        gen = SubtitleKaraokeGenerator(config)
        script = gen.generate_ass_script()
        if style == "phrase_fade":
            assert r"\fad(150,150)" in script
        elif style == "static":
            assert r"\fscx" not in script
            assert r"\fad" not in script


def test_collision_avoidance_margin_shift():
    """Verify that when a face is detected in the subtitle region, margin_v is increased."""
    planner = CollisionAvoidancePlanner(
        config=SubtitleCollisionConfig(enabled=True, min_clearance_fraction=0.02),
        canvas_width=1080,
        canvas_height=1920,
        base_bottom_margin=280,
        subtitle_box_height=160,
    )

    # Subtitle region baseline: bottom at 1920 - 280 = 1640. Top at 1640 - 160 = 1480.
    # Face placed at Y=1500 with height 200 (Y spans 1500 to 1700) -> Collides!
    face = FaceBoxSample(timestamp_s=0.5, x=400, y=1500, width=280, height=200)

    directive = planner.calculate_placement(
        start_s=0.0,
        end_s=1.0,
        face_boxes=[face],
    )

    # Clearance is 1920 * 0.02 = 38px
    # Subtitle bottom must be at <= 1500 - 38 = 1462
    # MarginV = 1920 - 1462 = 458px (shifted up from base 280)
    assert directive.margin_v > 280
    assert directive.alignment == 2


def test_collision_avoidance_top_relocation():
    """Verify that when face spans too low/high, subtitles flip to top_safe alignment 8."""
    planner = CollisionAvoidancePlanner(
        config=SubtitleCollisionConfig(enabled=True, min_clearance_fraction=0.02),
        canvas_width=1080,
        canvas_height=1920,
        base_bottom_margin=280,
        subtitle_box_height=160,
    )

    # Face covers massive portion from Y=600 to Y=1800
    face = FaceBoxSample(timestamp_s=0.5, x=200, y=600, width=680, height=1200)

    directive = planner.calculate_placement(
        start_s=0.0,
        end_s=1.0,
        face_boxes=[face],
    )

    # Pushing upward would exceed 60% of canvas height, so it relocates to top_safe (alignment 8)
    assert directive.alignment == 8


def test_subtitle_service_file_generation():
    """Verify end-to-end ASS file creation via SubtitleCompositionService."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = SubtitleCompositionConfig(
            enabled=True,
            preset_id="preset_podcast_highlight",
            segments=[
                SubtitleSegmentRef(
                    segment_id="s1",
                    start_us=0,
                    end_us=1_500_000,
                    text="Welcome to ClipForge AI",
                    speaker_id="SPEAKER_00",
                    words=[
                        SubtitleWordRef(word="Welcome", start_us=0, end_us=500_000),
                        SubtitleWordRef(word="to", start_us=500_000, end_us=800_000),
                        SubtitleWordRef(word="ClipForge", start_us=800_000, end_us=1_200_000),
                        SubtitleWordRef(word="AI", start_us=1_200_000, end_us=1_500_000),
                    ],
                )
            ]
        )

        ass_path = SubtitleCompositionService.generate_subtitles_for_composition(
            subtitle_config=config,
            output_dir=tmp_dir,
            composition_id="comp_test_123",
            version_number=1,
            canvas_width=1080,
            canvas_height=1920,
        )

        assert ass_path is not None
        assert os.path.exists(ass_path)
        content = Path(ass_path).read_text(encoding="utf-8")
        assert "[Script Info]" in content
        assert "ClipForge" in content


@pytest.mark.asyncio
async def test_render_with_burned_subtitles_real_ffmpeg(tmp_path):
    """Real FFmpeg end-to-end execution testing subtitle burning into video."""
    src_video = str(tmp_path / "input.mp4")
    out_video = str(tmp_path / "output_burned.mp4")
    generate_synthetic_mp4(src_video, duration_sec=1, width=1280, height=720)

    # 1. Generate real subtitle file
    config = SubtitleCompositionConfig(
        enabled=True,
        preset_id="preset_bold_creator",
        segments=[
            SubtitleSegmentRef(
                segment_id="s1",
                start_us=0,
                end_us=1_000_000,
                text="Real ASS Burn Test",
                words=[
                    SubtitleWordRef(word="Real", start_us=0, end_us=250_000),
                    SubtitleWordRef(word="ASS", start_us=250_000, end_us=500_000),
                    SubtitleWordRef(word="Burn", start_us=500_000, end_us=750_000),
                    SubtitleWordRef(word="Test", start_us=750_000, end_us=1_000_000),
                ],
            )
        ]
    )

    ass_file = SubtitleCompositionService.generate_subtitles_for_composition(
        subtitle_config=config,
        output_dir=str(tmp_path),
        composition_id="burn_test",
        version_number=1,
        canvas_width=1080,
        canvas_height=1920,
    )

    # 2. Build composition spec
    spec = CompositionSpec.create_default(
        composition_id="comp_burn_test",
        project_id="proj_burn",
        video_id="vid_burn",
        source_width=1280,
        source_height=720,
        source_fps=30.0,
        source_duration_us=1000000,
        clip_start_us=0,
        clip_end_us=1000000,
    )

    graph = CompositionToGraphBuilder.build_graph(
        spec=spec,
        source_media_path=src_video,
        output_file_path=out_video,
        ass_subtitle_path=ass_file,
    )

    delivery = get_default_delivery_profile("9:16")
    delivery.video_codec = "libx264"

    plan = RenderGraphCompiler.compile(
        graph=graph,
        delivery=delivery,
        render_id="render_burn_sub",
    )

    outcome = await RenderProcessRunner.run_plan(plan=plan, process_id="render_burn_sub", total_duration=1.0)
    assert outcome.success is True, f"Render failed: {outcome.error_message}"
    assert os.path.exists(out_video)
    assert os.path.getsize(out_video) > 10000

    val = OutputValidator.validate_file(out_video, delivery, expected_duration_seconds=1.0)
    assert val.is_valid is True, f"Validation errors: {val.errors}"
    assert val.video_width == 1080
    assert val.video_height == 1920
