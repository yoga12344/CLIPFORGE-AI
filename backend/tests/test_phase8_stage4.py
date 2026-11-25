"""
ClipForge AI - Phase 8 Stage 4 Test Suite
Tests Facial Landmarks, Lip Dynamics, AV Synchronization, Light-ASD, and Multimodal Fusion.
"""

import math
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import cv2
import numpy as np
import pytest

from app.ai.audio_visual.active_speaker_detector import LightASDDetector, compute_mfcc_13
from app.ai.audio_visual.av_fusion_engine import AudioVisualFusionEngine
from app.ai.audio_visual.av_synchronizer import (
    AudioVisualSynchronizer,
    StreamSyncInfo,
    SynchronizedAVWindow,
)
from app.ai.audio_visual.schemas import ActiveSpeakerObservation, ActiveSpeakerSegment, SpeakerFaceMatch
from app.ai.vision.landmark_detector import (
    MediaPipeFaceLandmarkDetector,
    EXPECTED_LANDMARKS_SHA256,
)
from app.ai.vision.lip_dynamics import LipDynamicsExtractor
from app.ai.vision.schemas import DenseFaceLandmarks, NormalizedBBox, LipDynamicsMeasurement


# ============================================================================
# 1. FACIAL LANDMARK INFERENCE TESTS
# ============================================================================

def test_landmark_model_loading_and_checksum():
    """Verify that the landmark detector initializes and validates checksum correctly."""
    detector = MediaPipeFaceLandmarkDetector(verify_checksum=True)
    assert detector.is_available() is True
    session = detector._ensure_session()
    assert session is not None


def test_landmark_checksum_failure(tmp_path):
    """Verify that an altered or corrupt file fails checksum validation."""
    fake_model = tmp_path / "corrupt_landmarks.onnx"
    fake_model.write_bytes(b"corrupted binary data")
    with pytest.raises(ValueError, match="checksum verification failed"):
        MediaPipeFaceLandmarkDetector(model_path=fake_model, verify_checksum=True)


def test_landmark_valid_face_crop():
    """Test landmark detection on a synthesized facial structure."""
    detector = MediaPipeFaceLandmarkDetector()
    # Draw simple face with eyes, nose, and mouth
    img = np.full((256, 256, 3), 200, dtype=np.uint8)
    cv2.ellipse(img, (128, 128), (60, 80), 0, 0, 360, (180, 150, 130), -1)
    cv2.circle(img, (105, 110), 8, (50, 50, 50), -1)
    cv2.circle(img, (151, 110), 8, (50, 50, 50), -1)
    cv2.ellipse(img, (128, 160), (25, 10), 0, 0, 360, (40, 40, 180), -1)

    res = detector.detect_landmarks_from_crop(img)
    assert res.is_valid is True
    assert res.confidence >= 0.50
    assert len(res.points) == 478
    assert res.upper_lip_inner is not None
    assert res.lower_lip_inner is not None
    # Anatomically, lower lip y must be below upper lip y
    assert res.lower_lip_inner[1] > res.upper_lip_inner[1]


def test_landmark_multiple_faces_batch():
    """Test batch inference with multiple face crops simultaneously."""
    detector = MediaPipeFaceLandmarkDetector()
    img = np.full((256, 256, 3), 200, dtype=np.uint8)
    cv2.ellipse(img, (128, 128), (60, 80), 0, 0, 360, (180, 150, 130), -1)
    cv2.circle(img, (105, 110), 8, (50, 50, 50), -1)
    cv2.circle(img, (151, 110), 8, (50, 50, 50), -1)
    cv2.ellipse(img, (128, 160), (25, 10), 0, 0, 360, (40, 40, 180), -1)

    bbox1 = NormalizedBBox(x=0.1, y=0.1, width=0.3, height=0.3)
    bbox2 = NormalizedBBox(x=0.6, y=0.1, width=0.3, height=0.3)

    results = detector.detect_landmarks_batch([(img, bbox1), (img, bbox2)])
    assert len(results) == 2
    assert results[0].is_valid is True
    assert results[1].is_valid is True
    # Verify coordinate remapping to distinct bounding boxes
    assert results[0].upper_lip_inner[0] < results[1].upper_lip_inner[0]


