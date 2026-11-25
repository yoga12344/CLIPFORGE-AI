from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, delete
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..db.models import Project, Video, Clip, Export, Job
from ..schemas.api_schemas import ProjectCreate, ProjectUpdate, ProjectResponse, DashboardStats

class ProjectService:
    @staticmethod
    async def create_project(db: AsyncSession, data: ProjectCreate) -> Project:
        project = Project(
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            status="active"
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    async def list_projects(
        db: AsyncSession,
        search: Optional[str] = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc"
    ) -> List[Dict[str, Any]]:
        # Query projects with video and clip counts
        query = select(Project).where(Project.status == "active")

        if search:
            query = query.where(Project.name.ilike(f"%{search.strip()}%"))

        order_col = getattr(Project, sort_by, Project.updated_at)
        if sort_order.lower() == "asc":
            query = query.order_by(asc(order_col))
        else:
            query = query.order_by(desc(order_col))

        result = await db.execute(query)
        projects = result.scalars().all()

        items = []
        for p in projects:
            # Count videos and clips
            v_res = await db.execute(select(func.count(Video.id)).where(Video.project_id == p.id))
            c_res = await db.execute(select(func.count(Clip.id)).where(Clip.project_id == p.id))
            video_count = v_res.scalar() or 0
            clip_count = c_res.scalar() or 0

            items.append({
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "video_count": video_count,
                "clip_count": clip_count,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            })
        return items

    @staticmethod
    async def get_project(db: AsyncSession, project_id: str) -> Optional[Dict[str, Any]]:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return None

        v_res = await db.execute(select(func.count(Video.id)).where(Video.project_id == project.id))
        c_res = await db.execute(select(func.count(Clip.id)).where(Clip.project_id == project.id))
        vids_res = await db.execute(select(Video).where(Video.project_id == project.id).order_by(Video.created_at.desc()))
        videos = vids_res.scalars().all()

        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "video_count": v_res.scalar() or 0,
            "clip_count": c_res.scalar() or 0,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "videos": videos,
        }

    @staticmethod
    async def update_project(db: AsyncSession, project_id: str, data: ProjectUpdate) -> Optional[Project]:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return None

        if data.name is not None:
            project.name = data.name.strip()
        if data.description is not None:
            project.description = data.description.strip()
        if data.status is not None:
            project.status = data.status

        project.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    async def delete_project(db: AsyncSession, project_id: str) -> bool:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            return False

        # Delete project cascade (database relations will delete clips and metadata)
        # Note: Original videos in uploads or external locations are never destroyed
        await db.delete(project)
        await db.commit()
        return True

    @staticmethod
    async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
        p_res = await db.execute(select(func.count(Project.id)).where(Project.status == "active"))
        v_res = await db.execute(select(func.count(Video.id)))
        c_res = await db.execute(select(func.count(Clip.id)))
        e_res = await db.execute(select(func.count(Export.id)))
        j_res = await db.execute(select(func.count(Job.id)).where(Job.status.in_(["queued", "running"])))

        recent = await ProjectService.list_projects(db, sort_by="updated_at", sort_order="desc")

        return DashboardStats(
            total_projects=p_res.scalar() or 0,
            total_videos=v_res.scalar() or 0,
            total_clips=c_res.scalar() or 0,
            total_exports=e_res.scalar() or 0,
            active_jobs=j_res.scalar() or 0,
            recent_projects=[ProjectResponse(**item) for item in recent[:5]]
        )
