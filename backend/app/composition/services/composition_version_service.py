"""
ClipForge AI - Composition Version Management Service
Enforces immutable version snapshots, optimistic concurrency control (OCC), and non-destructive rollbacks.
"""

import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Composition, CompositionVersion
from ..schemas.composition import CompositionSpec

logger = logging.getLogger("clipforge.composition.version_service")


class VersionConflictError(Exception):
    """Raised when an optimistic concurrency check fails."""
    pass


class ImmutableVersionError(Exception):
    """Raised when an attempt is made to mutate an existing immutable snapshot."""
    pass


class CompositionVersionService:

    @classmethod
    async def get_latest_version(
        cls,
        db: AsyncSession,
        composition_id: str,
    ) -> Optional[CompositionVersion]:
        """Fetch the highest version_number record for a composition."""
        res = await db.execute(
            select(CompositionVersion)
            .where(CompositionVersion.composition_id == composition_id)
            .order_by(desc(CompositionVersion.version_number))
            .limit(1)
        )
        return res.scalar_one_or_none()

    @classmethod
    async def get_version(
        cls,
        db: AsyncSession,
        composition_id: str,
        version_number: int,
    ) -> Optional[CompositionVersion]:
        """Fetch a specific immutable version snapshot by composition_id and version_number."""
        res = await db.execute(
            select(CompositionVersion)
            .where(
                CompositionVersion.composition_id == composition_id,
                CompositionVersion.version_number == version_number,
            )
        )
        return res.scalar_one_or_none()

    @classmethod
    async def list_versions(
        cls,
        db: AsyncSession,
        composition_id: str,
    ) -> List[CompositionVersion]:
        """List all version history records for a composition, sorted newest first."""
        res = await db.execute(
            select(CompositionVersion)
            .where(CompositionVersion.composition_id == composition_id)
            .order_by(desc(CompositionVersion.version_number))
        )
        return list(res.scalars().all())

    @classmethod
    async def create_version(
        cls,
        db: AsyncSession,
        composition: Composition,
        spec: CompositionSpec,
        change_summary: Optional[str] = None,
        is_draft: bool = False,
        expected_version_number: Optional[int] = None,
    ) -> CompositionVersion:
        """
        Creates a new immutable version snapshot for the composition.
        Supports Optimistic Concurrency Control (OCC) via expected_version_number.
        """
        latest = await cls.get_latest_version(db, composition.id)
        current_latest_num = latest.version_number if latest else 0

        # Optimistic Concurrency Control Check
        if expected_version_number is not None and expected_version_number != current_latest_num:
            raise VersionConflictError(
                f"Version conflict on composition {composition.id}: "
                f"client expected version {expected_version_number}, but database is at version {current_latest_num}."
            )

        new_version_num = current_latest_num + 1

        # Synchronize updated timestamps
        spec.updated_at = datetime.utcnow()
        spec_dict = spec.model_dump(mode="json")
        content_hash = spec.compute_content_hash()

        version = CompositionVersion(
            composition_id=composition.id,
            version_number=new_version_num,
            schema_version=spec.schema_version,
            spec_json=spec_dict,
            content_hash=content_hash,
            change_summary=change_summary or f"Revision {new_version_num}",
            is_draft=is_draft,
            created_at=datetime.utcnow(),
        )
        db.add(version)
        await db.flush()

        # Update parent composition pointer and timestamp
        composition.current_version_id = version.id
        composition.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(version)
        await db.refresh(composition)

        logger.info(
            f"Created CompositionVersion v{new_version_num} for composition {composition.id} "
            f"(hash: {content_hash[:8]}, is_draft: {is_draft})"
        )
        return version

    @classmethod
    async def restore_version(
        cls,
        db: AsyncSession,
        composition: Composition,
        target_version_number: int,
        description: Optional[str] = None,
    ) -> CompositionVersion:
        """
        Non-destructive rollback: Restores a previous version by creating a brand-new
        version snapshot with the historical spec contents. Earlier versions remain intact.
        """
        target = await cls.get_version(db, composition.id, target_version_number)
        if not target:
            raise ValueError(
                f"Cannot restore version {target_version_number}: version does not exist on composition {composition.id}"
            )

        historical_spec = CompositionSpec.model_validate(target.spec_json)
        summary = description or f"Restored from version {target_version_number}"

        return await cls.create_version(
            db=db,
            composition=composition,
            spec=historical_spec,
            change_summary=summary,
            is_draft=False,
        )