def test_landmark_missing_face_blank_image():
    """Verify that a uniform blank image is rejected with is_valid=False."""
    detector = MediaPipeFaceLandmarkDetector()
    blank = np.full((256, 256, 3), 128, dtype=np.uint8)
    res = detector.detect_landmarks_from_crop(blank)
    assert res.is_valid is False
    assert res.confidence < 0.50
    assert len(res.points) == 0


def test_landmark_low_resolution_crop():
    """Test that extremely tiny face crops are safely handled without crashes."""
    detector = MediaPipeFaceLandmarkDetector()
    tiny = np.full((4, 4, 3), 100, dtype=np.uint8)
    res = detector.detect_landmarks_from_crop(tiny)
    assert res.is_valid is False


def test_landmark_occluded_and_rotated_face():
    """Test that rotated face crops with occlusion are handled safely."""
    detector = MediaPipeFaceLandmarkDetector()
    img = np.full((256, 256, 3), 180, dtype=np.uint8)
    # Occlude lower half with black bar
    img[140:256, :] = 0
    res = detector.detect_landmarks_from_crop(img)
    # Should safely return observation without crash
    assert isinstance(res, DenseFaceLandmarks)


def test_landmark_cancellation():
    """Test that landmark inference aborts early when is_cancelled returns True."""
    detector = MediaPipeFaceLandmarkDetector()
    dummy = np.full((256, 256, 3), 180, dtype=np.uint8)
    res = detector.detect_landmarks_batch(
        [(dummy, None), (dummy, None)],
        is_cancelled=lambda: True,
    )
    assert len(res) == 0


# ============================================================================
# 2. LIP GEOMETRY & TEMPORAL DYNAMICS TESTS
# ============================================================================

def _create_mock_landmarks(aperture_y: float, width_x: float = 0.10, conf: float = 0.90) -> DenseFaceLandmarks:
    """Helper to generate dense landmarks with explicit lip aperture."""
    pts = [[0.5, 0.5, 0.0] for _ in range(478)]
    pts[13] = [0.5, 0.60, 0.0]
    pts[14] = [0.5, 0.60 + aperture_y, 0.0]
    pts[61] = [0.5 - (width_x / 2.0), 0.60 + (aperture_y / 2.0), 0.0]
    pts[291] = [0.5 + (width_x / 2.0), 0.60 + (aperture_y / 2.0), 0.0]
    return DenseFaceLandmarks(points=pts, confidence=conf)


def test_lip_dynamics_closed_mouth():
    """Test MAR for a tightly closed mouth."""
    ext = LipDynamicsExtractor()
    lmk = _create_mock_landmarks(aperture_y=0.002, width_x=0.10)
    m = ext.extract_measurement(lmk, "track_1", 0.0)
    assert m.is_valid is True
    assert m.mar_raw < 0.05
    assert m.mar_smooth < 0.05
    assert m.mar_velocity == 0.0


def test_lip_dynamics_repeated_opening_and_closing():
    """Test MAR and velocity during speech-like opening and closing cycles."""
    ext = LipDynamicsExtractor(smoothing_alpha=0.5)
    # Frame 0: Closed
    m0 = ext.extract_measurement(_create_mock_landmarks(0.002), "track_1", 0.0)
    # Frame 1: Opened wide (vowel /a:/) at dt=0.04s
    m1 = ext.extract_measurement(_create_mock_landmarks(0.060), "track_1", 0.04)
    # Frame 2: Closed (bilabial plosive /p/) at dt=0.08s
    m2 = ext.extract_measurement(_create_mock_landmarks(0.004), "track_1", 0.08)

    assert m1.mar_raw > m0.mar_raw
    assert m1.mar_velocity > 5.0
    assert m2.mar_raw < m1.mar_raw
    assert m2.mar_velocity > 5.0
    assert m2.mar_variance > 0.001


def test_lip_dynamics_static_open_mouth():
    """Verify that a continuously static open mouth has high MAR but near-zero velocity."""
    ext = LipDynamicsExtractor()
    for t in [0.0, 0.04, 0.08, 0.12, 0.16]:
        m = ext.extract_measurement(_create_mock_landmarks(0.050), "track_1", t)
    assert m.mar_raw == 0.50
    # Because mouth is static, velocity drops to 0.0
    assert m.mar_velocity == 0.0


