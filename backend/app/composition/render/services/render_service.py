"""
ClipForge AI - Composition Render Service
Phase 9 Stage 3: Orchestrates persistent render jobs, queue integration, and artifact queries.
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ....db.models import Composition, CompositionVersion, CompositionRender, RenderArtifact
from ....workers.job_manager import JobManager
from ..execution.render_cancellation import RenderCancellationHandler


class RenderService:
    """Manages persistent CompositionRender lifecycles."""

    @classmethod
    async def create_render(
        cls,
        composition_id: str,
        version_id: str,
        db: AsyncSession,
        custom_output_path: Optional[str] = None,
    ) -> CompositionRender:
        """Create a new CompositionRender record and enqueue an execution job."""
        c_res = await db.execute(select(Composition).where(Composition.id == composition_id))
        composition = c_res.scalar_one_or_none()
        if not composition:
            raise ValueError(f"Composition '{composition_id}' not found.")

        v_res = await db.execute(
            select(CompositionVersion).where(
                CompositionVersion.id == version_id,
                CompositionVersion.composition_id == composition_id
            )
        )
        version = v_res.scalar_one_or_none()
        if not version:
            raise ValueError(f"CompositionVersion '{version_id}' not found.")

        out_path = custom_output_path or f"storage/clipforge_data/exports/comp_{composition_id[:8]}_v{version.version_number}.mp4"

        render = CompositionRender(
            composition_id=composition_id,
            composition_version_id=version_id,
            output_path=out_path,
            status="queued",
            progress_percent=0,
            created_at=datetime.utcnow(),
        )
        db.add(render)
        await db.commit()
        await db.refresh(render)

        # Enqueue background job
        jm = JobManager.get_instance()
        await jm.start()
        job = await jm.enqueue_job(
            job_type="composition_render",
            project_id=composition.project_id,
            params={
                "render_id": render.id,
                "composition_id": composition_id,
                "version_id": version_id,
            }
        )

        render.job_id = job.id
        await db.commit()
        await db.refresh(render)

        return render

    @classmethod
    async def get_render(cls, render_id: str, db: AsyncSession) -> Optional[CompositionRender]:
        res = await db.execute(select(CompositionRender).where(CompositionRender.id == render_id))
        return res.scalar_one_or_none()

    @classmethod
    async def list_renders_for_composition(cls, composition_id: str, db: AsyncSession) -> List[CompositionRender]:
        res = await db.execute(
            select(CompositionRender)
            .where(CompositionRender.composition_id == composition_id)
            .order_by(desc(CompositionRender.created_at))
        )
        return list(res.scalars().all())

    @classmethod
    async def cancel_render(cls, render_id: str, db: AsyncSession) -> bool:
        render = await cls.get_render(render_id, db)
        if not render:
            return False

        if render.status in ("completed", "failed", "cancelled"):
            return False

        # Attempt process-tree cancellation
        proc_key = f"proc_{render_id}"
        await RenderCancellationHandler.cancel_render(proc_key)

        render.status = "cancelled"
        render.error_message = "Cancelled by user."
        render.completed_at = datetime.utcnow()
        await db.commit()
        return True

    @classmethod
    async def get_artifacts_for_render(cls, render_id: str, db: AsyncSession) -> List[RenderArtifact]:
        res = await db.execute(
            select(RenderArtifact)
            .where(RenderArtifact.composition_render_id == render_id)
            .order_by(RenderArtifact.created_at)
        )
        return list(res.scalars().all())
