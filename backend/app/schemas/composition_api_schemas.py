"""
ClipForge AI - Composition REST API Request and Response Schemas
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.composition.schemas.composition import CompositionSpec
from app.composition.schemas.validation import CompositionValidationResult


class CreateCompositionRequest(BaseModel):
    project_id: str = Field(..., description="Owning Project ID")
    video_id: str = Field(..., description="Parent Video ID")
    title: str = Field("Untitled Composition", max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    candidate_id: Optional[str] = Field(None, description="Optional approved HighlightCandidate ID")
    aspect_ratio: str = Field("9:16", description="Target aspect ratio: 9:16, 1:1, 4:5, 16:9")
    initial_spec: Optional[CompositionSpec] = None


class UpdateCompositionRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, description="draft, ready, rendering, exported, archived")


class CreateVersionRequest(BaseModel):
    spec: CompositionSpec
    change_summary: Optional[str] = Field(None, max_length=255)
    is_draft: bool = Field(False, description="True for autosaved working draft; False for locked revision")
    expected_version_number: Optional[int] = Field(
        None,
        description="Optimistic Concurrency Control: Expected latest version number to prevent race conditions"
    )


class RestoreVersionRequest(BaseModel):
    description: Optional[str] = Field(None, max_length=255)


class CompositionVersionResponse(BaseModel):
    id: str
    composition_id: str
    version_number: int
    schema_version: str
    content_hash: str
    change_summary: Optional[str]
    is_draft: bool
    created_at: datetime
    spec: CompositionSpec


class CompositionResponse(BaseModel):
    id: str
    project_id: str
    source_video_id: str
    candidate_id: Optional[str]
    title: str
    description: Optional[str]
    status: str
    current_version_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    active_version: Optional[CompositionVersionResponse] = None


class RegisterAssetRequest(BaseModel):
    asset_type: str = Field(..., description="videos, audio, images, broll, overlays, subtitles, fonts")
    logical_asset_id: str = Field(..., description="Alphanumeric slug (e.g. music_bed_01)")
    name: str = Field(..., description="Display name")
    file_path: str = Field(..., description="Relative project asset path")
    file_size_bytes: int = Field(0, ge=0)
    duration_seconds: Optional[float] = None
    media_metadata: Optional[Dict[str, Any]] = None


class CompositionAssetResponse(BaseModel):
    id: str
    project_id: str
    asset_type: str
    logical_asset_id: str
    asset_uri: str
    name: str
    file_size_bytes: int
    duration_seconds: Optional[float]
    media_metadata: Optional[Dict[str, Any]]
    created_at: datetime


class CompileExecutionPlanRequest(BaseModel):
    preferred_encoder: Optional[str] = Field(None, description="Optional override: h264_nvenc or libx264")


class CompileExecutionPlanResponse(BaseModel):
    composition_id: str
    version_id: str
    version_number: int
    video_encoder: str
    command_args: List[str]
    filter_complex_string: str
    is_script_file: bool
    input_files: List[str]
    output_file_path: str
    estimated_duration_seconds: float
    node_count: int
    edge_count: int


class CreateRenderRequest(BaseModel):
    custom_output_path: Optional[str] = Field(None, description="Optional custom destination path")


class AutoPlanCompositionRequest(BaseModel):
    project_id: str = Field(..., description="Owning Project ID")
    video_id: Optional[str] = Field(None, description="Source Video ID if planning from time window")
    candidate_id: Optional[str] = Field(None, description="HighlightCandidate ID if planning from highlight")
    start_time: Optional[float] = Field(None, ge=0.0, description="Start time in seconds if planning from time window")
    end_time: Optional[float] = Field(None, ge=0.0, description="End time in seconds if planning from time window")
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    aspect_ratio: str = Field("9:16", description="Target aspect ratio: 9:16, 1:1, 16:9")
    subtitle_preset: str = Field("preset_bold_creator", description="Subtitle preset ID")
    enable_subtitles: bool = Field(True)


class RenderArtifactResponse(BaseModel):
    id: str
    composition_render_id: str
    artifact_type: str
    file_path: str
    file_size_bytes: int
    created_at: datetime


class CompositionRenderResponse(BaseModel):
    id: str
    composition_id: str
    composition_version_id: str
    job_id: Optional[str]
    output_path: str
    status: str
    progress_percent: int
    error_message: Optional[str]
    render_duration_seconds: Optional[float]
    file_size_bytes: Optional[int]
    validation_metrics: Optional[Dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime]
    artifacts: List[RenderArtifactResponse] = Field(default_factory=list)
