"""
ClipForge AI - Structured Output Parsing and Schema Validation
Extracts, repairs, and validates structured JSON candidates from LLM responses.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("clipforge.ai.llm.structured_output")


class RawCandidateItem(BaseModel):
    start_time: float
    end_time: float
    title: str = "Untitled Highlight"
    hook: Optional[str] = None
    summary: Optional[str] = None
    reason: Optional[str] = None
    category: str = "general"
    key_quote: Optional[str] = None
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)


class RawCandidatesResponse(BaseModel):
    candidates: List[RawCandidateItem] = Field(default_factory=list)


def clean_json_string(text: str) -> str:
    """Strip code fences and trailing prose."""
    cleaned = text.strip()

    # Remove markdown code blocks ```json ... ```
    if "```json" in cleaned:
        pattern = r"```json\s*(.*?)\s*```"
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            return match.group(1).strip()

    if "```" in cleaned:
        pattern = r"```\s*(.*?)\s*```"
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            return match.group(1).strip()

    # If no fences, find the outermost curly braces { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace : last_brace + 1]

    return cleaned


def repair_json_string(json_str: str) -> str:
    """Repair common small syntax mistakes produced by small LLMs."""
    # Remove trailing commas before closing braces/brackets
    repaired = re.sub(r",\s*([\]}])", r"\1", json_str)
    return repaired


def parse_and_validate_candidates(raw_llm_output: str) -> RawCandidatesResponse:
    """
    Parse LLM output into validated RawCandidatesResponse.
    Robust against markdown wrappers, chatter, and trailing commas.
    """
    cleaned = clean_json_string(raw_llm_output)
    repaired = repair_json_string(cleaned)

    try:
        data = json.loads(repaired)
    except json.JSONDecodeError as err:
        logger.warning(f"Initial JSON parse failed ({err}), attempting fallback repair...")
        # Sometimes small LLMs produce a bare list instead of {"candidates": [...]}
        first_bracket = repaired.find("[")
        last_bracket = repaired.rfind("]")
        if first_bracket != -1 and last_bracket != -1:
            try:
                list_data = json.loads(repaired[first_bracket : last_bracket + 1])
                if isinstance(list_data, list):
                    data = {"candidates": list_data}
                else:
                    raise ValueError("Extracted JSON is not a list")
            except Exception:
                raise ValueError(f"Failed to parse LLM structured output as JSON: {err}. Raw: {raw_llm_output[:200]}")
        else:
            raise ValueError(f"Failed to parse LLM structured output as JSON: {err}. Raw: {raw_llm_output[:200]}")

    if not isinstance(data, dict):
        raise ValueError("Parsed JSON is not an object/dictionary")

    # Adapt if key is slightly different (e.g. "clips" instead of "candidates")
    if "candidates" not in data:
        for alternate in ["clips", "highlights", "moments", "results"]:
            if alternate in data and isinstance(data[alternate], list):
                data["candidates"] = data[alternate]
                break

    return RawCandidatesResponse(**data)
