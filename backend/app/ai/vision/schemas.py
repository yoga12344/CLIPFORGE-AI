"""
ClipForge AI - Computer Vision & Face Tracking Schemas
Pydantic definitions for face detection, tracking, scene analysis, and reframing.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NormalizedBBox(BaseModel):
    """
    Normalized bounding box where coordinates and dimensions are in range [0.0, 1.0]
    relative to the source frame width and height.
    """
    x: float = Field(..., ge=0.0, le=1.0, description="Top-left x position (normalized)")
    y: float = Field(..., ge=0.0, le=1.0, description="Top-left y position (normalized)")
    width: float = Field(..., ge=0.0, le=1.0, description="Box width (normalized)")
    height: float = Field(..., ge=0.0, le=1.0, description="Box height (normalized)")

    @property
    def center_x(self) -> float:
        return self.x + (self.width / 2.0)

    @property
    def center_y(self) -> float:
        return self.y + (self.height / 2.0)

    @property
    def area(self) -> float:
        return self.width * self.height


class FacialLandmarks(BaseModel):
    """Normalized coordinates for 5 key facial points (YuNet output)."""
    right_eye: Optional[List[float]] = None   # [x, y]
    left_eye: Optional[List[float]] = None    # [x, y]
    nose_tip: Optional[List[float]] = None    # [x, y]
    right_mouth: Optional[List[float]] = None # [x, y]
    left_mouth: Optional[List[float]] = None  # [x, y]


class FaceDetection(BaseModel):
    """A single face detected in a video frame."""
    bbox: NormalizedBBox
    confidence: float = Field(..., ge=0.0, le=1.0)
    frame_index: int
    timestamp_seconds: float
    landmarks: Optional[FacialLandmarks] = None
    track_id: Optional[str] = None


class TrackSample(BaseModel):
    """A temporal sample in a face trajectory."""
    timestamp_seconds: float
    frame_index: int
    bbox: NormalizedBBox
    confidence: float


class TrackedFace(BaseModel):
    """A continuous subject track associated across multiple video frames."""
    track_id: str
    start_time: float
    end_time: float
    detection_count: int
    average_confidence: float
    average_bbox: NormalizedBBox
    samples: List[TrackSample] = Field(default_factory=list)


class SceneComposition(BaseModel):
    """Scene classification and density metrics."""
    total_frames_sampled: int
    frames_with_faces: int
    max_simultaneous_faces: int
    average_face_count: float
    primary_track_id: Optional[str] = None
    has_multiple_subjects: bool = False
    has_no_faces: bool = False
    scene_type: str = "single_subject" # single_subject, multi_person, crowd, b_roll


class CropCoordinate(BaseModel):
    """Computed crop rectangle for a specific timestamp."""
    timestamp_seconds: float
    # Normalized crop (0.0 to 1.0)
    crop_x: float
    crop_y: float
    crop_width: float
    crop_height: float
    # Absolute pixel values for FFmpeg
    pixel_x: int = 0
    pixel_y: int = 0
    pixel_width: int = 0
    pixel_height: int = 0
    # Metadata
    selected_track_id: Optional[str] = None
    confidence: float = 1.0
    reframing_mode: str = "auto_tracking" # auto_tracking, manual_track, group, center_fallback, blur_fallback


class ReframeConfig(BaseModel):
    """Parameters for smart crop trajectory generation."""
    aspect_ratio: str = "9:16"             # 9:16, 1:1, 4:5, 16:9
    strategy: str = "largest_face"          # largest_face, center_face, manual_track, group
    selected_track_id: Optional[str] = None
    smoothing_strength: float = 0.85        # EMA alpha (higher = smoother, 0.1 to 0.95)
    crop_padding: float = 0.15              # Extra side margin
    headroom: float = 0.20                  # Space above forehead/eyes
    max_crop_velocity_per_sec: float = 0.50 # Max normalized position shift per second
    face_confidence_threshold: float = 0.55
    sampling_fps: float = 4.0               # Detection sampling rate


class ManualCropInput(BaseModel):
    """User keyframe crop adjustment."""
    timestamp_seconds: float
    crop_x: float = Field(..., ge=0.0, le=1.0)
    crop_y: float = Field(..., ge=0.0, le=1.0)
    crop_width: float = Field(..., ge=0.0, le=1.0)
    crop_height: float = Field(..., ge=0.0, le=1.0)


class DenseFaceLandmarks(BaseModel):
    """
    Detailed 3D facial landmarks from MediaPipe FaceMesh V2 (478 keypoints).
    Coordinates are normalized to [0.0, 1.0] relative to original video frame dimensions.
    """
    points: List[List[float]] = Field(default_factory=list, description="478 [x, y, z] points")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Face presence confidence")
    is_valid: bool = True
    # Key semantic indices
    upper_lip_inner: Optional[List[float]] = None  # Index 13
    lower_lip_inner: Optional[List[float]] = None  # Index 14
    mouth_left_corner: Optional[List[float]] = None # Index 61
    mouth_right_corner: Optional[List[float]] = None # Index 291
    upper_lip_outer: Optional[List[float]] = None  # Index 0
    lower_lip_outer: Optional[List[float]] = None  # Index 17


class LipDynamicsMeasurement(BaseModel):
    """
    Biomechanical lip motion and Mouth Aspect Ratio (MAR) metrics for a single observation.
    """
    timestamp_seconds: float
    face_track_id: str
    aperture: float = Field(..., ge=0.0, description="Inner-lip vertical distance ||p13 - p14||")
    mouth_width: float = Field(..., ge=0.0, description="Mouth horizontal corner distance ||p61 - p291||")
    mar_raw: float = Field(..., ge=0.0, description="Raw Mouth Aspect Ratio aperture / width")
    mar_smooth: float = Field(..., ge=0.0, description="Temporally smoothed Mouth Aspect Ratio")
    mar_velocity: float = Field(0.0, ge=0.0, description="Temporal rate of change dMAR/dt")
    mar_variance: float = Field(0.0, ge=0.0, description="Short-window MAR variance")
    quality_confidence: float = Field(1.0, ge=0.0, le=1.0, description="Landmark tracking confidence")
    is_valid: bool = True

