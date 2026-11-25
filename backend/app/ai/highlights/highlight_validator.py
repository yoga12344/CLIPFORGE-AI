"""
ClipForge AI - Highlight Candidate Validator
Verifies timestamp boundaries, duration constraints, and ensures quotes exist verbatim in the transcript.
"""

import logging
import re
from typing import Any, List, Optional, Tuple

logger = logging.getLogger("clipforge.ai.highlights.validator")


class HighlightValidator:
    """Validates highlight candidates against transcript ground truth."""

    @classmethod
    def verify_quote_in_transcript(
        cls,
        quote: Optional[str],
        segments: List[Any]
    ) -> bool:
        """Verify that key_quote appears in the overall transcript segments."""
        if not quote or not quote.strip():
            return True
        full_text = " ".join(s.text for s in segments)
        valid, _, _ = cls.verify_quote(quote, full_text)
        return valid

    @classmethod
    def verify_quote(
        cls,
        quote: Optional[str],
        transcript_excerpt: str
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Verify that key_quote actually appears in the transcript excerpt.
        Returns: (is_valid, match_score, verified_quote)
        """
        if not quote or not quote.strip():
            # If quote is empty, consider valid but with zero bonus
            return True, 0.0, None

        clean_quote = re.sub(r"[^\w\s]", "", quote.lower()).strip()
        clean_excerpt = re.sub(r"[^\w\s]", "", transcript_excerpt.lower()).strip()

        if not clean_quote:
            return True, 0.0, None

        # Check exact substring
        if clean_quote in clean_excerpt:
            return True, 1.0, quote.strip()

        # Word-level overlap check (for slight punctuation/casing variations)
        quote_words = clean_quote.split()
        excerpt_words = clean_excerpt.split()

        if not quote_words:
            return True, 0.0, None

        # Check n-gram match
        quote_len = len(quote_words)
        max_overlap = 0
        for i in range(len(excerpt_words) - quote_len + 1):
            window = excerpt_words[i : i + quote_len]
            matches = sum(1 for q, w in zip(quote_words, window) if q == w)
            if matches > max_overlap:
                max_overlap = matches

        overlap_ratio = max_overlap / max(1, quote_len)
        if overlap_ratio >= 0.7:  # At least 70% match
            return True, overlap_ratio, quote.strip()

        logger.warning(f"Key quote '{quote[:40]}...' not found in candidate excerpt (overlap={overlap_ratio:.2f})")
        return False, overlap_ratio, None

    @classmethod
    def validate_candidate(
        cls,
        start_time: float,
        end_time: float,
        total_video_duration: float,
        min_duration: float = 15.0,
        max_duration: float = 90.0,
        quote: Optional[str] = None,
        transcript_excerpt: str = "",
        strict_quote: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validate all physical constraints of a candidate.
        Returns (is_valid, list_of_errors).
        """
        errors = []

        if start_time < 0:
            errors.append(f"Start time ({start_time}s) cannot be negative.")

        if end_time <= start_time:
            errors.append(f"End time ({end_time}s) must be greater than start time ({start_time}s).")

        if total_video_duration > 0 and end_time > (total_video_duration + 1.0):
            errors.append(f"End time ({end_time}s) exceeds total video duration ({total_video_duration:.1f}s).")

        duration = end_time - start_time
        if duration < (min_duration * 0.7):
            errors.append(f"Duration ({duration:.1f}s) is below minimum allowable ({min_duration * 0.7:.1f}s).")

        if duration > (max_duration * 1.3):
            errors.append(f"Duration ({duration:.1f}s) exceeds maximum allowable ({max_duration * 1.3:.1f}s).")

        # Quote validation (strict mode only rejects physical candidate; non-strict informs scoring)
        if strict_quote and quote and transcript_excerpt:
            quote_valid, match_score, _ = cls.verify_quote(quote, transcript_excerpt)
            if not quote_valid:
                errors.append(f"Key quote hallucinated or not found in speech transcript (match score: {match_score:.2f}).")

        return len(errors) == 0, errors
