from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from datetime import datetime

from ..core.config import settings
from ..db.models import AppSetting

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
    "language": "en",
    "startup_behavior": "dashboard",
    "project_storage_path": str(settings.PROJECTS_DIR),
    "cache_path": str(settings.CACHE_DIR),
    "export_directory": str(settings.EXPORTS_DIR),
    "gpu_acceleration": True,
    "cpu_fallback": True,
    "max_concurrent_gpu_jobs": 1,
    "vram_budget_mb": 6000,
    "default_transcription_model": "whisper-base-int8",
    "default_llm_model": "llama-3.2-3b-instruct",
    "model_storage_location": str(settings.MODELS_DIR),
}

class SettingsService:
    @staticmethod
    async def get_all_settings(db: AsyncSession) -> Dict[str, Any]:
        """Fetch all settings from SQLite, seeding defaults for any missing keys."""
        result = await db.execute(select(AppSetting))
        rows = result.scalars().all()
        db_map = {row.key: row.value for row in rows}

        merged = dict(DEFAULT_SETTINGS)
        needs_commit = False

        for k, default_val in DEFAULT_SETTINGS.items():
            if k in db_map:
                merged[k] = db_map[k]
            else:
                # Seed default key in DB
                setting_row = AppSetting(key=k, value=default_val, description=f"Default setting for {k}")
                db.add(setting_row)
                needs_commit = True

        if needs_commit:
            await db.commit()

        return merged

    @staticmethod
    async def update_settings(db: AsyncSession, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update settings keys in SQLite."""
        for key, val in updates.items():
            res = await db.execute(select(AppSetting).where(AppSetting.key == key))
            existing = res.scalar_one_or_none()
            if existing:
                existing.value = val
                existing.updated_at = datetime.utcnow()
            else:
                new_row = AppSetting(key=key, value=val)
                db.add(new_row)

        await db.commit()
        return await SettingsService.get_all_settings(db)
