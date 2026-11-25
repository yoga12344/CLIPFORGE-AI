"""
ClipForge AI - Highlight Boundary Refiner
Deterministically aligns candidate start/end timestamps to sentence and word boundaries.
"""

import logging
import re
from typing import List, Optional, Tuple
from .transcript_chunker import TimedSentence, TimedWord

logger = logging.getLogger("clipforge.ai.highlights.refiner")


class BoundaryRefiner:
    """Refines rough candidate start and end times to natural sentence and word boundaries."""

    @classmethod
    def refine_boundaries(
        cls,
        raw_start: float,
        raw_end: float,
        sentences: List[TimedSentence],
        words: List[TimedWord],
        min_duration: float = 15.0,
        max_duration: float = 90.0,
        quote: Optional[str] = None
    ) -> Tuple[float, float, str, str]:
        """
        Snap raw timestamps to the best sentence and word boundaries.
        Returns: (refined_start, refined_end, opening_hook_phrase, full_transcript_excerpt)
        """
        if not sentences or not words:
            return raw_start, raw_end, "", ""

        # Step 1: Find best starting sentence
        # Look for sentence whose start_time is closest to raw_start
        best_start_sent_idx = 0
        min_start_diff = float("inf")

        for idx, sent in enumerate(sentences):
            diff = abs(sent.start_time - raw_start)
            # Prefer slightly earlier sentence if within 1.5s to include context
            if diff < min_start_diff:
                min_start_diff = diff
                best_start_sent_idx = idx

        # If a key quote is provided, align start sentence to encompass quote if close
        if quote and quote.strip():
            clean_q = re.sub(r"[^\w\s]", "", quote.lower()).strip()
            q_words = [w for w in clean_q.split() if len(w) > 3]
            if q_words:
                for idx, sent in enumerate(sentences):
                    clean_s = re.sub(r"[^\w\s]", "", sent.text.lower())
                    if clean_q in clean_s or sum(1 for w in q_words if w in clean_s) >= max(2, len(q_words) // 2):
                        if abs(idx - best_start_sent_idx) <= 2:
                            best_start_sent_idx = min(best_start_sent_idx, idx)
                            break

        # Step 2: Find best ending sentence
        best_end_sent_idx = best_start_sent_idx
        min_end_diff = float("inf")

        for idx in range(best_start_sent_idx, len(sentences)):
            sent = sentences[idx]
            diff = abs(sent.end_time - raw_end)
            if diff < min_end_diff:
                min_end_diff = diff
                best_end_sent_idx = idx

        # Step 3: Check resulting duration
        candidate_sentences = sentences[best_start_sent_idx : best_end_sent_idx + 1]
        start_time = candidate_sentences[0].start_time
        end_time = candidate_sentences[-1].end_time
        duration = end_time - start_time

        # If too short and more sentences available, extend forward
        while duration < min_duration and best_end_sent_idx + 1 < len(sentences):
            best_end_sent_idx += 1
            end_time = sentences[best_end_sent_idx].end_time
            duration = end_time - start_time

        # If too long and multiple sentences, shrink backward
        while duration > max_duration and best_end_sent_idx > best_start_sent_idx:
            best_end_sent_idx -= 1
            end_time = sentences[best_end_sent_idx].end_time
            duration = end_time - start_time

        # Step 4: Extract exact word boundaries
        refined_sentences = sentences[best_start_sent_idx : best_end_sent_idx + 1]
        first_word = refined_sentences[0].words[0] if refined_sentences[0].words else None
        last_word = refined_sentences[-1].words[-1] if refined_sentences[-1].words else None

        final_start = first_word.start if first_word else refined_sentences[0].start_time
        final_end = last_word.end if last_word else refined_sentences[-1].end_time

        # Step 5: Build excerpt and hook
        full_excerpt = " ".join(s.text for s in refined_sentences)
        hook_phrase = refined_sentences[0].text

        return (
            round(final_start, 2),
            round(final_end, 2),
            hook_phrase,
            full_excerpt
        )
