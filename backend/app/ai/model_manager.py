import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Callable, Coroutine, Dict, List, Optional, Set
from pydantic import BaseModel

from ..core.config import settings
from .model_registry import ModelRegistry, WhisperModelDefinition

logger = logging.getLogger("clipforge.ai.models")

class ModelStatus(BaseModel):
    model_id: str
    display_name: str
    description: str
    parameter_count: str
    is_installed: bool
    is_downloading: bool = False
    download_progress: int = 0
    disk_size_mb: float
    recommended_vram_mb: int
    local_path: Optional[str] = None
    missing_files: List[str] = []
    license: str
    source_url: str

class ModelManager:
    _active_downloads: Set[str] = set()
    _download_tasks: Dict[str, asyncio.Task] = {}

    @classmethod
    def get_models_dir(cls) -> Path:
        models_dir = settings.DATA_DIR / "models" / "whisper"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir

    @classmethod
    def get_model_path(cls, model_id: str) -> Path:
        return cls.get_models_dir() / model_id.lower()

    @classmethod
    def check_model_status(cls, model_id: str) -> ModelStatus:
        defn = ModelRegistry.get(model_id)
        if not defn:
            raise ValueError(f"Unknown Whisper model: {model_id}")

        model_dir = cls.get_model_path(model_id)
        is_downloading = model_id.lower() in cls._active_downloads

        if not model_dir.exists() or not model_dir.is_dir():
            return ModelStatus(
                model_id=defn.model_id,
                display_name=defn.display_name,
                description=defn.description,
                parameter_count=defn.parameter_count,
                is_installed=False,
                is_downloading=is_downloading,
                disk_size_mb=0.0,
                recommended_vram_mb=defn.recommended_vram_mb,
                missing_files=defn.required_files,
                license=defn.license,
                source_url=defn.source_url
            )

        # Check required files
        missing = []
        for req in defn.required_files:
            target_f = model_dir / req
            if not target_f.exists() or target_f.stat().st_size == 0:
                missing.append(req)

        # Calculate actual disk size
        total_bytes = 0
        for root, _, files in os.walk(model_dir):
            for f in files:
                total_bytes += os.path.getsize(os.path.join(root, f))
        disk_mb = round(total_bytes / (1024 * 1024), 1)

        is_installed = len(missing) == 0

        return ModelStatus(
            model_id=defn.model_id,
            display_name=defn.display_name,
            description=defn.description,
            parameter_count=defn.parameter_count,
            is_installed=is_installed,
            is_downloading=is_downloading,
            disk_size_mb=disk_mb,
            recommended_vram_mb=defn.recommended_vram_mb,
            local_path=str(model_dir.resolve()) if is_installed else None,
            missing_files=missing,
            license=defn.license,
            source_url=defn.source_url
        )

    @classmethod
    def list_models_status(cls) -> List[ModelStatus]:
        return [cls.check_model_status(defn.model_id) for defn in ModelRegistry.list_all()]

    @classmethod
    async def download_model(
        cls,
        model_id: str,
        on_progress: Optional[Callable[[int, str], Coroutine[None, None, None]]] = None
    ) -> str:
        """
        Download a Whisper model from Hugging Face on-demand with progress tracking.
        Prevents concurrent downloads of the same model.
        """
        model_id_clean = model_id.lower()
        defn = ModelRegistry.get(model_id_clean)
        if not defn:
            raise ValueError(f"Unknown Whisper model: {model_id}")

        if model_id_clean in cls._active_downloads:
            raise RuntimeError(f"Model '{model_id}' is already downloading.")

        # Check if already installed
        status = cls.check_model_status(model_id_clean)
        if status.is_installed:
            logger.info(f"Model '{model_id}' is already installed at {status.local_path}")
            return status.local_path

        dest_dir = cls.get_model_path(model_id_clean)
        dest_dir.mkdir(parents=True, exist_ok=True)

        cls._active_downloads.add(model_id_clean)
        logger.info(f"Starting download of model '{model_id_clean}' from {defn.repo_id}...")

        if on_progress:
            await on_progress(5, f"Connecting to Hugging Face ({defn.repo_id})...")

        try:
            import faster_whisper

            loop = asyncio.get_running_loop()

            # Execute faster_whisper.download_model in a worker thread
            def do_download():
                return faster_whisper.download_model(
                    size_or_id=defn.model_id,
                    output_dir=str(dest_dir.resolve())
                )

            if on_progress:
                await on_progress(20, f"Downloading {defn.display_name} weights (~{defn.disk_size_mb} MB)...")

            downloaded_path = await loop.run_in_executor(None, do_download)

            # Verify installation
            post_status = cls.check_model_status(model_id_clean)
            if not post_status.is_installed:
                raise RuntimeError(
                    f"Model download completed but required files are missing: {post_status.missing_files}"
                )

            if on_progress:
                await on_progress(100, f"Model {defn.display_name} verified and ready.")

            logger.info(f"Model '{model_id_clean}' installed successfully at {downloaded_path}")
            return str(dest_dir.resolve())

        except Exception as e:
            logger.error(f"Failed to download model '{model_id_clean}': {e}", exc_info=True)
            # Cleanup corrupt partial download
            if dest_dir.exists():
                shutil.rmtree(dest_dir, ignore_errors=True)
            raise
        finally:
            cls._active_downloads.discard(model_id_clean)

    @classmethod
    def delete_model(cls, model_id: str) -> bool:
        """Safely delete model files from disk."""
        model_id_clean = model_id.lower()
        if model_id_clean in cls._active_downloads:
            raise RuntimeError(f"Cannot delete model '{model_id}' while download is in progress.")

        model_dir = cls.get_model_path(model_id_clean)
        if model_dir.exists() and model_dir.is_dir():
            shutil.rmtree(model_dir, ignore_errors=True)
            logger.info(f"Deleted Whisper model '{model_id_clean}' from {model_dir}")
            return True
        return False
