"""
ClipForge AI - Render Coordinator Validator
Phase 9 Stage 3: Orchestrates pre-flight composition checks and post-flight artifact verification.
"""

from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel, Field

from ...schemas.composition import CompositionSpec
from ...schemas.delivery import DeliveryProfile
from .output_validator import OutputValidator, OutputValidationResult
from .synchronization_validator import SynchronizationValidator, SynchronizationReport


class RenderValidator:
    """Pre-flight and post-flight validator for composition render operations."""

    @classmethod
    def pre_flight_check(cls, spec: CompositionSpec) -> List[str]:
        """Validate composition specification semantics before any file generation."""
        res = spec.validate_semantics()
        if not res.is_valid:
            return [e.message for e in res.errors]
        return []

    @classmethod
    def post_flight_check(
        cls,
        rendered_file_path: str,
        delivery: DeliveryProfile,
        expected_duration_seconds: Optional[float] = None
    ) -> OutputValidationResult:
        """Deeply inspect rendered binary file using FFprobe."""
        return OutputValidator.validate_file(
            file_path=rendered_file_path,
            expected_delivery=delivery,
            expected_duration_seconds=expected_duration_seconds
        )
