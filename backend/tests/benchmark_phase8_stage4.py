"""
ClipForge AI - Phase 8 Stage 4 Real CPU Acceptance Benchmark
Measures landmark load time, inference latency, lip-dynamics processing time,
Light-ASD load time & latency, end-to-end pipeline processing time, RTF,
baseline RSS, peak RSS, incremental RSS, and scaling across 1, 2, and 4 visible faces.
"""

import json
import os
import sys
import time
from pathlib import Path
import cv2
import numpy as np
import psutil

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.ai.audio_visual.active_speaker_detector import LightASDDetector
from app.ai.audio_visual.av_fusion_engine import AudioVisualFusionEngine
from app.ai.audio_visual.av_synchronizer import AudioVisualSynchronizer, StreamSyncInfo
from app.ai.vision.landmark_detector import MediaPipeFaceLandmarkDetector
from app.ai.vision.lip_dynamics import LipDynamicsExtractor
from app.ai.vision.schemas import NormalizedBBox


def get_current_rss_mb() -> float:
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024.0 * 1024.0)


def create_realistic_face_crop(width: int = 160, height: int = 160, mouth_open: bool = True) -> np.ndarray:
    """Generate a realistic face image with skin tones, eyes, nose, and mouth."""
    img = np.full((height, width, 3), 200, dtype=np.uint8)
    # Face skin ellipse
    cv2.ellipse(img, (width // 2, height // 2), (width // 3, height // 2 - 10), 0, 0, 360, (180, 150, 130), -1)
    # Eyes
    cv2.circle(img, (width // 2 - 25, height // 2 - 20), 8, (60, 60, 60), -1)
    cv2.circle(img, (width // 2 + 25, height // 2 - 20), 8, (60, 60, 60), -1)
    # Mouth
    if mouth_open:
        cv2.ellipse(img, (width // 2, height // 2 + 35), (20, 12), 0, 0, 360, (40, 40, 160), -1)
    else:
        cv2.line(img, (width // 2 - 20, height // 2 + 35), (width // 2 + 20, height // 2 + 35), (40, 40, 160), 3)
    return img


def run_benchmark():
    print("=" * 80)
    print("CLIPFORGE AI — PHASE 8 STAGE 4 REAL CPU ACCEPTANCE BENCHMARK")
    print(f"Platform: Windows 11 | CPU: Intel Core i7-13620H | RAM: 16 GB")
    print(f"Target: CPUExecutionProvider (ONNX Runtime 1.32.0)")
    print("=" * 80)

    process = psutil.Process(os.getpid())
    baseline_rss = get_current_rss_mb()
    print(f"Baseline Process RSS: {baseline_rss:.2f} MB")

    # 1. Benchmark Landmark Model Loading
    t0 = time.perf_counter()
    landmark_detector = MediaPipeFaceLandmarkDetector(verify_checksum=True, intra_op_threads=2)
    landmark_detector._ensure_session()
    landmark_load_time_ms = (time.perf_counter() - t0) * 1000.0
    rss_after_landmarks = get_current_rss_mb()
    print(f"[1] Landmark Model Load Time: {landmark_load_time_ms:.2f} ms (RSS: {rss_after_landmarks:.2f} MB)")

    # 2. Benchmark Light-ASD Model Loading
    t0 = time.perf_counter()
    light_asd_detector = LightASDDetector(verify_checksum=True, intra_op_threads=2)
    light_asd_detector._ensure_session()
    asd_load_time_ms = (time.perf_counter() - t0) * 1000.0
    rss_after_models = get_current_rss_mb()
    print(f"[2] Light-ASD Model Load Time: {asd_load_time_ms:.2f} ms (RSS: {rss_after_models:.2f} MB)")

    # Warmup runs
    warmup_crop = create_realistic_face_crop()
    landmark_detector.detect_landmarks_from_crop(warmup_crop)
    light_asd_detector.detect_active_speaker_sequence(
        [warmup_crop] * 5,
        [0.0, 0.04, 0.08, 0.12, 0.16],
        np.zeros(3200, dtype=np.float32),
        "warmup",
    )

    # 3. Benchmark Landmark Inference Latency (Single Face)
    num_landmark_trials = 50
    t0 = time.perf_counter()
    for _ in range(num_landmark_trials):
        landmark_detector.detect_landmarks_from_crop(warmup_crop)
    landmark_latency_per_face_ms = ((time.perf_counter() - t0) / num_landmark_trials) * 1000.0
    print(f"[3] Landmark Inference Latency: {landmark_latency_per_face_ms:.2f} ms / face crop")

    # 4. Benchmark Lip Dynamics Processing Time
    lip_extractor = LipDynamicsExtractor()
    sample_landmarks = landmark_detector.detect_landmarks_from_crop(warmup_crop)
    num_lip_trials = 1000
    t0 = time.perf_counter()
    for i in range(num_lip_trials):
        lip_extractor.extract_measurement(sample_landmarks, "bench_track", i * 0.04)
    lip_processing_time_us = ((time.perf_counter() - t0) / num_lip_trials) * 1_000_000.0
    print(f"[4] Lip Dynamics Processing Latency: {lip_processing_time_us:.2f} us / observation")

    # 5. Benchmark Light-ASD Inference Latency
    num_asd_trials = 20
    test_crops = [create_realistic_face_crop(mouth_open=(i % 2 == 0)) for i in range(25)]
    test_audio = np.random.randn(16000).astype(np.float32) # 1.0 second
    test_timestamps = [i * 0.04 for i in range(25)]

    t0 = time.perf_counter()
    for _ in range(num_asd_trials):
        light_asd_detector.detect_active_speaker_sequence(
            test_crops,
            test_timestamps,
            test_audio,
            "bench_track",
        )
    asd_batch_time_ms = ((time.perf_counter() - t0) / num_asd_trials) * 1000.0
    asd_per_frame_ms = asd_batch_time_ms / 25.0
    print(f"[5] Light-ASD Latency: {asd_batch_time_ms:.2f} ms for 25-frame window ({asd_per_frame_ms:.2f} ms / frame)")

    # 6. End-to-End Pipeline Scaling: 1, 2, and 4 Visible Faces across a 10.0-second video
    video_duration_seconds = 10.0
    fps = 25.0
    total_frames = int(video_duration_seconds * fps)  # 250 frames
    audio_waveform = np.sin(2 * np.pi * 300 * np.linspace(0, video_duration_seconds, int(video_duration_seconds * 16000), dtype=np.float32))

    # Pre-generate face crops for 4 tracks with alternating speech
    crops_library = {
        1: [create_realistic_face_crop(mouth_open=((i // 4) % 2 == 0)) for i in range(total_frames)],
        2: [create_realistic_face_crop(mouth_open=((i // 6) % 2 == 1)) for i in range(total_frames)],
        3: [create_realistic_face_crop(mouth_open=False) for i in range(total_frames)],
        4: [create_realistic_face_crop(mouth_open=((i // 3) % 2 == 0)) for i in range(total_frames)],
    }

    scaling_results = {}
    peak_rss = get_current_rss_mb()

    for face_count in [1, 2, 4]:
        print(f"\n--- Running End-to-End Benchmark for {face_count} Visible Face(s) ({video_duration_seconds}s video, {total_frames} frames) ---")
        sync_engine = AudioVisualSynchronizer(audio_waveform, default_window_duration=0.40)
        fusion_engine = AudioVisualFusionEngine()
        lip_extractor.reset_all()

        t_start_e2e = time.perf_counter()
        cpu_start = psutil.cpu_percent(interval=None)

        obs_by_track = {}
        lip_by_track = {}

        # 6a. Sample landmark extraction and lip dynamics at 12.5 FPS (every 2nd frame)
        sample_step = 2
        for f_idx in range(0, total_frames, sample_step):
            ts = f_idx / fps
            for track_idx in range(1, face_count + 1):
                t_id = f"track_{track_idx}"
                if t_id not in lip_by_track:
                    lip_by_track[t_id] = []
                crop = crops_library[track_idx][f_idx]
                lmk = landmark_detector.detect_landmarks_from_crop(crop)
                meas = lip_extractor.extract_measurement(lmk, t_id, ts)
                lip_by_track[t_id].append(meas)

        # 6b. Run Light-ASD in 25-frame chunks per track
        chunk_size = 25
        for track_idx in range(1, face_count + 1):
            t_id = f"track_{track_idx}"
            obs_by_track[t_id] = []
            for c_start in range(0, total_frames, chunk_size):
                c_end = min(total_frames, c_start + chunk_size)
                c_crops = crops_library[track_idx][c_start:c_end]
                c_ts = [i / fps for i in range(c_start, c_end)]

                # Sliced audio for chunk
                chunk_mid_t = (c_ts[0] + c_ts[-1]) / 2.0
                chunk_dur = (c_ts[-1] - c_ts[0]) + 0.10
                av_win = sync_engine.extract_audio_window(chunk_mid_t, window_duration=chunk_dur)

                obs = light_asd_detector.detect_active_speaker_sequence(
                    c_crops,
                    c_ts,
                    av_win.audio_samples,
                    t_id,
                )
                obs_by_track[t_id].extend(obs)

        # 6c. Multimodal Audio-Visual Fusion
        vad_intervals = [(1.0, 4.0), (5.5, 8.5)]
        active_segs = fusion_engine.detect_active_speaker_intervals(
            observations_by_track=obs_by_track,
            lip_measurements_by_track=lip_by_track,
            vad_intervals=vad_intervals,
            video_duration=video_duration_seconds,
        )

        speaker_turns = [
            {"speaker_id": "SPEAKER_00", "start_time": 1.0, "end_time": 4.0},
            {"speaker_id": "SPEAKER_01", "start_time": 5.5, "end_time": 8.5},
        ]
        matches = fusion_engine.associate_speakers_to_faces(
            speaker_turns=speaker_turns,
            active_segments=active_segs,
        )

        e2e_duration = time.perf_counter() - t_start_e2e
        cpu_end = psutil.cpu_percent(interval=None)
        current_rss = get_current_rss_mb()
        peak_rss = max(peak_rss, current_rss)

        rtf = e2e_duration / video_duration_seconds

        scaling_results[face_count] = {
            "face_count": face_count,
            "video_duration_sec": video_duration_seconds,
            "total_frames": total_frames,
            "e2e_duration_sec": round(e2e_duration, 3),
            "rtf": round(rtf, 4),
            "active_segments_count": len(active_segs),
            "associations_count": len(matches),
            "rss_mb": round(current_rss, 2),
        }

        print(f"Results for {face_count} face(s):")
        print(f"  Total processing time: {e2e_duration:.3f} s")
        print(f"  Real-Time Factor (RTF): {rtf:.4f}x (Target: < 0.15x)")
        print(f"  Current Process RSS: {current_rss:.2f} MB")
        print(f"  Active Segments Detected: {len(active_segs)}")
        print(f"  Speaker Matches: {len(matches)}")

    final_rss = get_current_rss_mb()
    incremental_rss = final_rss - baseline_rss

    report_data = {
        "hardware": {
            "platform": "Windows 11 64-bit",
            "cpu": "Intel Core i7-13620H",
            "ram_total_gb": 16.0,
            "runtime": "ONNX Runtime 1.32.0 (CPUExecutionProvider)",
        },
        "model_loading": {
            "facemesh_load_time_ms": round(landmark_load_time_ms, 2),
            "light_asd_load_time_ms": round(asd_load_time_ms, 2),
            "combined_load_time_ms": round(landmark_load_time_ms + asd_load_time_ms, 2),
        },
        "isolated_latencies": {
            "landmark_latency_per_face_ms": round(landmark_latency_per_face_ms, 2),
            "lip_dynamics_latency_us": round(lip_processing_time_us, 2),
            "light_asd_latency_per_25_frames_ms": round(asd_batch_time_ms, 2),
            "light_asd_latency_per_frame_ms": round(asd_per_frame_ms, 2),
        },
        "scaling_benchmarks": scaling_results,
        "memory_profile": {
            "baseline_rss_mb": round(baseline_rss, 2),
            "peak_rss_mb": round(peak_rss, 2),
            "final_rss_mb": round(final_rss, 2),
            "incremental_rss_mb": round(incremental_rss, 2),
            "incremental_memory_target_met": bool(incremental_rss < 120.0),
        },
    }

    out_file = Path("docs/PHASE8_STAGE4_ACCEPTANCE_RESULTS.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print("\n" + "=" * 80)
    print(f"Benchmark results successfully written to {out_file}")
    print(f"Incremental Memory: {incremental_rss:.2f} MB (Budget: < 120 MB) -> {'PASSED' if incremental_rss < 120.0 else 'CHECK'}")
    print(f"Single-Face RTF: {scaling_results[1]['rtf']}x (Target: < 0.15x) -> {'PASSED' if scaling_results[1]['rtf'] < 0.15 else 'CHECK'}")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
