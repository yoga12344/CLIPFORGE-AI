"""
ClipForge AI - Phase 9 Stage 4 Test Suite
Automated verification for Intelligent Composition Planner, Multi-modal Subject Evaluator,
Shot Selector, Transition Planner, and Speaker-Aware Reframing.
"""

import pytest
import uuid
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.core.database import Base, get_db
from app.core.security import verify_session_token
from app.main import app
from app.db.models import (
    Project,
    Video,
    Transcript,
    TranscriptSegment,
    HighlightCandidate,
    VisionAnalysis,
    FaceTrack,
    ActiveSpeakerInterval,
    SpeakerFaceAssociation,
    AudioAnalysis,
    Speaker,
    SpeakerTurn,
    ManualCropCorrection,
)
from app.composition.schemas.layout import NormalizedRect
from app.composition.schemas.camera import ManualOverride
from app.composition.planner import (
    SubjectEvaluator,
    SubjectCandidate,
    ShotSelector,
    ShotDecision,
    TransitionPlanner,
    CompositionPlannerService,
    CompositionPlanningError,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield async_session

    async def override_verify_token():
        return True

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_session_token] = override_verify_token

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

    app.dependency_overrides.clear()


# =========================================================================
# Unit Tests: SubjectEvaluator
# =========================================================================

def test_subject_evaluator_scoring():
    evaluator = SubjectEvaluator()

    face_tracks = [
        {
            "track_id": "track_1",
            "start_time": 0.0,
            "end_time": 10.0,
            "average_bbox": {"x": 0.1, "y": 0.2, "width": 0.25, "height": 0.3},
            "average_confidence": 0.9,
        },
        {
            "track_id": "track_2",
            "start_time": 0.0,
            "end_time": 10.0,
            "average_bbox": {"x": 0.65, "y": 0.2, "width": 0.20, "height": 0.25},
            "average_confidence": 0.85,
        },
    ]

    active_intervals = [
        {
            "face_track_id": "track_2",
            "start_time": 2.0,
            "end_time": 5.0,
            "state": "active_speaker",
            "confidence": 0.95,
        }
    ]

    speaker_turns = [
        {
            "speaker_id": "spk_2",
            "start_time": 2.0,
            "end_time": 5.0,
        }
    ]

    speaker_face_map = {"spk_2": "track_2"}

    # At t = 1.0 (neither is active speaker): track_1 has larger face and is slightly closer to center
    candidates_t1 = evaluator.evaluate_candidates_at(
        timestamp_sec=1.0,
        face_tracks=face_tracks,
        active_intervals=active_intervals,
        speaker_turns=speaker_turns,
        speaker_face_map=speaker_face_map,
    )
    assert len(candidates_t1) == 2
    assert candidates_t1[0].face_track_id == "track_1"
    assert not candidates_t1[0].is_active_speaker

    # At t = 3.0 (track_2 is active speaker): track_2 must be top candidate
    candidates_t3 = evaluator.evaluate_candidates_at(
        timestamp_sec=3.0,
        face_tracks=face_tracks,
        active_intervals=active_intervals,
        speaker_turns=speaker_turns,
        speaker_face_map=speaker_face_map,
    )
    assert len(candidates_t3) == 2
    assert candidates_t3[0].face_track_id == "track_2"
    assert candidates_t3[0].is_active_speaker
    assert candidates_t3[0].strategy == "active_speaker"
    assert candidates_t3[0].importance_score > candidates_t3[1].importance_score


# =========================================================================
# Unit Tests: ShotSelector
# =========================================================================

