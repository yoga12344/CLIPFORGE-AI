"""
ClipForge AI - Phase 8 Stage 3 Speaker Diarization Test Suite
Tests SpeakerDiarizer end-to-end pipeline, window slicing, turn consolidation, and DER evaluation.
"""

from pathlib import Path
import sys
import wave
import numpy as np
import pytest

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.ai.audio.speaker_diarizer import (
    DiarizationConfig,
    DiarizationResult,
    DiarizedSpeaker,
    SpeakerDiarizer,
    SpeakerTurnData,
)
from app.ai.audio.voice_activity_detector import SpeechInterval


class TestSpeakerDiarizer:
    """Tests for offline local speaker diarization."""

    @pytest.fixture(scope="class")
    def diarizer(self):
        return SpeakerDiarizer()

    def test_capabilities(self, diarizer):
        caps = diarizer.get_capabilities()
        assert caps["diarization_available"] is True
        assert caps["model_name"] == "3D-Speaker CAM++ (VoxCeleb 16k)"
        assert caps["embedding_dimension"] == 512
        assert caps["execution_device"] == "cpu"
        assert caps["offline_only"] is True

    def test_empty_audio_diarization(self, diarizer):
        res = diarizer.diarize(np.array([], dtype=np.float32))
        assert res.num_speakers == 0
        assert len(res.speakers) == 0
        assert len(res.speaker_turns) == 0
        assert res.total_speech_duration == 0.0

    def test_slice_speech_intervals(self, diarizer):
        # 3 intervals: 0.2s (too short), 1.0s (fits 1 window), 4.0s (multiple sliding windows)
        intervals = [
            SpeechInterval(start_time=0.0, end_time=0.2, duration=0.2),
            SpeechInterval(start_time=1.0, end_time=2.0, duration=1.0),
            SpeechInterval(start_time=5.0, end_time=9.0, duration=4.0),
        ]
        windows = diarizer.slice_speech_intervals(
            speech_intervals=intervals,
            window_duration=1.5,
            step_duration=0.75,
            min_speech_duration=0.3,
        )
        assert len(windows) > 1
        # First interval (0.2s) should be excluded
        assert windows[0] == (1.0, 2.0)
        # Check window bounds for third interval
        third_windows = [w for w in windows if w[0] >= 5.0]
        assert len(third_windows) >= 4
        assert third_windows[0] == (5.0, 6.5)
        assert third_windows[1] == (5.75, 7.25)

    def test_consolidate_turns_same_speaker(self, diarizer):
        speakers = [
            DiarizedSpeaker(
                speaker_index=0,
                speaker_identifier="SPEAKER_00",
                display_name="Speaker 1",
                total_speech_duration=0.0,
                turn_count=0,
                centroid=np.zeros(512, dtype=np.float32),
                color="#6366f1",
            )
        ]
        windows = [(0.0, 1.5), (0.75, 2.25), (1.5, 3.0)]
        labels = np.array([0, 0, 0], dtype=int)
        confs = np.array([0.9, 0.95, 0.92], dtype=np.float32)

        turns = diarizer.consolidate_turns(
            windows=windows,
            labels=labels,
            confidences=confs,
            speakers=speakers,
        )
        assert len(turns) == 1
        assert turns[0].speaker_index == 0
        assert turns[0].start_time == 0.0
        assert turns[0].end_time == 3.0
        assert turns[0].duration == 3.0

    def test_consolidate_turns_speaker_switch_midpoint(self, diarizer):
        speakers = [
            DiarizedSpeaker(0, "SPEAKER_00", "Speaker 1", 0.0, 0, np.zeros(512), "#6366f1"),
            DiarizedSpeaker(1, "SPEAKER_01", "Speaker 2", 0.0, 0, np.zeros(512), "#10b981"),
        ]
        # Overlapping transition at 1.5s
        windows = [(0.0, 1.5), (0.75, 2.25)]
        labels = np.array([0, 1], dtype=int)
        confs = np.array([0.9, 0.85], dtype=np.float32)

        turns = diarizer.consolidate_turns(
            windows=windows,
            labels=labels,
            confidences=confs,
            speakers=speakers,
        )
        assert len(turns) == 2
        # Midpoint of overlap [0.75, 1.5] is (0.75 + 1.5) / 2 = 1.125s
        assert turns[0].speaker_index == 0
        assert turns[0].start_time == 0.0
        assert abs(turns[0].end_time - 1.125) < 1e-3
        assert turns[1].speaker_index == 1
        assert abs(turns[1].start_time - 1.125) < 1e-3
        assert turns[1].end_time == 2.25

    def test_der_evaluation(self, diarizer):
        ref_turns = [
            (0.0, 5.0, "SPEAKER_00"),
            (5.0, 10.0, "SPEAKER_01"),
        ]
        hyp_turns = [
            SpeakerTurnData(0, "SPEAKER_00", "Speaker 1", 0.0, 5.0, 5.0, 0.95),
            SpeakerTurnData(1, "SPEAKER_01", "Speaker 2", 5.0, 10.0, 5.0, 0.95),
        ]
        der_metrics = diarizer.evaluate_der(ref_turns, hyp_turns, collar_sec=0.25)
        assert der_metrics["der"] == 0.0
        assert der_metrics["confusion_time"] == 0.0

    def test_real_speech_diarization(self, diarizer):
        ref_path = Path("backend/storage/clipforge_data/cache/speech_ref_35s.wav")
        if not ref_path.exists():
            pytest.skip("Test audio file speech_ref_35s.wav not present")

        with wave.open(str(ref_path), "rb") as wf:
            pcm = wf.readframes(wf.getnframes())
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

        res = diarizer.diarize(audio, sample_rate=16000)
        assert res.num_speakers == 1
        assert len(res.speakers) == 1
        assert res.speakers[0].speaker_identifier == "SPEAKER_00"
        assert res.speakers[0].display_name == "Speaker 1"
        assert res.total_speech_duration > 20.0
        assert res.rtf < 0.5  # Sub-real-time CPU execution
