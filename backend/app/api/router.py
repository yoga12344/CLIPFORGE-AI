from fastapi import APIRouter
from .routes.health import router as health_router
from .routes.projects import router as projects_router
from .routes.dashboard import router as dashboard_router
from .routes.videos import router as videos_router
from .routes.settings import router as settings_router
from .routes.clips import router as clips_router
from .routes.jobs import router as jobs_router
from .routes.transcription import router as transcription_router
from .routes.transcripts import router as transcripts_router
from .routes.llm import router as llm_router
from .routes.highlights import router as highlights_router
from .routes.vision import router as vision_router
from .routes.subtitles import router as subtitles_router
from .routes.exports import router as exports_router
from .routes.audio import router as audio_router
from .routes.speakers import router as speakers_router
from .routes.active_speakers import router as active_speakers_router
from .routes.compositions import router as compositions_router
from .routes.models import router as models_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(projects_router)
api_router.include_router(dashboard_router)
api_router.include_router(videos_router)
api_router.include_router(settings_router)
api_router.include_router(clips_router)
api_router.include_router(jobs_router)
api_router.include_router(transcription_router)
api_router.include_router(transcripts_router)
api_router.include_router(llm_router)
api_router.include_router(highlights_router)
api_router.include_router(vision_router)
api_router.include_router(subtitles_router)
api_router.include_router(exports_router)
api_router.include_router(audio_router)
api_router.include_router(speakers_router)
api_router.include_router(active_speakers_router)
api_router.include_router(compositions_router)
api_router.include_router(models_router)
