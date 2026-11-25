from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.security import verify_session_token
from ...db.models import Job
from ...schemas.api_schemas import JobResponse
from ...workers.job_manager import JobManager

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("", response_model=List[JobResponse])
async def list_jobs(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """List recent background video processing jobs."""
    query = select(Job)
    if project_id:
        query = query.where(Job.project_id == project_id)
    if status:
        query = query.where(Job.status == status)
    
    query = query.order_by(Job.created_at.desc()).limit(limit)
    res = await db.execute(query)
    return res.scalars().all()

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Get status and progress of a background job."""
    res = await db.execute(select(Job).where(Job.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Cancel a running or queued job."""
    res = await db.execute(select(Job).where(Job.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cancelled = await JobManager.get_instance().cancel_job(job_id)
    await db.refresh(job)
    return job

@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retry a failed or cancelled job."""
    job = await JobManager.get_instance().retry_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found for retry")
    return job
