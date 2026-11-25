from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Projects ---
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    video_count: int = 0
    clip_count: int = 0
    created_at: datetime
    updated_at: datetime
    videos: Optional[List[Any]] = []

    class Config:
        from_attributes = True

# --- Dashboard Stats ---
class DashboardStats(BaseModel):
    total_projects: int
    total_videos: int
    total_clips: int
    total_exports: int
    active_jobs: int
    recent_projects: List[ProjectResponse]

# --- Videos & Probe ---
class VideoProbeRequest(BaseModel):
    file_path: str

class VideoProbeResponse(BaseModel):
    valid: bool
    error: Optional[str] = None
    filename: str
    file_path: str
    file_size_bytes: int
    format_name: Optional[str] = None
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    has_audio: bool = False
    audio_channels: int = 0

class VideoImportRequest(BaseModel):
    project_id: str
    file_path: str
    copy_to_storage: bool = True

class VideoResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_path: str
    file_size_bytes: int
    format: Optional[str] = None
    duration_seconds: float
    width: int
    height: int
    fps: float
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    has_audio: bool
    thumbnail_path: Optional[str] = None
    preview_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- Phase 3: Video Actions & Clips ---
class VideoActionResponse(BaseModel):
    job_id: str
    message: str

class ClipGenerateRequest(BaseModel):
    project_id: str
    video_id: str
    title: str = "Untitled Clip"
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., gt=0.0)
    aspect_ratio: str = "9:16"
    reframe_mode: str = "center_crop"

class ClipResponse(BaseModel):
    id: str
    project_id: str
    video_id: str
    title: str
    start_time: float
    end_time: float
    duration_seconds: float
    aspect_ratio: str
    file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Phase 3: Background Jobs ---
class JobResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    job_type: str
    status: str
    progress_percent: int
    stage_description: str
    error_message: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result_data: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- Phase 4: Transcription & AI Models ---
class TranscribeVideoRequest(BaseModel):
    model_name: str = "small"
    language: Optional[str] = None
    device: str = "auto"
    compute_type: Optional[str] = None
    vad_filter: bool = True
    vad_threshold: float = 0.5
    beam_size: int = 5
    word_timestamps: bool = True
    temperature: float = 0.0

class TranscriptWordSchema(BaseModel):
    word: str
    start: float
    end: float
    prob: float

class TranscriptSegmentResponse(BaseModel):
    id: str
    segment_index: int
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    words: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True

class TranscriptResponse(BaseModel):
    id: str
    video_id: str
    language: str
    model_used: Optional[str] = None
    status: str
    task_type: str
    device_used: Optional[str] = None
    processing_duration_seconds: Optional[float] = None
    full_text: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    segments: List[TranscriptSegmentResponse] = []

    class Config:
        from_attributes = True

class TranscriptUpdateSchema(BaseModel):
    full_text: Optional[str] = None
    language: Optional[str] = None

class SegmentUpdateSchema(BaseModel):
    text: str

class WhisperModelResponse(BaseModel):
    model_id: str
    display_name: str
    description: str
    parameter_count: str
    is_installed: bool
    is_downloading: bool = False
    disk_size_mb: float
    recommended_vram_mb: int
    license: str
    source_url: str

# --- Settings ---
class AppSettingsSchema(BaseModel):
    theme: str = "dark"
    language: str = "en"
    startup_behavior: str = "dashboard"
    project_storage_path: str = ""
    cache_path: str = ""
    export_directory: str = ""
    gpu_acceleration: bool = True
    cpu_fallback: bool = True
    max_concurrent_gpu_jobs: int = 1
    vram_budget_mb: int = 6000
    default_transcription_model: str = "whisper-base-int8"
    default_llm_model: str = "llama-3.2-3b-instruct"
    model_storage_location: str = ""

class SettingsUpdateSchema(BaseModel):
    settings: Dict[str, Any]
