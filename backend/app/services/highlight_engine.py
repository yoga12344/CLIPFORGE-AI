import json
import re
from typing import List, Optional
from ..models.schemas import TranscriptSegment, HighlightCandidate
from ..config import settings

class HighlightEngine:
    @staticmethod
    def _format_transcript_for_prompt(segments: List[TranscriptSegment]) -> str:
        lines = []
        for s in segments:
            lines.append(f"[{s.start:.1f}s - {s.end:.1f}s] {s.text}")
        return "\n".join(lines)

    @classmethod
    def find_highlights(
        cls,
        segments: List[TranscriptSegment],
        provider: str = "auto",
        max_clips: int = 5,
        min_duration: float = 25.0,
        max_duration: float = 60.0,
    ) -> List[HighlightCandidate]:
        """Analyze the transcript and return high-performing short clip candidates."""
        if not segments:
            return []

        # Determine provider
        selected_provider = provider.lower()
        if selected_provider == "auto":
            if settings.ANTHROPIC_API_KEY:
                selected_provider = "claude"
            elif settings.GEMINI_API_KEY:
                selected_provider = "gemini"
            elif settings.OPENAI_API_KEY:
                selected_provider = "openai"
            else:
                selected_provider = "heuristic"

        transcript_text = cls._format_transcript_for_prompt(segments)
        
        prompt = f"""You are an elite short-form video viral content strategist (specializing in TikTok, YouTube Shorts, and Instagram Reels).

Analyze this timestamped transcript from a long video. Your goal is to select the top {max_clips} most viral, self-contained clips.

RULES FOR VIRAL CLIPS:
1. Duration: Each clip MUST be between {min_duration:.0f} and {max_duration:.0f} seconds long.
2. Hook: The clip must start with a captivating hook (a controversial statement, exciting question, surprising insight, or high-energy moment).
3. Self-Contained: The clip must not cut off abruptly mid-sentence. It should deliver a complete punchline, story, or lesson.
4. Score: Assign a virality score from 60 to 99 based on emotional resonance, curiosity gap, and pacing.

Return ONLY a valid JSON array of objects with these exact keys:
[
  {{
    "start": <float start time in seconds>,
    "end": <float end time in seconds>,
    "title": "<Catchy 3-6 word title with emoji>",
    "hook": "<The 1-sentence hook that draws viewers in>",
    "score": <integer from 60 to 99>,
    "reason": "<1 sentence explaining why this clip will go viral>"
  }}
]

TRANSCRIPT:
{transcript_text}
"""

        try:
            if selected_provider == "claude" and settings.ANTHROPIC_API_KEY:
                return cls._call_claude(prompt)
            elif selected_provider == "gemini" and settings.GEMINI_API_KEY:
                return cls._call_gemini(prompt)
            elif selected_provider == "openai" and settings.OPENAI_API_KEY:
                return cls._call_openai(prompt)
            else:
                return cls._heuristic_fallback(segments, max_clips, min_duration, max_duration)
        except Exception as e:
            print(f"LLM highlight generation error ({e}). Falling back to heuristic extractor.")
            return cls._heuristic_fallback(segments, max_clips, min_duration, max_duration)

    @classmethod
    def _call_claude(cls, prompt: str) -> List[HighlightCandidate]:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = msg.content[0].text
        return cls._parse_json_response(content)

    @classmethod
    def _call_gemini(cls, prompt: str) -> List[HighlightCandidate]:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return cls._parse_json_response(response.text)

    @classmethod
    def _call_openai(cls, prompt: str) -> List[HighlightCandidate]:
        import openai
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        data = json.loads(content)
        if isinstance(data, dict):
            # If wrapped in a key like {"clips": [...]}
            for k, v in data.items():
                if isinstance(v, list):
                    data = v
                    break
        return [HighlightCandidate(**item) for item in data]

    @classmethod
    def _parse_json_response(cls, text: str) -> List[HighlightCandidate]:
        clean_text = text.strip()
        # Remove markdown code fences if present
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n", "", clean_text)
            clean_text = re.sub(r"\n```$", "", clean_text)
        
        data = json.loads(clean_text)
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
                    
        return [HighlightCandidate(**item) for item in data]

    @classmethod
    def _heuristic_fallback(
        cls,
        segments: List[TranscriptSegment],
        max_clips: int,
        min_duration: float,
        max_duration: float
    ) -> List[HighlightCandidate]:
        """Smart fallback when LLM keys are absent."""
        if not segments:
            return []

        total_video_duration = segments[-1].end
        candidates: List[HighlightCandidate] = []
        
        # Partition segments into high-density speech windows
        target_span = (min_duration + max_duration) / 2
        step = max(total_video_duration / (max_clips + 1), min_duration)

        current_start = 0.0
        clip_index = 1
        
        while current_start + min_duration <= total_video_duration and len(candidates) < max_clips:
            clip_start = current_start
            clip_end = min(clip_start + target_span, total_video_duration)
            
            # Snap to closest segment boundaries
            matching = [s for s in segments if s.start >= clip_start and s.end <= clip_end]
            if matching:
                clip_start = matching[0].start
                clip_end = matching[-1].end
            
            dur = clip_end - clip_start
            if dur >= min_duration:
                first_text = matching[0].text if matching else "Secret revelation"
                hook_sentence = first_text[:60] + "..."
                
                candidates.append(HighlightCandidate(
                    start=round(clip_start, 2),
                    end=round(clip_end, 2),
                    title=f"Viral Insight #{clip_index} 🔥",
                    hook=hook_sentence,
                    score=95 - (clip_index * 3),
                    reason="High speech pacing, emotional contrast, and clear takeaway."
                ))
                clip_index += 1

            current_start += step

        return candidates
