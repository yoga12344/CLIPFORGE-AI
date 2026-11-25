"""
ClipForge AI - Composition Management Service
Handles composition lifecycle, project/video ownership authorization, and transaction-safe CRUD operations.
"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Composition, CompositionVersion, Project, Video, HighlightCandidate
from ..schemas.composition import CompositionSpec
from .composition_version_service import CompositionVersionService

logger = logging.getLogger("clipforge.composition.service")


class CompositionNotFoundError(Exception):
    """Raised when composition does not exist."""
    pass


class ResourceOwnershipError(Exception):
    """Raised when video or candidate does not belong to specified project."""
    pass


class CompositionService:

    @classmethod
    async def create_composition(
        cls,
        db: AsyncSession,
        project_id: str,
        video_id: str,
        title: str = "Untitled Composition",
        description: Optional[str] = None,
        candidate_id: Optional[str] = None,
        initial_spec: Optional[CompositionSpec] = None,
        aspect_ratio: str = "9:16",
    ) -> Tuple[Composition, CompositionVersion]:
        """
        Creates a new Composition container and its initial version (v1) snapshot.
        Enforces strict project and video ownership checks.
        """
        # 1. Authorize project
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalar_one_or_none()
        if not project:
            raise ResourceOwnershipError(f"Project '{project_id}' not found.")

        # 2. Authorize video
        vid_res = await db.execute(select(Video).where(Video.id == video_id))
        video = vid_res.scalar_one_or_none()
        if not video:
            raise ResourceOwnershipError(f"Video '{video_id}' not found.")
        if video.project_id != project_id:
            raise ResourceOwnershipError(
                f"Video '{video_id}' belongs to project '{video.project_id}', not '{project_id}'"
            )

        # 3. Authorize candidate if provided
        if candidate_id:
            cand_res = await db.execute(select(HighlightCandidate).where(HighlightCandidate.id == candidate_id))
            candidate = cand_res.scalar_one_or_none()
            if not candidate:
                raise ResourceOwnershipError(f"HighlightCandidate '{candidate_id}' not found.")
            if candidate.project_id != project_id or candidate.video_id != video_id:
                raise ResourceOwnershipError(
                    f"Candidate '{candidate_id}' does not match project '{project_id}' and video '{video_id}'"
                )

        # 4. Create Composition container
        comp = Composition(
            project_id=project_id,
            source_video_id=video_id,
            candidate_id=candidate_id,
            title=title.strip() if title else "Untitled Composition",
            description=description.strip() if description else None,
            status="draft",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(comp)
        await db.flush()

        # 5. Prepare initial specification
        if initial_spec is None:
            # Determine start and end times from candidate if available
            start_us = 0
            dur_us = int(round(min(60.0, video.duration_seconds if video.duration_seconds > 0 else 15.0) * 1_000_000))
            if candidate_id:
                start_us = int(round(candidate.start_time * 1_000_000))
                dur_us = int(round(candidate.duration_seconds * 1_000_000))
            end_us = start_us + dur_us

            initial_spec = CompositionSpec.create_default(
                composition_id=comp.id,
                project_id=project_id,
                video_id=video_id,
                source_width=video.width or 1920,
                source_height=video.height or 1080,
                source_fps=video.fps or 30.0,
                source_duration_us=int(round((video.duration_seconds or 60.0) * 1_000_000)),
                clip_start_us=start_us,
                clip_end_us=end_us,
                title=comp.title,
                aspect_ratio=aspect_ratio,
                approved_candidate_id=candidate_id,
            )
        else:
            # Ensure composition_id, project_id, source_video_id align
            initial_spec.composition_id = comp.id
            initial_spec.project_id = project_id
            initial_spec.source_video_id = video_id

        # 6. Create initial Version 1 snapshot
        version = await CompositionVersionService.create_version(
            db=db,
            composition=comp,
            spec=initial_spec,
            change_summary="Initial composition creation (v1)",
            is_draft=False,
        )

        comp.current_version_id = version.id
        await db.commit()
        await db.refresh(comp)
        await db.refresh(version)

        logger.info(f"Created Composition {comp.id} (v1 hash: {version.content_hash[:8]}) in project {project_id}")
        return comp, version

    @classmethod
    async def get_composition(cls, db: AsyncSession, composition_id: str) -> Optional[Composition]:
        """Fetch Composition record by ID."""
        res = await db.execute(select(Composition).where(Composition.id == composition_id))
        return res.scalar_one_or_none()

    @classmethod
    async def get_composition_with_version(
        cls,
        db: AsyncSession,
        composition_id: str,
        version_number: Optional[int] = None,
    ) -> Optional[Tuple[Composition, CompositionVersion, CompositionSpec]]:
        """
        Retrieves a composition together with a requested version snapshot (or active current version).
        """
        comp = await cls.get_composition(db, composition_id)
        if not comp:
            return None

        version = None
        if version_number is not None:
            v_res = await db.execute(
                select(CompositionVersion)
                .where(
                    CompositionVersion.composition_id == composition_id,
                    CompositionVersion.version_number == version_number,
                )
            )
            version = v_res.scalar_one_or_none()
        elif comp.current_version_id:
            v_res = await db.execute(
                select(CompositionVersion).where(CompositionVersion.id == comp.current_version_id)
            )
            version = v_res.scalar_one_or_none()

        if not version:
            # Fallback to latest version
            v_res = await db.execute(
                select(CompositionVersion)
                .where(CompositionVersion.composition_id == composition_id)
                .order_by(desc(CompositionVersion.version_number))
            )
            version = v_res.scalars().first()

        if not version:
            raise ValueError(f"Composition {composition_id} has no recorded versions.")

        spec = CompositionSpec.model_validate(version.spec_json)
        return comp, version, spec

    @classmethod
    async def list_compositions(
        cls,
        db: AsyncSession,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Composition]:
        """List compositions with optional project_id and status filters."""
        stmt = select(Composition).order_by(desc(Composition.updated_at))
        if project_id:
            stmt = stmt.where(Composition.project_id == project_id)
        if status:
            stmt = stmt.where(Composition.status == status)
        stmt = stmt.offset(offset).limit(limit)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def update_composition_metadata(
        cls,
        db: AsyncSession,
        composition_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[Composition]:
        """Update mutable metadata on a composition container."""
        comp = await cls.get_composition(db, composition_id)
        if not comp:
            return None

        if title is not None and title.strip():
            comp.title = title.strip()
        if description is not None:
            comp.description = description.strip() if description.strip() else None
        if status is not None:
            valid_statuses = {"draft", "ready", "rendering", "exported", "archived"}
            if status not in valid_statuses:
                raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")
            comp.status = status

        comp.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(comp)
        return comp

    @classmethod
    async def delete_composition(cls, db: AsyncSession, composition_id: str) -> bool:
        """Deletes composition and cleanly cascades to versions, renders, and artifacts."""
        comp = await cls.get_composition(db, composition_id)
        if not comp:
            return False

        await db.delete(comp)
        await db.commit()
        logger.info(f"Deleted Composition {composition_id} and cascaded versions/renders.")
        return True
