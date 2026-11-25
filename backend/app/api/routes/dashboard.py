from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import verify_session_token
from ...schemas.api_schemas import DashboardStats
from ...services.project_service import ProjectService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve non-mock statistics for the dashboard directly from SQLite."""
    stats = await ProjectService.get_dashboard_stats(db)
    return stats
