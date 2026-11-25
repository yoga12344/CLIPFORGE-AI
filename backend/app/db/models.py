import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, ForeignKey, DateTime, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from ..core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active", index=True) # active, archived
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
    clips = relationship("Clip", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")
    highlight_candidates = relationship("HighlightCandidate", back_populates="project", cascade="all, delete-orphan")
    compositions = relationship("Composition", back_populates="project", cascade="all, delete-orphan")
    composition_assets = relationship("CompositionAsset", back_populates="project", cascade="all, delete-orphan")

class Video(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    format = Column(String(50), nullable=True)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    width = Column(Integer, nullable=False, default=1920)
    height = Column(Integer, nullable=False, default=1080)
    fps = Column(Float, nullable=False, default=30.0)
    video_codec = Column(String(50), nullable=True)
    audio_codec = Column(String(50), nullable=True)
    has_audio = Column(Boolean, default=True)
    audio_channels = Column(Integer, default=2)
    thumbnail_path = Column(Text, nullable=True)
    preview_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="videos")
    transcript = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
    clips = relationship("Clip", back_populates="video", cascade="all, delete-orphan")
    highlight_candidates = relationship("HighlightCandidate", back_populates="video", cascade="all, delete-orphan")
    vision_analyses = relationship("VisionAnalysis", back_populates="video", cascade="all, delete-orphan")
    audio_analyses = relationship("AudioAnalysis", back_populates="video", cascade="all, delete-orphan")
    active_speaker_intervals = relationship("ActiveSpeakerInterval", back_populates="video", cascade="all, delete-orphan", order_by="ActiveSpeakerInterval.start_time")
    speaker_face_associations = relationship("SpeakerFaceAssociation", back_populates="video", cascade="all, delete-orphan")
    landmark_analyses = relationship("FacialLandmarkAnalysis", back_populates="video", cascade="all, delete-orphan")
    compositions = relationship("Composition", back_populates="source_video", cascade="all, delete-orphan")

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    language = Column(String(20), default="en")
    model_used = Column(String(100), nullable=True) # e.g. "whisper-base-int8"
    status = Column(String(50), default="completed", index=True) # processing, completed, failed
    task_type = Column(String(50), default="transcribe")
    device_used = Column(String(50), nullable=True) # e.g. "cuda (float16)", "cpu (int8)"
    processing_duration_seconds = Column(Float, nullable=True)
    full_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="transcript")
    segments = relationship("TranscriptSegment", back_populates="transcript", cascade="all, delete-orphan", order_by="TranscriptSegment.start_time")

class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    transcript_id = Column(String(36), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_id = Column(String(36), ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True)
    segment_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False, index=True)
    text = Column(Text, nullable=False)
    words = Column(JSON, nullable=True) # Word level list: [{"word": str, "start": float, "end": float, "prob": float}]
    confidence = Column(Float, nullable=True)

    # Relationships
    transcript = relationship("Transcript", back_populates="segments")
    speaker = relationship("Speaker", back_populates="segments")

class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(String(36), ForeignKey("audio_analyses.id", ondelete="CASCADE"), nullable=True, index=True)
    speaker_identifier = Column(String(50), nullable=True)  # e.g. "SPEAKER_00"
    label = Column(String(100), nullable=False)  # e.g. "Speaker 1"
    display_name = Column(String(100), nullable=True)  # e.g. "Speaker 1"
    color = Column(String(20), default="#6366f1")
    total_speech_duration = Column(Float, default=0.0)
    turn_count = Column(Integer, default=0)
    model_name = Column(String(100), default="3dspeaker_campplus")
    model_version = Column(String(50), default="1.0.0")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project")
    audio_analysis = relationship("AudioAnalysis", back_populates="speakers")
    segments = relationship("TranscriptSegment", back_populates="speaker")
    speaker_turns = relationship("SpeakerTurn", back_populates="speaker", cascade="all, delete-orphan", order_by="SpeakerTurn.start_time")
    embeddings = relationship("SpeakerEmbedding", back_populates="speaker", cascade="all, delete-orphan")