def test_lip_dynamics_smile_motion():
    """Verify that smiling (mouth width increases while vertical aperture stays small) keeps MAR low."""
    ext = LipDynamicsExtractor()
    # Baseline neutral mouth
    m_neutral = ext.extract_measurement(_create_mock_landmarks(0.010, width_x=0.08), "track_1", 0.0)
    # Wide smile: aperture increases slightly, but width expands significantly
    m_smile = ext.extract_measurement(_create_mock_landmarks(0.012, width_x=0.14), "track_1", 0.04)
    assert m_smile.mouth_width > m_neutral.mouth_width
    assert m_smile.mar_raw < m_neutral.mar_raw


def test_lip_dynamics_jitter_rejection():
    """Test that sudden non-physical single-frame landmark jumps are clamped."""
    ext = LipDynamicsExtractor()
    ext.extract_measurement(_create_mock_landmarks(0.010), "track_1", 0.0)
    # Impossible single-frame jump to 0.90 in 0.02s
    m_jitter = ext.extract_measurement(_create_mock_landmarks(0.090), "track_1", 0.02)
    # Velocity should be bounded and raw clamped
    assert m_jitter.mar_raw <= 0.10 + 0.45


def test_lip_dynamics_occlusion_gap_reset():
    """Test that after a long tracking gap (>0.5s), smoothed state is reset without false velocity spikes."""
    ext = LipDynamicsExtractor()
    ext.extract_measurement(_create_mock_landmarks(0.010), "track_1", 0.0)
    # Gap of 1.5 seconds
    m_after_gap = ext.extract_measurement(_create_mock_landmarks(0.050), "track_1", 1.50)
    # Velocity must be reset to 0.0 after long gap rather than computing huge delta across 1.5s
    assert m_after_gap.mar_velocity == 0.0
    assert m_after_gap.mar_smooth == m_after_gap.mar_raw


def test_lip_dynamics_track_identity_independence():
    """Verify that multiple tracks maintain strictly independent temporal state."""
    ext = LipDynamicsExtractor()
    m_t1 = ext.extract_measurement(_create_mock_landmarks(0.010), "track_1", 0.0)
    m_t2 = ext.extract_measurement(_create_mock_landmarks(0.060), "track_2", 0.0)

    assert m_t1.face_track_id == "track_1"
    assert m_t2.face_track_id == "track_2"
    assert m_t1.mar_raw < m_t2.mar_raw


# ============================================================================
# 3. AUDIO-VIDEO TIMESTAMP SYNCHRONIZATION TESTS
# ============================================================================

def test_av_sync_constant_frame_rate():
    """Test audio slicing for CFR video timestamps."""
    sample_rate = 16000
    # 5 seconds of audio
    audio = np.linspace(0.0, 5.0, 5 * sample_rate, dtype=np.float32)
    sync = AudioVisualSynchronizer(audio, sample_rate=sample_rate, default_window_duration=0.40)

    w = sync.extract_audio_window(video_pts=2.0)
    assert len(w.audio_samples) == 6400  # 0.4s * 16000
    assert w.is_padded_left is False
    assert w.is_padded_right is False
    assert w.sync_confidence == 1.0
    # Center sample should match ~2.0
    mid_val = w.audio_samples[3200]
    assert abs(mid_val - 2.0) < 0.05


def test_av_sync_variable_frame_rate():
    """Test audio slicing across non-uniform VFR video timestamps."""
    audio = np.ones(160000, dtype=np.float32)
    sync_info = StreamSyncInfo(is_vfr=True, nominal_fps=29.97)
    sync = AudioVisualSynchronizer(audio, sync_info=sync_info)

    vfr_pts = [0.033, 0.071, 0.102, 0.138, 0.201, 0.235]
    windows = sync.extract_audio_windows_for_timestamps(vfr_pts)
    assert len(windows) == len(vfr_pts)
    for w in windows:
        assert len(w.audio_samples) == 6400


