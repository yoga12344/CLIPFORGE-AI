import os
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from ..config import settings
from ..models.schemas import JobCreateRequest, JobResponse, ClipInfo, HighlightCandidate
from ..services.downloader import VideoDownloader
from ..services.transcriber import AudioTranscriber
from ..services.highlight_engine import HighlightEngine
from ..services.face_tracker import FaceTracker
from ..services.subtitles import SubtitleGenerator
from ..services.video_processor import VideoProcessor

router = APIRouter()

# In-memory job repository (easily pluggable into PostgreSQL / SQLite)
jobs_db: Dict[str, JobResponse] = {
    "demo-opus-1": JobResponse(
        id="demo-opus-1",
        status="completed",
        progress=100,
        step_description="Successfully generated 2 viral clips!",
        video_title="How Top Creators Double Watch Time With Hook Retention",
        video_duration=15.0,
        clips=[
            ClipInfo(
                id="demo_output_clip",
                job_id="demo-opus-1",
                title="The Secret to Viral Shorts Retention 🔥",
                hook="The single biggest secret to scaling an online business isn't fancy ad campaigns.",
                score=98,
                reason="High-energy provocation with immediate curiosity gap and strong pacing that drives 80%+ completion rate.",
                start=0.0,
                end=13.0,
                duration=13.0,
                video_url="/storage/outputs/demo_output_clip.mp4",
                thumbnail_url="/storage/outputs/demo_output_thumb.jpg",
                transcript="THE SECRET TO VIRAL SHORTS IS HOOK RETENTION ANIMATED KARAOKE SUBTITLES DOUBLE WATCH TIME"
            )
        ]
    )
}

async def run_clip_pipeline(
    job_id: str,
    video_source_path: str,
    video_title: str,
    options: JobCreateRequest
):
    """The master pipeline orchestrating download -> transcribe -> highlight -> face track -> crop & burn."""
    job = jobs_db[job_id]
    try:
        # Step 1: Video Inspection & Probe
        job.status = "transcribing"
        job.progress = 15
        job.step_description = "Transcribing audio with word-level timestamps..."
        
        probe_info = VideoDownloader.probe_video(video_source_path)
        job.video_title = video_title
        job.video_duration = probe_info["duration"]

        # Step 2: Audio Transcription
        # Running Whisper in a thread pool to avoid blocking the asyncio event loop
        segments = await asyncio.to_thread(AudioTranscriber.transcribe, video_source_path)
        
        # Step 3: LLM Viral Highlight Selection
        job.status = "analyzing"
        job.progress = 40
        job.step_description = "AI identifying most viral hooks and engaging segments..."
        
        highlights: List[HighlightCandidate] = await asyncio.to_thread(
            HighlightEngine.find_highlights,
            segments=segments,
            provider=options.ai_provider,
            max_clips=options.max_clips,
            min_duration=options.target_duration_min,
            max_duration=options.target_duration_max,
        )

        if not highlights:
            raise RuntimeError("No highlight segments could be extracted.")

        # Step 4: Render Each Clip (Crop, Subtitle, Audio Normalization)
        job.status = "rendering"
        job.step_description = "Tracking speakers, auto-framing 9:16 and burning karaoke captions..."
        
        total_clips = len(highlights)
        rendered_clips: List[ClipInfo] = []
        face_tracker = FaceTracker()

        for idx, h in enumerate(highlights):
            clip_id = f"{job_id}_{idx + 1}"
            job.progress = 50 + int((idx / total_clips) * 45)
            job.step_description = f"Rendering Clip {idx + 1}/{total_clips}: {h.title}..."

            # 4a. Face Tracking Crop
            crop_box = None
            if options.enable_face_tracking:
                crop_box = await asyncio.to_thread(
                    face_tracker.calculate_crop_box,
                    video_path=video_source_path,
                    start_time=h.start,
                    end_time=h.end,
                    source_width=probe_info["width"],
                    source_height=probe_info["height"],
                    target_aspect_ratio=(9, 16)
                )

            # 4b. Generate Animated Karaoke Subtitles
            ass_sub_path = None
            if options.enable_subtitles:
                ass_file = str(settings.TEMP_DIR / f"{clip_id}.ass")
                ass_sub_path = await asyncio.to_thread(
                    SubtitleGenerator.generate_ass,
                    segments=segments,
                    clip_start=h.start,
                    clip_end=h.end,
                    output_file=ass_file,
                    style_preset=options.subtitle_style
                )

            # 4c. Render Video File
            clip_filename = f"{clip_id}.mp4"
            clip_output_path = str(settings.OUTPUT_DIR / clip_filename)
            thumb_filename = f"{clip_id}_thumb.jpg"
            thumb_output_path = str(settings.OUTPUT_DIR / thumb_filename)

            await asyncio.to_thread(
                VideoProcessor.render_clip,
                source_video=video_source_path,
                start_time=h.start,
                end_time=h.end,
                output_path=clip_output_path,
                crop_box=crop_box,
                ass_subtitle_path=ass_sub_path,
                target_resolution=(1080, 1920),
                normalize_audio=True
            )

            # 4d. Generate Thumbnail
            await asyncio.to_thread(
                VideoProcessor.generate_thumbnail,
                video_path=clip_output_path,
                output_thumb_path=thumb_output_path,
                timestamp=1.0
            )

            # Compile clip transcript text
            clip_transcript = " ".join(
                s.text for s in segments if s.start >= h.start - 0.5 and s.end <= h.end + 0.5
            )

            rendered_clips.append(ClipInfo(
                id=clip_id,
                job_id=job_id,
                title=h.title,
                hook=h.hook,
                score=h.score,
                reason=h.reason,
                start=h.start,
                end=h.end,
                duration=round(h.end - h.start, 2),
                video_url=f"/storage/outputs/{clip_filename}",
                thumbnail_url=f"/storage/outputs/{thumb_filename}",
                transcript=clip_transcript,
            ))

        job.clips = rendered_clips
        job.status = "completed"
        job.progress = 100
        job.step_description = f"Successfully generated {len(rendered_clips)} viral clips!"
        job.updated_at = datetime.utcnow()

    except Exception as e:
        import traceback
        traceback.print_exc()
        job.status = "failed"
        job.error = str(e)
        job.step_description = f"Failed: {str(e)}"
        job.updated_at = datetime.utcnow()


