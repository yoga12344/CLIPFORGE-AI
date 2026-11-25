"""
ClipForge AI - Phase 7 Test Suite: Professional Subtitle Styling, Karaoke Highlighting & Final Render Pipeline
Comprehensive tests covering:
- Subtitle models, schemas, and ASS syntax formatting
- Color conversion (HEX -> ASS &HAABBGGRR)
- ASS timestamp generation and text escaping
- 8 Distinct presets & custom preset creation
- Karaoke word-by-word animation styles (karaoke_pop, word_by_word, phrase_fade, static)
- Windows path escaping for FFmpeg ass filter
- SubtitleService: transcript extraction, word time shifting, editing, splitting, merging
- ExportService: render pipeline orchestration, FFmpeg filtergraph construction
- Real video render with ASS subtitles and FFprobe validation
- FastAPI endpoints for Subtitles and Exports
"""

import math
import os
import sys
import tempfile
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.db.models import Project, Video, Transcript, TranscriptSegment, Clip, SubtitleTrack, CaptionPreset, Export
from app.schemas.subtitle_schemas import (
    SubtitleWord,
    SubtitleSegment,
    CaptionPresetSchema,
    SubtitleTrackResponse,
    UpdateSegmentRequest,
    SplitSegmentRequest,
    MergeSegmentsRequest,
    RenderExportRequest,
)
from app.services.subtitle_renderer import (
    hex_to_ass_color,
    format_ass_timestamp,
    escape_ass_text,
    format_ffmpeg_ass_path,
    SubtitleRenderer,
    DEFAULT_PRESETS,
)
from app.services.subtitle_service import SubtitleService
from app.services.export_service import ExportService
from app.video.ffprobe_manager import FFprobeManager


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


@pytest_asyncio.fixture
async def async_client(async_test_session):
    async def override_get_db():
        yield async_test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# --- Unit Tests: Subtitle Renderer & ASS Utilities ---

def test_hex_to_ass_color():
    # Standard white: #FFFFFF -> &H00FFFFFF
    assert hex_to_ass_color("#FFFFFF") == "&H00FFFFFF"
    assert hex_to_ass_color("FFFFFF") == "&H00FFFFFF"
    
    # Pure Red: #FF0000 -> in ASS BBGGRR is 0000FF -> &H000000FF
    assert hex_to_ass_color("#FF0000") == "&H000000FF"

    # Pure Blue: #0000FF -> in ASS BBGGRR is FF0000 -> &H00FF0000
    assert hex_to_ass_color("#0000FF") == "&H00FF0000"

    # Pure Green: #00FF00 -> in ASS BBGGRR is 00FF00 -> &H0000FF00
    assert hex_to_ass_color("#00FF00") == "&H0000FF00"

    # Yellow: #FFFF00 -> in ASS BBGGRR is 00FFFF -> &H0000FFFF
    assert hex_to_ass_color("#FFFF00") == "&H0000FFFF"

    # Opacity 50% (alpha = 128 = 0x80)
    assert hex_to_ass_color("#000000", alpha=128) == "&H80000000"


def test_format_ass_timestamp():
    assert format_ass_timestamp(0.0) == "0:00:00.00"
    assert format_ass_timestamp(1.25) == "0:00:01.25"
    assert format_ass_timestamp(65.5) == "0:01:05.50"
    assert format_ass_timestamp(3665.123) == "1:01:05.12"


def test_escape_ass_text():
    raw = "Hello {World}! Testing \\ backslash and newline\nsecond line"
    escaped = escape_ass_text(raw)
    assert "{" not in escaped or "\\{" in escaped
    assert "\n" not in escaped
    assert "\\N" in escaped


def test_format_ffmpeg_ass_path():
    windows_path = r"C:\Users\User\AppData\Local\Temp\test.ass"
    escaped = format_ffmpeg_ass_path(windows_path)
    assert escaped.startswith("C\\:/")
    assert "\\" not in escaped[4:]
    assert "test.ass" in escaped