def test_shot_selector_framing_and_hold_duration():
    selector = ShotSelector(min_hold_duration_sec=1.2)

    cand_person_a = SubjectCandidate(
        face_track_id="track_a",
        speaker_id="spk_a",
        bbox=NormalizedRect(x=0.2, y=0.2, width=0.2, height=0.3),
        importance_score=0.9,
        is_active_speaker=True,
        confidence=0.95,
    )

    cand_person_b = SubjectCandidate(
        face_track_id="track_b",
        speaker_id="spk_b",
        bbox=NormalizedRect(x=0.6, y=0.2, width=0.2, height=0.3),
        importance_score=0.88,
        is_active_speaker=True,
        confidence=0.92,
    )

    # Initial decision at t = 0.0 -> Person A (cut)
    dec_0 = selector.select_shot(0.0, None, [cand_person_a, cand_person_b])
    assert dec_0.target_subject.face_track_id == "track_a"
    assert dec_0.shot_type == "close_up"
    assert dec_0.transition_mode == "cut"

    # Rapid change of speaker at t = 0.5 (< 1.2s min hold duration)
    # The selector should hold Person A to prevent jittery cutting
    dec_rapid = selector.select_shot(0.5, dec_0, [cand_person_b, cand_person_a])
    assert dec_rapid.transition_mode == "hold"
    assert dec_rapid.target_subject.face_track_id == "track_a"

    # At t = 1.5 (> 1.2s hold duration elapsed) -> Person B cut allowed
    dec_switch = selector.select_shot(1.5, dec_0, [cand_person_b, cand_person_a])
    assert dec_switch.transition_mode == "cut"
    assert dec_switch.target_subject.face_track_id == "track_b"


# =========================================================================
# Unit Tests: TransitionPlanner
# =========================================================================

def test_transition_planner_crop_aspect_ratio_and_clamping():
    # 16:9 source (1920x1080) to 9:16 target (1080x1920)
    planner = TransitionPlanner(
        source_width=1920,
        source_height=1080,
        target_width=1080,
        target_height=1920,
    )

    face_bbox = NormalizedRect(x=0.4, y=0.2, width=0.15, height=0.25)
    crop = planner.calculate_crop_rect(face_bbox, shot_type="medium_shot")

    # Verify aspect ratio of the crop in source pixel coordinates
    # crop_w_px / crop_h_px must equal 9/16 = 0.5625
    crop_w_px = crop.width * 1920
    crop_h_px = crop.height * 1080
    aspect_ratio_calc = crop_w_px / crop_h_px
    assert abs(aspect_ratio_calc - (9.0 / 16.0)) < 0.005

    # Verify boundary constraints
    assert 0.0 <= crop.x <= 1.0
    assert 0.0 <= crop.y <= 1.0
    assert (crop.x + crop.width) <= 1.00001
    assert (crop.y + crop.height) <= 1.00001


def test_transition_planner_velocity_clamping_and_smoothing():
    planner = TransitionPlanner(
        source_width=1920,
        source_height=1080,
        target_width=1080,
        target_height=1920,
        max_velocity_per_sec=0.40,
        smoothing_strength=0.85,
    )

    cand_left = SubjectCandidate(
        face_track_id="t1",
        speaker_id="s1",
        bbox=NormalizedRect(x=0.05, y=0.2, width=0.15, height=0.25),
        importance_score=0.9,
        is_active_speaker=True,
        confidence=0.9,
    )
    cand_right = SubjectCandidate(
        face_track_id="t1",  # Same person moving across screen
        speaker_id="s1",
        bbox=NormalizedRect(x=0.75, y=0.2, width=0.15, height=0.25),
        importance_score=0.9,
        is_active_speaker=True,
        confidence=0.9,
    )

    dec_0 = ShotDecision(shot_type="medium_shot", transition_mode="cut", target_subject=cand_left, hold_duration_sec=1.2)
    # Next frame only 0.1s later with massive jump to right
    dec_jump = ShotDecision(shot_type="medium_shot", transition_mode="smooth", target_subject=cand_right, hold_duration_sec=1.2)

    plan = planner.plan_camera(
        timeline_duration_sec=2.0,
        shot_decisions=[(0.0, dec_0), (0.1, dec_jump)],
    )

    assert len(plan.keyframes) == 2
    kf0 = plan.keyframes[0]
    kf1 = plan.keyframes[1]

    # Verify shift between keyframes is clamped
    shift_x = abs(kf1.crop_rect.x - kf0.crop_rect.x)
    # At dt = 0.1s and max_velocity = 0.40/s, max step is 0.04
    assert shift_x <= 0.045


# =========================================================================
# Integration Tests: CompositionPlannerService
# =========================================================================