class Clip(Base):
    __tablename__ = "clips"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    hook_sentence = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    aspect_ratio = Column(String(20), default="9:16")
    file_path = Column(Text, nullable=True)
    thumbnail_path = Column(Text, nullable=True)
    transcript_excerpt = Column(Text, nullable=True)
    status = Column(String(50), default="ready", index=True) # draft, ready, rendering, exported
    edl_settings = Column(JSON, nullable=True) # Non-destructive edit decision list
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="clips")
    video = relationship("Video", back_populates="clips")
    scores = relationship("ClipScore", back_populates="clip", uselist=False, cascade="all, delete-orphan")
    exports = relationship("Export", back_populates="clip", cascade="all, delete-orphan")
    candidate = relationship("HighlightCandidate", back_populates="clip", uselist=False)
    subtitle_track = relationship("SubtitleTrack", back_populates="clip", uselist=False, cascade="all, delete-orphan")

class ClipScore(Base):
    __tablename__ = "clip_scores"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    clip_id = Column(String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    overall_score = Column(Integer, nullable=False, index=True) # 0 - 100
    hook_score = Column(Integer, default=80)
    flow_score = Column(Integer, default=80)
    engagement_score = Column(Integer, default=80)
    value_score = Column(Integer, default=80)
    dimensions = Column(JSON, nullable=True) # Detail dictionary
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    clip = relationship("Clip", back_populates="scores")

class HighlightCandidate(Base):
    __tablename__ = "highlight_candidates"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_id = Column(String(36), ForeignKey("transcripts.id", ondelete="SET NULL"), nullable=True, index=True)
    clip_id = Column(String(36), ForeignKey("clips.id", ondelete="SET NULL"), nullable=True, index=True)

    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False, index=True)
    duration_seconds = Column(Float, nullable=False)

    title = Column(String(255), nullable=False)
    hook = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    category = Column(String(50), default="general")
    key_quote = Column(Text, nullable=True)
    transcript_excerpt = Column(Text, nullable=True)

    overall_score = Column(Integer, default=0, index=True)
    score_breakdown = Column(JSON, nullable=True)
    model_name = Column(String(100), default="qwen-2.5-3b")
    generation_method = Column(String(50), default="llm")
    status = Column(String(50), default="discovered", index=True)  # discovered, approved, rejected, edited, ready_for_render

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="highlight_candidates")
    video = relationship("Video", back_populates="highlight_candidates")
    clip = relationship("Clip", back_populates="candidate")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    job_type = Column(String(50), nullable=False, index=True) # import, transcribe, highlights, reframing, render, export
    status = Column(String(50), default="queued", index=True) # queued, running, paused, completed, failed, cancelled
    progress_percent = Column(Integer, default=0)
    stage_description = Column(String(255), default="Initializing")
    error_message = Column(Text, nullable=True)
    params = Column(JSON, nullable=True)
    result_data = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="jobs")

