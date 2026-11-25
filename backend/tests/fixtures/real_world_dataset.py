"""
ClipForge AI - Real-World Audio-Visual Active Speaker Benchmark Dataset
Constructs reproducible, deterministic test fixtures and ground-truth annotations
for 20 challenging real-world multi-modal scenarios.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.ai.audio_visual.schemas import (
    ActiveSpeakerObservation,
    ActiveSpeakerSegment,
    SpeakerFaceMatch,
)
from app.ai.vision.schemas import LipDynamicsMeasurement


@dataclass
class ScenarioGroundTruth:
    """Ground truth expectations for a benchmark scenario."""
    scenario_id: str
    description: str
    duration_seconds: float
    ground_truth_active_intervals: List[Dict[str, Any]]  # [{"track_id": str, "start": float, "end": float}]
    ground_truth_associations: Dict[str, Optional[str]]   # speaker_id -> face_track_id (or None for off-screen)
    expected_off_screen_speakers: List[str] = field(default_factory=list)
    has_cross_talk: bool = False
    has_scene_cut: bool = False
    notes: str = ""


@dataclass
class ScenarioTestData:
    """Generated multimodal signals for a scenario."""
    ground_truth: ScenarioGroundTruth
    observations_by_track: Dict[str, List[ActiveSpeakerObservation]]
    lip_measurements_by_track: Dict[str, List[LipDynamicsMeasurement]]
    vad_intervals: List[Tuple[float, float]]
    speaker_turns: List[Dict[str, Any]]
    scene_cuts: List[float] = field(default_factory=list)


def create_scenario_observations(
    track_id: str,
    timestamps: List[float],
    active_ranges: List[Tuple[float, float]],
    mouth_behavior: str = "normal_speech",  # normal_speech, silent_chewing, smiling, static_open, yawning, listener
    is_occluded_ranges: Optional[List[Tuple[float, float]]] = None,
) -> Tuple[List[ActiveSpeakerObservation], List[LipDynamicsMeasurement]]:
    """Helper to synthesize physically grounded multimodal observations for a track."""
    is_occluded_ranges = is_occluded_ranges or []
    obs_list: List[ActiveSpeakerObservation] = []
    lip_list: List[LipDynamicsMeasurement] = []

    for t in timestamps:
        is_active = any(s <= t <= e for s, e in active_ranges)
        is_occluded = any(s <= t <= e for s, e in is_occluded_ranges)

        if is_occluded:
            obs = ActiveSpeakerObservation(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                raw_logit=-3.0,
                speaking_probability=0.01,
                is_speaking=False,
                sync_confidence=0.2,
                state="unknown",
            )
            lip = LipDynamicsMeasurement(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                aperture=0.0,
                mouth_width=0.0,
                mar_raw=0.0,
                mar_smooth=0.0,
                mar_velocity=0.0,
                mar_variance=0.0,
            )
        elif mouth_behavior == "normal_speech":
            if is_active:
                obs = ActiveSpeakerObservation(
                    timestamp_seconds=round(t, 3),
                    face_track_id=track_id,
                    raw_logit=2.2,
                    speaking_probability=0.90,
                    is_speaking=True,
                    sync_confidence=1.0,
                    state="active",
                )
                lip = LipDynamicsMeasurement(
                    timestamp_seconds=round(t, 3),
                    face_track_id=track_id,
                    aperture=0.04,
                    mouth_width=0.10,
                    mar_raw=0.40,
                    mar_smooth=0.40,
                    mar_velocity=6.2,
                    mar_variance=0.012,
                )
            else:
                obs = ActiveSpeakerObservation(
                    timestamp_seconds=round(t, 3),
                    face_track_id=track_id,
                    raw_logit=-2.0,
                    speaking_probability=0.08,
                    is_speaking=False,
                    sync_confidence=1.0,
                    state="inactive",
                )
                lip = LipDynamicsMeasurement(
                    timestamp_seconds=round(t, 3),
                    face_track_id=track_id,
                    aperture=0.005,
                    mouth_width=0.10,
                    mar_raw=0.05,
                    mar_smooth=0.05,
                    mar_velocity=0.2,
                    mar_variance=0.0001,
                )
        elif mouth_behavior == "silent_chewing":
            # Moving lips, but audio cross-modal confirms negative correlation
            obs = ActiveSpeakerObservation(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                raw_logit=-1.5,
                speaking_probability=0.15,
                is_speaking=False,
                sync_confidence=0.8,
                state="inactive",
            )
            lip = LipDynamicsMeasurement(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                aperture=0.025,
                mouth_width=0.09,
                mar_raw=0.28,
                mar_smooth=0.28,
                mar_velocity=3.5,
                mar_variance=0.005,
            )
        elif mouth_behavior == "smiling":
            obs = ActiveSpeakerObservation(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                raw_logit=-1.8,
                speaking_probability=0.10,
                is_speaking=False,
                sync_confidence=1.0,
                state="inactive",
            )
            lip = LipDynamicsMeasurement(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                aperture=0.015,
                mouth_width=0.14,
                mar_raw=0.11,
                mar_smooth=0.11,
                mar_velocity=0.4,
                mar_variance=0.0002,
            )
        elif mouth_behavior == "static_open":
            obs = ActiveSpeakerObservation(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                raw_logit=-2.2,
                speaking_probability=0.07,
                is_speaking=False,
                sync_confidence=1.0,
                state="inactive",
            )
            lip = LipDynamicsMeasurement(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                aperture=0.05,
                mouth_width=0.10,
                mar_raw=0.50,
                mar_smooth=0.50,
                mar_velocity=0.05,
                mar_variance=0.00001,
            )
        elif mouth_behavior == "yawning":
            obs = ActiveSpeakerObservation(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                raw_logit=-2.5,
                speaking_probability=0.05,
                is_speaking=False,
                sync_confidence=0.9,
                state="inactive",
            )
            lip = LipDynamicsMeasurement(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                aperture=0.07,
                mouth_width=0.11,
                mar_raw=0.64,
                mar_smooth=0.64,
                mar_velocity=0.8,
                mar_variance=0.0003,
            )
        else:  # listener
            obs = ActiveSpeakerObservation(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                raw_logit=-2.0,
                speaking_probability=0.05,
                is_speaking=False,
                sync_confidence=1.0,
                state="inactive",
            )
            lip = LipDynamicsMeasurement(
                timestamp_seconds=round(t, 3),
                face_track_id=track_id,
                aperture=0.005,
                mouth_width=0.10,
                mar_raw=0.05,
                mar_smooth=0.05,
                mar_velocity=0.1,
                mar_variance=0.0001,
            )

        obs_list.append(obs)
        lip_list.append(lip)

    return obs_list, lip_list


def build_scenario(scenario_num: int) -> ScenarioTestData:
    """Builds one of the 20 benchmark scenarios (1 to 20)."""
    # 25 FPS timestamps for 3.0s duration (75 frames)
    dur = 3.0
    ts = [round(i * 0.04, 3) for i in range(int(dur / 0.04))]

    if scenario_num == 1:
        # Scenario 1: Solo speaker to camera
        gt = ScenarioGroundTruth(
            scenario_id="scenario_01_solo_speaker",
            description="Solo speaker to camera with clean speech",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": "face_solo", "start": 0.4, "end": 2.6}],
            ground_truth_associations={"SPEAKER_00": "face_solo"},
        )
        obs, lips = create_scenario_observations("face_solo", ts, [(0.4, 2.6)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_solo": obs},
            lip_measurements_by_track={"face_solo": lips},
            vad_intervals=[(0.4, 2.6)],
            speaker_turns=[{"speaker_id": "SPEAKER_00", "start_time": 0.4, "end_time": 2.6}],
        )

    elif scenario_num == 2:
        # Scenario 2: Two-person alternating dialogue
        gt = ScenarioGroundTruth(
            scenario_id="scenario_02_two_person_dialogue",
            description="Two visible speakers alternating turns without overlap",
            duration_seconds=dur,
            ground_truth_active_intervals=[
                {"track_id": "face_a", "start": 0.2, "end": 1.2},
                {"track_id": "face_b", "start": 1.5, "end": 2.8},
            ],
            ground_truth_associations={"SPEAKER_00": "face_a", "SPEAKER_01": "face_b"},
        )
        obs_a, lips_a = create_scenario_observations("face_a", ts, [(0.2, 1.2)], "normal_speech")
        obs_b, lips_b = create_scenario_observations("face_b", ts, [(1.5, 2.8)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_a": obs_a, "face_b": obs_b},
            lip_measurements_by_track={"face_a": lips_a, "face_b": lips_b},
            vad_intervals=[(0.2, 1.2), (1.5, 2.8)],
            speaker_turns=[
                {"speaker_id": "SPEAKER_00", "start_time": 0.2, "end_time": 1.2},
                {"speaker_id": "SPEAKER_01", "start_time": 1.5, "end_time": 2.8},
            ],
        )

    elif scenario_num == 3:
        # Scenario 3: 3+ visible people (1 speaks, 2 listen)
        gt = ScenarioGroundTruth(
            scenario_id="scenario_03_multi_person_panel",
            description="3 visible people: 1 active speaker, 2 quiet listeners",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": "face_speaker", "start": 0.3, "end": 2.5}],
            ground_truth_associations={"SPEAKER_00": "face_speaker"},
        )
        obs_s, lips_s = create_scenario_observations("face_speaker", ts, [(0.3, 2.5)], "normal_speech")
        obs_l1, lips_l1 = create_scenario_observations("face_listen1", ts, [], "listener")
        obs_l2, lips_l2 = create_scenario_observations("face_listen2", ts, [], "listener")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_speaker": obs_s, "face_listen1": obs_l1, "face_listen2": obs_l2},
            lip_measurements_by_track={"face_speaker": lips_s, "face_listen1": lips_l1, "face_listen2": lips_l2},
            vad_intervals=[(0.3, 2.5)],
            speaker_turns=[{"speaker_id": "SPEAKER_00", "start_time": 0.3, "end_time": 2.5}],
        )

    elif scenario_num == 4:
        # Scenario 4: Off-screen narrator (zero faces in frame)
        gt = ScenarioGroundTruth(
            scenario_id="scenario_04_off_screen_narrator",
            description="Off-screen narrator with no faces visible",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": None, "start": 0.5, "end": 2.5}],
            ground_truth_associations={"SPEAKER_NARRATOR": None},
            expected_off_screen_speakers=["SPEAKER_NARRATOR"],
        )
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={},
            lip_measurements_by_track={},
            vad_intervals=[(0.5, 2.5)],
            speaker_turns=[{"speaker_id": "SPEAKER_NARRATOR", "start_time": 0.5, "end_time": 2.5}],
        )

    elif scenario_num == 5:
        # Scenario 5: Voiceover with silent visible people
        gt = ScenarioGroundTruth(
            scenario_id="scenario_05_voiceover_with_silent_people",
            description="Voiceover narration while visible faces sit silently",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": None, "start": 0.5, "end": 2.5}],
            ground_truth_associations={"SPEAKER_VOICEOVER": None},
            expected_off_screen_speakers=["SPEAKER_VOICEOVER"],
        )
        obs_silent, lips_silent = create_scenario_observations("face_silent_person", ts, [], "listener")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_silent_person": obs_silent},
            lip_measurements_by_track={"face_silent_person": lips_silent},
            vad_intervals=[(0.5, 2.5)],
            speaker_turns=[{"speaker_id": "SPEAKER_VOICEOVER", "start_time": 0.5, "end_time": 2.5}],
        )

    elif scenario_num == 6:
        # Scenario 6: Silent mouth movement (chewing/mouthing)
        gt = ScenarioGroundTruth(
            scenario_id="scenario_06_silent_chewing",
            description="Person chewing food silently; zero vocalization",
            duration_seconds=dur,
            ground_truth_active_intervals=[],
            ground_truth_associations={},
        )
        obs_chew, lips_chew = create_scenario_observations("face_chewing", ts, [], "silent_chewing")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_chewing": obs_chew},
            lip_measurements_by_track={"face_chewing": lips_chew},
            vad_intervals=[],
            speaker_turns=[],
        )

    elif scenario_num == 7:
        # Scenario 7: Smiling and laughing (no speech)
        gt = ScenarioGroundTruth(
            scenario_id="scenario_07_smiling_laughing",
            description="Person smiling wide without speech",
            duration_seconds=dur,
            ground_truth_active_intervals=[],
            ground_truth_associations={},
        )
        obs_smile, lips_smile = create_scenario_observations("face_smiling", ts, [], "smiling")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_smiling": obs_smile},
            lip_measurements_by_track={"face_smiling": lips_smile},
            vad_intervals=[],
            speaker_turns=[],
        )

    elif scenario_num == 8:
        # Scenario 8: Static open mouth (gasp)
        gt = ScenarioGroundTruth(
            scenario_id="scenario_08_static_open_mouth",
            description="Static open mouth with zero motion velocity and zero speech",
            duration_seconds=dur,
            ground_truth_active_intervals=[],
            ground_truth_associations={},
        )
        obs_static, lips_static = create_scenario_observations("face_open", ts, [], "static_open")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_open": obs_static},
            lip_measurements_by_track={"face_open": lips_static},
            vad_intervals=[],
            speaker_turns=[],
        )

    elif scenario_num == 9:
        # Scenario 9: Yawning
        gt = ScenarioGroundTruth(
            scenario_id="scenario_09_yawning",
            description="Person yawning slowly without acoustic speech",
            duration_seconds=dur,
            ground_truth_active_intervals=[],
            ground_truth_associations={},
        )
        obs_yawn, lips_yawn = create_scenario_observations("face_yawn", ts, [], "yawning")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_yawn": obs_yawn},
            lip_measurements_by_track={"face_yawn": lips_yawn},
            vad_intervals=[],
            speaker_turns=[],
        )

    elif scenario_num == 10:
        # Scenario 10: Rapid interruptions
        gt = ScenarioGroundTruth(
            scenario_id="scenario_10_rapid_interruptions",
            description="Person B interrupts Person A mid-sentence",
            duration_seconds=dur,
            ground_truth_active_intervals=[
                {"track_id": "face_interrupted", "start": 0.2, "end": 1.4},
                {"track_id": "face_interruptor", "start": 1.3, "end": 2.7},
            ],
            ground_truth_associations={"SPEAKER_00": "face_interrupted", "SPEAKER_01": "face_interruptor"},
            has_cross_talk=True,
        )
        obs_int_a, lips_int_a = create_scenario_observations("face_interrupted", ts, [(0.2, 1.4)], "normal_speech")
        obs_int_b, lips_int_b = create_scenario_observations("face_interruptor", ts, [(1.3, 2.7)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_interrupted": obs_int_a, "face_interruptor": obs_int_b},
            lip_measurements_by_track={"face_interrupted": lips_int_a, "face_interruptor": lips_int_b},
            vad_intervals=[(0.2, 2.7)],
            speaker_turns=[
                {"speaker_id": "SPEAKER_00", "start_time": 0.2, "end_time": 1.4},
                {"speaker_id": "SPEAKER_01", "start_time": 1.3, "end_time": 2.7},
            ],
        )

    elif scenario_num == 11:
        # Scenario 11: Overlapping cross-talk
        gt = ScenarioGroundTruth(
            scenario_id="scenario_11_overlapping_crosstalk",
            description="Two visible people speaking concurrently over an extended interval",
            duration_seconds=dur,
            ground_truth_active_intervals=[
                {"track_id": "face_talk_1", "start": 0.3, "end": 2.4},
                {"track_id": "face_talk_2", "start": 0.8, "end": 2.7},
            ],
            ground_truth_associations={"SPEAKER_A": "face_talk_1", "SPEAKER_B": "face_talk_2"},
            has_cross_talk=True,
        )
        obs_c1, lips_c1 = create_scenario_observations("face_talk_1", ts, [(0.3, 2.4)], "normal_speech")
        obs_c2, lips_c2 = create_scenario_observations("face_talk_2", ts, [(0.8, 2.7)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_talk_1": obs_c1, "face_talk_2": obs_c2},
            lip_measurements_by_track={"face_talk_1": lips_c1, "face_talk_2": lips_c2},
            vad_intervals=[(0.3, 2.7)],
            speaker_turns=[
                {"speaker_id": "SPEAKER_A", "start_time": 0.3, "end_time": 2.4},
                {"speaker_id": "SPEAKER_B", "start_time": 0.8, "end_time": 2.7},
            ],
        )

    elif scenario_num == 12:
        # Scenario 12: Similar visual/acoustic speakers
        gt = ScenarioGroundTruth(
            scenario_id="scenario_12_similar_speakers",
            description="Two similar speakers with distinct turns",
            duration_seconds=dur,
            ground_truth_active_intervals=[
                {"track_id": "face_twin_1", "start": 0.2, "end": 1.2},
                {"track_id": "face_twin_2", "start": 1.6, "end": 2.6},
            ],
            ground_truth_associations={"SPEAKER_TWIN_1": "face_twin_1", "SPEAKER_TWIN_2": "face_twin_2"},
        )
        obs_tw1, lips_tw1 = create_scenario_observations("face_twin_1", ts, [(0.2, 1.2)], "normal_speech")
        obs_tw2, lips_tw2 = create_scenario_observations("face_twin_2", ts, [(1.6, 2.6)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_twin_1": obs_tw1, "face_twin_2": obs_tw2},
            lip_measurements_by_track={"face_twin_1": lips_tw1, "face_twin_2": lips_tw2},
            vad_intervals=[(0.2, 1.2), (1.6, 2.6)],
            speaker_turns=[
                {"speaker_id": "SPEAKER_TWIN_1", "start_time": 0.2, "end_time": 1.2},
                {"speaker_id": "SPEAKER_TWIN_2", "start_time": 1.6, "end_time": 2.6},
            ],
        )

    elif scenario_num == 13:
        # Scenario 13: Return after long gap
        dur_long = 6.0
        ts_long = [round(i * 0.04, 3) for i in range(int(dur_long / 0.04))]
        gt = ScenarioGroundTruth(
            scenario_id="scenario_13_return_after_long_gap",
            description="Speaker speaks at t=0.5s, pauses for 3s, speaks again at t=4.5s",
            duration_seconds=dur_long,
            ground_truth_active_intervals=[
                {"track_id": "face_return", "start": 0.5, "end": 1.5},
                {"track_id": "face_return", "start": 4.5, "end": 5.5},
            ],
            ground_truth_associations={"SPEAKER_00": "face_return"},
        )
        obs_ret, lips_ret = create_scenario_observations("face_return", ts_long, [(0.5, 1.5), (4.5, 5.5)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_return": obs_ret},
            lip_measurements_by_track={"face_return": lips_ret},
            vad_intervals=[(0.5, 1.5), (4.5, 5.5)],
            speaker_turns=[
                {"speaker_id": "SPEAKER_00", "start_time": 0.5, "end_time": 1.5},
                {"speaker_id": "SPEAKER_00", "start_time": 4.5, "end_time": 5.5},
            ],
        )

    elif scenario_num == 14:
        # Scenario 14: Partial occlusion (hand/cup covering mouth)
        gt = ScenarioGroundTruth(
            scenario_id="scenario_14_partial_occlusion",
            description="Speaker mouth occluded mid-speech (t=1.2 to 1.6s)",
            duration_seconds=dur,
            ground_truth_active_intervals=[
                {"track_id": "face_occluded", "start": 0.3, "end": 1.1},
                {"track_id": "face_occluded", "start": 1.8, "end": 2.8},
            ],
            ground_truth_associations={"SPEAKER_00": "face_occluded"},
        )
        obs_occ, lips_occ = create_scenario_observations(
            "face_occluded", ts, [(0.3, 2.8)], "normal_speech", is_occluded_ranges=[(1.2, 1.7)]
        )
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_occluded": obs_occ},
            lip_measurements_by_track={"face_occluded": lips_occ},
            vad_intervals=[(0.3, 2.8)],
            speaker_turns=[{"speaker_id": "SPEAKER_00", "start_time": 0.3, "end_time": 2.8}],
        )

    elif scenario_num == 15:
        # Scenario 15: Profile face turned away
        gt = ScenarioGroundTruth(
            scenario_id="scenario_15_profile_face",
            description="Speaker turns head sideways during speech",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": "face_profile", "start": 0.3, "end": 1.2}],
            ground_truth_associations={"SPEAKER_00": "face_profile"},
        )
        obs_prof, lips_prof = create_scenario_observations(
            "face_profile", ts, [(0.3, 2.5)], "normal_speech", is_occluded_ranges=[(1.3, 2.5)]
        )
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_profile": obs_prof},
            lip_measurements_by_track={"face_profile": lips_prof},
            vad_intervals=[(0.3, 2.5)],
            speaker_turns=[{"speaker_id": "SPEAKER_00", "start_time": 0.3, "end_time": 2.5}],
        )

    elif scenario_num == 16:
        # Scenario 16: Scene cut
        gt = ScenarioGroundTruth(
            scenario_id="scenario_16_scene_cut",
            description="Scene cut at t=1.5s resetting visual tracks",
            duration_seconds=dur,
            ground_truth_active_intervals=[
                {"track_id": "face_cam_a", "start": 0.2, "end": 1.4},
                {"track_id": "face_cam_b", "start": 1.6, "end": 2.8},
            ],
            ground_truth_associations={"SPEAKER_00": "face_cam_a"},
            has_scene_cut=True,
        )
        obs_sc_a, lips_sc_a = create_scenario_observations("face_cam_a", ts, [(0.2, 1.4)], "normal_speech")
        obs_sc_b, lips_sc_b = create_scenario_observations("face_cam_b", ts, [(1.6, 2.8)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_cam_a": obs_sc_a, "face_cam_b": obs_sc_b},
            lip_measurements_by_track={"face_cam_a": lips_sc_a, "face_cam_b": lips_sc_b},
            vad_intervals=[(0.2, 1.4), (1.6, 2.8)],
            speaker_turns=[
                {"speaker_id": "SPEAKER_00", "start_time": 0.2, "end_time": 1.4},
                {"speaker_id": "SPEAKER_01", "start_time": 1.6, "end_time": 2.8},
            ],
            scene_cuts=[1.5],
        )

    elif scenario_num == 17:
        # Scenario 17: Background music
        gt = ScenarioGroundTruth(
            scenario_id="scenario_17_background_music",
            description="Speaker speaking with continuous background music",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": "face_music", "start": 0.4, "end": 2.6}],
            ground_truth_associations={"SPEAKER_00": "face_music"},
        )
        obs_mus, lips_mus = create_scenario_observations("face_music", ts, [(0.4, 2.6)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_music": obs_mus},
            lip_measurements_by_track={"face_music": lips_mus},
            vad_intervals=[(0.4, 2.6)],
            speaker_turns=[{"speaker_id": "SPEAKER_00", "start_time": 0.4, "end_time": 2.6}],
        )

    elif scenario_num == 18:
        # Scenario 18: Low SNR audio
        gt = ScenarioGroundTruth(
            scenario_id="scenario_18_low_snr_audio",
            description="Low SNR audio; relying on visual lip sync",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": "face_noisy", "start": 0.4, "end": 2.6}],
            ground_truth_associations={"SPEAKER_00": "face_noisy"},
        )
        obs_nsy, lips_nsy = create_scenario_observations("face_noisy", ts, [(0.4, 2.6)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_noisy": obs_nsy},
            lip_measurements_by_track={"face_noisy": lips_nsy},
            vad_intervals=[(0.4, 2.6)],
            speaker_turns=[{"speaker_id": "SPEAKER_00", "start_time": 0.4, "end_time": 2.6}],
        )

    elif scenario_num == 19:
        # Scenario 19: Non-zero AV stream offset (+80 ms)
        gt = ScenarioGroundTruth(
            scenario_id="scenario_19_nonzero_av_offset",
            description="Audio offset by +80 ms; handled by AV synchronizer",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": "face_offset", "start": 0.4, "end": 2.6}],
            ground_truth_associations={"SPEAKER_00": "face_offset"},
        )
        obs_off, lips_off = create_scenario_observations("face_offset", ts, [(0.4, 2.6)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_offset": obs_off},
            lip_measurements_by_track={"face_offset": lips_off},
            vad_intervals=[(0.48, 2.68)],  # Shifted audio by +80ms
            speaker_turns=[{"speaker_id": "SPEAKER_00", "start_time": 0.48, "end_time": 2.68}],
        )

    elif scenario_num == 20:
        # Scenario 20: Variable Frame Rate (VFR) video
        gt = ScenarioGroundTruth(
            scenario_id="scenario_20_vfr_video",
            description="Variable frame rate with timestamp jitter",
            duration_seconds=dur,
            ground_truth_active_intervals=[{"track_id": "face_vfr", "start": 0.3, "end": 2.5}],
            ground_truth_associations={"SPEAKER_00": "face_vfr"},
        )
        # Jittered timestamps
        vfr_ts = sorted([round(t + (0.008 if i % 2 == 0 else -0.008), 3) for i, t in enumerate(ts)])
        obs_vfr, lips_vfr = create_scenario_observations("face_vfr", vfr_ts, [(0.3, 2.5)], "normal_speech")
        return ScenarioTestData(
            ground_truth=gt,
            observations_by_track={"face_vfr": obs_vfr},
            lip_measurements_by_track={"face_vfr": lips_vfr},
            vad_intervals=[(0.3, 2.5)],
            speaker_turns=[{"speaker_id": "SPEAKER_00", "start_time": 0.3, "end_time": 2.5}],
        )

    else:
        raise ValueError(f"Unknown scenario number: {scenario_num}. Must be 1 to 20.")
