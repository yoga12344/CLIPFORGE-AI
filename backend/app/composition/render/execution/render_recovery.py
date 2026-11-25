"""
ClipForge AI - Render Crash & Restart Recovery
Phase 9 Stage 3: Detects interrupted composition renders and cleans up temporary files on startup.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....db.models import CompositionRender

logger = logging.getLogger("clipforge.composition.render.recovery")


class RenderRecoveryService:
    """Recovers interrupted composition renders after an unexpected application crash or restart."""

    @classmethod
    async def recover_interrupted_renders(cls, db: AsyncSession) -> int:
        """Find any renders left in 'rendering' or 'preparing' status and mark them failed."""
        res = await db.execute(
            select(CompositionRender).where(CompositionRender.status.in_(["rendering", "preparing", "compiling"]))
        )
        interrupted = res.scalars().all()
        count = len(interrupted)

        for r in interrupted:
            logger.warning(f"Recovering interrupted composition render '{r.id}' (was {r.status})")
            r.status = "failed"
            r.error_message = "Interrupted by application restart."
            r.completed_at = datetime.utcnow()

            # Clean up partial temporary output if it exists
            tmp_path = Path(f"{r.output_path}.tmp.mp4")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception as e:
                    logger.debug(f"Could not delete partial temp render file {tmp_path}: {e}")

        if count > 0:
            await db.commit()
            logger.info(f"Cleaned up {count} interrupted composition renders.")

        return count