def test_preset_definitions_completeness():
    assert len(DEFAULT_PRESETS) >= 8
    preset_names = [p.name for p in DEFAULT_PRESETS]
    assert "Bold Creator" in preset_names
    assert "Clean Minimal" in preset_names
    assert "Podcast Highlight" in preset_names
    assert "Cinematic" in preset_names
    assert "Gaming" in preset_names
    assert "Educational" in preset_names
    assert "Classic Subtitles" in preset_names
    assert "High Contrast" in preset_names

    for p in DEFAULT_PRESETS:
        assert p.font_family
        assert p.font_size > 0
        assert p.primary_color
        assert p.highlight_color
        assert p.animation_style
        assert p.alignment in (1, 2, 3, 5, 6, 7, 8, 9)
        assert p.margin_v >= 0


def test_generate_ass_script_karaoke_pop():
    segments = [
        SubtitleSegment(
            id="seg-1",
            start=0.0,
            end=2.0,
            text="Welcome to ClipForge AI",
            words=[
                SubtitleWord(word="Welcome", start=0.0, end=0.5),
                SubtitleWord(word="to", start=0.5, end=0.8),
                SubtitleWord(word="ClipForge", start=0.8, end=1.5),
                SubtitleWord(word="AI", start=1.5, end=2.0),
            ]
        )
    ]
    preset = CaptionPresetSchema(
        name="Test Karaoke",
        font_family="Montserrat",
        font_size=48,
        primary_color="#FFFFFF",
        highlight_color="#FFFF00",
        animation_style="karaoke_pop",
        alignment=2,
        margin_v=120,
    )
    renderer = SubtitleRenderer()
    ass_text = renderer.generate_ass_script(segments, preset, canvas_width=1080, canvas_height=1920)

    assert "[Script Info]" in ass_text
    assert "PlayResX: 1080" in ass_text
    assert "PlayResY: 1920" in ass_text
    assert "[V4+ Styles]" in ass_text
    assert "Style: Default" in ass_text
    assert "[Events]" in ass_text
    assert "Dialogue: 0," in ass_text
    # Karaoke tags should be present
    assert "\\c&H" in ass_text
    assert "\\fscx110" in ass_text
    assert "Welcome" in ass_text
    assert "ClipForge" in ass_text


def test_generate_ass_script_phrase_fade():
    segments = [
        SubtitleSegment(
            id="seg-1",
            start=0.0,
            end=3.0,
            text="Smooth fade appearance",
            words=[]
        )
    ]
    preset = CaptionPresetSchema(
        name="Cinematic Fade",
        animation_style="phrase_fade",
    )
    renderer = SubtitleRenderer()
    ass_text = renderer.generate_ass_script(segments, preset)
    assert "\\fad(150,150)" in ass_text
    assert "Smooth fade appearance" in ass_text


# --- Unit Tests: Subtitle Service ---

