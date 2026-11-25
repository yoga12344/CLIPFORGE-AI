"""
ClipForge AI - LLM Inference Manager
Controls local model lifecycle, enforces sequential execution lock, and coordinates unloading.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

from .llm_provider import LLMProvider, LlamaCppBinaryProvider
from .model_manager import LLMModelManager, LLMModelStatus
from .model_registry import ModelRegistry, LLMModelDefinition
from ..transcription_engine import TranscriptionEngine

logger = logging.getLogger("clipforge.ai.llm.inference")


class LLMInferenceStatus(BaseModel):
    is_busy: bool = False
    active_model_id: Optional[str] = None
    loaded_at: Optional[float] = None
    llama_binary_available: bool = False
    installed_models: List[str] = []


class LLMInferenceManager:
    _instance: Optional["LLMInferenceManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()
    _active_provider: Optional[LLMProvider] = None
    _active_model_id: Optional[str] = None
    _loaded_at: Optional[float] = None

    @classmethod
    def get_instance(cls) -> "LLMInferenceManager":
        if cls._instance is None:
            cls._instance = LLMInferenceManager()
        return cls._instance

    def get_status(self) -> LLMInferenceStatus:
        installed = [
            s.model_id for s in LLMModelManager.list_installed_models() if s.is_installed
        ]
        bin_path = LlamaCppBinaryProvider.get_binary_path()
        return LLMInferenceStatus(
            is_busy=self._lock.locked(),
            active_model_id=self._active_model_id,
            loaded_at=self._loaded_at,
            llama_binary_available=bin_path is not None and bin_path.is_file(),
            installed_models=installed
        )

    def unload(self) -> None:
        """Release active LLM provider from memory."""
        if self._active_provider is not None:
            logger.info(f"Unloading LLM model '{self._active_model_id}'...")
            try:
                self._active_provider.unload()
            except Exception as e:
                logger.warning(f"Error unloading LLM provider: {e}")
            finally:
                self._active_provider = None
                self._active_model_id = None
                self._loaded_at = None

    async def get_provider(
        self,
        model_id: str,
        context_window: int = 4096,
        threads: int = 6
    ) -> LLMProvider:
        """
        Obtain an initialized LLMProvider for the requested model.
        Unloads any Whisper model currently in memory to protect system RAM/VRAM.
        """
        # Ensure Whisper model is unloaded
        TranscriptionEngine.get_instance().unload_model()

        model_status = LLMModelManager.check_model_status(model_id)
        if not model_status.is_installed or not model_status.file_path:
            raise FileNotFoundError(
                f"LLM model '{model_id}' is not installed locally. Please download it first."
            )

        # If already loaded with the same model, return it
        if self._active_provider is not None and self._active_model_id == model_id:
            return self._active_provider

        # Unload previous
        self.unload()

        provider = LlamaCppBinaryProvider(
            model_path=model_status.file_path,
            context_window=context_window,
            threads=threads
        )

        if not provider.is_available():
            raise RuntimeError(
                f"Llama.cpp runtime is not available for model '{model_id}'. "
                f"Check binary at {LlamaCppBinaryProvider.get_binary_path()}"
            )

        self._active_provider = provider
        self._active_model_id = model_id
        self._loaded_at = time.time()
        logger.info(f"Initialized LlamaCppBinaryProvider for '{model_id}'.")
        return provider

    async def execute_inference(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        context_window: int = 4096,
        threads: int = 6,
        cancellation_token: Optional[asyncio.Event] = None
    ) -> str:
        """
        Execute inference under sequential acquisition lock.
        Unloads model automatically after generation if configured.
        """
        async with self._lock:
            provider = await self.get_provider(
                model_id=model_id,
                context_window=context_window,
                threads=threads
            )

            try:
                res = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    cancellation_token=cancellation_token
                )
                return res
            finally:
                # Release memory promptly to preserve RAM
                self.unload()
