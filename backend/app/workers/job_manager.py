import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..core.database import async_session_factory
from ..db.models import Job
from .cancellation import CancellationManager, CancellationToken
from .job_events import JobEvent, JobEventBroadcaster
from .job_executor import JobExecutor

logger = logging.getLogger("clipforge.workers.manager")

class JobManager:
    _instance: Optional["JobManager"] = None
    _queue: Optional[asyncio.Queue] = None
    _worker_task: Optional[asyncio.Task] = None
    _current_job_id: Optional[str] = None
    _current_token: Optional[CancellationToken] = None
    _is_running: bool = False

    @classmethod
    def get_instance(cls) -> "JobManager":
        if cls._instance is None:
            cls._instance = JobManager()
        return cls._instance

    def _get_queue(self) -> asyncio.Queue:
        cur_loop = asyncio.get_running_loop()
        if self._queue is None or getattr(self._queue, "_loop", None) != cur_loop:
            self._queue = asyncio.Queue()
        return self._queue

    async def start(self):
        """Start the background job worker and perform startup recovery."""
        self._get_queue()

        if self._worker_task and not self._worker_task.done():
            return

        self._is_running = True
        await self._recover_interrupted_jobs()
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Background JobManager started with bounded single-worker concurrency.")

    async def stop(self):
        """Gracefully shut down the worker and active processes."""
        self._is_running = False
        if self._current_job_id:
            await self.cancel_job(self._current_job_id)
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("JobManager stopped.")

    async def _recover_interrupted_jobs(self):
        """Reset any jobs that were left in 'running' or 'queued' state during a previous crash/restart."""
        try:
            async with async_session_factory() as db:
                res = await db.execute(select(Job).where(Job.status.in_(["running", "queued"])))
                interrupted_jobs = res.scalars().all()
                for j in interrupted_jobs:
                    logger.warning(f"Recovering orphaned job {j.id} (was {j.status} during restart)")
                    j.status = "failed"
                    j.error_message = "Interrupted by application restart."
                    j.stage_description = "Interrupted"
                    j.completed_at = datetime.utcnow()
                await db.commit()
                if interrupted_jobs:
                    logger.info(f"Cleaned up {len(interrupted_jobs)} orphaned jobs from previous session.")
        except Exception as e:
            logger.error(f"Error recovering interrupted jobs: {e}")

    async def enqueue_job(
        self,
        job_type: str,
        project_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Job:
        """Create a new job in SQLite and push to queue."""
        from ..db.models import Project
        async with async_session_factory() as db:
            valid_project_id = None
            if project_id:
                p_check = await db.execute(select(Project.id).where(Project.id == project_id))
                if p_check.scalar_one_or_none():
                    valid_project_id = project_id

            job = Job(
                job_type=job_type,
                project_id=valid_project_id,
                params=params or {},
                status="queued",
                progress_percent=0,
                stage_description="Queued"
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            job_id = job.id

        await self._get_queue().put(job_id)

        await JobEventBroadcaster.broadcast(JobEvent(
            job_id=job_id,
            project_id=project_id,
            job_type=job_type,
            event_type="created",
            progress_percent=0,
            stage_description="Queued"
        ))

        logger.info(f"Enqueued job {job_id} of type '{job_type}'")
        return job

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or queued job."""
        if self._current_job_id == job_id and self._current_token:
            self._current_token.cancel()
            CancellationManager.cancel_job(job_id)
            return True

        # If not active, mark cancelled directly in database
        async with async_session_factory() as db:
            res = await db.execute(select(Job).where(Job.id == job_id))
            job = res.scalar_one_or_none()
            if job and job.status in ("queued", "running"):
                job.status = "cancelled"
                job.stage_description = "Cancelled by user"
                job.completed_at = datetime.utcnow()
                await db.commit()

                await JobEventBroadcaster.broadcast(JobEvent(
                    job_id=job_id,
                    project_id=job.project_id,
                    job_type=job.job_type,
                    event_type="cancelled",
                    stage_description="Cancelled"
                ))
                return True

        return False

    async def retry_job(self, job_id: str) -> Optional[Job]:
        """Re-enqueue a failed or cancelled job."""
        async with async_session_factory() as db:
            res = await db.execute(select(Job).where(Job.id == job_id))
            job = res.scalar_one_or_none()
            if not job:
                return None

            job.status = "queued"
            job.progress_percent = 0
            job.stage_description = "Queued for retry"
            job.error_message = None
            job.started_at = None
            job.completed_at = None
            await db.commit()
            await db.refresh(job)

        await self._get_queue().put(job_id)

        await JobEventBroadcaster.broadcast(JobEvent(
            job_id=job_id,
            project_id=job.project_id,
            job_type=job.job_type,
            event_type="created",
            progress_percent=0,
            stage_description="Queued for retry"
        ))

        return job

    async def _worker_loop(self):
        """Worker loop processing 1 job at a time."""
        while self._is_running:
            try:
                q = self._get_queue()
                job_id = await q.get()

                # Verify job is still queued
                async with async_session_factory() as db:
                    res = await db.execute(select(Job).where(Job.id == job_id))
                    job = res.scalar_one_or_none()
                    if not job or job.status != "queued":
                        q.task_done()
                        continue

                self._current_job_id = job_id
                self._current_token = CancellationManager.create_token(job_id)

                try:
                    await JobExecutor.execute_job(job_id, self._current_token)
                except asyncio.CancelledError:
                    logger.info(f"Job {job_id} was successfully cancelled.")
                except Exception as e:
                    logger.error(f"Job {job_id} failed during execution: {e}")
                finally:
                    CancellationManager.remove_token(job_id)
                    self._current_job_id = None
                    self._current_token = None
                    q.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job worker loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)
