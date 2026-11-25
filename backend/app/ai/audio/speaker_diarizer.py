"""
ClipForge AI - Local Speaker Diarization Engine
Combines Voice Activity Detection, 3D-Speaker CAM++ embeddings, and Agglomerative
Hierarchical Clustering into an offline multi-speaker segmentation pipeline.
Consolidates sliding temporal windows into clean speaker turns.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from .audio_preprocessor import AudioPreprocessor
from .speaker_clustering import ClusteringConfig, ClusteringResult, SpeakerClusterer
from .speaker_embeddings import SpeakerEmbeddingExtractor
from .voice_activity_detector import VoiceActivityDetector, SpeechInterval

logger = logging.getLogger("clipforge.ai.audio.diarizer")

# Distinct accessible palette for UI presentation
SPEAKER_PALETTE = [
    "#6366f1",  # Indigo
    "#10b981",  # Emerald
    "#f59e0b",  # Amber
    "#ec4899",  # Pink
    "#8b5cf6",  # Purple
    "#06b6d4",  # Cyan
    "#f97316",  # Orange
    "#14b8a6",  # Teal
    "#84cc16",  # Lime
    "#3b82f6",  # Blue
]


@dataclass
class DiarizationConfig:
    """Configuration parameters for speaker diarization."""
    distance_threshold: float = 0.65
    expected_speakers: Optional[int] = None
    min_speakers: int = 1
    max_speakers: int = 10
    window_duration_sec: float = 1.5
    step_duration_sec: float = 0.75
    min_speech_duration_sec: float = 0.3
    max_bridge_gap_sec: float = 0.4
    collar_sec: float = 0.25


@dataclass
class DiarizedSpeaker:
    """Profile of a recognized speaker identity."""
    speaker_index: int
    speaker_identifier: str  # e.g. "SPEAKER_00"
    display_name: str        # e.g. "Speaker 1"
    total_speech_duration: float
    turn_count: int
    centroid: np.ndarray     # (512,) float32
    color: str


@dataclass
class SpeakerTurnData:
    """Individual continuous speech interval assigned to a speaker."""
    speaker_index: int
    speaker_identifier: str
    display_name: str
    start_time: float
    end_time: float
    duration: float
    confidence: float
    assignment_status: str = "auto"  # "auto", "manual", "provisional"


@dataclass
class SpeakerEmbeddingData:
    """Window-level extracted embedding metadata."""
    segment_start_time: float
    segment_end_time: float
    embedding: np.ndarray
    quality_score: float
    speaker_index: Optional[int] = None


@dataclass
class DiarizationResult:
    """Complete output of speaker diarization."""
    speakers: List[DiarizedSpeaker]
    speaker_turns: List[SpeakerTurnData]
    embeddings: List[SpeakerEmbeddingData]
    num_speakers: int
    total_speech_duration: float
    silhouette_score: Optional[float]
    processing_duration: float
    rtf: float
    execution_device: str = "cpu"


class SpeakerDiarizer:
    """
    Offline local speaker diarization pipeline.
    Segments speech intervals into sliding analysis windows, extracts CAM++ embeddings,
    clusters distinct voices, and consolidates windows into unified speaker turns.
    """

    def __init__(
        self,
        embedding_extractor: Optional[SpeakerEmbeddingExtractor] = None,
        clusterer: Optional[SpeakerClusterer] = None,
    ) -> None:
        self.embedding_extractor = embedding_extractor or SpeakerEmbeddingExtractor.get_instance()
        self.clusterer = clusterer or SpeakerClusterer()

    def get_capabilities(self) -> Dict[str, Any]:
        """Return runtime capabilities of the local diarization subsystem."""
        ext_caps = self.embedding_extractor.get_capabilities()
        return {
            "diarization_available": ext_caps.get("model_available", False),
            "model_name": ext_caps.get("model_name", "3D-Speaker CAM++"),
            "embedding_dimension": ext_caps.get("embedding_dimension", 512),
            "sample_rate": ext_caps.get("sample_rate", 16000),
            "execution_device": "cpu",
            "offline_only": True,
            "clustering_algorithm": "AHC-UPGMA-Cosine",
            "supported_speakers_range": [1, 10],
        }

    def slice_speech_intervals(
        self,
        speech_intervals: List[SpeechInterval],
        window_duration: float = 1.5,
        step_duration: float = 0.75,
        min_speech_duration: float = 0.3,
    ) -> List[Tuple[float, float]]:
        """
        Slice continuous speech intervals into uniform overlapping analysis windows.
        """
        windows: List[Tuple[float, float]] = []

        for interval in speech_intervals:
            start = float(interval.start_time)
            end = float(interval.end_time)
            dur = end - start

            if dur < min_speech_duration:
                # Interval is very short; keep as single short window if >= 0.25s
                if dur >= 0.25:
                    windows.append((start, end))
                continue

            if dur <= window_duration:
                # Interval fits in one window
                windows.append((start, end))
            else:
                # Sliding window across interval
                curr = start
                while curr + 0.25 <= end:
                    w_end = min(curr + window_duration, end)
                    windows.append((curr, w_end))
                    if w_end >= end:
                        break
                    curr += step_duration

        return windows

    def diarize(
        self,
        samples: np.ndarray,
        sample_rate: int = 16000,
        speech_intervals: Optional[List[SpeechInterval]] = None,
        config: Optional[DiarizationConfig] = None,
        time_offset: float = 0.0,
        max_duration: Optional[float] = None,
    ) -> DiarizationResult:
        """
        Perform speaker diarization on 1D audio waveform.
        
        Args:
            samples: 1D numpy array of audio (16kHz float32 or int16).
            sample_rate: sampling frequency in Hz (16000 expected).
            speech_intervals: pre-computed VAD speech intervals (if None, VAD is run automatically).
            config: diarization hyperparameter overrides.
            time_offset: timestamp shift in seconds (for chunked audio).
            max_duration: upper boundary ceiling for timestamps.
            
        Returns:
            DiarizationResult containing speakers, speaker turns, embeddings, and stats.
        """
        start_time_proc = time.perf_counter()
        cfg = config or DiarizationConfig()

        if samples is None or len(samples) == 0:
            return DiarizationResult(
                speakers=[],
                speaker_turns=[],
                embeddings=[],
                num_speakers=0,
                total_speech_duration=0.0,
                silhouette_score=None,
                processing_duration=0.0,
                rtf=0.0,
                execution_device="cpu",
            )

        audio = np.asarray(samples, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.flatten()
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / 32768.0

        audio_duration = len(audio) / float(sample_rate)
        if max_duration is None:
            max_duration = audio_duration

        # 1. Voice Activity Detection if intervals not provided
        if speech_intervals is None:
            logger.debug("Running VoiceActivityDetector on audio array...")
            speech_intervals = VoiceActivityDetector.detect_speech_array(
                samples=audio,
                sample_rate=sample_rate,
                max_duration=max_duration,
            )

        if not speech_intervals:
            proc_duration = time.perf_counter() - start_time_proc
            return DiarizationResult(
                speakers=[],
                speaker_turns=[],
                embeddings=[],
                num_speakers=0,
                total_speech_duration=0.0,
                silhouette_score=None,
                processing_duration=round(proc_duration, 4),
                rtf=round(proc_duration / max(audio_duration, 0.001), 4),
                execution_device="cpu",
            )

        # 2. Slice speech intervals into sliding analysis windows
        raw_windows = self.slice_speech_intervals(
            speech_intervals=speech_intervals,
            window_duration=cfg.window_duration_sec,
            step_duration=cfg.step_duration_sec,
            min_speech_duration=cfg.min_speech_duration_sec,
        )

        if not raw_windows:
            proc_duration = time.perf_counter() - start_time_proc
            return DiarizationResult(
                speakers=[],
                speaker_turns=[],
                embeddings=[],
                num_speakers=0,
                total_speech_duration=0.0,
                silhouette_score=None,
                processing_duration=round(proc_duration, 4),
                rtf=round(proc_duration / max(audio_duration, 0.001), 4),
                execution_device="cpu",
            )

        # 3. Extract embeddings for all windows
        extracted_embeddings: List[np.ndarray] = []
        valid_windows: List[Tuple[float, float]] = []
        embedding_records: List[SpeakerEmbeddingData] = []

        for w_start, w_end in raw_windows:
            start_sample = max(0, int(round(w_start * sample_rate)))
            end_sample = min(len(audio), int(round(w_end * sample_rate)))
            seg = audio[start_sample:end_sample]

            # Quality heuristic: RMS energy of speech slice
            rms = float(np.sqrt(np.mean(seg**2))) if len(seg) > 0 else 0.0
            quality = float(min(1.0, max(0.0, rms * 10.0)))

            emb = self.embedding_extractor.extract_embedding(seg, sample_rate, min_duration_sec=0.25)
            if emb is not None:
                extracted_embeddings.append(emb)
                valid_windows.append((w_start, w_end))
                embedding_records.append(
                    SpeakerEmbeddingData(
                        segment_start_time=round(w_start + time_offset, 3),
                        segment_end_time=round(w_end + time_offset, 3),
                        embedding=emb,
                        quality_score=round(quality, 4),
                    )
                )

        if not extracted_embeddings:
            proc_duration = time.perf_counter() - start_time_proc
            return DiarizationResult(
                speakers=[],
                speaker_turns=[],
                embeddings=[],
                num_speakers=0,
                total_speech_duration=0.0,
                silhouette_score=None,
                processing_duration=round(proc_duration, 4),
                rtf=round(proc_duration / max(audio_duration, 0.001), 4),
                execution_device="cpu",
            )

        # 4. Cluster embeddings into speakers
        X = np.array(extracted_embeddings, dtype=np.float32)
        clustering_cfg = ClusteringConfig(
            distance_threshold=cfg.distance_threshold,
            min_speakers=cfg.min_speakers,
            max_speakers=cfg.max_speakers,
            expected_speakers=cfg.expected_speakers,
        )
        clustering_res: ClusteringResult = self.clusterer.cluster(
            embeddings=X,
            expected_speakers=cfg.expected_speakers,
            distance_threshold=cfg.distance_threshold,
        )

        num_speakers = clustering_res.num_clusters
        labels = clustering_res.labels
        confidences = clustering_res.confidences
        centroids = clustering_res.centroids

        # Associate speaker index with embedding records
        for i, rec in enumerate(embedding_records):
            rec.speaker_index = int(labels[i])

        # 5. Build speaker profiles
        speakers: List[DiarizedSpeaker] = []
        for spk_idx in range(num_speakers):
            spk_id = f"SPEAKER_{spk_idx:02d}"
            display_name = f"Speaker {spk_idx + 1}"
            color = SPEAKER_PALETTE[spk_idx % len(SPEAKER_PALETTE)]
            centroid = centroids[spk_idx] if spk_idx < len(centroids) else np.zeros(512, dtype=np.float32)
            speakers.append(
                DiarizedSpeaker(
                    speaker_index=spk_idx,
                    speaker_identifier=spk_id,
                    display_name=display_name,
                    total_speech_duration=0.0,
                    turn_count=0,
                    centroid=centroid,
                    color=color,
                )
            )

        # 6. Consolidate window labels into contiguous speaker turns
        speaker_turns = self.consolidate_turns(
            windows=valid_windows,
            labels=labels,
            confidences=confidences,
            speakers=speakers,
            time_offset=time_offset,
            max_duration=max_duration + time_offset,
            max_bridge_gap=cfg.max_bridge_gap_sec,
        )

        # 7. Reconcile total speech time and turn counts
        total_speech = 0.0
        for spk in speakers:
            spk_turns = [t for t in speaker_turns if t.speaker_index == spk.speaker_index]
            spk.turn_count = len(spk_turns)
            spk_dur = sum(t.duration for t in spk_turns)
            spk.total_speech_duration = round(spk_dur, 3)
            total_speech += spk_dur

        proc_duration = time.perf_counter() - start_time_proc
        rtf = proc_duration / max(audio_duration, 0.001)

        return DiarizationResult(
            speakers=speakers,
            speaker_turns=speaker_turns,
            embeddings=embedding_records,
            num_speakers=num_speakers,
            total_speech_duration=round(total_speech, 3),
            silhouette_score=clustering_res.silhouette_score,
            processing_duration=round(proc_duration, 4),
            rtf=round(rtf, 4),
            execution_device="cpu",
        )

    def consolidate_turns(
        self,
        windows: List[Tuple[float, float]],
        labels: np.ndarray,
        confidences: np.ndarray,
        speakers: List[DiarizedSpeaker],
        time_offset: float = 0.0,
        max_duration: Optional[float] = None,
        max_bridge_gap: float = 0.4,
    ) -> List[SpeakerTurnData]:
        """
        Merge overlapping and adjacent sliding analysis windows into non-overlapping speaker turns.
        """
        if not windows or len(labels) == 0:
            return []

        # Construct raw segment items sorted by start time
        segments = []
        for i, (ws, we) in enumerate(windows):
            segments.append({
                "start": ws + time_offset,
                "end": we + time_offset,
                "speaker": int(labels[i]),
                "conf": float(confidences[i]),
            })
        segments.sort(key=lambda s: s["start"])

        consolidated: List[Dict[str, Any]] = []

        for seg in segments:
            if not consolidated:
                consolidated.append({
                    "speaker": seg["speaker"],
                    "start": seg["start"],
                    "end": seg["end"],
                    "confs": [seg["conf"]],
                })
                continue

            last = consolidated[-1]

            if seg["speaker"] == last["speaker"]:
                # Same speaker
                if seg["start"] <= last["end"] + max_bridge_gap:
                    # Overlap or short bridge gap: extend turn
                    last["end"] = max(last["end"], seg["end"])
                    last["confs"].append(seg["conf"])
                else:
                    # Significant silence gap: start new turn for same speaker
                    consolidated.append({
                        "speaker": seg["speaker"],
                        "start": seg["start"],
                        "end": seg["end"],
                        "confs": [seg["conf"]],
                    })
            else:
                # Speaker change
                if seg["start"] < last["end"]:
                    # Overlapping windows with different speakers: split at midpoint
                    mid = (seg["start"] + last["end"]) / 2.0
                    last["end"] = mid
                    seg_start = mid
                else:
                    seg_start = seg["start"]

                if seg["end"] > seg_start:
                    consolidated.append({
                        "speaker": seg["speaker"],
                        "start": seg_start,
                        "end": seg["end"],
                        "confs": [seg["conf"]],
                    })

        # Build final SpeakerTurnData objects
        speaker_map = {s.speaker_index: s for s in speakers}
        result_turns: List[SpeakerTurnData] = []

        for c in consolidated:
            start_t = max(0.0, c["start"])
            end_t = c["end"]
            if max_duration is not None:
                end_t = min(max_duration, end_t)
            dur = max(0.0, end_t - start_t)

            if dur < 0.05:  # Filter out microscopic slice artifacts (< 50ms)
                continue

            spk = speaker_map.get(c["speaker"])
            spk_id = spk.speaker_identifier if spk else f"SPEAKER_{c['speaker']:02d}"
            name = spk.display_name if spk else f"Speaker {c['speaker'] + 1}"
            mean_conf = float(np.mean(c["confs"])) if c["confs"] else 1.0

            result_turns.append(
                SpeakerTurnData(
                    speaker_index=c["speaker"],
                    speaker_identifier=spk_id,
                    display_name=name,
                    start_time=round(start_t, 3),
                    end_time=round(end_t, 3),
                    duration=round(dur, 3),
                    confidence=round(mean_conf, 4),
                    assignment_status="auto",
                )
            )

        return result_turns

    @staticmethod
    def evaluate_der(
        reference_turns: List[Tuple[float, float, str]],
        hypothesis_turns: List[SpeakerTurnData],
        collar_sec: float = 0.25,
    ) -> Dict[str, float]:
        """
        Evaluate Diarization Error Rate (DER) against ground truth reference turns.
        Supports collar tolerance window for boundary transitions.
        
        DER = (Missed Speech + False Alarm + Speaker Confusion) / Total Reference Speech
        """
        if not reference_turns:
            return {
                "der": 0.0,
                "missed_speech_time": 0.0,
                "false_alarm_time": 0.0,
                "confusion_time": 0.0,
                "total_reference_time": 0.0,
            }

        total_ref_time = sum(max(0.0, end - start) for start, end, _ in reference_turns)
        if total_ref_time == 0.0:
            return {"der": 0.0, "total_reference_time": 0.0}

        # Discrete sampling at 10ms resolution for exact temporal scoring
        step = 0.01  # 10ms
        max_time = max(
            max(end for _, end, _ in reference_turns),
            max((t.end_time for t in hypothesis_turns), default=0.0),
        )
        time_points = np.arange(0.0, max_time + step, step)

        missed = 0.0
        false_alarm = 0.0
        confusion = 0.0
        evaluated_ref_time = 0.0

        # Build mapping of hypothesis speaker index to reference speaker
        # Optimal mapping based on co-occurrence overlap
        overlap_matrix: Dict[Tuple[str, str], float] = {}
        for r_start, r_end, r_spk in reference_turns:
            for hyp in hypothesis_turns:
                inter_start = max(r_start, hyp.start_time)
                inter_end = min(r_end, hyp.end_time)
                if inter_end > inter_start:
                    pair = (r_spk, hyp.speaker_identifier)
                    overlap_matrix[pair] = overlap_matrix.get(pair, 0.0) + (inter_end - inter_start)

        # Greedy best-match mapping
        hyp_to_ref: Dict[str, str] = {}
        sorted_pairs = sorted(overlap_matrix.items(), key=lambda kv: kv[1], reverse=True)
        mapped_ref = set()
        mapped_hyp = set()
        for (r_spk, h_spk), ov in sorted_pairs:
            if r_spk not in mapped_ref and h_spk not in mapped_hyp:
                hyp_to_ref[h_spk] = r_spk
                mapped_ref.add(r_spk)
                mapped_hyp.add(h_spk)

        # Sample evaluation points
        for t in time_points:
            # Check collar: if point is within collar of any reference boundary, ignore
            in_collar = False
            for r_start, r_end, _ in reference_turns:
                if abs(t - r_start) <= collar_sec or abs(t - r_end) <= collar_sec:
                    in_collar = True
                    break
            if in_collar:
                continue

            ref_active = [r_spk for r_start, r_end, r_spk in reference_turns if r_start <= t <= r_end]
            hyp_active = [t_obj for t_obj in hypothesis_turns if t_obj.start_time <= t <= t_obj.end_time]

            if ref_active:
                evaluated_ref_time += step
                if not hyp_active:
                    missed += step
                else:
                    mapped_hyp_spk = hyp_to_ref.get(hyp_active[0].speaker_identifier, "")
                    if mapped_hyp_spk != ref_active[0]:
                        confusion += step
            else:
                if hyp_active:
                    false_alarm += step

        denom = max(evaluated_ref_time, 0.001)
        der = (missed + false_alarm + confusion) / denom

        return {
            "der": round(float(der), 4),
            "missed_speech_time": round(float(missed), 3),
            "false_alarm_time": round(float(false_alarm), 3),
            "confusion_time": round(float(confusion), 3),
            "total_reference_time": round(float(total_ref_time), 3),
            "evaluated_reference_time": round(float(evaluated_ref_time), 3),
        }
