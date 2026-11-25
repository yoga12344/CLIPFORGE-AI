"""
ClipForge AI - AI Highlight Discovery Subsystem
"""

from .transcript_chunker import (
    TimedWord,
    TimedSentence,
    TranscriptChunk,
    TranscriptChunker
)
from .candidate_generator import CandidateGenerator, DiscoveredCandidate
from .boundary_refiner import BoundaryRefiner
from .highlight_validator import HighlightValidator
from .candidate_scorer import CandidateScorer, ScoreBreakdown
from .duplicate_detector import DuplicateDetector
from .highlight_analyzer import (
    HighlightAnalyzer,
    HighlightAnalysisConfig,
    EnrichedHighlightCandidate
)

__all__ = [
    "TimedWord",
    "TimedSentence",
    "TranscriptChunk",
    "TranscriptChunker",
    "CandidateGenerator",
    "DiscoveredCandidate",
    "BoundaryRefiner",
    "HighlightValidator",
    "CandidateScorer",
    "ScoreBreakdown",
    "DuplicateDetector",
    "HighlightAnalyzer",
    "HighlightAnalysisConfig",
    "EnrichedHighlightCandidate"
]
