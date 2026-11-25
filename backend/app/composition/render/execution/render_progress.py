"""
ClipForge AI - Render Progress Handler & Broadcaster
Phase 9 Stage 3: Live progress translation and WebSocket dispatch.
"""

from typing import Callable, Coroutine, Optional
from ....video.ffmpeg_manager import FFmpegProgress
from ....workers.job_events import JobEvent, JobEventBroadcaster


class RenderProgressTracker:
    """Tracks and broadcasts composite rendering progress across pipeline phases."""

    def __init__(self, job_id: str, project_id: Optional[str] = None):
        self.job_id = job_id
        self.project_id = project_id
        self.current_percent: int = 0
        self.current_stage: str = "Queued"

    async def update_stage(self, stage_name: str, base_percent: int) -> None:
        self.current_stage = stage_name
        self.current_percent = base_percent
        await JobEventBroadcaster.broadcast(JobEvent(
            job_id=self.job_id,
            project_id=self.project_id,
            job_type="composition_render",
            event_type="progress",
            progress_percent=self.current_percent,
            stage_description=self.current_stage,
        ))

    async def handle_ffmpeg_progress(self, p: FFmpegProgress) -> None:
        """Map raw FFmpeg progress (0-100%) to the active rendering window (20% - 90%)."""
        render_window_percent = int(20 + (p.progress_percent * 0.70))
        self.current_percent = min(90, max(20, render_window_percent))
        stage_desc = f"Rendering video ({p.progress_percent}% @ {p.fps:.1f} fps)"

        await JobEventBroadcaster.broadcast(JobEvent(
            job_id=self.job_id,
            project_id=self.project_id,
            job_type="composition_render",
            event_type="progress",
            progress_percent=self.current_percent,
            stage_description=stage_desc,
        ))