@pytest.mark.asyncio
async def test_composition_planner_from_highlight_candidate(async_session: AsyncSession):
    # 1. Seed database with test entities
    proj = Project(name="Planner Test Project")
    async_session.add(proj)
    await async_session.flush()

    video = Video(
        project_id=proj.id,
        filename="interview.mp4",
        file_path="C:/videos/interview.mp4",
        file_size_bytes=10_000_000,
        width=1920,
        height=1080,
        fps=30.0,
        duration_seconds=60.0,
        has_audio=True,
    )
    async_session.add(video)
    await async_session.flush()

    # Transcript with words
    transcript = Transcript(
        video_id=video.id,
        language="en",
        full_text="Welcome to the artificial intelligence discussion.",
    )
    async_session.add(transcript)
    await async_session.flush()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        segment_index=0,
        start_time=5.0,
        end_time=12.0,
        text="Welcome to the artificial intelligence discussion.",
        words=[
            {"word": "Welcome", "start": 5.0, "end": 5.8, "prob": 0.99},
            {"word": "to", "start": 5.9, "end": 6.1, "prob": 0.98},
            {"word": "the", "start": 6.2, "end": 6.4, "prob": 0.99},
            {"word": "discussion", "start": 6.5, "end": 7.5, "prob": 0.95},
        ],
    )
    async_session.add(seg)

    # Highlight candidate from 5.0s to 15.0s
    cand = HighlightCandidate(
        project_id=proj.id,
        video_id=video.id,
        transcript_id=transcript.id,
        start_time=5.0,
        end_time=15.0,
        duration_seconds=10.0,
        title="AI Discussion Highlight",
        hook="Welcome to the discussion",
        overall_score=92,
    )
    async_session.add(cand)
    await async_session.flush()

    # Face tracks (YuNet)
    va = VisionAnalysis(video_id=video.id, status="completed")
    async_session.add(va)
    await async_session.flush()

    track1 = FaceTrack(
        vision_analysis_id=va.id,
        track_id="face_01",
        start_time=0.0,
        end_time=20.0,
        average_confidence=0.92,
        average_bbox={"x": 0.35, "y": 0.25, "width": 0.18, "height": 0.28},
    )
    async_session.add(track1)

    # Active Speaker interval
    asi = ActiveSpeakerInterval(
        video_id=video.id,
        face_track_id="face_01",
        speaker_id="speaker_A",
        start_time=5.0,
        end_time=12.0,
        duration=7.0,
        state="active_speaker",
        confidence=0.96,
        speaking_score=0.91,
    )
    async_session.add(asi)
    await async_session.commit()

    # Execute CompositionPlannerService
    comp, version, spec = await CompositionPlannerService.plan_composition_for_candidate(
        db=async_session,
        candidate_id=cand.id,
        aspect_ratio="9:16",
    )

    assert comp is not None
    assert comp.title == "AI Discussion Highlight"
    assert comp.source_video_id == video.id
    assert comp.candidate_id == cand.id

    assert version is not None
    assert version.version_number == 1

    assert spec.schema_version == "1.0.0"
    assert spec.clip_boundary.source_start_seconds == 5.0
    assert spec.clip_boundary.source_end_seconds == 15.0
    assert spec.timeline.total_duration_seconds == 10.0

    # Camera plan keyframes check
    assert len(spec.camera.keyframes) >= 1
    first_kf = spec.camera.keyframes[0]
    assert first_kf.slot_id == "slot_0"
    assert first_kf.target_subject is not None
    assert first_kf.target_subject.face_track_id == "face_01"

    # Subtitles check
    assert spec.subtitles.enabled is True
    assert len(spec.subtitles.segments) >= 1
    sub_seg = spec.subtitles.segments[0]
    assert len(sub_seg.words) == 4
    # Word timestamps should be offset relative to clip start (5.0s -> 0.0s)
    first_word = sub_seg.words[0]
    assert first_word.word == "Welcome"
    assert abs(first_word.start_seconds - 0.0) < 0.01


