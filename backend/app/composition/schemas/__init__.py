"""
ClipForge AI - Composition Schemas Package
"""

from .timeline import (
    RationalTimebase,
    ClipBoundary,
    TimelineSceneBoundary,
    TimelineTransition,
    TimelineSpec,
    us_to_seconds,
    seconds_to_us,
    format_us_to_ffmpeg,
    source_to_composition_us,
    composition_to_source_us,
    composition_to_output_us,
    output_to_composition_us,
)
from .assets import (
    VALID_ASSET_TYPES,
    ParsedAssetUri,
    parse_and_validate_asset_uri,
    validate_asset_uri_string,
    CompositionAssetSpec,
)
from .layout import (
    NormalizedRect,
    SafeAreaConfig,
    BackgroundTreatment,
    LayoutSlot,
    LayoutConfig,
)
from .camera import (
    SubjectReference,
    CameraKeyframe,
    ManualOverride,
    CameraPlan,
)
from .tracks import (
    TrackSegment,
    VideoTrack,
    AudioTrack,
    SubtitleTrackSpec,
    BrollTrackSpec,
    OverlayTrackSpec,
    CompositionTrack,
)
from .subtitles import (
    SubtitleWordRef,
    SubtitleSegmentRef,
    SubtitleStyleOverrides,
    SubtitleCollisionConfig,
    SubtitleCompositionConfig,
)
from .overlays import (
    BRollItemSpec,
    GraphicOverlaySpec,
    OverlayCompositionConfig,
)
from .audio import (
    VoiceDialogueConfig,
    BackgroundMusicConfig,
    AudioDuckingConfig,
    SoundEffectItem,
    LoudnessMasteringConfig,
    AudioCompositionConfig,
)
from .delivery import (
    DeliveryProfile,
    STANDARD_DELIVERY_PROFILES,
    get_default_delivery_profile,
)
from .validation import (
    ValidationErrorItem,
    ValidationWarningItem,
    CompositionValidationResult,
    validate_composition_semantics,
)
from .composition import (
    SourceMediaMetadata,
    CompositionSpec,
)

__all__ = [
    "RationalTimebase",
    "ClipBoundary",
    "TimelineSceneBoundary",
    "TimelineTransition",
    "TimelineSpec",
    "us_to_seconds",
    "seconds_to_us",
    "format_us_to_ffmpeg",
    "source_to_composition_us",
    "composition_to_source_us",
    "composition_to_output_us",
    "output_to_composition_us",
    "VALID_ASSET_TYPES",
    "ParsedAssetUri",
    "parse_and_validate_asset_uri",
    "validate_asset_uri_string",
    "CompositionAssetSpec",
    "NormalizedRect",
    "SafeAreaConfig",
    "BackgroundTreatment",
    "LayoutSlot",
    "LayoutConfig",
    "SubjectReference",
    "CameraKeyframe",
    "ManualOverride",
    "CameraPlan",
    "TrackSegment",
    "VideoTrack",
    "AudioTrack",
    "SubtitleTrackSpec",
    "BrollTrackSpec",
    "OverlayTrackSpec",
    "CompositionTrack",
    "SubtitleWordRef",
    "SubtitleSegmentRef",
    "SubtitleStyleOverrides",
    "SubtitleCollisionConfig",
    "SubtitleCompositionConfig",
    "BRollItemSpec",
    "GraphicOverlaySpec",
    "OverlayCompositionConfig",
    "VoiceDialogueConfig",
    "BackgroundMusicConfig",
    "AudioDuckingConfig",
    "SoundEffectItem",
    "LoudnessMasteringConfig",
    "AudioCompositionConfig",
    "DeliveryProfile",
    "STANDARD_DELIVERY_PROFILES",
    "get_default_delivery_profile",
    "ValidationErrorItem",
    "ValidationWarningItem",
    "CompositionValidationResult",
    "validate_composition_semantics",
    "SourceMediaMetadata",
    "CompositionSpec",
]
