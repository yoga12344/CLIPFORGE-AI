import os
import shutil
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "ClipsMaster"
    API_V1_STR: str = "/api"
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOAD_DIR: Path = STORAGE_DIR / "uploads"
    OUTPUT_DIR: Path = STORAGE_DIR / "outputs"
    TEMP_DIR: Path = STORAGE_DIR / "temp"
    
    # AI API Keys
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Whisper settings
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    
    # FFmpeg custom path if not in global PATH
    FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "")

    class Config:
        env_file = ".env"
        extra = "allow"

    def get_ffmpeg_executable(self) -> str:
        """Find the working ffmpeg executable."""
        if self.FFMPEG_PATH and os.path.isfile(self.FFMPEG_PATH):
            return self.FFMPEG_PATH
        
        # Check standard PATH
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
        
        # Check standard Windows Gyan/winget paths
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            # Winget Gyan install location
            os.path.join(local_app_data, "Microsoft", "WinGet", "Packages"),
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
        ]
        
        for cand in candidates:
            if os.path.isdir(cand):
                for root, _, files in os.walk(cand):
                    if "ffmpeg.exe" in files:
                        return os.path.join(root, "ffmpeg.exe")
            elif os.path.isfile(cand):
                return cand
                
        return "ffmpeg"

settings = Settings()

# Ensure FFmpeg directory is in system PATH
ffmpeg_exec = settings.get_ffmpeg_executable()
if os.path.isfile(ffmpeg_exec):
    ffmpeg_dir = str(Path(ffmpeg_exec).parent)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

# Ensure directories exist
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
