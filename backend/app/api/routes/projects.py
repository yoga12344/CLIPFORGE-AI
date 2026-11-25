from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from ...core.database import get_db
from ...core.security import verify_session_token
from ...schemas.api_schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from ...services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    search: Optional[str] = Query(None),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve list of projects with video & clip counts."""
    projects = await ProjectService.list_projects(
        db, search=search, sort_by=sort_by, sort_order=sort_order
    )
    return projects

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Create a new project in SQLite."""
    project = await ProjectService.create_project(db, data)
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "video_count": 0,
        "clip_count": 0,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Get project details by ID."""
    project = await ProjectService.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Update project name, description or status."""
    project = await ProjectService.update_project(db, project_id, data)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    details = await ProjectService.get_project(db, project_id)
    return details

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Safely delete project and related SQLite records."""
    success = await ProjectService.delete_project(db, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return None
