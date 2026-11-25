"""
ClipForge AI - Multi-Evidence Audio-Visual Fusion Engine
Combines Silero VAD, CAM++ Diarization, Face Tracking, Lip Dynamics, and Light-ASD into a unified intelligence engine.
Strictly separates Concept A (Active Speaker Detection) from Concept B (Speaker-Face Identity Association).
Local-first, CPU-optimized, zero cloud dependencies.
"""

import collections
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from ..vision.schemas import LipDynamicsMeasurement
from .schemas import (
    ActiveSpeakerObservation,
    ActiveSpeakerSegment,
    SpeakerFaceMatch,
)

logger = logging.getLogger("clipforge.ai.audio_visual.fusion")

DEFAULT_ONSET_THRESHOLD = 0.65
DEFAULT_OFFSET_THRESHOLD = 0.35
MIN_SPEECH_DURATION_SECONDS = 0.25
MIN_GAP_MERGE_SECONDS = 0.15
MIN_ASSOCIATION_CONFIDENCE = 0.30
MIN_SUSTAINED_ONSET_FRAMES = 3  # ~120 ms at 25 FPS
MIN_SUSTAINED_OFFSET_FRAMES = 6  # ~240 ms at 25 FPS


class AudioVisualFusionEngine:
    """
    Multimodal fusion engine synthesizing acoustic and visual evidence.
    Does not enforce forced identity assignments. Handles off-screen voices,
    silent mouth movements, cross-talk, scene cuts, and multi-turn acoustic dialogue.
    """

    def __init__(
        self,
        onset_threshold: float = DEFAULT_ONSET_THRESHOLD,
        offset_threshold: float = DEFAULT_OFFSET_THRESHOLD,
        min_speech_duration: float = MIN_SPEECH_DURATION_SECONDS,
        min_gap_merge: float = MIN_GAP_MERGE_SECONDS,
        min_association_confidence: float = MIN_ASSOCIATION_CONFIDENCE,
        weight_asd: float = 0.70,
        weight_lip: float = 0.30,
    ):
        self.onset_threshold = onset_threshold
        self.offset_threshold = offset_threshold
        self.min_speech_duration = min_speech_duration
        self.min_gap_merge = min_gap_merge
        self.min_association_confidence = min_association_confidence
        self.weight_asd = weight_asd
        self.weight_lip = weight_lip

    def compute_composite_frame_score(
        self,
        asd_prob: float,
        mar_velocity: float,
        mar_variance: float,
        is_vad_active: bool,
        sync_confidence: float = 1.0,
        is_occluded: bool = False,
    ) -> float:
        """
        Combines acoustic VAD gate, visual mouth velocity/variance, and Light-ASD cross-modal score.
        VAD acts as a soft modulating signal rather than a destructive unconditional kill-switch.
        Handles occluded faces and rejects silent mouth movement (chewing, yawning, smiling).
        """
        if is_occluded:
            return 0.0

        # Lip motion dynamic score normalized
        # Typical active speech has mar_velocity in [2.0, 10.0] and variance > 0.001
        norm_velocity = np.clip(mar_velocity / 6.0, 0.0, 1.0)
        norm_variance = np.clip(mar_variance / 0.015, 0.0, 1.0)
        lip_score = 0.70 * norm_velocity + 0.30 * norm_variance

        # Cross-modal model score
        raw_multimodal = (self.weight_asd * asd_prob + self.weight_lip * lip_score) * sync_confidence

        # VAD modulation: if VAD is active, maintain or boost confidence.
        # If VAD is inactive, apply damping unless visual/ASD evidence is overwhelming.
        if is_vad_active:
            composite = raw_multimodal * 1.05
        else:
            # Soft attenuation: allows strong visual speech to be preserved even if VAD missed it.
            # Rejects silent mouth movements (chewing, yawning, smiling) where VAD is 0 and ASD is low.
            if raw_multimodal > 0.80 and lip_score > 0.60:
                composite = raw_multimodal * 0.85
            else:
                composite = raw_multimodal * 0.35

        return float(np.clip(composite, 0.0, 1.0))

    def detect_active_speaker_intervals(
        self,
        observations_by_track: Dict[str, List[ActiveSpeakerObservation]],
        lip_measurements_by_track: Dict[str, List[LipDynamicsMeasurement]],
        vad_intervals: List[Tuple[float, float]],  # List of (start_time, end_time)
        video_duration: float,
        scene_cuts: Optional[List[float]] = None,
    ) -> List[ActiveSpeakerSegment]:
        """
        CONCEPT A: Instantaneous active speaker detection across all visible face tracks over time.
        Categorizes visible faces, detects simultaneous speech (overlapping), and off-screen speech.
        """
        active_segments: List[ActiveSpeakerSegment] = []
        scene_cuts = scene_cuts or []

        # Helper to query if a timestamp falls within any acoustic VAD speech interval
        def check_vad_active(t: float) -> bool:
            for v_start, v_end in vad_intervals:
                if v_start <= t <= v_end:
                    return True
            return False

        # Process each face track independently
        all_tracks = sorted(list(set(observations_by_track.keys()) | set(lip_measurements_by_track.keys())))

        for track_id in all_tracks:
            asd_obs = observations_by_track.get(track_id, [])
            lip_obs = lip_measurements_by_track.get(track_id, [])

            # Index by timestamp
            asd_dict = {round(obs.timestamp_seconds, 3): obs for obs in asd_obs}
            lip_dict = {round(lip.timestamp_seconds, 3): lip for lip in lip_obs}
            common_times = sorted(set(asd_dict.keys()) | set(lip_dict.keys()))

            scored_times: List[Tuple[float, float]] = []
            for t in common_times:
                obs = asd_dict.get(t)
                lip = lip_dict.get(t)

                asd_p = obs.speaking_probability if obs else 0.0
                mar_v = lip.mar_velocity if lip else 0.0
                mar_var = lip.mar_variance if lip else 0.0
                sync_c = obs.sync_confidence if obs else 1.0
                vad_active = check_vad_active(t)

                score = self.compute_composite_frame_score(
                    asd_prob=asd_p,
                    mar_velocity=mar_v,
                    mar_variance=mar_var,
                    is_vad_active=vad_active,
                    sync_confidence=sync_c,
                )
                scored_times.append((t, score))

            # Apply temporal hysteresis for this track
            raw_intervals = self._apply_hysteresis_intervals(scored_times, scene_cuts=scene_cuts)

            for seg_start, seg_end, avg_conf in raw_intervals:
                active_segments.append(
                    ActiveSpeakerSegment(
                        start_time=round(seg_start, 3),
                        end_time=round(seg_end, 3),
                        duration=round(seg_end - seg_start, 3),
                        face_track_id=track_id,
                        confidence=round(avg_conf, 3),
                        speaking_score=round(avg_conf, 3),
                        state="active_speaker",
                    )
                )

        # Detect simultaneous speech (cross-talk / overlapping) across multiple visible tracks
        self._tag_overlapping_intervals(active_segments)

        # Detect OFF-SCREEN speech intervals:
        # Time intervals where VAD speech occurs, but no visible face track is classified as active_speaker
        off_screen_segments = self._detect_off_screen_intervals(vad_intervals, active_segments)
        active_segments.extend(off_screen_segments)

        # Sort all segments chronologically
        active_segments.sort(key=lambda s: s.start_time)
        return active_segments

    def _apply_hysteresis_intervals(
        self,
        scored_times: List[Tuple[float, float]],
        scene_cuts: Optional[List[float]] = None,
    ) -> List[Tuple[float, float, float]]:
        """
        Applies dual-threshold hysteresis (onset=0.65, offset=0.35), sustained frames check,
        minimum duration filtering, gap bridging, and scene-cut boundary resets.
        """
        if not scored_times:
            return []

        scene_cuts = scene_cuts or []
        intervals: List[Tuple[float, float, float]] = []
        is_active = False
        start_t = 0.0
        scores_in_interval: List[float] = []

        consecutive_onset_frames = 0
        consecutive_offset_frames = 0

        for t, score in scored_times:
            if not is_active:
                if score >= self.onset_threshold:
                    consecutive_onset_frames += 1
                    if consecutive_onset_frames >= MIN_SUSTAINED_ONSET_FRAMES:
                        is_active = True
                        start_t = t - (consecutive_onset_frames - 1) * 0.04
                        scores_in_interval = [score]
                        consecutive_offset_frames = 0
                else:
                    consecutive_onset_frames = 0
            else:
                scores_in_interval.append(score)
                if score < self.offset_threshold:
                    consecutive_offset_frames += 1
                    if consecutive_offset_frames >= MIN_SUSTAINED_OFFSET_FRAMES:
                        is_active = False
                        end_t = t - (consecutive_offset_frames - 1) * 0.04
                        dur = end_t - start_t
                        if dur >= self.min_speech_duration:
                            avg_c = float(np.mean(scores_in_interval))
                            intervals.append((start_t, end_t, avg_c))
                        scores_in_interval = []
                        consecutive_onset_frames = 0
                else:
                    consecutive_offset_frames = 0

        # Flush trailing interval
        if is_active and scores_in_interval:
            end_t = scored_times[-1][0]
            dur = end_t - start_t
            if dur >= self.min_speech_duration:
                intervals.append((start_t, end_t, float(np.mean(scores_in_interval))))

        # Merge adjacent intervals separated by small gap (< 150 ms), respecting scene cuts
        merged: List[Tuple[float, float, float]] = []
        for interval in intervals:
            if not merged:
                merged.append(interval)
            else:
                prev_s, prev_e, prev_c = merged[-1]
                curr_s, curr_e, curr_c = interval
                gap = curr_s - prev_e

                # Check if a scene cut falls in between
                cut_in_between = any(prev_e <= cut <= curr_s for cut in scene_cuts)

                if gap <= self.min_gap_merge and not cut_in_between:
                    # Merge
                    new_end = curr_e
                    new_conf = (prev_c + curr_c) / 2.0
                    merged[-1] = (prev_s, new_end, new_conf)
                else:
                    merged.append(interval)

        return merged

    def _tag_overlapping_intervals(self, active_segments: List[ActiveSpeakerSegment]) -> None:
        """
        Tags active speaker segments that overlap with other active tracks as 'overlapping'
        in their metadata to identify cross-talk and interruptions.
        """
        for i, seg_a in enumerate(active_segments):
            if not seg_a.face_track_id:
                continue
            for j, seg_b in enumerate(active_segments):
                if i != j and seg_b.face_track_id and seg_a.face_track_id != seg_b.face_track_id:
                    inter_s = max(seg_a.start_time, seg_b.start_time)
                    inter_e = min(seg_a.end_time, seg_b.end_time)
                    if inter_e - inter_s >= 0.10:
                        seg_a.metadata["has_cross_talk"] = True
                        seg_b.metadata["has_cross_talk"] = True

    def _detect_off_screen_intervals(
        self,
        vad_intervals: List[Tuple[float, float]],
        active_face_segments: List[ActiveSpeakerSegment],
    ) -> List[ActiveSpeakerSegment]:
        """
        Identifies audio speech segments where no visible face was active.
        """
        off_screen: List[ActiveSpeakerSegment] = []

        for v_start, v_end in vad_intervals:
            # Compute total overlap with any visible active speaker
            overlap_dur = 0.0
            for seg in active_face_segments:
                if seg.face_track_id is not None:
                    inter_s = max(v_start, seg.start_time)
                    inter_e = min(v_end, seg.end_time)
                    if inter_e > inter_s:
                        overlap_dur += (inter_e - inter_s)

            vad_dur = v_end - v_start
            if vad_dur > 0:
                coverage_ratio = overlap_dur / vad_dur
                # If less than 20% of speech is matched to a visible face, classify as off-screen
                if coverage_ratio < 0.20 and vad_dur >= self.min_speech_duration:
                    off_screen.append(
                        ActiveSpeakerSegment(
                            start_time=round(v_start, 3),
                            end_time=round(v_end, 3),
                            duration=round(vad_dur, 3),
                            face_track_id=None,
                            confidence=0.85,
                            speaking_score=0.85,
                            state="off_screen_speaker",
                        )
                    )

        return off_screen

    def associate_speakers_to_faces(
        self,
        speaker_turns: List[Dict[str, Any]],  # List of turns: {"speaker_id": str, "start_time": float, "end_time": float}
        active_segments: List[ActiveSpeakerSegment],
        manual_overrides: Optional[Dict[str, str]] = None,  # speaker_id -> face_track_id
    ) -> List[SpeakerFaceMatch]:
        """
        CONCEPT B: Global identity association between acoustic Speaker IDs and visual Face Tracks.
        Enforces multi-turn aggregation, negative co-occurrence penalization, turn consistency,
        bipartite matching, and absolute preservation of manual overrides.
        """
        manual_overrides = manual_overrides or {}

        # Collect unique speaker IDs and face track IDs
        speaker_ids = sorted(list(set(turn["speaker_id"] for turn in speaker_turns if turn.get("speaker_id"))))
        visible_track_ids = sorted(list(set(seg.face_track_id for seg in active_segments if seg.face_track_id)))

        matches: List[SpeakerFaceMatch] = []
        assigned_tracks: Set[str] = set()

        # 1. Apply manual overrides first (they have absolute precedence and are locked)
        for spk_id in speaker_ids:
            if spk_id in manual_overrides:
                target_face = manual_overrides[spk_id]
                is_off = target_face in (None, "off_screen", "")
                actual_face = None if is_off else target_face
                if actual_face:
                    assigned_tracks.add(actual_face)

                matches.append(
                    SpeakerFaceMatch(
                        speaker_id=spk_id,
                        face_track_id=actual_face,
                        confidence=1.0,
                        overlap_duration=0.0,
                        turn_consistency=1.0,
                        status="confirmed",
                        is_manual=True,
                        is_off_screen=is_off,
                        evidence_notes="User manual override (permanent)",
                    )
                )

        remaining_speakers = [s for s in speaker_ids if s not in manual_overrides]
        available_tracks = [t for t in visible_track_ids if t not in assigned_tracks]

        if not remaining_speakers:
            return matches

        # 2. Multi-turn aggregation matrices
        # speaker_turns_by_id: speaker_id -> List of (start_t, end_t)
        spk_turns: Dict[str, List[Tuple[float, float]]] = collections.defaultdict(list)
        speaker_total_dur: Dict[str, float] = collections.defaultdict(float)

        for turn in speaker_turns:
            s_id = turn.get("speaker_id")
            if s_id in speaker_ids:
                s_t = float(turn["start_time"])
                e_t = float(turn["end_time"])
                spk_turns[s_id].append((s_t, e_t))
                speaker_total_dur[s_id] += max(0.0, e_t - s_t)

        # Overlap matrix: overlap_matrix[s_id][track_id] = total overlap seconds
        overlap_matrix: Dict[str, Dict[str, float]] = {s: {t: 0.0 for t in available_tracks} for s in remaining_speakers}
        # Turn match matrix: turn_match_matrix[s_id][track_id] = number of turns where face vocalized
        turn_match_matrix: Dict[str, Dict[str, int]] = {s: {t: 0 for t in available_tracks} for s in remaining_speakers}

        for s_id in remaining_speakers:
            turns = spk_turns[s_id]
            for t_start, t_end in turns:
                turn_dur = t_end - t_start
                if turn_dur <= 0:
                    continue
                turn_tracks_active: Set[str] = set()

                for seg in active_segments:
                    if seg.face_track_id in available_tracks:
                        inter_s = max(t_start, seg.start_time)
                        inter_e = min(t_end, seg.end_time)
                        if inter_e > inter_s:
                            dur_overlap = inter_e - inter_s
                            overlap_matrix[s_id][seg.face_track_id] += dur_overlap
                            if dur_overlap >= min(0.20, turn_dur * 0.30):
                                turn_tracks_active.add(seg.face_track_id)

                for t_active in turn_tracks_active:
                    turn_match_matrix[s_id][t_active] += 1

        # Negative co-occurrence: duration where face was active during OTHER speakers' turns
        negative_matrix: Dict[str, Dict[str, float]] = {s: {t: 0.0 for t in available_tracks} for s in remaining_speakers}
        for s_id in remaining_speakers:
            other_speakers = [other for other in speaker_ids if other != s_id]
            for other_id in other_speakers:
                for o_start, o_end in spk_turns[other_id]:
                    for seg in active_segments:
                        if seg.face_track_id in available_tracks:
                            inter_s = max(o_start, seg.start_time)
                            inter_e = min(o_end, seg.end_time)
                            if inter_e > inter_s:
                                negative_matrix[s_id][seg.face_track_id] += (inter_e - inter_s)

        # 3. Solve maximum weight association with multi-turn scoring
        for spk_id in remaining_speakers:
            best_track: Optional[str] = None
            best_score: float = -1.0
            best_overlap: float = 0.0
            best_consistency: float = 0.0
            best_matched_turns: int = 0

            total_spk_time = max(0.1, speaker_total_dur.get(spk_id, 0.0))
            total_turns = len(spk_turns[spk_id])

            for trk_id in available_tracks:
                overlap = overlap_matrix[spk_id].get(trk_id, 0.0)
                neg_overlap = negative_matrix[spk_id].get(trk_id, 0.0)
                matched_turns = turn_match_matrix[spk_id].get(trk_id, 0)

                consistency = matched_turns / max(1, total_turns)
                # Net score penalizes face if it vocalized when someone else was speaking
                net_dur = max(0.0, overlap - 0.50 * neg_overlap)
                score = net_dur / total_spk_time

                if score > best_score:
                    best_score = score
                    best_overlap = overlap
                    best_track = trk_id
                    best_consistency = consistency
                    best_matched_turns = matched_turns

            if best_track is not None and best_score >= self.min_association_confidence:
                # Determine status: confirmed vs provisional
                is_confirmed = (total_turns >= 2 and best_consistency >= 0.70 and best_score >= 0.50)
                status = "confirmed" if is_confirmed else "provisional"

                matches.append(
                    SpeakerFaceMatch(
                        speaker_id=spk_id,
                        face_track_id=best_track,
                        confidence=round(min(1.0, float(best_score)), 3),
                        overlap_duration=round(best_overlap, 3),
                        turn_consistency=round(best_consistency, 3),
                        status=status,
                        turns_matched=best_matched_turns,
                        total_turns=total_turns,
                        is_manual=False,
                        is_off_screen=False,
                        evidence_notes=(
                            f"Multi-turn overlap {round(best_overlap, 2)}s ({round(best_score * 100, 1)}%), "
                            f"{best_matched_turns}/{total_turns} turns consistent ({status})"
                        ),
                    )
                )
                available_tracks.remove(best_track)
            else:
                # Mark as off-screen
                matches.append(
                    SpeakerFaceMatch(
                        speaker_id=spk_id,
                        face_track_id=None,
                        confidence=0.85 if best_score < 0.10 else round(1.0 - best_score, 3),
                        overlap_duration=round(best_overlap, 3),
                        turn_consistency=0.0,
                        status="off_screen",
                        turns_matched=0,
                        total_turns=total_turns,
                        is_manual=False,
                        is_off_screen=True,
                        evidence_notes="Off-screen speaker (no visible face matches acoustic turns)",
                    )
                )

        return matches
