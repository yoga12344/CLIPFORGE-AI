"""
ClipForge AI - Composition Validation Service
Validates composition specifications against project asset authorization boundaries and database records.
"""

from typing import Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CompositionAsset, Video
from ..schemas.composition import CompositionSpec
from ..schemas.validation import CompositionValidationResult, validate_composition_semantics


class CompositionValidationService:

    @classmethod
    async def validate_spec(
        cls,
        db: AsyncSession,
        spec: CompositionSpec,
    ) -> CompositionValidationResult:
        """
        Validates the composition specification against database project assets and internal semantics.
        Does not perform rendering or disk modifications.
        """
        # 1. Fetch authorized project assets
        stmt = select(CompositionAsset).where(CompositionAsset.project_id == spec.project_id)
        res = await db.execute(stmt)
        assets = res.scalars().all()

        authorized_uris: Set[str] = set()
        for a in assets:
            authorized_uris.add(f"asset://{a.asset_type}/{a.logical_asset_id}")

        # Also authorize source video logical URI
        v_res = await db.execute(
            select(Video).where(
                Video.id == spec.source_video_id,
                Video.project_id == spec.project_id,
            )
        )
        source_vid = v_res.scalar_one_or_none()
        if source_vid:
            authorized_uris.add(spec.source_media.asset_uri)
            authorized_uris.add(f"asset://videos/source_{source_vid.id[:8]}")

        # 2. Run semantic and asset authorization validation
        result = validate_composition_semantics(spec, authorized_asset_uris=authorized_uris)

        if not source_vid:
            result.add_error(
                "source_media.video_id",
                f"Source video '{spec.source_video_id}' not found or does not belong to project '{spec.project_id}'",
                "SOURCE_VIDEO_NOT_FOUND"
            )

        return result
