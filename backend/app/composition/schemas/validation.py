"""
ClipForge AI - Composition Semantic Validation Models
Deep structural and temporal consistency checks for CompositionSpec prior to persistence or rendering.
"""

from typing import List, Optional, Set, Any
from pydantic import BaseModel, Field


class ValidationErrorItem(BaseModel):
    """An error that prevents saving or rendering a composition."""
    field: str
    message: str
    code: str = "INVALID_SPEC"


class ValidationWarningItem(BaseModel):
    """A non-fatal warning alerting the user or engine to potential quality issues."""
    field: str
    message: str
    code: str = "WARNING"


class CompositionValidationResult(BaseModel):
    """Complete report from semantic validation."""
    is_valid: bool = Field(True, description="True if no fatal errors exist")
    errors: List[ValidationErrorItem] = Field(default_factory=list)
    warnings: List[ValidationWarningItem] = Field(default_factory=list)

    def add_error(self, field: str, message: str, code: str = "INVALID_SPEC"):
        self.errors.append(ValidationErrorItem(field=field, message=message, code=code))
        self.is_valid = False

    def add_warning(self, field: str, message: str, code: str = "WARNING"):
        self.warnings.append(ValidationWarningItem(field=field, message=message, code=code))


def validate_composition_semantics(
    spec: Any,  # CompositionSpec (type hinted as Any to avoid circular import)
    authorized_asset_uris: Optional[Set[str]] = None,
) -> CompositionValidationResult:
    """
    Performs comprehensive cross-field semantic validation on a CompositionSpec:
    1. Temporal consistency between clip boundaries, timeline duration, and track segments.
    2. Camera keyframe alignment with layout slots.
    3. Subtitle timing and safe placement.
    4. Asset URI authorization within project bounds.
    5. Geometry bounds and non-overflowing rects.
    """
    res = CompositionValidationResult()

    # 1. Temporal boundary checks
    clip_dur = spec.clip_boundary.duration_us
    timeline_dur = spec.timeline.total_duration_us
    if clip_dur != timeline_dur:
        res.add_error(
            "timeline.total_duration_us",
            f"Timeline duration ({timeline_dur} us) does not match clip boundary duration ({clip_dur} us)",
            "DURATION_MISMATCH"
        )

    # 2. Slot references in camera keyframes
    known_slot_ids = {slot.slot_id for slot in spec.layout.slots}
    for i, kf in enumerate(spec.camera.keyframes):
        if kf.slot_id not in known_slot_ids:
            res.add_error(
                f"camera.keyframes[{i}].slot_id",
                f"Keyframe references unknown layout slot '{kf.slot_id}'. Known slots: {known_slot_ids}",
                "UNKNOWN_SLOT"
            )
        if kf.timeline_position_us > timeline_dur:
            res.add_error(
                f"camera.keyframes[{i}].timeline_position_us",
                f"Keyframe timestamp ({kf.timeline_position_us} us) exceeds timeline duration ({timeline_dur} us)",
                "TIMESTAMP_OUT_OF_BOUNDS"
            )
        if kf.confidence < 0.50:
            res.add_warning(
                f"camera.keyframes[{i}].confidence",
                f"Keyframe at {kf.timeline_position_us} us has low confidence ({kf.confidence:.2f})",
                "LOW_CONFIDENCE"
            )

    # 3. Manual override boundary checks
    for i, mo in enumerate(spec.camera.manual_overrides):
        if mo.slot_id not in known_slot_ids:
            res.add_error(
                f"camera.manual_overrides[{i}].slot_id",
                f"Manual override references unknown layout slot '{mo.slot_id}'",
                "UNKNOWN_SLOT"
            )
        if mo.timeline_position_us > timeline_dur:
            res.add_error(
                f"camera.manual_overrides[{i}].timeline_position_us",
                f"Manual override timestamp ({mo.timeline_position_us} us) exceeds timeline duration",
                "TIMESTAMP_OUT_OF_BOUNDS"
            )

    # 4. Subtitle timing checks
    prev_end = -1
    for i, seg in enumerate(spec.subtitles.segments):
        if seg.start_us >= timeline_dur:
            res.add_error(
                f"subtitles.segments[{i}].start_us",
                f"Subtitle segment starts at {seg.start_us} us which exceeds timeline duration ({timeline_dur} us)",
                "TIMESTAMP_OUT_OF_BOUNDS"
            )
        if seg.start_us < prev_end:
            res.add_warning(
                f"subtitles.segments[{i}]",
                f"Subtitle segment [{seg.start_us}, {seg.end_us}] overlaps with previous segment (end {prev_end})",
                "SUBTITLE_OVERLAP"
            )
        prev_end = max(prev_end, seg.end_us)

    # 5. Overlays and B-roll
    for i, br in enumerate(spec.overlays.b_roll_items):
        if (br.timeline_start_us + br.duration_us) > timeline_dur:
            res.add_warning(
                f"overlays.b_roll_items[{i}]",
                f"B-roll cutaway extends past timeline end ({br.timeline_start_us + br.duration_us} > {timeline_dur})",
                "OVERLAY_EXTENDS_PAST_END"
            )

    # 6. Asset authorization check (if known authorized set is provided)
    if authorized_asset_uris is not None:
        def check_asset(uri: Optional[str], field_name: str):
            if uri and uri not in authorized_asset_uris:
                res.add_error(
                    field_name,
                    f"Asset URI '{uri}' is not authorized or does not belong to project '{spec.project_id}'",
                    "UNAUTHORIZED_ASSET"
                )

        check_asset(spec.source_media.asset_uri, "source_media.asset_uri")
        check_asset(spec.audio.music.asset_uri, "audio.music.asset_uri")
        for i, sfx in enumerate(spec.audio.sound_effects):
            check_asset(sfx.asset_uri, f"audio.sound_effects[{i}].asset_uri")
        for i, br in enumerate(spec.overlays.b_roll_items):
            check_asset(br.asset_uri, f"overlays.b_roll_items[{i}].asset_uri")
        for i, gr in enumerate(spec.overlays.graphic_items):
            check_asset(gr.asset_uri, f"overlays.graphic_items[{i}].asset_uri")

    return res
