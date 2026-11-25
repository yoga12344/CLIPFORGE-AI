"""
ClipForge AI - Local LLM Model Manager
Handles on-demand download, verification, integrity checking, and lifecycle of GGUF models.
"""

import asyncio
import logging
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Callable, Coroutine, Optional
from pydantic import BaseModel

from ...core.config import settings
from .model_registry import ModelRegistry, LLMModelDefinition

logger = logging.getLogger("clipforge.ai.llm.manager")


class LLMModelStatus(BaseModel):
    model_id: str
    name: str
    is_installed: bool = False
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    expected_size_bytes: int = 0
    parameter_count: str = ""
    quantization: str = ""
    is_downloading: bool = False
    download_percent: float = 0.0


class LLMModelManager:
    _downloading: dict = {}

    @classmethod
    def get_models_dir(cls) -> Path:
        models_dir = settings.DATA_DIR / "models" / "llm"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir

    @classmethod
    def get_model_path(cls, model_id: str) -> Optional[Path]:
        defn = ModelRegistry.get_model(model_id)
        if not defn:
            return None
        return cls.get_models_dir() / defn.file_name

    @classmethod
    def check_model_status(cls, model_id: str) -> LLMModelStatus:
        defn = ModelRegistry.get_model(model_id)
        if not defn:
            return LLMModelStatus(
                model_id=model_id,
                name="Unknown Model",
                is_installed=False
            )

        target_file = cls.get_models_dir() / defn.file_name
        is_installed = False
        actual_size = 0

        if target_file.is_file():
            actual_size = target_file.stat().st_size
            # A valid GGUF download has non-trivial size and meets minimal threshold (> 10MB)
            if actual_size > 10 * 1024 * 1024:
                is_installed = True

        return LLMModelStatus(
            model_id=defn.id,
            name=defn.name,
            is_installed=is_installed,
            file_path=str(target_file) if is_installed else None,
            file_size_bytes=actual_size,
            expected_size_bytes=defn.file_size_bytes,
            parameter_count=defn.parameter_count,
            quantization=defn.quantization,
            is_downloading=cls._downloading.get(model_id, False),
            download_percent=0.0
        )

    @classmethod
    def list_installed_models(cls) -> list[LLMModelStatus]:
        results = []
        for defn in ModelRegistry.list_models():
            results.append(cls.check_model_status(defn.id))
        return results

    @classmethod
    async def download_model(
        cls,
        model_id: str,
        on_progress: Optional[Callable[[float, int, int], Coroutine[None, None, None]]] = None,
        cancellation_token: Optional[asyncio.Event] = None
    ) -> Path:
        """
        Download a GGUF model with streaming progress and cancellation support.
        """
        defn = ModelRegistry.get_model(model_id)
        if not defn:
            raise ValueError(f"Unknown model identifier '{model_id}'")

        if cancellation_token and cancellation_token.is_set():
            raise asyncio.CancelledError("Download cancelled by user.")

        dest_file = cls.get_models_dir() / defn.file_name
        temp_file = cls.get_models_dir() / f"{defn.file_name}.part"

        if cls.check_model_status(model_id).is_installed:
            logger.info(f"Model '{model_id}' is already installed at {dest_file}")
            return dest_file

        loop = asyncio.get_running_loop()
        cls._downloading[model_id] = True
        logger.info(f"Starting download of '{defn.name}' from {defn.source_url}...")

        try:
            def _sync_download():
                existing_bytes = temp_file.stat().st_size if temp_file.exists() else 0
                headers = {"User-Agent": "ClipForge-AI/1.0"}
                mode = "wb"
                if existing_bytes > 0:
                    headers["Range"] = f"bytes={existing_bytes}-"
                    mode = "ab"

                req = urllib.request.Request(defn.source_url, headers=headers)
                try:
                    resp = urllib.request.urlopen(req, timeout=30)
                except urllib.error.HTTPError as err:
                    if err.code in (416,):  # Range Not Satisfiable -> file already complete
                        existing_bytes = 0
                        mode = "wb"
                        headers.pop("Range", None)
                        req = urllib.request.Request(defn.source_url, headers=headers)
                        resp = urllib.request.urlopen(req, timeout=30)
                    else:
                        raise

                with resp as response:
                    status = getattr(response, "status", 200)
                    if status == 206:
                        # Resumed download
                        content_range = response.headers.get("content-range", "")
                        if "/" in content_range:
                            total_bytes = int(content_range.split("/")[-1])
                        else:
                            total_bytes = existing_bytes + int(response.headers.get("content-length", 0))
                        downloaded = existing_bytes
                    else:
                        mode = "wb"
                        downloaded = 0
                        total_bytes = int(response.headers.get("content-length", defn.file_size_bytes))

                    with open(temp_file, mode) as out_f:
                        chunk_size = 1024 * 1024  # 1 MB chunk
                        while True:
                            if cancellation_token and cancellation_token.is_set():
                                raise asyncio.CancelledError("Download cancelled by user.")

                            chunk = response.read(chunk_size)
                            if not chunk:
                                break

                            out_f.write(chunk)
                            downloaded += len(chunk)

                            if on_progress:
                                pct = min(100.0, (downloaded / max(1, total_bytes)) * 100.0)
                                try:
                                    if loop.is_running():
                                        asyncio.run_coroutine_threadsafe(
                                            on_progress(pct, downloaded, total_bytes),
                                            loop
                                        )
                                except Exception:
                                    pass

            # Run download in worker thread
            await asyncio.to_thread(_sync_download)

            # Atomic rename from .part to final .gguf
            if temp_file.exists():
                temp_file.replace(dest_file)

            logger.info(f"Model '{model_id}' downloaded successfully to {dest_file}")
            return dest_file

        except Exception as e:
            logger.error(f"Failed to download model '{model_id}': {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise e
        finally:
            cls._downloading[model_id] = False

    @classmethod
    def delete_model(cls, model_id: str) -> bool:
        defn = ModelRegistry.get_model(model_id)
        if not defn:
            return False

        target_file = cls.get_models_dir() / defn.file_name
        part_file = cls.get_models_dir() / f"{defn.file_name}.part"

        deleted = False
        if target_file.exists():
            target_file.unlink()
            deleted = True
        if part_file.exists():
            part_file.unlink()

        logger.info(f"Deleted model '{model_id}' files: {deleted}")
        return deleted