def test_av_sync_positive_audio_offset():
    """
    Test positive offset: Audio stream starts 0.20s AFTER video stream (audio_start > video_start).
    When video is at t=0.10s, audio has not started yet -> left padded.
    """
    audio = np.ones(32000, dtype=np.float32)
    sync_info = StreamSyncInfo(video_start_time=0.0, audio_start_time=0.20, relative_offset_seconds=0.20)
    sync = AudioVisualSynchronizer(audio, sync_info=sync_info, default_window_duration=0.40)

    w = sync.extract_audio_window(video_pts=0.10)
    # Audio center = 0.10 - 0.20 = -0.10s -> padded on left
    assert w.is_padded_left is True
    assert len(w.audio_samples) == 6400


def test_av_sync_negative_audio_offset():
    """
    Test negative offset: Audio stream starts 0.15s BEFORE video stream.
    When video is at t=0.05s, audio time = 0.05 - (-0.15) = 0.20s -> fully inside audio.
    """
    audio = np.ones(48000, dtype=np.float32)
    sync_info = StreamSyncInfo(video_start_time=0.15, audio_start_time=0.0, relative_offset_seconds=-0.15)
    sync = AudioVisualSynchronizer(audio, sync_info=sync_info, default_window_duration=0.40)

    w = sync.extract_audio_window(video_pts=0.05)
    assert w.is_padded_left is False
    assert len(w.audio_samples) == 6400


def test_av_sync_missing_audio():
    """Test robust fallback when video has no audio stream."""
    sync = AudioVisualSynchronizer(audio_samples=None)
    w = sync.extract_audio_window(video_pts=1.50)
    assert len(w.audio_samples) == 6400
    assert np.all(w.audio_samples == 0.0)
    assert w.sync_confidence == 0.0


def test_av_sync_boundary_padding():
    """Test boundary clipping at start and end of audio stream."""
    # Only 0.5s of audio (8000 samples)
    audio = np.ones(8000, dtype=np.float32)
    sync = AudioVisualSynchronizer(audio, default_window_duration=0.40)

    # Center at 0.0s -> window [-0.2, 0.2] -> left side padded with zeros
    w_start = sync.extract_audio_window(video_pts=0.0)
    assert w_start.is_padded_left is True
    assert w_start.audio_samples[0] == 0.0
    assert w_start.audio_samples[3200] == 1.0

    # Center at 0.5s -> window [0.3, 0.7] -> right side padded with zeros
    w_end = sync.extract_audio_window(video_pts=0.50)
    assert w_end.is_padded_right is True
    assert w_end.audio_samples[-1] == 0.0


# ============================================================================
# 4. LIGHT-ASD ACTIVE SPEAKER INFERENCE TESTS
# ============================================================================

def test_light_asd_loading_and_checksum():
    """Verify Light-ASD ONNX model loads and passes checksum validation."""
    detector = LightASDDetector(verify_checksum=True)
    assert detector.is_available() is True
    session = detector._ensure_session()
    assert session is not None


def test_light_asd_mfcc_extraction():
    """Verify 13-dim MFCC extraction produces correct temporal steps and dimensions."""
    # 1 second of 16 kHz audio
    audio = np.random.randn(16000).astype(np.float32)
    mfcc = compute_mfcc_13(audio, sample_rate=16000)
    # 1 second with 10ms hop produces ~100 frames
    assert mfcc.shape[1] == 13
    assert abs(mfcc.shape[0] - 100) <= 2


def test_light_asd_single_face_sequence():
    """Test sequence active speaker inference for a single face track."""
    detector = LightASDDetector()
    num_frames = 10
    crops = [np.full((112, 112, 3), 120, dtype=np.uint8) for _ in range(num_frames)]
    timestamps = [i * 0.04 for i in range(num_frames)]
    audio = np.random.randn(6400).astype(np.float32)

    obs = detector.detect_active_speaker_sequence(
        face_crops=crops,
        timestamps=timestamps,
        audio_segment=audio,
        face_track_id="track_single",
    )
    assert len(obs) == num_frames
    for o in obs:
        assert o.face_track_id == "track_single"
        assert 0.0 <= o.speaking_probability <= 1.0
        assert isinstance(o.is_speaking, bool)
        assert isinstance(o.raw_logit, float)


