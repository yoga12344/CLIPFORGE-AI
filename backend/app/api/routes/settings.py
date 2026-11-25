from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from ...core.database import get_db
from ...core.security import verify_session_token
from ...schemas.api_schemas import SettingsUpdateSchema
from ...services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("", response_model=Dict[str, Any])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Retrieve all current application settings."""
    return await SettingsService.get_all_settings(db)

@router.patch("", response_model=Dict[str, Any])
async def update_settings(
    data: SettingsUpdateSchema,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token)
):
    """Update application settings."""
    return await SettingsService.update_settings(db, data.settings)
