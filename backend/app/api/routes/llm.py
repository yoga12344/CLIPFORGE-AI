"""
ClipForge AI - Local LLM Management Routes
"""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...core.security import verify_session_token
from ...ai.llm.model_registry import ModelRegistry, LLMModelDefinition
from ...ai.llm.model_manager import LLMModelManager, LLMModelStatus
from ...ai.llm.inference_manager import LLMInferenceManager, LLMInferenceStatus

router = APIRouter(prefix="/ai/llm", tags=["AI LLM"], dependencies=[Depends(verify_session_token)])


class LLMModelResponse(BaseModel):
    id: str
    name: str
    parameter_count: str
    quantization: str
    file_name: str
    file_size_bytes: int
    context_window: int
    is_default: bool
    description: str
    is_installed: bool
    is_downloading: bool
    file_path: Optional[str] = None


@router.get("/status", response_model=LLMInferenceStatus)
async def get_llm_status():
    """Retrieve runtime status of local LLM inference subsystem."""
    return LLMInferenceManager.get_instance().get_status()


@router.get("/models", response_model=List[LLMModelResponse])
async def list_llm_models():
    """List all supported GGUF models along with their installation status."""
    defs = ModelRegistry.list_models()
    results = []
    for d in defs:
        status_info = LLMModelManager.check_model_status(d.id)
        results.append(LLMModelResponse(
            id=d.id,
            name=d.name,
            parameter_count=d.parameter_count,
            quantization=d.quantization,
            file_name=d.file_name,
            file_size_bytes=d.file_size_bytes,
            context_window=d.context_window,
            is_default=d.is_default,
            description=d.description,
            is_installed=status_info.is_installed,
            is_downloading=status_info.is_downloading,
            file_path=status_info.file_path
        ))
    return results


@router.post("/models/{model_name}/download")
async def download_llm_model(model_name: str):
    """Trigger background download of a GGUF model."""
    defn = ModelRegistry.get_model(model_name)
    if not defn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found in registry."
        )

    # Launch download in background task
    asyncio.create_task(LLMModelManager.download_model(model_name))
    return {
        "status": "download_started",
        "model_id": model_name,
        "name": defn.name,
        "message": f"Download initiated for {defn.name}."
    }


@router.delete("/models/{model_name}")
async def delete_llm_model(model_name: str):
    """Delete a downloaded GGUF model from disk."""
    success = LLMModelManager.delete_model(model_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' file not found or could not be deleted."
        )
    return {"status": "deleted", "model_id": model_name}