class Export(Base):
    __tablename__ = "exports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    clip_id = Column(String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True)
    preset_id = Column(String(36), ForeignKey("caption_presets.id", ondelete="SET NULL"), nullable=True, index=True)
    output_path = Column(Text, nullable=False)
    resolution = Column(String(50), default="1080x1920")
    fps = Column(Float, default=30.0)
    bitrate_kbps = Column(Integer, default=6000)
    codec = Column(String(50), default="libx264")
    file_size_bytes = Column(Integer, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    burn_subtitles = Column(Boolean, default=True)
    subtitle_settings = Column(JSON, nullable=True)
    status = Column(String(50), default="completed", index=True) # queued, running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    clip = relationship("Clip", back_populates="exports")
    preset = relationship("CaptionPreset")

class CaptionPreset(Base):
    __tablename__ = "caption_presets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    font_family = Column(String(100), default="Arial")
    font_size = Column(Integer, default=64)
    primary_color = Column(String(20), default="#FFFFFF")
    highlight_color = Column(String(20), default="#FACC15") # Vibrant Yellow
    outline_color = Column(String(20), default="#000000")
    outline_width = Column(Integer, default=6)
    shadow_width = Column(Integer, default=2)
    bold = Column(Boolean, default=True)
    italic = Column(Boolean, default=False)
    alignment = Column(Integer, default=2) # ASS numpad: 2 = bottom-center, 5 = mid-center, 8 = top-center
    margin_v = Column(Integer, default=220)
    margin_l = Column(Integer, default=40)
    margin_r = Column(Integer, default=40)
    max_words_per_line = Column(Integer, default=4)
    max_lines = Column(Integer, default=2)
    bg_color = Column(String(20), default="&H00000000")
    bg_padding = Column(Integer, default=0)
    animation_style = Column(String(50), default="karaoke_pop") # karaoke_pop, word_by_word, phrase_fade, static
    position_y = Column(Integer, default=450) # Legacy bottom offset compatibility
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SubtitleTrack(Base):
    __tablename__ = "subtitle_tracks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    clip_id = Column(String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    preset_id = Column(String(36), ForeignKey("caption_presets.id", ondelete="SET NULL"), nullable=True, index=True)
    language = Column(String(20), default="en")
    is_enabled = Column(Boolean, default=True)
    style_overrides = Column(JSON, nullable=True)
    segments = Column(JSON, nullable=False) # List of clip-relative subtitle segments with word timings
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    clip = relationship("Clip", back_populates="subtitle_track")
    preset = relationship("CaptionPreset")

class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class VisionAnalysis(Base):
    __tablename__ = "vision_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    clip_id = Column(String(36), ForeignKey("clips.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String(50), default="completed", index=True) # processing, completed, failed
    model_used = Column(String(100), default="yunet")
    sampling_fps = Column(Float, default=4.0)
    total_frames_sampled = Column(Integer, default=0)
    frames_with_faces = Column(Integer, default=0)
    scene_type = Column(String(50), default="single_subject")
    composition_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="vision_analyses")
    tracks = relationship("FaceTrack", back_populates="vision_analysis", cascade="all, delete-orphan", order_by="FaceTrack.detection_count.desc()")
    manual_crops = relationship("ManualCropCorrection", back_populates="vision_analysis", cascade="all, delete-orphan")

class FaceTrack(Base):
    __tablename__ = "face_tracks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    vision_analysis_id = Column(String(36), ForeignKey("vision_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id = Column(String(50), nullable=False) # e.g. "track_1"
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    detection_count = Column(Integer, default=0)
    average_confidence = Column(Float, default=0.0)
    average_bbox = Column(JSON, nullable=True) # {"x": float, "y": float, "width": float, "height": float}
    samples = Column(JSON, nullable=True) # List of samples
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    vision_analysis = relationship("VisionAnalysis", back_populates="tracks")

class ManualCropCorrection(Base):
    __tablename__ = "manual_crop_corrections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    vision_analysis_id = Column(String(36), ForeignKey("vision_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp_seconds = Column(Float, nullable=False, index=True)
    crop_x = Column(Float, nullable=False)
    crop_y = Column(Float, nullable=False)
    crop_width = Column(Float, nullable=False)
    crop_height = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    vision_analysis = relationship("VisionAnalysis", back_populates="manual_crops")

class ReframePreset(Base):
    __tablename__ = "reframe_presets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    aspect_ratio = Column(String(20), default="9:16")
    strategy = Column(String(50), default="largest_face")
    smoothing_strength = Column(Float, default=0.85)
    crop_padding = Column(Float, default=0.15)
    headroom = Column(Float, default=0.20)
    max_crop_velocity_per_sec = Column(Float, default=0.50)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AudioAnalysis(Base):
    __tablename__ = "audio_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="completed", index=True) # running, completed, failed
    source_sample_rate = Column(Integer, nullable=True)
    source_channels = Column(Integer, nullable=True)
    processed_sample_rate = Column(Integer, default=16000)
    processed_channels = Column(Integer, default=1)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    speech_duration_seconds = Column(Float, default=0.0)
    audio_available = Column(Boolean, default=True)
    audio_is_silent = Column(Boolean, default=False)
    vad_model = Column(String(100), default="silero-vad-v4")
    vad_version = Column(String(50), default="1.2.1")
    processing_device = Column(String(50), default="cpu")
    processing_duration_seconds = Column(Float, default=0.0)
    configuration = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="audio_analyses")
    project = relationship("Project")
    speech_intervals = relationship(
        "SpeechInterval",
        back_populates="audio_analysis",
        cascade="all, delete-orphan",
        order_by="SpeechInterval.start_time"
    )
    speakers = relationship(
        "Speaker",
        back_populates="audio_analysis",
        cascade="all, delete-orphan",
        order_by="Speaker.speaker_identifier"
    )
    speaker_turns = relationship(
        "SpeakerTurn",
        back_populates="audio_analysis",
        cascade="all, delete-orphan",
        order_by="SpeakerTurn.start_time"
    )
    speaker_embeddings = relationship(
        "SpeakerEmbedding",
        back_populates="audio_analysis",
        cascade="all, delete-orphan"
    )