def test_light_asd_cancellation():
    """Test early cancellation probe during Light-ASD inference."""
    detector = LightASDDetector()
    crops = [np.full((112, 112, 3), 100, dtype=np.uint8) for _ in range(5)]
    obs = detector.detect_active_speaker_sequence(
        face_crops=crops,
        timestamps=[0.0, 0.04, 0.08, 0.12, 0.16],
        audio_segment=np.zeros(3200, dtype=np.float32),
        face_track_id="track_1",
        is_cancelled=lambda: True,
    )
    assert len(obs) == 0


def test_light_asd_empty_input():
    """Test graceful handling of empty inputs."""
    detector = LightASDDetector()
    obs = detector.detect_active_speaker_sequence(
        face_crops=[],
        timestamps=[],
        audio_segment=np.zeros(0, dtype=np.float32),
        face_track_id="track_empty",
    )
    assert len(obs) == 0


# ============================================================================
# 5. MULTIMODAL AUDIO-VISUAL FUSION TESTS
# ============================================================================

def test_fusion_single_visible_speaker():
    """Test fusion when speech matches a single active visible face."""
    fusion = AudioVisualFusionEngine(onset_threshold=0.60, offset_threshold=0.35)

    num_samples = 30  # 1.2s at 25 FPS
    timestamps = [i * 0.04 for i in range(num_samples)]

    obs = [
        ActiveSpeakerObservation(
            timestamp_seconds=t,
            face_track_id="track_speaker",
            raw_logit=2.0,
            speaking_probability=0.88,
            is_speaking=True,
        )
        for t in timestamps
    ]
    lips = [
        LipDynamicsMeasurement(
            timestamp_seconds=t,
            face_track_id="track_speaker",
            aperture=0.04,
            mouth_width=0.10,
            mar_raw=0.40,
            mar_smooth=0.40,
            mar_velocity=5.5,
            mar_variance=0.008,
        )
        for t in timestamps
    ]
    vad = [(0.0, 1.2)]

    segs = fusion.detect_active_speaker_intervals(
        observations_by_track={"track_speaker": obs},
        lip_measurements_by_track={"track_speaker": lips},
        vad_intervals=vad,
        video_duration=1.2,
    )

    assert len(segs) >= 1
    main_seg = segs[0]
    assert main_seg.face_track_id == "track_speaker"
    assert main_seg.state == "active_speaker"
    assert main_seg.confidence >= 0.70


def test_fusion_multiple_visible_faces():
    """
    Test dialogue scene with 2 visible faces:
    Face A is speaking (moving mouth, high ASD probability).
    Face B is listening quietly (static mouth, low ASD probability).
    """
    fusion = AudioVisualFusionEngine()
    timestamps = [i * 0.04 for i in range(25)]

    obs_a = [
        ActiveSpeakerObservation(
            timestamp_seconds=t,
            face_track_id="face_speaker",
            raw_logit=1.8,
            speaking_probability=0.85,
            is_speaking=True,
        )
        for t in timestamps
    ]
    lips_a = [
        LipDynamicsMeasurement(
            timestamp_seconds=t,
            face_track_id="face_speaker",
            aperture=0.04,
            mouth_width=0.10,
            mar_raw=0.40,
            mar_smooth=0.40,
            mar_velocity=6.0,
            mar_variance=0.010,
        )
        for t in timestamps
    ]

    obs_b = [
        ActiveSpeakerObservation(
            timestamp_seconds=t,
            face_track_id="face_listener",
            raw_logit=-1.5,
            speaking_probability=0.12,
            is_speaking=False,
        )
        for t in timestamps
    ]
    lips_b = [
        LipDynamicsMeasurement(
            timestamp_seconds=t,
            face_track_id="face_listener",
            aperture=0.005,
            mouth_width=0.10,
            mar_raw=0.05,
            mar_smooth=0.05,
            mar_velocity=0.2,
            mar_variance=0.0001,
        )
        for t in timestamps
    ]

    vad = [(0.0, 1.0)]

    segs = fusion.detect_active_speaker_intervals(
        observations_by_track={"face_speaker": obs_a, "face_listener": obs_b},
        lip_measurements_by_track={"face_speaker": lips_a, "face_listener": lips_b},
        vad_intervals=vad,
        video_duration=1.0,
    )

    # Face A must be detected as active; Face B must NOT be classified as active
    face_a_active = any(s.face_track_id == "face_speaker" and s.state == "active_speaker" for s in segs)
    face_b_active = any(s.face_track_id == "face_listener" and s.state == "active_speaker" for s in segs)
    assert face_a_active is True
    assert face_b_active is False