@pytest.mark.asyncio
async def test_composition_planner_from_range_with_manual_override(async_session: AsyncSession):
    proj = Project(name="Range Project")
    async_session.add(proj)
    await async_session.flush()

    video = Video(
        project_id=proj.id,
        filename="lecture.mp4",
        file_path="C:/videos/lecture.mp4",
        file_size_bytes=5_000_000,
        width=1920,
        height=1080,
        duration_seconds=30.0,
    )
    async_session.add(video)
    await async_session.flush()

    va = VisionAnalysis(video_id=video.id, status="completed")
    async_session.add(va)
    await async_session.flush()

    # Add a manual crop correction at t = 12.0s
    mc = ManualCropCorrection(
        vision_analysis_id=va.id,
        timestamp_seconds=12.0,
        crop_x=0.25,
        crop_y=0.0,
        crop_width=0.3164,
        crop_height=1.0,
    )
    async_session.add(mc)
    await async_session.commit()

    # Plan for range 10.0s to 20.0s
    comp, version, spec = await CompositionPlannerService.plan_composition_for_range(
        db=async_session,
        video_id=video.id,
        project_id=proj.id,
        start_time=10.0,
        end_time=20.0,
        title="Lecture Segment",
    )

    assert comp.title == "Lecture Segment"
    assert len(spec.camera.manual_overrides) == 1
    override = spec.camera.manual_overrides[0]
    # Timestamp relative to clip start (12.0s - 10.0s = 2.0s = 2_000_000 us)
    assert override.timeline_position_us == 2_000_000
    assert abs(override.crop_rect.x - 0.25) < 1e-4


# =========================================================================
# REST API Tests
# =========================================================================

@pytest.mark.asyncio
async def test_auto_plan_rest_api_endpoint(client: AsyncClient, async_session: AsyncSession):
    proj = Project(name="API Project")
    async_session.add(proj)
    await async_session.flush()

    video = Video(
        project_id=proj.id,
        filename="api_test.mp4",
        file_path="C:/videos/api_test.mp4",
        file_size_bytes=1_000_000,
        width=1920,
        height=1080,
        duration_seconds=20.0,
    )
    async_session.add(video)
    await async_session.flush()

    cand = HighlightCandidate(
        project_id=proj.id,
        video_id=video.id,
        start_time=2.0,
        end_time=8.0,
        duration_seconds=6.0,
        title="API Planned Highlight",
    )
    async_session.add(cand)
    await async_session.commit()

    # 1. Test auto-plan via candidate_id
    payload_cand = {
        "project_id": proj.id,
        "candidate_id": cand.id,
        "aspect_ratio": "9:16",
        "subtitle_preset": "preset_bold_creator",
        "enable_subtitles": True,
    }
    resp = await client.post("/api/compositions/auto-plan", json=payload_cand)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"] == "API Planned Highlight"
    assert data["candidate_id"] == cand.id
    assert data["active_version"] is not None
    assert data["active_version"]["version_number"] == 1

    # 2. Test auto-plan via custom range
    payload_range = {
        "project_id": proj.id,
        "video_id": video.id,
        "start_time": 10.0,
        "end_time": 15.0,
        "title": "Custom Range Composition",
        "aspect_ratio": "9:16",
    }
    resp2 = await client.post("/api/compositions/auto-plan", json=payload_range)
    assert resp2.status_code == 201, resp2.text
    data2 = resp2.json()
    assert data2["title"] == "Custom Range Composition"
    assert data2["source_video_id"] == video.id


@pytest.mark.asyncio
async def test_composition_planner_handles_no_faces_gracefully(async_session: AsyncSession):
    proj = Project(name="No Face Project")
    async_session.add(proj)
    await async_session.flush()

    video = Video(
        project_id=proj.id,
        filename="scenery.mp4",
        file_path="C:/videos/scenery.mp4",
        file_size_bytes=2_000_000,
        width=1920,
        height=1080,
        duration_seconds=15.0,
    )
    async_session.add(video)
    await async_session.commit()

    comp, version, spec = await CompositionPlannerService.plan_composition_for_range(
        db=async_session,
        video_id=video.id,
        project_id=proj.id,
        start_time=0.0,
        end_time=5.0,
        title="Landscape Scenery",
    )

    assert comp is not None
    assert len(spec.camera.keyframes) >= 1
    first_kf = spec.camera.keyframes[0]
    # In absence of faces, crop should be center-aligned
    assert abs(first_kf.crop_rect.center_x - 0.5) < 0.05
    assert first_kf.target_subject is None


