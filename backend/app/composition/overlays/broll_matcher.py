"""
ClipForge AI - Semantic B-Roll Matcher
Matches transcript tokens and highlight topics to available B-roll video assets.
"""

import re
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from app.composition.schemas.overlays import BRollItemSpec
from app.composition.schemas.subtitles import SubtitleSegmentRef


class BRollAsset(BaseModel):
    """Metadata representing an indexed B-roll video file."""
    asset_id: str
    asset_uri: str
    file_path: str
    duration_us: int
    tags: List[str] = Field(default_factory=list)
    description: str = ""


class BRollMatcher:
    """
    Scans subtitle segments and dialogue keywords to automatically propose
    intelligent B-roll cutaway insertion points.
    """

    STOPWORDS: Set[str] = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did", "i", "you",
        "he", "she", "it", "we", "they", "this", "that", "these", "those", "my", "your",
        "his", "her", "its", "our", "their", "so", "just", "like", "well", "know", "think"
    }

    @classmethod
    def extract_keywords(cls, text: str) -> List[str]:
        """Extract clean alphanumeric keywords ignoring common stopwords."""
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        return [w for w in words if w not in cls.STOPWORDS]

    @classmethod
    def match_transcript_to_broll(
        cls,
        segments: List[SubtitleSegmentRef],
        available_assets: List[BRollAsset],
        min_broll_duration_us: int = 2_000_000,   # 2.0s
        max_broll_duration_us: int = 4_000_000,   # 4.0s
        min_gap_between_brolls_us: int = 4_000_000 # 4.0s gap
    ) -> List[BRollItemSpec]:
        """
        Analyzes subtitle segments and generates non-overlapping B-roll insertion specs.
        """
        if not segments or not available_assets:
            return []

        # Build tag index: tag -> list of assets
        tag_index: Dict[str, List[BRollAsset]] = {}
        for asset in available_assets:
            for tag in asset.tags:
                norm_tag = tag.lower().strip()
                if norm_tag not in tag_index:
                    tag_index[norm_tag] = []
                    tag_index[norm_tag].append(asset)
            # Also index words from description
            desc_words = cls.extract_keywords(asset.description)
            for dw in desc_words:
                if dw not in tag_index:
                    tag_index[dw] = []
                if asset not in tag_index[dw]:
                    tag_index[dw].append(asset)

        planned_items: List[BRollItemSpec] = []
        last_broll_end_us = -min_gap_between_brolls_us
        used_asset_ids: Set[str] = set()

        for seg in segments:
            seg_keywords = cls.extract_keywords(seg.text)
            matched_asset: Optional[BRollAsset] = None

            # Find matching asset with highest tag overlap
            for kw in seg_keywords:
                if kw in tag_index:
                    candidates = [a for a in tag_index[kw] if a.asset_id not in used_asset_ids]
                    if candidates:
                        matched_asset = candidates[0]
                        break

            if matched_asset:
                start_us = seg.start_us
                # Ensure minimum gap from previous B-roll
                if start_us < (last_broll_end_us + min_gap_between_brolls_us):
                    continue

                duration_us = min(
                    max_broll_duration_us,
                    max(min_broll_duration_us, seg.end_us - seg.start_us),
                    matched_asset.duration_us
                )

                item = BRollItemSpec(
                    item_id=f"broll_{matched_asset.asset_id}_{start_us}",
                    asset_uri=matched_asset.asset_uri,
                    timeline_start_us=start_us,
                    duration_us=duration_us,
                    source_offset_us=0,
                    display_mode="full_frame_cutaway",
                    opacity=1.0,
                    mute_audio=True,
                    transition_in="fade",
                    transition_out="fade",
                )
                planned_items.append(item)
                used_asset_ids.add(matched_asset.asset_id)
                last_broll_end_us = start_us + duration_us

        return planned_items
