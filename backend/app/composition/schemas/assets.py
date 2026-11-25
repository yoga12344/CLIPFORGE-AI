"""
ClipForge AI - Composition Asset Addressing & Logical URI Models
Enforces project-scoped logical asset URIs, path traversal defense, and strict URI validation.
"""

import re
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


# Supported logical asset categories
VALID_ASSET_TYPES = {
    "videos",
    "audio",
    "images",
    "broll",
    "overlays",
    "subtitles",
    "fonts"
}

# Strict regex matching: asset://<type>/<identifier>
# Identifier must be an alphanumeric slug with underscores and hyphens (1 to 100 chars)
ASSET_URI_PATTERN = re.compile(
    r"^asset://(?P<type>videos|audio|images|broll|overlays|subtitles|fonts)/(?P<id>[a-zA-Z0-9_\-]{1,100})$"
)


class ParsedAssetUri(BaseModel):
    """Parsed and validated components of an asset URI."""
    scheme: Literal["asset"] = "asset"
    asset_type: str
    logical_id: str
    raw_uri: str

    def to_uri(self) -> str:
        return f"asset://{self.asset_type}/{self.logical_id}"


def parse_and_validate_asset_uri(uri: str) -> ParsedAssetUri:
    """
    Strictly validates and parses a logical asset URI.
    Rejects:
    - Path traversal sequences ('..', '%2e%2e', etc.)
    - Windows drive letters ('C:', 'D:')
    - Windows backslashes ('\')
    - External schemes ('file://', 'http://', 'https://')
    - Invalid or unauthorized asset categories
    """
    if not isinstance(uri, str):
        raise ValueError(f"Asset URI must be a string, got {type(uri).__name__}")

    stripped = uri.strip()
    if not stripped:
        raise ValueError("Asset URI cannot be empty")

    # Security: Explicit traversal and absolute path check
    if ".." in stripped or "\\" in stripped or ":" in stripped[6:]:
        raise ValueError(f"Security violation: path traversal or invalid characters in asset URI: '{uri}'")

    match = ASSET_URI_PATTERN.match(stripped)
    if not match:
        raise ValueError(
            f"Invalid asset URI format: '{uri}'. Must match 'asset://<type>/<id>' where type is one of "
            f"{sorted(list(VALID_ASSET_TYPES))} and id is an alphanumeric slug."
        )

    asset_type = match.group("type")
    logical_id = match.group("id")

    return ParsedAssetUri(
        scheme="asset",
        asset_type=asset_type,
        logical_id=logical_id,
        raw_uri=stripped,
    )


def validate_asset_uri_string(v: str) -> str:
    """Helper validator for Pydantic fields."""
    parsed = parse_and_validate_asset_uri(v)
    return parsed.raw_uri


class CompositionAssetSpec(BaseModel):
    """
    Representation of an asset registered within a composition's project namespace.
    """
    asset_uri: str = Field(..., description="Logical URI in asset://<type>/<id> format")
    project_id: str = Field(..., description="Project scoping boundary")
    name: str = Field(..., description="Human-readable asset display name")
    asset_type: str = Field(..., description="videos, audio, images, broll, overlays, subtitles, fonts")
    logical_id: str = Field(..., description="Unique slug within project and type")
    file_size_bytes: int = Field(0, ge=0)
    duration_us: Optional[int] = Field(None, ge=0, description="Media duration in microseconds if applicable")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("asset_uri")
    @classmethod
    def check_uri(cls, v: str) -> str:
        return validate_asset_uri_string(v)

    @field_validator("asset_type")
    @classmethod
    def check_asset_type(cls, v: str) -> str:
        if v not in VALID_ASSET_TYPES:
            raise ValueError(f"Unsupported asset type '{v}'. Must be one of {VALID_ASSET_TYPES}")
        return v
