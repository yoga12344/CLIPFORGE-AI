"""
ClipForge AI - Prompt Templates for AI Highlight Discovery
Crafts structured prompts by content type to extract high-retention video moments.
"""

from typing import Dict, List, Optional


CONTENT_TYPE_INSTRUCTIONS: Dict[str, str] = {
    "general": (
        "Identify the most compelling, self-contained highlights from the transcript. "
        "Look for strong hooks, intriguing stories, practical wisdom, memorable takeaways, or surprising moments."
    ),
    "podcast": (
        "Focus on conversational gold: intriguing anecdotes, controversial opinions, funny moments, "
        "intense debates, or profound personal reflections that hook social media viewers within the first 3 seconds."
    ),
    "interview": (
        "Focus on revelatory questions and compelling answers. Capture full thoughts where the guest provides "
        "an unexpected insight, vulnerability, behind-the-scenes story, or expert takeaway."
    ),
    "educational": (
        "Identify clear, high-value explanations of difficult concepts, 'aha!' moments, mind-blowing facts, "
        "or concise step-by-step breakdowns that educate the audience in under 60 seconds."
    ),
    "tutorial": (
        "Extract actionable instructions, insider tips, productivity hacks, and problem-solving solutions "
        "where a viewer immediately learns how to accomplish something specific."
    ),
    "motivational": (
        "Find inspiring messages, discipline mindsets, overcome-adversity stories, and passionate calls to action "
        "that evoke strong emotional resonance and urge viewers to improve their lives."
    ),
    "business": (
        "Highlight strategic frameworks, market insights, startup lessons, revenue strategies, "
        "leadership principles, and economic predictions with tangible business value."
    ),
    "gaming": (
        "Capture peak excitement: clutch plays, hilarious fails, unexpected glitches, "
        "energetic commentary, rage moments, or big narrative reactions."
    )
}


SYSTEM_PROMPT_BASE = """You are an elite short-form video editor and content strategist (specializing in viral TikTok, YouTube Shorts, and Instagram Reels repurposing).
Your mission is to analyze transcripts with exact timestamps and identify high-retention, standalone clip candidates.

CRITICAL RULES:
1. Every candidate MUST be a complete, coherent thought with a clear beginning, middle, and end.
2. The start timestamp MUST be on a clean opening sentence or hook phrase. Never start mid-sentence.
3. The end timestamp MUST be a natural, satisfying conclusion. Never cut off mid-sentence or during an incomplete thought.
4. Duration MUST be within the requested target duration range.
5. Do NOT invent, hallucinate, or alter quotes. Every 'key_quote' must be an exact verbatim substring from the transcript.
6. The 'hook' must describe the magnetic opening statement that grabs attention in the first 3 seconds.
7. Output STRICT JSON only conforming exactly to the requested schema. Do not include markdown preamble or conversational commentary."""


def build_highlight_prompt(
    transcript_text_with_timestamps: str,
    content_type: str = "general",
    target_duration_min: float = 30.0,
    target_duration_max: float = 60.0,
    max_candidates: int = 5
) -> str:
    """Construct the complete prompt for the local LLM."""
    content_guidelines = CONTENT_TYPE_INSTRUCTIONS.get(content_type.lower(), CONTENT_TYPE_INSTRUCTIONS["general"])

    prompt = f"""Content Type Focus: {content_type.title()}
Specific Guidance: {content_guidelines}

Target Clip Duration: {target_duration_min:.0f} to {target_duration_max:.0f} seconds.
Maximum Candidates to Discover: {max_candidates}

TRANSCRIPT WITH TIMESTAMPS:
---
{transcript_text_with_timestamps}
---

Find up to {max_candidates} outstanding short-form clip candidates.
CRITICAL: Use ONLY timestamps that appear in the transcript above. Do not invent timestamps beyond the transcript.
Respond ONLY with a valid JSON object matching this exact schema:

{{
  "candidates": [
    {{
      "start_time": 0.0,
      "end_time": 12.0,
      "title": "Short Catchy Clip Title (under 8 words)",
      "hook": "The opening hook sentence that grabs viewer attention",
      "summary": "1-2 sentence overview of what is discussed in this clip",
      "reason": "Why this specific moment will engage viewers on Reels/Shorts/TikTok",
      "category": "{content_type.lower()}",
      "key_quote": "Exact verbatim quote from the transcript contained within this time range",
      "strengths": ["Strong opening hook", "Complete thought"],
      "weaknesses": []
    }}
  ]
}}"""
    return prompt