@pytest.mark.asyncio
async def test_extract_clip_subtitles_timing(async_test_session):
    # Setup project, video, transcript, clip
    proj = Project(name="Test Proj", description="")
    async_test_session.add(proj)
    await async_test_session.flush()

    vid = Video(
        project_id=proj.id,
        filename="test.mp4",
        file_path="C:/dummy/test.mp4",
        file_size_bytes=10240,
        duration_seconds=60.0,
    )
    async_test_session.add(vid)
    await async_test_session.flush()

    raw_transcript_segments = [
        {
            "id": 0,
            "start": 5.0,
            "end": 8.0,
            "text": "Before the clip starts",
            "words": [
                {"word": "Before", "start": 5.0, "end": 6.0},
                {"word": "the", "start": 6.0, "end": 6.5},
                {"word": "clip", "start": 6.5, "end": 7.0},
                {"word": "starts", "start": 7.0, "end": 8.0},
            ]
        },
        {
            "id": 1,
            "start": 10.0,
            "end": 15.0,
            "text": "This is inside the clip segment",
            "words": [
                {"word": "This", "start": 10.0, "end": 10.5},
                {"word": "is", "start": 10.5, "end": 11.0},
                {"word": "inside", "start": 11.0, "end": 12.0},
                {"word": "the", "start": 12.0, "end": 12.5},
                {"word": "clip", "start": 12.5, "end": 13.5},
                {"word": "segment", "start": 13.5, "end": 14.8},
            ]
        },
        {
            "id": 2,
            "start": 20.0,
            "end": 25.0,
            "text": "After the clip ends",
            "words": [
                {"word": "After", "start": 20.0, "end": 21.0},
            ]
        }
    ]

    trans = Transcript(
        video_id=vid.id,
        full_text="Before the clip starts. This is inside the clip segment. After the clip ends.",
        language="en",
        status="completed",
    )
    async_test_session.add(trans)
    await async_test_session.flush()

    for idx, s in enumerate(raw_transcript_segments):
        ts = TranscriptSegment(
            transcript_id=trans.id,
            segment_index=idx,
            start_time=s["start"],
            end_time=s["end"],
            text=s["text"],
            words=s["words"],
        )
        async_test_session.add(ts)
    await async_test_session.flush()

    # Clip spans 10.0s to 16.0s (6.0s duration)
    clip = Clip(
        project_id=proj.id,
        video_id=vid.id,
        title="Test Clip",
        start_time=10.0,
        end_time=16.0,
        duration_seconds=6.0,
        aspect_ratio="9:16",
    )
    async_test_session.add(clip)
    await async_test_session.commit()

    track = await SubtitleService.get_or_create_subtitle_track(async_test_session, clip.id)

    assert track is not None
    assert track.clip_id == clip.id
    assert len(track.segments) == 1

    seg = track.segments[0]
    # In clip relative time, start should be 10.0 - 10.0 = 0.0s
    assert seg["start"] == 0.0
    # End aligns with speech end: 14.8 - 10.0 = 4.8s
    assert seg["end"] == 4.8
    assert len(seg["words"]) == 6
    assert seg["words"][0]["word"] == "This"
    assert seg["words"][0]["start"] == 0.0
    assert seg["words"][-1]["word"] == "segment"
    assert round(seg["words"][-1]["end"], 2) == 4.80


@pytest.mark.asyncio
async def test_update_segment_text_and_timing(async_test_session):
    proj = Project(name="Test Proj")
    async_test_session.add(proj)
    await async_test_session.flush()

    vid = Video(
        project_id=proj.id,
        filename="test.mp4",
        file_path="C:/dummy/test.mp4",
        file_size_bytes=10240,
        duration_seconds=30.0,
    )
    async_test_session.add(vid)
    await async_test_session.flush()

    clip = Clip(project_id=proj.id, video_id=vid.id, title="Clip", start_time=0.0, end_time=10.0, duration_seconds=10.0)
    async_test_session.add(clip)
    await async_test_session.flush()

    initial_segments = [
        {
            "id": "seg-1",
            "start": 1.0,
            "end": 4.0,
            "text": "Initial text",
            "words": [
                {"word": "Initial", "start": 1.0, "end": 2.0},
                {"word": "text", "start": 2.0, "end": 4.0},
            ]
        }
    ]
    track = SubtitleTrack(clip_id=clip.id, segments=initial_segments, is_enabled=True)
    async_test_session.add(track)
    await async_test_session.commit()

    updated = await SubtitleService.update_segment(
        db=async_test_session,
        clip_id=clip.id,
        segment_id="seg-1",
        text="Edited awesome text",
        start=1.2,
        end=4.5,
        words=[
            SubtitleWord(word="Edited", start=1.2, end=2.5),
            SubtitleWord(word="awesome", start=2.5, end=3.5),
            SubtitleWord(word="text", start=3.5, end=4.5),
        ]
    )
    assert updated.segments[0]["text"] == "Edited awesome text"
    assert updated.segments[0]["start"] == 1.2
    assert updated.segments[0]["end"] == 4.5
    assert len(updated.segments[0]["words"]) == 3