@pytest.mark.asyncio
async def test_composition_planner_speaker_alternation(async_session: AsyncSession):
    proj = Project(name="Alternation Project")
    async_session.add(proj)
    await async_session.flush()

    video = Video(
        project_id=proj.id,
        filename="debate.mp4",
        file_path="C:/videos/debate.mp4",
        file_size_bytes=10_000_000,
        width=1920,
        height=1080,
        duration_seconds=30.0,
    )
    async_session.add(video)
    await async_session.flush()

    va = VisionAnalysis(video_id=video.id, status="completed")
    async_session.add(va)
    await async_session.flush()

    # Track A on left, Track B on right
    track_a = FaceTrack(
        vision_analysis_id=va.id,
        track_id="debater_a",
        start_time=0.0,
        end_time=30.0,
        average_confidence=0.95,
        average_bbox={"x": 0.15, "y": 0.2, "width": 0.2, "height": 0.25},
    )
    track_b = FaceTrack(
        vision_analysis_id=va.id,
        track_id="debater_b",
        start_time=0.0,
        end_time=30.0,
        average_confidence=0.95,
        average_bbox={"x": 0.65, "y": 0.2, "width": 0.2, "height": 0.25},
    )
    async_session.add_all([track_a, track_b])
    await async_session.flush()

    # Debater A speaks 0s to 5s, Debater B speaks 6s to 12s
    asi_a = ActiveSpeakerInterval(
        video_id=video.id,
        face_track_id="debater_a",
        speaker_id="spk_a",
        start_time=0.0,
        end_time=5.0,
        duration=5.0,
        state="active_speaker",
        confidence=0.95,
    )
    asi_b = ActiveSpeakerInterval(
        video_id=video.id,
        face_track_id="debater_b",
        speaker_id="spk_b",
        start_time=6.0,
        end_time=12.0,
        duration=6.0,
        state="active_speaker",
        confidence=0.95,
    )
    async_session.add_all([asi_a, asi_b])
    await async_session.commit()

    comp, version, spec = await CompositionPlannerService.plan_composition_for_range(
        db=async_session,
        video_id=video.id,
        project_id=proj.id,
        start_time=0.0,
        end_time=12.0,
        title="Debate Cut",
    )

    # Keyframes should track Debater A on the left early on, then cut to Debater B on the right
    early_kfs = [k for k in spec.camera.keyframes if k.timeline_position_seconds <= 4.0]
    late_kfs = [k for k in spec.camera.keyframes if k.timeline_position_seconds >= 6.5]

    assert len(early_kfs) > 0
    assert early_kfs[0].target_subject.face_track_id == "debater_a"
    assert early_kfs[0].crop_rect.center_x < 0.45

    assert len(late_kfs) > 0
    assert late_kfs[-1].target_subject.face_track_id == "debater_b"
    assert late_kfs[-1].crop_rect.center_x > 0.55


@pytest.mark.asyncio
async def test_composition_planner_invalid_range_raises(async_session: AsyncSession):
    proj = Project(name="Invalid Range Project")
    async_session.add(proj)
    await async_session.flush()

    video = Video(
        project_id=proj.id,
        filename="clip.mp4",
        file_path="C:/videos/clip.mp4",
        file_size_bytes=100_000,
        duration_seconds=10.0,
    )
    async_session.add(video)
    await async_session.commit()

    with pytest.raises(CompositionPlanningError, match="must be greater than"):
        await CompositionPlannerService.plan_composition_for_range(
            db=async_session,
            video_id=video.id,
            project_id=proj.id,
            start_time=5.0,
            end_time=5.0,
        )


@pytest.mark.asyncio
async def test_auto_plan_rest_api_validation_error(client: AsyncClient, async_session: AsyncSession):
    proj = Project(name="Validation Project")
    async_session.add(proj)
    await async_session.commit()

    # Neither candidate_id nor (video_id, start_time, end_time) provided
    payload = {"project_id": proj.id}
    resp = await client.post("/api/compositions/auto-plan", json=payload)
    assert resp.status_code == 400
    assert "Either candidate_id or" in resp.json()["detail"]