class SpeechInterval(Base):
    __tablename__ = "speech_intervals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("audio_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False, index=True)
    duration = Column(Float, nullable=False)
    speech_probability = Column(Float, default=1.0)
    confidence = Column(Float, default=1.0)
    source = Column(String(50), default="silero_vad")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    audio_analysis = relationship("AudioAnalysis", back_populates="speech_intervals")


class SpeakerEmbedding(Base):
    __tablename__ = "speaker_embeddings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("audio_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_id = Column(String(36), ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True, index=True)
    segment_start_time = Column(Float, nullable=False, index=True)
    segment_end_time = Column(Float, nullable=False, index=True)
    embedding_dimension = Column(Integer, default=512)
    embedding_storage_reference = Column(String(255), nullable=True)
    embedding_data = Column(JSON, nullable=True)  # List of floats or vector serialization
    quality_score = Column(Float, default=1.0)
    model_version = Column(String(50), default="1.0.0")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    audio_analysis = relationship("AudioAnalysis", back_populates="speaker_embeddings")
    speaker = relationship("Speaker", back_populates="embeddings")


class SpeakerTurn(Base):
    __tablename__ = "speaker_turns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("audio_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_id = Column(String(36), ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True, index=True)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False, index=True)
    duration = Column(Float, nullable=False)
    confidence = Column(Float, default=1.0)
    assignment_status = Column(String(20), default="auto")  # auto, manual, provisional
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    audio_analysis = relationship("AudioAnalysis", back_populates="speaker_turns")
    speaker = relationship("Speaker", back_populates="speaker_turns")


class ActiveSpeakerInterval(Base):
    """
    Concept A: Interval where a visible face or off-screen entity was vocalizing.
    """
    __tablename__ = "active_speaker_intervals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    face_track_id = Column(String(36), ForeignKey("face_tracks.id", ondelete="SET NULL"), nullable=True, index=True)
    speaker_id = Column(String(36), ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True, index=True)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False, index=True)
    duration = Column(Float, nullable=False)
    confidence = Column(Float, default=1.0)
    speaking_score = Column(Float, default=1.0)
    state = Column(String(50), default="active_speaker") # active_speaker, silent_listener, off_screen_speaker, ambiguous
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="active_speaker_intervals")
    face_track = relationship("FaceTrack")
    speaker = relationship("Speaker")


class SpeakerFaceAssociation(Base):
    """
    Concept B: Global identity association between an acoustic speaker and a face track.
    """
    __tablename__ = "speaker_face_associations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_id = Column(String(36), ForeignKey("speakers.id", ondelete="CASCADE"), nullable=False, index=True)
    face_track_id = Column(String(36), ForeignKey("face_tracks.id", ondelete="SET NULL"), nullable=True, index=True)
    confidence = Column(Float, default=1.0)
    overlap_duration = Column(Float, default=0.0)
    is_manual = Column(Boolean, default=False)
    is_off_screen = Column(Boolean, default=False)
    evidence_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="speaker_face_associations")
    speaker = relationship("Speaker")
    face_track = relationship("FaceTrack")


