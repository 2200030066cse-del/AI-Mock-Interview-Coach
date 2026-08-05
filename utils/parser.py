"""Helpers for robustly extracting JSON from LLM completions.

LLMs routinely wrap JSON in markdown fences, prepend commentary ("Sure,
here's the evaluation:"), or emit trailing text. `extract_json` copes with
all of these instead of assuming a clean `json.loads` will work.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json(raw_text: str) -> dict[str, Any]:
    """Extract and parse a single JSON object from arbitrary LLM output.

    Strategy, in order:
      1. Try parsing the whole string as-is.
      2. Look for a ```json ... ``` (or bare ```) fenced block.
      3. Fall back to slicing from the first `{` to the last `}`.

    Raises `ValueError` if none of these yield valid JSON.
    """
    text = raw_text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not parse JSON from LLM output: {exc}") from exc

    raise ValueError("No JSON object found in LLM output.")


def truncate_for_prompt(text: str, max_chars: int = 4000) -> str:
    """Guard against runaway-length candidate answers blowing up prompt cost.

    Long answers (a pasted essay, an accidental paste of a whole codebase)
    are truncated with a marker rather than silently sent in full.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated for length]"
