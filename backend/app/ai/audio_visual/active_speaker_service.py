"""
ClipForge AI - Active Speaker Analysis Service
High-level service orchestrating Face Landmarks, Lip Dynamics, Audio Synchronization,
Light-ASD inference, and Multi-Evidence Audio-Visual Fusion.
Local-first, CPU-optimized, zero cloud dependencies.
"""

import gc
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from ...core.config import settings
from ..audio.audio_preprocessor import AudioPreprocessor
from ..vision.landmark_detector import MediaPipeFaceLandmarkDetector
from ..vision.lip_dynamics import LipDynamicsExtractor
from ..vision.schemas import DenseFaceLandmarks, LipDynamicsMeasurement, NormalizedBBox
from .active_speaker_detector import AVTemporalAdapter, LightASDDetector
from .av_fusion_engine import AudioVisualFusionEngine
from .av_synchronizer import AudioVisualSynchronizer, StreamSyncInfo
from .schemas import (
    ActiveSpeakerAnalysisResult,
    ActiveSpeakerObservation,
    ActiveSpeakerSegment,
    SpeakerFaceMatch,
)

logger = logging.getLogger("clipforge.ai.audio_visual.service")


def get_primary_active_speaker_at(
    timestamp: float,
    active_segments: List[ActiveSpeakerSegment],
) -> Optional[Dict[str, Any]]:
    """
    Consumer interface for Phase 6 SubjectSelector / ReframeEngine.
    Returns the primary active speaker at the given timestamp, or None if no active speaker.
    Handles overlapping/cross-talk by returning the highest confidence segment.
    """
    candidates = [
        s for s in active_segments
        if s.start_time <= timestamp <= s.end_time
        and s.state in ("active_speaker", "active")
        and s.face_track_id
    ]
    if not candidates:
        return None
    # Sort by confidence descending
    candidates.sort(key=lambda x: x.confidence, reverse=True)
    best = candidates[0]
    return {
        "face_track_id": best.face_track_id,
        "speaker_id": best.speaker_id,
        "confidence": best.confidence,
        "state": best.state,
        "speaking_score": best.speaking_score,
    }