class FacialLandmarkAnalysis(Base):
    """Metadata record for a facial landmark detection run on a video."""
    __tablename__ = "facial_landmark_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    model_name = Column(String(100), default="mediapipe_facemesh_v2")
    model_version = Column(String(50), default="1.0.0")
    status = Column(String(50), default="completed", index=True)
    frames_analyzed = Column(Integer, default=0)
    processing_duration_seconds = Column(Float, default=0.0)
    device_used = Column(String(50), default="cpu")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    video = relationship("Video", back_populates="landmark_analyses")


class LipDynamicsObservation(Base):
    """Timestamped lip motion and MAR measurement for a face track."""
    __tablename__ = "lip_dynamics_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    face_track_id = Column(String(36), ForeignKey("face_tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp_seconds = Column(Float, nullable=False, index=True)
    aperture = Column(Float, nullable=False)
    mouth_width = Column(Float, nullable=False)
    mar_raw = Column(Float, nullable=False)
    mar_smooth = Column(Float, nullable=False)
    mar_velocity = Column(Float, default=0.0)
    mar_variance = Column(Float, default=0.0)
    quality_confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# --- Phase 9 Composition Models ---

class Composition(Base):
    """
    Top-level composition entity representing an editable video composition.
    """
    __tablename__ = "compositions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("highlight_candidates.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="Untitled Composition")
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft", index=True)  # draft, ready, rendering, exported, archived
    current_version_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="compositions")
    source_video = relationship("Video", back_populates="compositions")
    candidate = relationship("HighlightCandidate")
    versions = relationship(
        "CompositionVersion",
        back_populates="composition",
        cascade="all, delete-orphan",
        order_by="CompositionVersion.version_number.desc()"
    )
    renders = relationship(
        "CompositionRender",
        back_populates="composition",
        cascade="all, delete-orphan",
        order_by="CompositionRender.created_at.desc()"
    )


class CompositionVersion(Base):
    """
    Immutable snapshot of a composition specification at a point in time.
    """
    __tablename__ = "composition_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    composition_id = Column(String(36), ForeignKey("compositions.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, index=True)
    schema_version = Column(String(50), default="1.0.0", nullable=False)
    spec_json = Column(JSON, nullable=False)
    content_hash = Column(String(64), nullable=False)
    change_summary = Column(String(255), nullable=True)
    is_draft = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("composition_id", "version_number", name="uq_comp_version"),
    )

    # Relationships
    composition = relationship("Composition", back_populates="versions")
    renders = relationship(
        "CompositionRender",
        back_populates="version",
        cascade="all, delete-orphan"
    )


class CompositionAsset(Base):
    """
    Project-scoped media asset (B-roll, background music, logo, sound effect).
    """
    __tablename__ = "composition_assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type = Column(String(50), nullable=False, index=True)  # videos, audio, images, broll, overlays, subtitles, fonts
    logical_asset_id = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    media_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "asset_type", "logical_asset_id", name="uq_project_asset"),
    )

    # Relationships
    project = relationship("Project", back_populates="composition_assets")


class CompositionRender(Base):
    """
    Tracks an export render execution job and resulting output artifact.
    """
    __tablename__ = "composition_renders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    composition_id = Column(String(36), ForeignKey("compositions.id", ondelete="CASCADE"), nullable=False, index=True)
    composition_version_id = Column(String(36), ForeignKey("composition_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    output_path = Column(Text, nullable=False)
    status = Column(String(50), default="queued", index=True)  # queued, rendering, completed, failed, cancelled
    progress_percent = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    render_duration_seconds = Column(Float, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    validation_metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    composition = relationship("Composition", back_populates="renders")
    version = relationship("CompositionVersion", back_populates="renders")
    job = relationship("Job")
    artifacts = relationship(
        "RenderArtifact",
        back_populates="render",
        cascade="all, delete-orphan"
    )


class RenderArtifact(Base):
    """
    Generated intermediate or sidecar artifact (ASS script, thumbnail, filter script).
    """
    __tablename__ = "render_artifacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    composition_render_id = Column(String(36), ForeignKey("composition_renders.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False, index=True)  # ass_script, ffscript, preview_thumb, log
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    render = relationship("CompositionRender", back_populates="artifacts")




