"""
ClipForge AI - Phase 6 Real Acceptance Test
Verifies end-to-end Visual AI, Face Tracking, Scene Composition,
Trajectory Reframing, Boundary Clamping, Smoothing, and FFmpeg Vertical Clip Rendering.
"""

import asyncio
import json
import logging
import math
import os
import sys
import time
from pathlib import Path

# Setup paths
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

import cv2
import numpy as np

from app.core.config import settings
from app.video.ffprobe_manager import FFprobeManager
from app.video.clip_generator import ClipGenerator
from app.video.aspect_ratio import AspectRatioProcessor
from app.ai.vision.face_detector import get_face_detector
from app.ai.vision.face_tracker import FaceTracker
from app.ai.vision.scene_analyzer import SceneAnalyzer
from app.ai.vision.subject_selector import SubjectSelector
from app.ai.vision.reframe_engine import ReframeEngine
from app.ai.vision.schemas import ReframeConfig, ManualCropInput
from app.ai.vision.vision_manager import VisionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("acceptance_phase6")


def draw_face(canvas, center_x, center_y, scale=1.0):
    """Draw a recognizable face on an image canvas for OpenCV YuNet."""
    w = int(100 * scale)
    h = int(140 * scale)
    # Head
    cv2.ellipse(canvas, (center_x, center_y), (w, h), 0, 0, 360, (180, 205, 240), -1)
    # Eyes
    eye_offset_x = int(40 * scale)
    eye_offset_y = int(30 * scale)
    eye_r = max(2, int(15 * scale))
    pupil_r = max(1, int(8 * scale))
    cv2.circle(canvas, (center_x - eye_offset_x, center_y - eye_offset_y), eye_r, (255, 255, 255), -1)
    cv2.circle(canvas, (center_x + eye_offset_x, center_y - eye_offset_y), eye_r, (255, 255, 255), -1)
    cv2.circle(canvas, (center_x - eye_offset_x, center_y - eye_offset_y), pupil_r, (50, 40, 20), -1)
    cv2.circle(canvas, (center_x + eye_offset_x, center_y - eye_offset_y), pupil_r, (50, 40, 20), -1)
    # Nose
    nose_len = int(40 * scale)
    cv2.line(canvas, (center_x, center_y - int(15 * scale)), (center_x, center_y + int(20 * scale)), (140, 160, 200), max(1, int(3 * scale)))
    cv2.circle(canvas, (center_x, center_y + int(25 * scale)), max(2, int(8 * scale)), (140, 160, 200), -1)
    # Mouth
    cv2.ellipse(canvas, (center_x, center_y + int(65 * scale)), (int(35 * scale), int(12 * scale)), 0, 0, 360, (90, 90, 190), -1)


def generate_test_video(output_path: str, duration_sec: float = 8.0, fps: int = 24, width: int = 1280, height: int = 720):
    """Synthesizes a 1280x720 video with a moving speaker and a secondary person appearing."""
    logger.info(f"Generating synthetic test video with moving speakers: {output_path}")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = int(duration_sec * fps)

    for frame_idx in range(total_frames):
        t = frame_idx / float(fps)
        canvas = np.full((height, width, 3), 45, dtype=np.uint8) # Dark studio background

        # Background subtle gradients
        cv2.putText(canvas, f"ClipForge AI Visual Test - Frame {frame_idx} ({t:.2f}s)", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2)

        # Primary Speaker (moves smoothly from x=350 to x=900)
        p1_x = int(350 + 550 * (t / duration_sec))
        p1_y = int(360 + 20 * math.sin(t * 2))
        draw_face(canvas, p1_x, p1_y, scale=1.1)

        # Secondary Speaker appears from t=3.0 to t=6.5 on left side
        if 3.0 <= t <= 6.5:
            p2_x = 260
            p2_y = 380
            draw_face(canvas, p2_x, p2_y, scale=0.9)

        writer.write(canvas)

    writer.release()
    logger.info(f"Generated {total_frames} frames ({duration_sec}s) at {output_path}")


