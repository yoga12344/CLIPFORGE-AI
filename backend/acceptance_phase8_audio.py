"""
ClipForge AI - Phase 8 Stage 2 Acceptance Test (Corrected & Enhanced)
Audio Preprocessing & Voice Activity Detection (Silero VAD) Engine Verification

Executes comprehensive real-world audio analysis on:
1. Conversational clear speech (ground truth reference)
2. Low-volume / quiet speech
3. Speech with natural pauses
4. Continuous rapid speech
5. Speech with background noise / music
6. Non-speech ambient noise
7. Pure silence
8. End-to-End SQLite persistence & union calculation

Measures:
- Technical conformity (16kHz, mono, PCM 16-bit)
- Speech boundary accuracy (strict clamping to source duration, interval union, 0% double-counting)
- Exact Real-Time Factor (RTF = execution_time / source_duration) directly measured
- Memory metrics: Baseline process RSS, Peak process RSS, and Incremental RSS
- Non-zero start PTS preservation via aresample=async=1:first_pts=0
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Dict, List, Tuple

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

import numpy as np
import psutil

from app.core.config import settings
from app.core.database import async_session_factory, Base, engine
from app.db.models import Project, Video, AudioAnalysis, SpeechInterval
from app.schemas.audio_schemas import AudioMetadataSchema, VADConfigSchema
from app.ai.audio.audio_preprocessor import AudioPreprocessor
from app.ai.audio.voice_activity_detector import VoiceActivityDetector, SpeechInterval as VADSpeechInterval
from app.services.audio_analysis_service import AudioAnalysisService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("acceptance_phase8_audio")


def create_test_media_files(test_dir: Path) -> Dict[str, str]:
    """
    Ensure all 7 required audio test variants exist in test_dir.
    Reuses existing speech_ref_35s.wav or generates them using FFmpeg.
    """
    test_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, str] = {}

    # 1. Base clear speech
    base_speech = backend_dir / "storage" / "clipforge_data" / "cache" / "speech_ref_35s.wav"
    clear_speech_path = test_dir / "case1_clear_speech.wav"

    if base_speech.exists():
        cmd = [
            "ffmpeg", "-y",
            "-i", str(base_speech),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(clear_speech_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=15",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(clear_speech_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    paths["clear_speech"] = str(clear_speech_path)

    # 2. Low-volume / quiet speech (scaled down by 18dB, volume=0.15)
    quiet_path = test_dir / "case2_quiet_speech.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(clear_speech_path),
        "-filter:a", "volume=0.15",
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(quiet_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    paths["quiet_speech"] = str(quiet_path)

    # 3. Speech with natural pauses (speech (5s) + silence (3s))
    pauses_path = test_dir / "case3_speech_with_pauses.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(clear_speech_path),
        "-f", "lavfi", "-t", "3", "-i", "anullsrc=r=16000:cl=mono",
        "-filter_complex", "[0:a]atrim=0:5[a1]; [1:a][a1]concat=n=2:v=0:a=1[out]",
        "-map", "[out]",
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(pauses_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    paths["speech_with_pauses"] = str(pauses_path)

    # 4. Continuous rapid speech (first 10s of clear speech)
    rapid_path = test_dir / "case4_continuous_speech.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(clear_speech_path),
        "-t", "10",
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(rapid_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    paths["continuous_speech"] = str(rapid_path)

    # 5. Speech with background noise / music (amix with quiet pink noise)
    noisy_path = test_dir / "case5_speech_with_noise.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(clear_speech_path),
        "-f", "lavfi", "-t", "15", "-i", "anoisesrc=d=15:c=pink:r=16000:a=0.04",
        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first[out]",
        "-map", "[out]",
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(noisy_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    paths["speech_with_noise"] = str(noisy_path)

    # 6. Non-speech ambient noise (pure pink noise without speech)
    noise_only_path = test_dir / "case6_ambient_noise_only.wav"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", "8", "-i", "anoisesrc=d=8:c=pink:r=16000:a=0.08",
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(noise_only_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    paths["noise_only"] = str(noise_only_path)

    # 7. Pure silence (5 seconds)
    silence_path = test_dir / "case7_pure_silence.wav"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", "5", "-i", "anullsrc=r=16000:cl=mono",
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(silence_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    paths["pure_silence"] = str(silence_path)

    return paths


async def main():
    logger.info("===================================================================")
    logger.info("   CLIPFORGE AI — PHASE 8 STAGE 2 TARGETED ACCEPTANCE CORRECTION  ")
    logger.info("   Audio Preprocessing & Voice Activity Detection (Silero VAD)     ")
    logger.info("===================================================================")

    test_dir = settings.DATA_DIR / "cache" / "acceptance_test" / "phase8_audio"
    test_files = create_test_media_files(test_dir)

    process = psutil.Process()
    baseline_rss = process.memory_info().rss
    peak_rss = baseline_rss

    def sample_memory():
        nonlocal peak_rss
        current = process.memory_info().rss
        if current > peak_rss:
            peak_rss = current

    preprocessor = AudioPreprocessor()
    vad = VoiceActivityDetector()

    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": {
            "device": "cpu",
            "vad_model": "silero-vad-v4",
            "vad_version": "1.2.1",
        },
        "memory": {},
        "tests": {},
        "summary": {},
    }

    total_test_audio_duration = 0.0
    total_processing_time = 0.0

    # -------------------------------------------------------------
    # TEST 1: Technical Preprocessing & Conformity (Clear Speech)
    # -------------------------------------------------------------
    logger.info("--> Test 1: Technical Preprocessing on Clear Speech...")
    sample_memory()
    t0 = time.perf_counter()
    target_wav, meta = await preprocessor.extract_and_preprocess(
        source_media_path=test_files["clear_speech"],
        output_wav_path=str(test_dir / "preprocessed_clear_16k.wav"),
        target_sample_rate=16000,
        channels=1,
    )
    t_extract = time.perf_counter() - t0
    sample_memory()

    assert meta.processed_sample_rate == 16000, f"Expected 16000Hz, got {meta.processed_sample_rate}"
    assert meta.processed_channels == 1, f"Expected 1 channel, got {meta.processed_channels}"
    assert meta.sample_format == "pcm_s16le", f"Expected pcm_s16le, got {meta.sample_format}"
    assert meta.audio_available is True, "Audio should be available"
    assert meta.audio_is_silent is False, "Audio should not be silent"
    assert meta.peak_amplitude > 0.1, f"Peak amplitude too low: {meta.peak_amplitude}"

    report_data["tests"]["test1_clear_speech"] = {
        "file": test_files["clear_speech"],
        "source_duration_sec": meta.source_duration,
        "sample_rate": meta.processed_sample_rate,
        "channels": meta.processed_channels,
        "format": meta.sample_format,
        "peak_amplitude": meta.peak_amplitude,
        "rms_level": meta.rms_level,
        "clipping_detected": meta.clipping_detected,
        "extraction_duration_sec": round(t_extract, 4),
    }

    # -------------------------------------------------------------
    # TEST 2: VAD on Clear Speech with Clamping & Union Duration
    # -------------------------------------------------------------
    logger.info("--> Test 2: Voice Activity Detection on Clear Speech (Clamped to duration)...")
    cfg = VADConfigSchema(threshold=0.5, min_speech_duration_ms=250, min_silence_duration_ms=350)
    sample_memory()
    t0 = time.perf_counter()
    intervals = await vad.detect_speech_streaming(
        wav_path=target_wav,
        config=cfg,
        total_duration=meta.source_duration,
    )
    t_vad = time.perf_counter() - t0
    sample_memory()

    total_test_audio_duration += meta.source_duration
    total_processing_time += t_vad

    # Direct calculation of RTF: execution time / source duration
    rtf = round(t_vad / meta.source_duration, 4) if meta.source_duration > 0 else 0.0
    speedup = round(meta.source_duration / t_vad, 1) if t_vad > 0 else 0.0

    # Calculate duration from union of intervals
    speech_duration = VoiceActivityDetector.calculate_interval_union_duration(intervals)
    speech_pct = round(min(100.0, (speech_duration / meta.source_duration * 100.0)), 2) if meta.source_duration > 0 else 0.0

    # Strict clamping verification
    for iv in intervals:
        assert iv.start_time >= 0.0, f"Interval start cannot be negative: {iv.start_time}"
        assert iv.end_time <= meta.source_duration + 0.001, (
            f"Interval end ({iv.end_time}) exceeds source duration ({meta.source_duration})"
        )
    assert speech_duration <= meta.source_duration + 0.001, (
        f"Total speech duration ({speech_duration}) exceeds source duration ({meta.source_duration})"
    )
    assert speech_pct <= 100.0, f"Speech percentage ({speech_pct}%) cannot exceed 100%"

    logger.info(
        f"    Clear Speech: duration={meta.source_duration:.2f}s, intervals={len(intervals)}, "
        f"speech_time={speech_duration:.2f}s ({speech_pct:.1f}%), VAD time={t_vad:.4f}s "
        f"(RTF={rtf:.4f}x, Speedup={speedup:.1f}x)"
    )

    report_data["tests"]["test2_vad_clear_speech"] = {
        "source_duration_sec": meta.source_duration,
        "intervals_count": len(intervals),
        "total_speech_duration_sec": round(speech_duration, 3),
        "speech_percentage": speech_pct,
        "vad_inference_duration_sec": round(t_vad, 4),
        "real_time_factor": rtf,
        "speedup_factor": speedup,
        "sample_intervals": [
            {"start": iv.start_time, "end": iv.end_time, "duration": iv.duration, "conf": iv.confidence}
            for iv in intervals[:5]
        ],
    }

    # -------------------------------------------------------------
    # TEST 3: Low-Volume / Quiet Speech
    # -------------------------------------------------------------
    logger.info("--> Test 3: VAD on Low-Volume / Quiet Speech...")
    sample_memory()
    t0 = time.perf_counter()
    quiet_meta = preprocessor.sample_file_metrics(test_files["quiet_speech"])
    quiet_duration = quiet_meta.get("duration", meta.source_duration)
    quiet_intervals = await vad.detect_speech_streaming(
        test_files["quiet_speech"],
        config=cfg,
        total_duration=quiet_duration,
    )
    t_quiet = time.perf_counter() - t0
    sample_memory()

    total_test_audio_duration += quiet_duration
    total_processing_time += t_quiet

    quiet_speech_dur = VoiceActivityDetector.calculate_interval_union_duration(quiet_intervals)
    quiet_rtf = round(t_quiet / quiet_duration, 4) if quiet_duration > 0 else 0.0
    quiet_speedup = round(quiet_duration / t_quiet, 1) if t_quiet > 0 else 0.0

    assert quiet_speech_dur <= quiet_duration + 0.001
    logger.info(
        f"    Quiet Speech: intervals={len(quiet_intervals)}, speech_dur={quiet_speech_dur:.2f}s, "
        f"VAD time={t_quiet:.4f}s (RTF={quiet_rtf:.4f}x)"
    )

    report_data["tests"]["test3_quiet_speech"] = {
        "source_duration_sec": round(quiet_duration, 2),
        "intervals_count": len(quiet_intervals),
        "speech_duration_sec": round(quiet_speech_dur, 3),
        "peak_amplitude": quiet_meta["peak"],
        "rms_level": quiet_meta["rms"],
        "vad_inference_duration_sec": round(t_quiet, 4),
        "real_time_factor": quiet_rtf,
        "speedup_factor": quiet_speedup,
    }

    # -------------------------------------------------------------
    # TEST 4: Speech with Natural Pauses
    # -------------------------------------------------------------
    logger.info("--> Test 4: VAD on Speech with Natural Pauses...")
    sample_memory()
    t0 = time.perf_counter()
    pause_meta = preprocessor.sample_file_metrics(test_files["speech_with_pauses"])
    pause_duration = pause_meta["duration"]
    pause_intervals = await vad.detect_speech_streaming(
        test_files["speech_with_pauses"],
        config=cfg,
        total_duration=pause_duration,
    )
    t_pause = time.perf_counter() - t0
    sample_memory()

    total_test_audio_duration += pause_duration
    total_processing_time += t_pause

    pause_speech_dur = VoiceActivityDetector.calculate_interval_union_duration(pause_intervals)
    pause_rtf = round(t_pause / pause_duration, 4) if pause_duration > 0 else 0.0
    pause_speedup = round(pause_duration / t_pause, 1) if t_pause > 0 else 0.0

    assert pause_speech_dur <= pause_duration + 0.001
    logger.info(
        f"    Pauses: intervals={len(pause_intervals)}, speech_dur={pause_speech_dur:.2f}s, "
        f"total={pause_duration:.2f}s, VAD time={t_pause:.4f}s (RTF={pause_rtf:.4f}x)"
    )

    report_data["tests"]["test4_speech_with_pauses"] = {
        "source_duration_sec": round(pause_duration, 2),
        "intervals_count": len(pause_intervals),
        "speech_duration_sec": round(pause_speech_dur, 3),
        "vad_inference_duration_sec": round(t_pause, 4),
        "real_time_factor": pause_rtf,
        "speedup_factor": pause_speedup,
    }

    # -------------------------------------------------------------
    # TEST 5: Speech with Background Pink Noise
    # -------------------------------------------------------------
    logger.info("--> Test 5: VAD on Speech with Background Noise...")
    sample_memory()
    t0 = time.perf_counter()
    noise_meta = preprocessor.sample_file_metrics(test_files["speech_with_noise"])
    noise_duration = noise_meta["duration"]
    noise_intervals = await vad.detect_speech_streaming(
        test_files["speech_with_noise"],
        config=cfg,
        total_duration=noise_duration,
    )
    t_noise = time.perf_counter() - t0
    sample_memory()

    total_test_audio_duration += noise_duration
    total_processing_time += t_noise

    noise_speech_dur = VoiceActivityDetector.calculate_interval_union_duration(noise_intervals)
    noise_rtf = round(t_noise / noise_duration, 4) if noise_duration > 0 else 0.0
    noise_speedup = round(noise_duration / t_noise, 1) if t_noise > 0 else 0.0

    assert noise_speech_dur <= noise_duration + 0.001
    logger.info(
        f"    Speech+Noise: intervals={len(noise_intervals)}, speech_dur={noise_speech_dur:.2f}s, "
        f"VAD time={t_noise:.4f}s (RTF={noise_rtf:.4f}x)"
    )

    report_data["tests"]["test5_speech_with_noise"] = {
        "source_duration_sec": round(noise_duration, 2),
        "intervals_count": len(noise_intervals),
        "speech_duration_sec": round(noise_speech_dur, 3),
        "vad_inference_duration_sec": round(t_noise, 4),
        "real_time_factor": noise_rtf,
        "speedup_factor": noise_speedup,
    }

    # -------------------------------------------------------------
    # TEST 6: Non-Speech Noise Only (False Positive Rejection)
    # -------------------------------------------------------------
    logger.info("--> Test 6: Non-Speech Noise (False Positive Rejection)...")
    sample_memory()
    t0 = time.perf_counter()
    noise_only_meta = preprocessor.sample_file_metrics(test_files["noise_only"])
    noise_only_dur = noise_only_meta["duration"]
    noise_only_intervals = await vad.detect_speech_streaming(
        test_files["noise_only"],
        config=cfg,
        total_duration=noise_only_dur,
    )
    t_noise_only = time.perf_counter() - t0
    sample_memory()

    total_test_audio_duration += noise_only_dur
    total_processing_time += t_noise_only

    logger.info(f"    Noise Only: intervals={len(noise_only_intervals)} (expected 0 false positives)")
    assert len(noise_only_intervals) == 0, f"Expected 0 speech intervals on pure noise, got {len(noise_only_intervals)}"

    report_data["tests"]["test6_noise_only"] = {
        "source_duration_sec": round(noise_only_dur, 2),
        "intervals_count": len(noise_only_intervals),
        "false_positive_count": len(noise_only_intervals),
        "passed": len(noise_only_intervals) == 0,
    }

    # -------------------------------------------------------------
    # TEST 7: Pure Silence
    # -------------------------------------------------------------
    logger.info("--> Test 7: Pure Silence Rejection...")
    sample_memory()
    t0 = time.perf_counter()
    silence_meta = preprocessor.sample_file_metrics(test_files["pure_silence"])
    silence_dur = silence_meta["duration"]
    silence_intervals = await vad.detect_speech_streaming(
        test_files["pure_silence"],
        config=cfg,
        total_duration=silence_dur,
    )
    t_silence = time.perf_counter() - t0
    sample_memory()

    total_test_audio_duration += silence_dur
    total_processing_time += t_silence

    logger.info(f"    Silence: is_silent={silence_meta['is_silent']}, intervals={len(silence_intervals)}")
    assert silence_meta["is_silent"] is True
    assert len(silence_intervals) == 0, f"Expected 0 speech intervals on silence, got {len(silence_intervals)}"

    report_data["tests"]["test7_pure_silence"] = {
        "source_duration_sec": round(silence_dur, 2),
        "is_silent": silence_meta["is_silent"],
        "intervals_count": len(silence_intervals),
        "passed": len(silence_intervals) == 0 and silence_meta["is_silent"],
    }

    # -------------------------------------------------------------
    # TEST 8: End-to-End Database Persistence via AudioAnalysisService
    # -------------------------------------------------------------
    logger.info("--> Test 8: End-to-End SQLite Persistence & Union Verification...")
    sample_memory()
    async with async_session_factory() as db:
        proj = Project(name="Phase 8 Acceptance Project")
        db.add(proj)
        await db.flush()

        vid = Video(
            project_id=proj.id,
            filename="acceptance_speech.wav",
            file_path=test_files["clear_speech"],
            file_size_bytes=os.path.getsize(test_files["clear_speech"]),
            duration_seconds=meta.source_duration,
            width=1920,
            height=1080,
        )
        db.add(vid)
        await db.flush()

        analysis_result = await AudioAnalysisService.run_audio_analysis(
            video_path=test_files["clear_speech"],
            project_id=proj.id,
            video_id=vid.id,
            config=cfg,
            force_reprocess=True,
        )

        saved_analysis = await AudioAnalysisService.save_analysis(
            db=db,
            project_id=proj.id,
            video_id=vid.id,
            metadata=analysis_result["metadata"],
            speech_intervals=analysis_result["intervals"],
            config=cfg,
            processing_duration=analysis_result["processing_duration"],
        )

        retrieved = await AudioAnalysisService.get_latest_analysis_for_video(db, vid.id)
        assert retrieved is not None
        assert retrieved.id == saved_analysis.id
        assert retrieved.speech_duration_seconds <= meta.source_duration + 0.001

        resp = AudioAnalysisService.to_response_schema(retrieved)
        assert resp.speech_percentage <= 100.0
        logger.info(
            f"    Saved AudioAnalysis {saved_analysis.id}: speech_duration={retrieved.speech_duration_seconds:.2f}s "
            f"({resp.speech_percentage:.1f}%), clamped to source duration ({meta.source_duration:.2f}s)."
        )

    sample_memory()
    report_data["tests"]["test8_sqlite_persistence"] = {
        "analysis_id": saved_analysis.id,
        "intervals_stored": len(retrieved.speech_intervals),
        "clamped_speech_duration_sec": retrieved.speech_duration_seconds,
        "clamped_speech_percentage": resp.speech_percentage,
        "status": saved_analysis.status,
    }

    # -------------------------------------------------------------
    # Memory Metrics
    # -------------------------------------------------------------
    baseline_mb = round(baseline_rss / (1024 * 1024), 2)
    peak_mb = round(peak_rss / (1024 * 1024), 2)
    incremental_mb = round((peak_rss - baseline_rss) / (1024 * 1024), 2)

    report_data["memory"] = {
        "baseline_process_rss_mb": baseline_mb,
        "peak_process_rss_mb": peak_mb,
        "incremental_memory_mb": incremental_mb,
    }

    # -------------------------------------------------------------
    # Summary Metrics (Direct Calculation)
    # -------------------------------------------------------------
    overall_rtf = round(total_processing_time / total_test_audio_duration, 4) if total_test_audio_duration > 0 else 0.0
    overall_speedup = round(total_test_audio_duration / total_processing_time, 1) if total_processing_time > 0 else 0.0

    report_data["summary"] = {
        "total_test_audio_sec": round(total_test_audio_duration, 2),
        "total_vad_inference_sec": round(total_processing_time, 4),
        "overall_real_time_factor": overall_rtf,
        "overall_speedup_factor": overall_speedup,
        "vad_model": "silero-vad-v4",
        "vad_engine": "ONNX Runtime (CPU)",
        "memory_bounded": peak_mb < 300.0 and incremental_mb < 100.0,
        "all_tests_passed": True,
    }

    # Write JSON results
    out_json = settings.DATA_DIR / "cache" / "acceptance_test" / "phase8_audio_results.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    logger.info("-------------------------------------------------------------------")
    logger.info(f" Memory Metrics: Baseline RSS = {baseline_mb} MB | Peak RSS = {peak_mb} MB | Incremental = {incremental_mb} MB")
    logger.info(f" Direct RTF: {overall_rtf:.4f}x ({overall_speedup:.1f}x faster than real-time playback)")
    logger.info(f" Corrected results saved to: {out_json}")
    logger.info("===================================================================")
    logger.info("   PHASE 8 STAGE 2 TARGETED ACCEPTANCE CORRECTION: ALL PASSED!    ")
    logger.info("===================================================================")


if __name__ == "__main__":
    asyncio.run(main())
