"""
ClipForge AI - Render Cancellation Handler
Phase 9 Stage 3: Graceful process-tree termination on Windows and status reconciliation.
"""

import logging
from typing import Optional

from ....video.ffmpeg_manager import FFmpegManager
from ....workers.cancellation import CancellationToken

logger = logging.getLogger("clipforge.composition.render.cancellation")


class RenderCancellationHandler:
    """Coordinates cancellation of active FFmpeg rendering processes."""

    @classmethod
    async def cancel_render(cls, process_id: str, cancel_token: Optional[CancellationToken] = None) -> bool:
        """Terminate active FFmpeg process tree on Windows."""
        if cancel_token:
            cancel_token.cancel()

        logger.warning(f"Requesting termination of render process '{process_id}'")
        success = await FFmpegManager.cancel_process(process_id)
        return success
