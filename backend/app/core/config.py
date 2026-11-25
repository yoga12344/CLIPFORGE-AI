import os
import shutil
import sys
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "ClipForge AI"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"

    # Base application directory
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # User data directory (local-first storage)
    DATA_DIR: Path = Path(os.environ.get("CLIPFORGE_DATA_DIR", BASE_DIR / "storage" / "clipforge_data"))
    
    # Subdirectories
    DATABASE_DIR: Path = DATA_DIR / "database"
    PROJECTS_DIR: Path = DATA_DIR / "projects"
    UPLOADS_DIR: Path = DATA_DIR / "uploads"
    CLIPS_DIR: Path = DATA_DIR / "clips"
    EXPORTS_DIR: Path = DATA_DIR / "exports"
    THUMBNAILS_DIR: Path = DATA_DIR / "thumbnails"
    CACHE_DIR: Path = DATA_DIR / "cache"
    MODELS_DIR: Path = DATA_DIR / "models"

    # SQLite Database URL (Async SQLite via aiosqlite)
    @property
    def DATABASE_URL(self) -> str:
        db_file = self.DATABASE_DIR / "clipforge.db"
        return f"sqlite+aiosqlite:///{db_file.as_posix()}"

    # Security: Session Authentication Token from Electron
    SESSION_TOKEN: str = os.environ.get("CLIPFORGE_SESSION_TOKEN", "")

    # FFmpeg & FFprobe configuration
    FFMPEG_PATH: str = os.environ.get("FFMPEG_PATH", "")

    def get_ffmpeg_binary(self) -> str:
        if self.FFMPEG_PATH and os.path.isfile(self.FFMPEG_PATH):
            return self.FFMPEG_PATH
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg:
            return sys_ffmpeg
        
        # Check standard Windows paths
        local_app = os.environ.get("LOCALAPPDATA", "")
        winget_path = os.path.join(local_app, "Microsoft", "WinGet", "Packages")
        if os.path.isdir(winget_path):
            for root, _, files in os.walk(winget_path):
                if "ffmpeg.exe" in files:
                    return os.path.join(root, "ffmpeg.exe")
        return "ffmpeg"

    def get_ffprobe_binary(self) -> str:
        ffmpeg = self.get_ffmpeg_binary()
        ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
        if os.path.isfile(ffprobe):
            return ffprobe
        sys_ffprobe = shutil.which("ffprobe")
        return sys_ffprobe or "ffprobe"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure all application storage directories exist
for folder in [
    settings.DATA_DIR,
    settings.DATABASE_DIR,
    settings.PROJECTS_DIR,
    settings.UPLOADS_DIR,
    settings.CLIPS_DIR,
    settings.EXPORTS_DIR,
    settings.THUMBNAILS_DIR,
    settings.CACHE_DIR,
    settings.MODELS_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)

# Prepend FFmpeg bin directory to environment PATH
ffmpeg_bin = settings.get_ffmpeg_binary()
if os.path.isfile(ffmpeg_bin):
    ffmpeg_dir = str(Path(ffmpeg_bin).parent)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