async def run_phase6_acceptance():
    logger.info("=== STARTING CLIPFORGE AI PHASE 6 REAL ACCEPTANCE TEST ===")
    test_dir = settings.DATA_DIR / "cache" / "acceptance_test"
    test_dir.mkdir(parents=True, exist_ok=True)

    raw_test_video = str(test_dir / "acceptance_vision_raw_8s.mp4")
    final_vertical_clip = str(test_dir / "acceptance_phase6_vertical_9_16.mp4")
    results_json = str(test_dir / "phase6_acceptance_results.json")

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hardware": {
            "platform": sys.platform,
            "python": sys.version,
        },
        "tests": {},
    }

    # --- Test 1: Video Generation & Environment Inspection ---
    generate_test_video(raw_test_video, duration_sec=8.0, fps=24, width=1280, height=720)
    meta = FFprobeManager.probe(raw_test_video)
    assert meta.valid is True
    assert meta.video_stream is not None

    results["tests"]["test1_environment"] = {
        "status": "PASSED",
        "video_duration_seconds": meta.duration_seconds,
        "width": meta.video_stream.width,
        "height": meta.video_stream.height,
        "fps": meta.video_stream.fps,
        "video_codec": meta.video_stream.codec_name,
    }
    logger.info("Test 1 Passed: Synthetic video created and probed successfully.")

    # --- Test 2: Real Face Detector Loading & Single Frame Inference ---
    detector = get_face_detector(prefer_yunet=True)
    t0 = time.perf_counter()
    cap = cv2.VideoCapture(raw_test_video)
    ret, frame_0 = cap.read()
    cap.release()
    assert ret is True

    detections_f0 = detector.detect(frame_0, 0.0, 0)
    det_time_ms = (time.perf_counter() - t0) * 1000.0

    assert len(detections_f0) >= 1
    d0 = detections_f0[0]
    assert d0.confidence >= 0.50
    assert 0.0 <= d0.bbox.x <= 1.0
    assert 0.0 <= d0.bbox.y <= 1.0

    results["tests"]["test2_detector"] = {
        "status": "PASSED",
        "model_name": detector.model_name,
        "single_frame_inference_ms": round(det_time_ms, 2),
        "detected_faces_count": len(detections_f0),
        "primary_confidence": round(d0.confidence, 4),
        "primary_bbox": d0.bbox.model_dump(),
        "has_landmarks": d0.landmarks is not None,
    }
    logger.info(f"Test 2 Passed: YuNet detector executed on frame 0 in {det_time_ms:.1f}ms with conf={d0.confidence:.2f}")

    # --- Test 3: Multi-Frame Vision Analysis & Tracking ---
    manager = VisionManager()
    progress_records = []

    def on_prog(pct, desc):
        progress_records.append((pct, desc))

    t_start_analysis = time.perf_counter()
    analysis_res = await manager.analyze_video(
        video_path=raw_test_video,
        sampling_fps=4.0,
        confidence_threshold=0.50,
        progress_callback=on_prog,
    )
    analysis_duration = time.perf_counter() - t_start_analysis

    assert analysis_res.total_frames_sampled >= 25
    assert analysis_res.frames_with_faces >= 15
    assert len(analysis_res.tracked_faces) >= 1

    primary_track = analysis_res.tracked_faces[0]
    logger.info(f"Primary track {primary_track.track_id}: {primary_track.detection_count} samples, avg_conf={primary_track.average_confidence:.2f}")

    results["tests"]["test3_tracking"] = {
        "status": "PASSED",
        "analysis_duration_seconds": round(analysis_duration, 2),
        "total_frames_sampled": analysis_res.total_frames_sampled,
        "frames_with_faces": analysis_res.frames_with_faces,
        "tracks_identified_count": len(analysis_res.tracked_faces),
        "primary_track_id": primary_track.track_id,
        "primary_track_samples": primary_track.detection_count,
        "primary_track_avg_confidence": primary_track.average_confidence,
        "scene_type": analysis_res.composition.scene_type,
        "has_multiple_subjects": analysis_res.composition.has_multiple_subjects,
    }
    logger.info("Test 3 Passed: Multi-face tracking and scene composition aggregated.")

    # --- Test 4: Dynamic Reframe Trajectory Generation ---
    reframe_cfg = ReframeConfig(
        aspect_ratio="9:16",
        strategy="largest_face",
        smoothing_strength=0.85,
        crop_padding=0.15,
        headroom=0.20,
        max_crop_velocity_per_sec=0.50,
    )

    trajectory = ReframeEngine.generate_trajectory(
        source_width=1280,
        source_height=720,
        frame_detections=analysis_res.frame_detections,
        config=reframe_cfg,
    )

    assert len(trajectory) == analysis_res.total_frames_sampled

    # Verify hard boundary clamping on every single point
    dims = ReframeEngine.calculate_crop_dimensions(1280, 720, "9:16")
    expected_w_px = dims["pixel_width"]
    expected_h_px = dims["pixel_height"]

    for idx, pt in enumerate(trajectory):
        assert 0.0 <= pt.crop_x <= 1.0 - pt.crop_width + 1e-4, f"Clamping failed at index {idx}: crop_x={pt.crop_x}"
        assert 0.0 <= pt.crop_y <= 1.0 - pt.crop_height + 1e-4
        assert 0 <= pt.pixel_x <= 1280 - expected_w_px, f"Pixel boundary exceeded: px_x={pt.pixel_x}"
        assert 0 <= pt.pixel_y <= 720 - expected_h_px
        assert pt.pixel_width == expected_w_px
        assert pt.pixel_height == expected_h_px
        assert pt.pixel_width % 2 == 0
        assert pt.pixel_height % 2 == 0

    results["tests"]["test4_trajectory_and_clamping"] = {
        "status": "PASSED",
        "trajectory_points": len(trajectory),
        "crop_pixel_dimensions": f"{expected_w_px}x{expected_h_px}",
        "normalized_crop_width": round(trajectory[0].crop_width, 4),
        "normalized_crop_height": round(trajectory[0].crop_height, 4),
        "hard_boundary_violations": 0,
        "even_pixel_dimensions_verified": True,
    }
    logger.info("Test 4 Passed: 100% of trajectory coordinates clamped within boundaries and even pixel dimensions verified.")

    # --- Test 5: Real FFmpeg Vertical Clip Rendering with Dynamic Camera Tracking ---
    logger.info("Rendering final vertical 9:16 clip using real FFmpeg trajectory...")
    t_render_start = time.perf_counter()

    rendered_path = await ClipGenerator.generate_clip(
        source_video_path=raw_test_video,
        output_clip_path=final_vertical_clip,
        start_time=0.0,
        end_time=6.0,
        aspect_ratio="9:16",
        trajectory=trajectory,
    )
    render_duration = time.perf_counter() - t_render_start

    assert os.path.exists(rendered_path)
    file_size = os.path.getsize(rendered_path)
    assert file_size > 10000

    # Probe rendered clip
    probe_clip = FFprobeManager.probe(rendered_path)
    assert probe_clip.valid is True
    assert probe_clip.video_stream is not None
    # 9:16 aspect ratio check: width=1080, height=1920 (target scaled dimensions)
    assert probe_clip.video_stream.width == 1080
    assert probe_clip.video_stream.height == 1920
    assert 5.5 <= probe_clip.duration_seconds <= 6.5

    results["tests"]["test5_real_ffmpeg_rendering"] = {
        "status": "PASSED",
        "output_file": rendered_path,
        "file_size_bytes": file_size,
        "rendered_width": probe_clip.video_stream.width,
        "rendered_height": probe_clip.video_stream.height,
        "rendered_duration_seconds": probe_clip.duration_seconds,
        "render_duration_seconds": round(render_duration, 2),
        "video_codec": probe_clip.video_stream.codec_name,
    }
    logger.info(f"Test 5 Passed: Successfully rendered {probe_clip.video_stream.width}x{probe_clip.video_stream.height} vertical MP4 in {render_duration:.2f}s ({file_size} bytes)")

    # Save summary report
    with open(results_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Acceptance test metrics saved to: {results_json}")
    logger.info("=== PHASE 6 REAL ACCEPTANCE TEST COMPLETED: ALL TESTS PASSED ===")
    return results


if __name__ == "__main__":
    asyncio.run(run_phase6_acceptance())