def test_fusion_off_screen_narrator():
    """Test voiceover / off-screen speech with no active visible face."""
    fusion = AudioVisualFusionEngine()
    # Speech occurs from 0.0 to 2.0s
    vad = [(0.0, 2.0)]
    # Listener face is present, but quiet
    timestamps = [i * 0.04 for i in range(50)]
    obs_silent = [
        ActiveSpeakerObservation(
            timestamp_seconds=t,
            face_track_id="face_silent",
            raw_logit=-2.0,
            speaking_probability=0.05,
            is_speaking=False,
        )
        for t in timestamps
    ]
    lips_silent = [
        LipDynamicsMeasurement(
            timestamp_seconds=t,
            face_track_id="face_silent",
            aperture=0.002,
            mouth_width=0.10,
            mar_raw=0.02,
            mar_smooth=0.02,
            mar_velocity=0.1,
            mar_variance=0.0,
        )
        for t in timestamps
    ]

    segs = fusion.detect_active_speaker_intervals(
        observations_by_track={"face_silent": obs_silent},
        lip_measurements_by_track={"face_silent": lips_silent},
        vad_intervals=vad,
        video_duration=2.0,
    )

    # Should detect off_screen_speaker segment
    off_screen_found = any(s.state == "off_screen_speaker" and s.face_track_id is None for s in segs)
    assert off_screen_found is True


def test_fusion_silent_mouth_motion_without_speech():
    """Test silent chewing/smiling (lip moves, but VAD and audio cross-modal confirm no speech)."""
    fusion = AudioVisualFusionEngine()
    timestamps = [i * 0.04 for i in range(25)]
    obs_chewing = [
        ActiveSpeakerObservation(
            timestamp_seconds=t,
            face_track_id="face_chewing",
            raw_logit=-1.8,
            speaking_probability=0.10,
            is_speaking=False,
        )
        for t in timestamps
    ]
    lips_chewing = [
        LipDynamicsMeasurement(
            timestamp_seconds=t,
            face_track_id="face_chewing",
            aperture=0.03,
            mouth_width=0.10,
            mar_raw=0.30,
            mar_smooth=0.30,
            mar_velocity=3.0,
            mar_variance=0.004,
        )
        for t in timestamps
    ]
    # Total silence in audio (no VAD speech)
    vad = []

    segs = fusion.detect_active_speaker_intervals(
        observations_by_track={"face_chewing": obs_chewing},
        lip_measurements_by_track={"face_chewing": lips_chewing},
        vad_intervals=vad,
        video_duration=1.0,
    )
    # Must NOT detect active speaker
    assert len(segs) == 0


def test_fusion_manual_override_preservation():
    """Verify that manual user speaker-to-face assignments are preserved and protected."""
    fusion = AudioVisualFusionEngine()

    active_segs = [
        ActiveSpeakerSegment(
            start_time=0.0,
            end_time=2.0,
            duration=2.0,
            face_track_id="track_auto_preferred",
            confidence=0.90,
            speaking_score=0.90,
            state="active_speaker",
        )
    ]
    turns = [{"speaker_id": "SPEAKER_00", "start_time": 0.0, "end_time": 2.0}]

    # User explicitly mapped SPEAKER_00 to track_manual_choice
    manual = {"SPEAKER_00": "track_manual_choice"}

    matches = fusion.associate_speakers_to_faces(
        speaker_turns=turns,
        active_segments=active_segs,
        manual_overrides=manual,
    )

    assert len(matches) == 1
    match = matches[0]
    assert match.speaker_id == "SPEAKER_00"
    assert match.face_track_id == "track_manual_choice"
    assert match.is_manual is True
    assert match.confidence == 1.0
