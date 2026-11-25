"""
ClipForge AI - Overlays and B-Roll Module
"""

from .broll_matcher import BRollAsset, BRollMatcher
from .overlay_planner import OverlayPlanner, ResolvedOverlayPlacement

__all__ = [
    "BRollAsset",
    "BRollMatcher",
    "OverlayPlanner",
    "ResolvedOverlayPlacement",
]
