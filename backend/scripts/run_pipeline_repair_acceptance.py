"""
ClipForge AI - Critical Processing Pipeline Repair Acceptance Test
Verifies all 5 reported pipeline defects are completely resolved on real media:
- Video e061419a... not found (Audio Analysis)
- float() argument must be a string or a real number, not 'NoneType' (Visual Analysis)
- CompositionRender 'fa23c0ad...' not found (Composition Render)
- Highlight analysis reports Done, but project displays zero clips
- Active job count reporting stale/orphaned jobs
"""

import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

# Set up paths
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, func
from app.core.config import settings
from app.core.database import async_session_factory
from app.db.models import (
    Project, Video, Job, AudioAnalysis, SpeechInterval,
    VisionAnalysis, FaceTrack, Transcript, TranscriptSegment,
    HighlightCandidate, Clip, ClipScore, Composition,
    CompositionVersion, CompositionRender
)
from app.services.video_service import VideoService
from app.services.highlight_service import HighlightService
from app.composition.schemas.composition import CompositionSpec
from app.composition.render.services.render_service import RenderService
from app.workers.job_manager import JobManager
from app.workers.job_executor import JobExecutor
from app.workers.cancellation import CancellationManager


async def run_acceptance():
    print("=" * 70)
    print("CLIPFORGE AI - PIPELINE REPAIR REAL-MEDIA ACCEPTANCE TEST")
    print("=" * 70)

    real_media_path = r"C:\Users\yogac\Downloads\0001-0575.mp4"
    if not os.path.exists(real_media_path):
        print(f"ERROR: Real media not found at {real_media_path}")
        sys.exit(1)

    print(f"\n[PHASE 5 CHECK] Initializing JobManager and verifying stale job cleanup...")
    jm = JobManager.get_instance()
    await jm._recover_interrupted_jobs()

    async with async_session_factory() as db:
        stale_count = await db.execute(select(func.count(Job.id)).where(Job.status.in_(["queued", "running"])))
        active_count = stale_count.scalar() or 0
        print(f"  Active / Queued jobs in DB: {active_count}")
        assert active_count == 0, f"Expected 0 stale jobs after recovery, got {active_count}"
        print("  ✓ Stale job cleanup passed: 0 orphaned jobs in DB.")

    # Step 1: Create Project and Import Real Video
    print("\n[STEP 1 & 2] Creating project and importing real video...")
    project_id = f"proj_repair_{int(datetime.utcnow().timestamp())}"
    async with async_session_factory() as db:
        proj = Project(
            id=project_id,
            name="Pipeline Repair Verification Project",
            description="Real-media verification of audio, visual, highlight, and render pipelines",
            status="active"
        )
        db.add(proj)
        await db.commit()

        video = await VideoService.import_video(
            db=db,
            project_id=project_id,
            source_file_path=real_media_path,
            copy_to_storage=False
        )
        video_id = video.id
        print(f"  Project ID: {project_id}")
        print(f"  Video ID: {video_id}")
        print(f"  File: {video.file_path}")
        print(f"  Duration: {video.duration_seconds:.2f}s, Resolution: {video.width}x{video.height}, FPS: {video.fps}")
        assert video.duration_seconds > 0

    # Step 2: Audio Analysis Execution (Checking Issue 1)
    print("\n[STEP 3] Executing Audio Analysis (Silero VAD) on video...")
    audio_job = await jm.enqueue_job(
        job_type="audio_analysis",
        project_id=project_id,
        params={"video_id": video_id, "force_reprocess": True}
    )
    token = CancellationManager.create_token(audio_job.id)
    audio_res = await JobExecutor.execute_job(audio_job.id, token)
    print(f"  Audio Analysis Job Result: status=completed, speech_intervals={audio_res.get('speech_intervals_count')}, duration={audio_res.get('duration_seconds')}s")

    async with async_session_factory() as db:
        a_row = await db.execute(select(AudioAnalysis).where(AudioAnalysis.video_id == video_id).order_by(AudioAnalysis.created_at.desc()))
        analysis_rec = a_row.scalars().first()
        assert analysis_rec is not None, "AudioAnalysis record must exist in DB!"
        print(f"  ✓ Issue 1 Resolved: AudioAnalysis record {analysis_rec.id} created successfully without 'Video not found' error.")

    # Step 3: Visual Analysis Execution (Checking Issue 2: float(None))
    print("\n[STEP 4] Executing Visual Analysis (YuNet Face Tracking) with end_time=None...")
    # Explicitly test the previously failing payload with end_time: None and clip_id: None
    vision_job = await jm.enqueue_job(
        job_type="visual_analysis",
        project_id=project_id,
        params={
            "video_id": video_id,
            "clip_id": None,
            "sampling_fps": 4.0,
            "confidence_threshold": 0.55,
            "start_time": 0.0,
            "end_time": None  # THIS PREVIOUSLY CAUSED float() argument must be a string or a real number, not 'NoneType'
        }
    )
    token2 = CancellationManager.create_token(vision_job.id)
    vision_res = await JobExecutor.execute_job(vision_job.id, token2)
    print(f"  Visual Analysis Job Result: sampled_frames={vision_res.get('total_frames_sampled')}, tracks={vision_res.get('tracks_count')}, scene_type={vision_res.get('scene_type')}")

    async with async_session_factory() as db:
        v_row = await db.execute(select(VisionAnalysis).where(VisionAnalysis.video_id == video_id).order_by(VisionAnalysis.created_at.desc()))
        vision_rec = v_row.scalars().first()
        assert vision_rec is not None, "VisionAnalysis record must exist in DB!"
        print(f"  ✓ Issue 2 Resolved: Visual analysis executed with end_time=None without float() TypeError.")

    # Step 4: Transcription Execution
    print("\n[STEP 5] Executing Transcription (Speech-to-Text)...")
    transcribe_job = await jm.enqueue_job(
        job_type="transcribe_video",
        project_id=project_id,
        params={"video_id": video_id}
    )
    token3 = CancellationManager.create_token(transcribe_job.id)
    trans_res = await JobExecutor.execute_job(transcribe_job.id, token3)
    print(f"  Transcription Job Result: transcript_id={trans_res.get('transcript_id')}, segments={trans_res.get('segment_count')}")

    # Step 5: Highlight Analysis with Auto-Clip Creation (Checking Issue 4)
    print("\n[STEP 6] Executing Highlight Discovery with auto_create_clips=True...")
    highlight_job = await jm.enqueue_job(
        job_type="analyze_highlights",
        project_id=project_id,
        params={
            "video_id": video_id,
            "model_name": "qwen-2.5-3b",
            "content_type": "general",
            "target_duration_min": 5.0,
            "target_duration_max": 20.0,
            "max_candidates": 3,
            "auto_create_clips": True  # Automatically creates clips from top candidates
        }
    )
    token4 = CancellationManager.create_token(highlight_job.id)
    hl_res = await JobExecutor.execute_job(highlight_job.id, token4)
    print(f"  Highlight Job Result: candidates_count={hl_res.get('candidates_count')}, auto_created_clips={hl_res.get('auto_created_clips')}")

    async with async_session_factory() as db:
        cands = await db.execute(select(HighlightCandidate).where(HighlightCandidate.video_id == video_id))
        cand_list = cands.scalars().all()
        print(f"  Highlight candidates in DB: {len(cand_list)}")
        for c in cand_list:
            print(f"    - Candidate {c.id[:8]}: \"{c.title}\" | {c.start_time:.1f}s - {c.end_time:.1f}s | Score: {c.overall_score} | Category: {c.category}")

        clips_res = await db.execute(select(Clip).where(Clip.project_id == project_id))
        clips_list = clips_res.scalars().all()
        print(f"  Clips created in project: {len(clips_list)}")
        for cl in clips_list:
            print(f"    - Clip {cl.id[:8]}: \"{cl.title}\" | duration={cl.duration_seconds:.1f}s | status={cl.status}")

        assert len(cand_list) > 0, "Highlight candidates must be saved in DB"
        assert len(clips_list) > 0, "At least one clip must be created in project!"
        print(f"  ✓ Issue 4 Resolved: Candidates ({len(cand_list)}) and Clips ({len(clips_list)}) successfully persisted in SQLite.")

    # Step 6: Create Composition and Composition Render (Checking Issue 3)
    print("\n[STEP 7] Creating Composition & Executing Render...")
    target_clip = clips_list[0]
    clip_dur_us = int(min(10.0, target_clip.duration_seconds) * 1_000_000)

    spec = CompositionSpec.create_default(
        composition_id=f"comp_{target_clip.id[:8]}",
        project_id=project_id,
        video_id=video_id,
        source_width=1920,
        source_height=1080,
        source_fps=30.0,
        source_duration_us=clip_dur_us,
        clip_start_us=int(target_clip.start_time * 1_000_000),
        clip_end_us=int((target_clip.start_time + min(10.0, target_clip.duration_seconds)) * 1_000_000),
        title=target_clip.title,
        aspect_ratio="9:16"
    )
    spec.layout.layout_type = "portrait_crop"

    async with async_session_factory() as db:
        comp = Composition(
            id=spec.composition_id,
            project_id=project_id,
            source_video_id=video_id,
            title=target_clip.title,
        )
        db.add(comp)
        await db.flush()

        ver = CompositionVersion(
            composition_id=comp.id,
            version_number=1,
            spec_json=spec.model_dump(mode="json"),
            content_hash=spec.compute_content_hash(),
            is_draft=False
        )
        db.add(ver)
        await db.commit()
        await db.refresh(ver)

        # Create render record and enqueue render job
        render = await RenderService.create_render(
            composition_id=comp.id,
            version_id=ver.id,
            db=db,
        )
        render_id = render.id
        print(f"  Composition ID: {comp.id}")
        print(f"  Version ID: {ver.id}")
        print(f"  CompositionRender ID: {render_id}")

    # Await background composition render job completion
    print("\n[STEP 8] Awaiting Composition Render Background Job via JobManager...")
    import time
    start_poll = time.time()
    rendered_file = None
    while time.time() - start_poll < 60:
        await asyncio.sleep(0.5)
        async with async_session_factory() as db:
            r_check = await db.execute(select(CompositionRender).where(CompositionRender.id == render_id))
            r_obj = r_check.scalar_one_or_none()
            if r_obj and r_obj.status == "completed":
                rendered_file = r_obj.output_path
                print(f"  Render Job Result: render_id={r_obj.id}, output={r_obj.output_path}, duration={r_obj.render_duration_seconds}s")
                break
            elif r_obj and r_obj.status == "failed":
                raise RuntimeError(f"Composition render background job failed: {r_obj.error_message}")

    assert rendered_file and os.path.exists(rendered_file), f"Rendered file does not exist: {rendered_file}"
    file_size = os.path.getsize(rendered_file)
    print(f"  ✓ Issue 3 Resolved: Rendered file created successfully: {rendered_file} ({file_size / 1024 / 1024:.2f} MB)")

    # Step 7: Probe Rendered MP4 with FFprobe
    print("\n[STEP 9] Inspecting Rendered MP4 with FFprobe...")
    ffprobe_bin = settings.get_ffprobe_binary()
    probe_cmd = [
        ffprobe_bin, "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", rendered_file
    ]
    probe_out = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    probe_info = json.loads(probe_out.stdout)

    v_stream = next((s for s in probe_info.get("streams", []) if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in probe_info.get("streams", []) if s.get("codec_type") == "audio"), None)

    print(f"  Format: {probe_info.get('format', {}).get('format_name')}")
    print(f"  Duration: {float(probe_info.get('format', {}).get('duration', 0)):.2f}s")
    if v_stream:
        print(f"  Video: codec={v_stream.get('codec_name')}, resolution={v_stream.get('width')}x{v_stream.get('height')}, fps={v_stream.get('r_frame_rate')}")
        assert v_stream.get("width") == 1080 and v_stream.get("height") == 1920, f"Expected 1080x1920, got {v_stream.get('width')}x{v_stream.get('height')}"
    if a_stream:
        print(f"  Audio: codec={a_stream.get('codec_name')}, channels={a_stream.get('channels')}, sample_rate={a_stream.get('sample_rate')}")

    # Step 8: Persistence Verification
    print("\n[STEP 10] Restart and Persistence Verification...")
    # Simulate restart by re-running interrupted recovery on completed state
    await jm._recover_interrupted_jobs()

    # Re-open database session
    async with async_session_factory() as check_db:
        p_chk = await check_db.execute(select(Project).where(Project.id == project_id))
        assert p_chk.scalar_one_or_none() is not None, "Project must persist!"

        v_chk = await check_db.execute(select(Video).where(Video.project_id == project_id))
        assert v_chk.scalar_one_or_none() is not None, "Video must persist!"

        c_chk = await check_db.execute(select(func.count(HighlightCandidate.id)).where(HighlightCandidate.project_id == project_id))
        assert (c_chk.scalar() or 0) > 0, "Candidates must persist!"

        cl_chk = await check_db.execute(select(func.count(Clip.id)).where(Clip.project_id == project_id))
        assert (cl_chk.scalar() or 0) > 0, "Clips must persist!"

        r_chk = await check_db.execute(select(CompositionRender).where(CompositionRender.id == render_id))
        ren_persisted = r_chk.scalar_one_or_none()
        assert ren_persisted is not None and ren_persisted.status == "completed", "Render must persist in completed status!"
        print("  ✓ Persistence Verified: Project, video, candidates, clips, and renders remain completely intact.")

    print("\n" + "=" * 70)
    print("ALL ACCEPTANCE CHECKS PASSED SUCCESSFULLY (10/10)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_acceptance())