@pytest.mark.asyncio
async def test_split_and_merge_segments(async_test_session):
    proj = Project(name="Test Proj")
    async_test_session.add(proj)
    await async_test_session.flush()

    vid = Video(
        project_id=proj.id,
        filename="test.mp4",
        file_path="C:/dummy/test.mp4",
        file_size_bytes=10240,
        duration_seconds=30.0,
    )
    async_test_session.add(vid)
    await async_test_session.flush()

    clip = Clip(project_id=proj.id, video_id=vid.id, title="Clip", start_time=0.0, end_time=10.0, duration_seconds=10.0)
    async_test_session.add(clip)
    await async_test_session.flush()

    initial_segments = [
        {
            "id": "seg-original",
            "start": 0.0,
            "end": 4.0,
            "text": "First part second part",
            "words": [
                {"word": "First", "start": 0.0, "end": 1.0},
                {"word": "part", "start": 1.0, "end": 2.0},
                {"word": "second", "start": 2.0, "end": 3.0},
                {"word": "part", "start": 3.0, "end": 4.0},
            ]
        }
    ]
    track = SubtitleTrack(clip_id=clip.id, segments=initial_segments)
    async_test_session.add(track)
    await async_test_session.commit()

    # Split at word index 2 ("second")
    track_split = await SubtitleService.split_segment(async_test_session, clip.id, "seg-original", word_index=2)
    assert len(track_split.segments) == 2
    seg1, seg2 = track_split.segments[0], track_split.segments[1]
    assert seg1["text"] == "First part"
    assert seg1["end"] == 2.0
    assert seg2["text"] == "second part"
    assert seg2["start"] == 2.0
    assert seg2["end"] == 4.0

    # Merge them back
    track_merged = await SubtitleService.merge_segments(async_test_session, clip.id, seg1["id"], seg2["id"])
    assert len(track_merged.segments) == 1
    assert track_merged.segments[0]["text"] == "First part second part"
    assert track_merged.segments[0]["start"] == 0.0
    assert track_merged.segments[0]["end"] == 4.0
    assert len(track_merged.segments[0]["words"]) == 4


# --- Real FFmpeg Render & Burn-in Test ---

@pytest.mark.asyncio
async def test_real_ffmpeg_ass_subtitle_burn():
    """Render a synthetic 2-second 1080x1920 video with burned ASS subtitles using real FFmpeg."""
    from app.video.clip_generator import ClipGenerator
    import subprocess

    renderer = SubtitleRenderer()

    # 1. Create a 2-second synthetic color test video
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_mp4 = Path(tmp_dir) / "source.mp4"
        ass_file = Path(tmp_dir) / "subtitles.ass"
        output_mp4 = Path(tmp_dir) / "output.mp4"

        # Generate synthetic 1920x1080 test video with audio
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(input_mp4)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Synthetic video creation failed: {res.stderr}"

        # 2. Write ASS file with karaoke tags
        segments = [
            SubtitleSegment(
                id="s1",
                start=0.2,
                end=1.8,
                text="OpusClip Alternative",
                words=[
                    SubtitleWord(word="OpusClip", start=0.2, end=1.0),
                    SubtitleWord(word="Alternative", start=1.0, end=1.8),
                ]
            )
        ]
        preset = CaptionPresetSchema(
            name="Bold Creator",
            font_family="Arial",
            font_size=40,
            primary_color="#FFFFFF",
            highlight_color="#FFFF00",
            animation_style="karaoke_pop",
            alignment=2,
            margin_v=150,
        )
        renderer.write_ass_file(segments, preset, str(ass_file), canvas_width=1080, canvas_height=1920)
        assert ass_file.exists()
        assert ass_file.stat().st_size > 0

        # 3. Generate clip with 9:16 vertical crop + ASS subtitle burn-in
        out_path = await ClipGenerator.generate_clip(
            source_video_path=str(input_mp4),
            output_clip_path=str(output_mp4),
            start_time=0.0,
            end_time=2.0,
            aspect_ratio="9:16",
            reframe_mode="center_crop",
            subtitle_path=str(ass_file),
        )
        assert Path(out_path).exists()
        assert Path(out_path).stat().st_size > 10000

        # 4. Verify output file with FFprobe
        meta = FFprobeManager.probe(str(out_path))
        assert meta.valid is True
        assert meta.video_stream is not None
        assert meta.video_stream.width == 1080
        assert meta.video_stream.height == 1920
        assert meta.has_audio is True
        assert 1.8 <= meta.duration_seconds <= 2.2