class ActiveSpeakerService:
    """
    Coordinates end-to-end active speaker analysis and speaker-to-face identity association.
    Uses bounded chunked processing to ensure incremental memory usage remains < 120 MB RAM.
    """

    def __init__(
        self,
        landmark_detector: Optional[MediaPipeFaceLandmarkDetector] = None,
        lip_dynamics_extractor: Optional[LipDynamicsExtractor] = None,
        light_asd_detector: Optional[LightASDDetector] = None,
        fusion_engine: Optional[AudioVisualFusionEngine] = None,
    ):
        self.landmark_detector = landmark_detector or MediaPipeFaceLandmarkDetector()
        self.lip_dynamics_extractor = lip_dynamics_extractor or LipDynamicsExtractor()
        self.light_asd_detector = light_asd_detector or LightASDDetector()
        self.fusion_engine = fusion_engine or AudioVisualFusionEngine()

    def analyze_active_speakers(
        self,
        video_id: str,
        video_path: Union[str, Path],
        audio_samples_16k: np.ndarray,
        face_tracks_data: List[Dict[str, Any]],  # List of tracks: {"track_id": str, "samples": [...]}
        speaker_turns: List[Dict[str, Any]],     # Diarization speaker turns
        vad_intervals: List[Tuple[float, float]],  # Silero VAD speech intervals (start, end)
        manual_overrides: Optional[Dict[str, str]] = None,  # speaker_id -> face_track_id
        scene_cuts: Optional[List[float]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> ActiveSpeakerAnalysisResult:
        """
        Executes end-to-end multimodal active speaker analysis.
        Args:
            video_id: UUID of the video.
            video_path: Path to the source video file on disk.
            audio_samples_16k: Canonical 16 kHz mono float32 waveform.
            face_tracks_data: Detected face tracks from Phase 6 computer vision.
            speaker_turns: Stage 3 speaker turns with speaker_id, start_time, end_time.
            vad_intervals: Stage 2 acoustic speech intervals.
            manual_overrides: Existing user manual speaker-to-face assignments.
            scene_cuts: Optional list of detected scene cut timestamps.
            progress_callback: Optional progress reporter (0.0 to 1.0, stage_description).
            is_cancelled: Optional cancellation probe.
        """
        start_wall_time = time.time()
        video_path = Path(video_path)

        def report(pct: float, msg: str):
            if progress_callback:
                progress_callback(pct, msg)

        report(0.05, "Initializing audio-visual synchronizer")
        sync_engine = AudioVisualSynchronizer(
            audio_samples=audio_samples_16k,
            sync_info=StreamSyncInfo(audio_sample_rate=16000),
            default_window_duration=0.40,
        )

        total_video_duration = len(audio_samples_16k) / 16000.0

        if not face_tracks_data:
            logger.info("No face tracks found in video; detecting off-screen speech only.")
            off_screen_segs = self.fusion_engine.detect_active_speaker_intervals(
                observations_by_track={},
                lip_measurements_by_track={},
                vad_intervals=vad_intervals,
                video_duration=total_video_duration,
                scene_cuts=scene_cuts,
            )
            matches = self.fusion_engine.associate_speakers_to_faces(
                speaker_turns=speaker_turns,
                active_segments=off_screen_segs,
                manual_overrides=manual_overrides,
            )
            dur_proc = time.time() - start_wall_time
            rtf = dur_proc / max(0.1, total_video_duration)
            return ActiveSpeakerAnalysisResult(
                video_id=video_id,
                status="completed",
                active_segments=off_screen_segs,
                associations=matches,
                total_active_speech_seconds=sum(s.duration for s in off_screen_segs if s.state == "active_speaker"),
                total_face_tracks_analyzed=0,
                rtf=round(rtf, 4),
                processing_time_seconds=round(dur_proc, 3),
            )

        # 1. Index face track samples by track
        tracks_by_id: Dict[str, List[Dict[str, Any]]] = {}
        for t_info in face_tracks_data:
            t_id = t_info.get("track_id", "track_unknown")
            samples = t_info.get("samples", [])
            clean_samples = []
            for s in samples:
                ts = float(s.get("timestamp_seconds", s.get("timestamp", 0.0)))
                b_raw = s.get("bbox")
                if isinstance(b_raw, dict):
                    bbox = NormalizedBBox(**b_raw)
                elif isinstance(b_raw, NormalizedBBox):
                    bbox = b_raw
                else:
                    continue
                clean_samples.append({"timestamp": ts, "bbox": bbox})
            clean_samples.sort(key=lambda x: x["timestamp"])
            tracks_by_id[t_id] = clean_samples

        observations_by_track: Dict[str, List[ActiveSpeakerObservation]] = {t: [] for t in tracks_by_id.keys()}
        lip_measurements_by_track: Dict[str, List[LipDynamicsMeasurement]] = {t: [] for t in tracks_by_id.keys()}

        # 2. Extract facial articulation & Light-ASD in bounded generator chunks
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise IOError(f"Could not open video file: {video_path}")

        total_tracks = len(tracks_by_id)

        try:
            for track_idx, (t_id, t_samples) in enumerate(tracks_by_id.items()):
                if is_cancelled and is_cancelled():
                    raise InterruptedError("Active speaker analysis cancelled.")

                if not t_samples:
                    continue

                track_start_t = t_samples[0]["timestamp"]
                track_end_t = t_samples[-1]["timestamp"]

                # Interpolate track keyframes to 25.0 FPS grid across track lifespan
                interp_keyframes = AVTemporalAdapter.interpolate_track_bboxes(
                    samples=t_samples,
                    start_time=track_start_t,
                    end_time=track_end_t,
                )

                chunk_size = 25  # 1.0 second per inference window
                for c_idx in range(0, len(interp_keyframes), chunk_size):
                    if is_cancelled and is_cancelled():
                        raise InterruptedError("Active speaker analysis cancelled.")

                    chunk_points = interp_keyframes[c_idx : c_idx + chunk_size]
                    chunk_crops: List[np.ndarray] = []
                    chunk_ts: List[float] = []

                    for ts, bbox in chunk_points:
                        chunk_ts.append(ts)
                        if bbox is None:
                            chunk_crops.append(np.zeros((112, 112, 3), dtype=np.uint8))
                            continue

                        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            crop, padded_bbox = self.landmark_detector.extract_face_crop(frame, bbox)
                            if crop.size > 0:
                                chunk_crops.append(crop)
                                # Landmark and lip dynamics measurement
                                landmarks = self.landmark_detector.detect_landmarks_from_crop(crop, padded_bbox)
                                lip_meas = self.lip_dynamics_extractor.extract_measurement(landmarks, t_id, ts)
                                lip_measurements_by_track[t_id].append(lip_meas)
                            else:
                                chunk_crops.append(np.zeros((112, 112, 3), dtype=np.uint8))
                        else:
                            chunk_crops.append(np.zeros((112, 112, 3), dtype=np.uint8))

                    # Audio slice for the chunk
                    audio_start_t = max(0.0, chunk_ts[0] - 0.05)
                    audio_end_t = chunk_ts[-1] + 0.05
                    center_audio_t = (audio_start_t + audio_end_t) / 2.0
                    av_win = sync_engine.extract_audio_window(center_audio_t, window_duration=(audio_end_t - audio_start_t))

                    # Run Light-ASD inference on the 25-frame chunk
                    obs_list = self.light_asd_detector.detect_active_speaker_sequence(
                        face_crops=chunk_crops,
                        timestamps=chunk_ts,
                        audio_segment=av_win.audio_samples,
                        face_track_id=t_id,
                        is_cancelled=is_cancelled,
                    )
                    observations_by_track[t_id].extend(obs_list)

                    # Bounded memory cleanup
                    del chunk_crops
                    del av_win

                pct = 0.15 + 0.65 * ((track_idx + 1) / max(1, total_tracks))
                report(pct, f"Analyzing track articulation & voice sync: {track_idx + 1}/{total_tracks}")

        finally:
            cap.release()
            gc.collect()

        report(0.85, "Fusing audio-visual evidence and identifying active speakers")

        # 3. Multimodal Audio-Visual Evidence Fusion (Concept A)
        active_segments = self.fusion_engine.detect_active_speaker_intervals(
            observations_by_track=observations_by_track,
            lip_measurements_by_track=lip_measurements_by_track,
            vad_intervals=vad_intervals,
            video_duration=total_video_duration,
            scene_cuts=scene_cuts,
        )

        report(0.92, "Associating acoustic speakers with visual face tracks")

        # 4. Speaker-to-Face Identity Association (Concept B)
        matches = self.fusion_engine.associate_speakers_to_faces(
            speaker_turns=speaker_turns,
            active_segments=active_segments,
            manual_overrides=manual_overrides,
        )

        # 5. Populate speaker IDs onto active speaker segments
        face_to_spk = {m.face_track_id: m.speaker_id for m in matches if m.face_track_id}
        for seg in active_segments:
            if seg.face_track_id and seg.face_track_id in face_to_spk:
                seg.speaker_id = face_to_spk[seg.face_track_id]

        total_proc_time = time.time() - start_wall_time
        rtf = total_proc_time / max(0.1, total_video_duration)
        total_active_speech = sum(s.duration for s in active_segments if s.state == "active_speaker")

        report(1.0, "Active speaker detection completed successfully")

        return ActiveSpeakerAnalysisResult(
            video_id=video_id,
            status="completed",
            active_segments=active_segments,
            associations=matches,
            total_active_speech_seconds=round(total_active_speech, 2),
            total_face_tracks_analyzed=len(tracks_by_id),
            rtf=round(rtf, 4),
            processing_time_seconds=round(total_proc_time, 3),
        )
