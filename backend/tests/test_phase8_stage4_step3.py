"""
ClipForge AI - Phase 8 Stage 4 Step 3 Automated Tests
Verifies AVTemporalAdapter, Multi-Evidence Fusion Engine across 20 Real-World Scenarios,
Multi-Turn Speaker-Face Identity Association, Metrics Benchmarking, and Reframe Interface.
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pytest

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.ai.audio_visual.active_speaker_detector import AVTemporalAdapter
from app.ai.audio_visual.active_speaker_service import get_primary_active_speaker_at
from app.ai.audio_visual.av_fusion_engine import AudioVisualFusionEngine
from app.ai.audio_visual.schemas import ActiveSpeakerSegment, SpeakerFaceMatch
from app.ai.vision.schemas import NormalizedBBox
from tests.fixtures.real_world_dataset import build_scenario


# ============================================================================
# 1. AV TEMPORAL ADAPTER TESTS
# ============================================================================

def test_av_temporal_adapter_interpolation():
    """Verify interpolation of 4.0 FPS keyframe bounding boxes to 25.0 FPS grid."""
    # Keyframe samples every 0.25s
    samples = [
        {"timestamp": 0.0, "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}},
        {"timestamp": 0.25, "bbox": {"x": 0.2, "y": 0.2, "width": 0.25, "height": 0.25}},
        {"timestamp": 0.50, "bbox": {"x": 0.3, "y": 0.3, "width": 0.3, "height": 0.3}},
    ]

    interp = AVTemporalAdapter.interpolate_track_bboxes(
        samples=samples,
        start_time=0.0,
        end_time=0.50,
    )

    # 0.50s / 0.04s + 1 = ~13 frames
    assert len(interp) >= 13

    # Check midpoint timestamp (t = 0.12s, alpha = 0.12/0.25 = 0.48)
    mid_frame = next((b for t, b in interp if abs(t - 0.12) < 0.01), None)
    assert mid_frame is not None
    assert mid_frame.x > 0.10 and mid_frame.x < 0.20
    assert mid_frame.width > 0.20 and mid_frame.width < 0.25


def test_av_temporal_adapter_track_discontinuity():
    """Verify that gaps exceeding 0.50s are not interpolated across."""
    samples = [
        {"timestamp": 0.0, "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}},
        # Gap of 1.0s (e.g. face left frame or track lost)
        {"timestamp": 1.0, "bbox": {"x": 0.4, "y": 0.4, "width": 0.2, "height": 0.2}},
    ]

    interp = AVTemporalAdapter.interpolate_track_bboxes(
        samples=samples,
        start_time=0.0,
        end_time=1.0,
        max_gap_seconds=0.50,
    )

    # In the middle of the gap (t = 0.50), bbox should be None
    gap_frame = next((b for t, b in interp if abs(t - 0.50) < 0.01), None)
    assert gap_frame is None


# ============================================================================
# 2. 20-SCENARIO REAL-WORLD BENCHMARK SUITE
# ============================================================================

@pytest.mark.parametrize("scenario_idx", list(range(1, 21)))
def test_real_world_scenario_evaluation(scenario_idx: int):
    """
    Evaluates each of the 20 real-world benchmark scenarios.
    Checks Concept A active speaker intervals and Concept B identity associations.
    """
    test_data = build_scenario(scenario_idx)
    gt = test_data.ground_truth
    fusion = AudioVisualFusionEngine()

    # Run Concept A: Active Speaker Detection
    active_segments = fusion.detect_active_speaker_intervals(
        observations_by_track=test_data.observations_by_track,
        lip_measurements_by_track=test_data.lip_measurements_by_track,
        vad_intervals=test_data.vad_intervals,
        video_duration=gt.duration_seconds,
        scene_cuts=test_data.scene_cuts,
    )

    # Run Concept B: Speaker-Face Identity Association
    associations = fusion.associate_speakers_to_faces(
        speaker_turns=test_data.speaker_turns,
        active_segments=active_segments,
    )

    # --- VERIFICATION CHECKS ---

    # Check 1: Non-speech scenarios (6: chewing, 7: smiling, 8: static open, 9: yawning)
    # Must have ZERO false active visible detections
    if scenario_idx in (6, 7, 8, 9):
        visible_actives = [s for s in active_segments if s.face_track_id is not None and s.state == "active_speaker"]
        assert len(visible_actives) == 0, f"False activation in scenario {scenario_idx} ({gt.description})"

    # Check 2: Off-screen speech scenarios (4: off-screen narrator, 5: voiceover with silent people)
    if scenario_idx in (4, 5):
        off_screen_segs = [s for s in active_segments if s.face_track_id is None]
        assert len(off_screen_segs) >= 1, f"Missing off-screen detection in scenario {scenario_idx}"
        for spk in gt.expected_off_screen_speakers:
            match = next((m for m in associations if m.speaker_id == spk), None)
            assert match is not None, f"Missing association for {spk}"
            assert match.is_off_screen is True or match.face_track_id is None

    # Check 3: Active dialogue scenarios (1, 2, 3, 10, 11, 12, 13, 16, 17, 18, 19, 20)
    if scenario_idx in (1, 2, 3, 10, 11, 12, 13, 16, 17, 18, 19, 20):
        assert len(active_segments) >= 1, f"Failed to detect active speech in scenario {scenario_idx}"
        # Verify identity associations match ground truth
        for spk_id, expected_track in gt.ground_truth_associations.items():
            match = next((m for m in associations if m.speaker_id == spk_id), None)
            assert match is not None, f"Missing match for {spk_id} in scenario {scenario_idx}"
            if expected_track is not None:
                assert match.face_track_id == expected_track, (
                    f"Mismatch in scenario {scenario_idx}: expected {expected_track}, got {match.face_track_id}"
                )
                assert match.confidence >= 0.30

    # Check 4: Cross-talk detection (10: rapid interruptions, 11: overlapping cross-talk)
    if scenario_idx in (10, 11):
        # Multiple active tracks should be present
        active_tracks = set(s.face_track_id for s in active_segments if s.face_track_id)
        assert len(active_tracks) >= 2, f"Failed to detect concurrent tracks in scenario {scenario_idx}"


# ============================================================================
# 3. MULTI-TURN ASSOCIATION & NEGATIVE PENALTY TESTS
# ============================================================================

def test_multi_turn_association_consistency():
    """Verify confirmed status when speaker consistently speaks across >= 2 turns."""
    fusion = AudioVisualFusionEngine()

    active_segs = [
        ActiveSpeakerSegment(start_time=1.0, end_time=2.0, duration=1.0, face_track_id="track_anchor", confidence=0.9, speaking_score=0.9, state="active_speaker"),
        ActiveSpeakerSegment(start_time=4.0, end_time=5.0, duration=1.0, face_track_id="track_anchor", confidence=0.9, speaking_score=0.9, state="active_speaker"),
    ]
    turns = [
        {"speaker_id": "SPEAKER_00", "start_time": 1.0, "end_time": 2.0},
        {"speaker_id": "SPEAKER_00", "start_time": 4.0, "end_time": 5.0},
    ]

    matches = fusion.associate_speakers_to_faces(turns, active_segs)
    assert len(matches) == 1
    m = matches[0]
    assert m.face_track_id == "track_anchor"
    assert m.turn_consistency == 1.0
    assert m.status == "confirmed"
    assert m.turns_matched == 2


def test_negative_cooccurrence_penalty():
    """
    If face track T1 is active while Speaker B is speaking, it should NOT be
    associated with Speaker A even if there is slight accidental overlap.
    """
    fusion = AudioVisualFusionEngine()

    # Face 1 speaks for 3 seconds: 0.1s during Speaker A turn, but 2.9s during Speaker B turn!
    active_segs = [
        ActiveSpeakerSegment(start_time=0.9, end_time=3.9, duration=3.0, face_track_id="face_imposter", confidence=0.9, speaking_score=0.9, state="active_speaker"),
    ]
    turns = [
        {"speaker_id": "SPEAKER_A", "start_time": 0.0, "end_time": 1.0},
        {"speaker_id": "SPEAKER_B", "start_time": 1.0, "end_time": 4.0},
    ]

    matches = fusion.associate_speakers_to_faces(turns, active_segs)
    # Face imposter must be associated with SPEAKER_B, NOT SPEAKER_A
    match_a = next(m for m in matches if m.speaker_id == "SPEAKER_A")
    match_b = next(m for m in matches if m.speaker_id == "SPEAKER_B")

    assert match_b.face_track_id == "face_imposter"
    assert match_a.face_track_id is None
    assert match_a.is_off_screen is True


# ============================================================================
# 4. REFRAME ENGINE CONSUMER INTERFACE TEST
# ============================================================================

def test_get_primary_active_speaker_interface():
    """Verify consumer helper for SubjectSelector / ReframeEngine."""
    segments = [
        ActiveSpeakerSegment(start_time=1.0, end_time=3.0, duration=2.0, face_track_id="track_alpha", confidence=0.95, speaking_score=0.95, state="active_speaker"),
        ActiveSpeakerSegment(start_time=2.0, end_time=4.0, duration=2.0, face_track_id="track_beta", confidence=0.70, speaking_score=0.70, state="active_speaker"),
    ]

    # At t=0.5 (before speech): None
    assert get_primary_active_speaker_at(0.5, segments) is None

    # At t=1.5 (only track_alpha is speaking): track_alpha
    spk_1_5 = get_primary_active_speaker_at(1.5, segments)
    assert spk_1_5 is not None
    assert spk_1_5["face_track_id"] == "track_alpha"

    # At t=2.5 (both speaking, overlapping): highest confidence wins (track_alpha 0.95 > track_beta 0.70)
    spk_2_5 = get_primary_active_speaker_at(2.5, segments)
    assert spk_2_5 is not None
    assert spk_2_5["face_track_id"] == "track_alpha"

    # At t=3.5 (only track_beta): track_beta
    spk_3_5 = get_primary_active_speaker_at(3.5, segments)
    assert spk_3_5 is not None
    assert spk_3_5["face_track_id"] == "track_beta"
