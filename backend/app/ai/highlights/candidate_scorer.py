"""
ClipForge AI - Transparent Candidate Scoring Engine
Computes explainable 0-100 scores across 7 distinct content quality dimensions.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger("clipforge.ai.highlights.scorer")

# Hook curiosity and pattern words
HOOK_PATTERNS = [
    r"^(why|how|what if|the secret|never|always|the truth|most people|imagine|here is)",
    r"\?$",  # Opening with a question
    r"(mistake|shocking|critical|rule|formula|trick|hack|key|framework|strategy)",
    r"(nobody talks about|everyone thinks|stop doing|start doing)"
]

VALUE_PATTERNS = [
    r"(because|reason|result|example|research|study|proves|step 1|first|second)",
    r"(save|earn|double|improve|faster|easier|solution|problem|insight)",
    r"(actionable|practical|principle|concept|mindset|tactic)"
]

EMOTION_PATTERNS = [
    r"(amazing|incredible|terrible|crazy|fascinating|insane|powerful|painful|heartbreaking)",
    r"(struggled|failed|succeeded|transformed|breakthrough|regret|passion)"
]

DANGLING_PRONOUNS_START = [
    r"^(and |but |so |then |also |he said|she said|like I said|as mentioned|in other words)",
    r"^(they |this is why|that is why)"
]


class ScoreBreakdown(BaseModel):
    overall_score: int
    hook_strength: int = 0         # max 20
    content_value: int = 0         # max 20
    narrative_completeness: int = 0 # max 20
    standalone_context: int = 0    # max 15
    interest_level: int = 0        # max 10
    conciseness: int = 0           # max 10
    ending_quality: int = 0        # max 5
    penalties: List[str] = []
    strengths: List[str] = []


class CandidateScorer:
    """Calculates an explainable 0-100 highlight score based on verifiable textual metrics."""

    @classmethod
    def score_candidate(
        cls,
        text: str,
        hook_phrase: str,
        duration: float,
        target_min_duration: float = 30.0,
        target_max_duration: float = 60.0,
        silence_duration: float = 0.0,
        has_verified_quote: bool = True
    ) -> ScoreBreakdown:
        lower_text = text.lower().strip()
        lower_hook = hook_phrase.lower().strip()
        words = lower_text.split()
        word_count = len(words)

        hook_pts = 10
        value_pts = 10
        narrative_pts = 10
        context_pts = 8
        interest_pts = 5
        concise_pts = 5
        ending_pts = 2

        penalties: List[str] = []
        strengths: List[str] = []

        # 1. Hook strength (max 20)
        for pattern in HOOK_PATTERNS:
            if re.search(pattern, lower_hook):
                hook_pts += 3
        if "?" in lower_hook:
            hook_pts += 2
            strengths.append("Starts with a provocative question")
        if re.search(r"\b(you|your|we)\b", lower_hook):
            hook_pts += 2
            strengths.append("Direct viewer address in hook")
        hook_pts = min(20, max(0, hook_pts))

        # 2. Content value (max 20)
        value_matches = 0
        for pattern in VALUE_PATTERNS:
            if re.search(pattern, lower_text):
                value_matches += 1
        value_pts += min(10, value_matches * 2)
        if value_matches >= 3:
            strengths.append("High informational value and reasoning keywords")
        value_pts = min(20, max(0, value_pts))

        # 3. Narrative completeness (max 20)
        # Ends with terminal punctuation?
        if re.search(r"[.?!][\"']?$", text.strip()):
            narrative_pts += 6
            strengths.append("Clean sentence termination")
        else:
            narrative_pts -= 5
            penalties.append("Abrupt or mid-sentence ending")

        # Starts with clean capitalization?
        if text and text[0].isupper():
            narrative_pts += 4

        narrative_pts = min(20, max(0, narrative_pts))

        # 4. Standalone context (max 15)
        has_dangling = False
        for pat in DANGLING_PRONOUNS_START:
            if re.search(pat, lower_hook):
                has_dangling = True
                break

        if has_dangling:
            context_pts -= 5
            penalties.append("Opening references prior unstated context")
        else:
            context_pts += 5
            strengths.append("Self-contained opening statement")

        context_pts = min(15, max(0, context_pts))

        # 5. Emotional or intellectual interest (max 10)
        for pattern in EMOTION_PATTERNS:
            if re.search(pattern, lower_text):
                interest_pts += 2
        interest_pts = min(10, max(0, interest_pts))

        # 6. Conciseness (max 10)
        if duration > 0:
            words_per_sec = word_count / duration
            # Ideal speech rate is 2.2 to 3.8 words per second
            if 2.2 <= words_per_sec <= 3.8:
                concise_pts += 4
                strengths.append("Optimal speech delivery cadence")
            elif words_per_sec < 1.8:
                concise_pts -= 2
                penalties.append("Slow pacing or prolonged dead air")
            elif words_per_sec > 4.2:
                concise_pts -= 2
                penalties.append("Excessively rapid delivery")

        # Duration bounds penalty
        if duration < target_min_duration:
            penalties.append(f"Below target duration ({duration:.1f}s < {target_min_duration:.0f}s)")
            concise_pts -= 3
        elif duration > target_max_duration:
            penalties.append(f"Above target duration ({duration:.1f}s > {target_max_duration:.0f}s)")
            concise_pts -= 3

        concise_pts = min(10, max(0, concise_pts))

        # 7. Ending quality (max 5)
        last_sentence = text.split(".")[-2] if "." in text else text
        if any(w in last_sentence.lower() for w in ["so", "remember", "always", "finally", "that is", "in conclusion"]):
            ending_pts += 2
            strengths.append("Decisive takeaway ending")
        if re.search(r"[.?!]$", text.strip()):
            ending_pts += 1
        ending_pts = min(5, max(0, ending_pts))

        # Overall total
        total = (
            hook_pts
            + value_pts
            + narrative_pts
            + context_pts
            + interest_pts
            + concise_pts
            + ending_pts
        )

        # Unverified quote penalty
        if not has_verified_quote:
            total = max(0, total - 15)
            penalties.append("Key quote could not be verified in transcript")

        final_score = min(100, max(10, total))

        return ScoreBreakdown(
            overall_score=final_score,
            hook_strength=hook_pts,
            content_value=value_pts,
            narrative_completeness=narrative_pts,
            standalone_context=context_pts,
            interest_level=interest_pts,
            conciseness=concise_pts,
            ending_quality=ending_pts,
            penalties=penalties,
            strengths=strengths
        )