@router.post("/jobs/url", response_model=JobResponse)
async def create_job_from_url(
    req: JobCreateRequest,
    background_tasks: BackgroundTasks
):
    """Submit a YouTube or direct video URL for clipping."""
    if not req.url:
        raise HTTPException(status_code=400, detail="Video URL is required")

    job_id = str(uuid.uuid4())[:8]
    job = JobResponse(
        id=job_id,
        status="downloading",
        progress=5,
        step_description="Downloading video stream from link..."
    )
    jobs_db[job_id] = job

    async def download_and_start():
        try:
            download_meta = await VideoDownloader.download_from_url(req.url)
            await run_clip_pipeline(
                job_id=job_id,
                video_source_path=download_meta["file_path"],
                video_title=download_meta["title"],
                options=req
            )
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.step_description = f"Download error: {str(e)}"

    background_tasks.add_task(download_and_start)
    return job


@router.post("/jobs/upload", response_model=JobResponse)
async def create_job_from_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_clips: int = Form(5),
    target_duration_min: float = Form(25.0),
    target_duration_max: float = Form(60.0),
    ai_provider: str = Form("auto"),
    aspect_ratio: str = Form("9:16"),
    enable_subtitles: bool = Form(True),
    subtitle_style: str = Form("karaoke_yellow"),
    enable_face_tracking: bool = Form(True),
):
    """Upload a raw video file directly."""
    job_id = str(uuid.uuid4())[:8]
    job = JobResponse(
        id=job_id,
        status="uploading",
        progress=5,
        step_description="Saving uploaded video file..."
    )
    jobs_db[job_id] = job

    content = await file.read()
    upload_meta = await VideoDownloader.save_uploaded_file(content, file.filename or "video.mp4")

    options = JobCreateRequest(
        max_clips=max_clips,
        target_duration_min=target_duration_min,
        target_duration_max=target_duration_max,
        ai_provider=ai_provider,
        aspect_ratio=aspect_ratio,
        enable_subtitles=enable_subtitles,
        subtitle_style=subtitle_style,
        enable_face_tracking=enable_face_tracking,
    )

    background_tasks.add_task(
        run_clip_pipeline,
        job_id=job_id,
        video_source_path=upload_meta["file_path"],
        video_title=upload_meta["title"],
        options=options
    )

    return job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """Check the real-time processing status of a job."""
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs():
    """List recent video generation jobs."""
    return sorted(jobs_db.values(), key=lambda j: j.created_at, reverse=True)