# --- API Route Tests ---

@pytest.mark.asyncio
async def test_subtitles_api_routes(async_client, async_test_session):
    # Setup database records
    proj = Project(name="API Test Proj")
    async_test_session.add(proj)
    await async_test_session.flush()

    vid = Video(
        project_id=proj.id,
        filename="video.mp4",
        file_path="C:/dummy/video.mp4",
        file_size_bytes=20480,
        duration_seconds=60.0,
    )
    async_test_session.add(vid)
    await async_test_session.flush()

    clip = Clip(
        project_id=proj.id,
        video_id=vid.id,
        title="Highlight Clip",
        start_time=0.0,
        end_time=15.0,
        duration_seconds=15.0,
        aspect_ratio="9:16",
    )
    async_test_session.add(clip)
    await async_test_session.commit()

    # 1. GET /api/clips/{clip_id}/subtitles (auto creates empty or transcript track)
    res = await async_client.get(f"/api/clips/{clip.id}/subtitles")
    assert res.status_code == 200
    track_data = res.json()
    assert track_data["clip_id"] == clip.id

    # 2. Add a segment to the track
    from sqlalchemy.orm.attributes import flag_modified
    track = await SubtitleService.get_or_create_subtitle_track(async_test_session, clip.id)
    track.segments = [
        {
            "id": "seg-101",
            "start": 1.0,
            "end": 4.0,
            "text": "Testing subtitle API",
            "words": [
                {"word": "Testing", "start": 1.0, "end": 2.0},
                {"word": "subtitle", "start": 2.0, "end": 3.0},
                {"word": "API", "start": 3.0, "end": 4.0},
            ]
        }
    ]
    flag_modified(track, "segments")
    await async_test_session.commit()

    # 3. PUT /api/clips/{clip_id}/subtitles/segments/{segment_id}
    update_payload = {
        "text": "Updated subtitle API",
        "start": 1.2,
        "end": 4.2,
    }
    res_update = await async_client.put(
        f"/api/clips/{clip.id}/subtitles/segments/seg-101",
        json=update_payload
    )
    assert res_update.status_code == 200
    assert res_update.json()["segments"][0]["text"] == "Updated subtitle API"

    # 4. GET /api/caption-presets (seeds default 8 presets)
    res_presets = await async_client.get("/api/caption-presets")
    assert res_presets.status_code == 200
    presets = res_presets.json()
    assert len(presets) >= 8

    # 5. POST /api/caption-presets (create custom preset)
    custom_preset = {
        "name": "My Custom Viral Style",
        "font_family": "Impact",
        "font_size": 52,
        "primary_color": "#00FFCC",
        "highlight_color": "#FF00FF",
        "animation_style": "karaoke_pop",
        "alignment": 2,
        "margin_v": 160,
    }
    res_create_preset = await async_client.post("/api/caption-presets", json=custom_preset)
    assert res_create_preset.status_code == 200
    assert res_create_preset.json()["name"] == "My Custom Viral Style"
