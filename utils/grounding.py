"""Grounding (lightweight RAG) for the Planner Agent.

Purpose: make the Planner's topic selection reflect real hiring practice
instead of pure LLM imagination, by retrieving a short block of reference
material -- a role-matched slice of a curated question bank, plus a note
on current interview trends -- and handing it to the Planner as optional
context it can draw on.

Design choices (see README "Grounding" section for the full rationale):
  * Default backend is a small curated local knowledge base
    (`knowledge/question_bank.json` + `knowledge/interview_trends.md`),
    retrieved via plain keyword matching. No embedding model, no vector
    DB, no extra paid API key required -- it always works out of the box.
  * An optional live web-search backend (Tavily) is used INSTEAD of the
    local bank when `TAVILY_API_KEY` is set, since live results are more
    current. Any failure (missing key, network, rate limit) silently
    falls back to the local bank -- grounding is a quality enhancement,
    never a hard dependency the interview flow can break on.
  * Grounding can be disabled entirely via `ENABLE_GROUNDING=false`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

_MAX_WEB_RESULTS = 3
_MAX_WEB_CHARS_PER_RESULT = 350


@dataclass
class GroundingContext:
    """Result of a grounding lookup, ready to inject into the Planner's prompt."""

    prompt_block: str  # "" if grounding is disabled or nothing was found
    source: str  # "web_search", "local_question_bank", or "none"


@lru_cache(maxsize=1)
def _load_question_bank() -> list[dict]:
    path = _KNOWLEDGE_DIR / "question_bank.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("roles", [])


@lru_cache(maxsize=1)
def _load_trends() -> str:
    path = _KNOWLEDGE_DIR / "interview_trends.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _best_matching_role(role_text: str) -> dict | None:
    """Keyword match: pick the KB entry whose longest matching keyword phrase wins.

    Falls back to the "general_behavioral" entry (keywords=[]) if nothing matches,
    so there's always at least generic-but-real reference material.
    """
    normalized = _normalize(role_text)
    best_entry, best_score = None, 0

    for entry in _load_question_bank():
        if entry["id"] == "general_behavioral":
            continue
        for phrase in entry.get("keywords", []):
            if _normalize(phrase) in normalized and len(phrase) > best_score:
                best_entry, best_score = entry, len(phrase)

    if best_entry is not None:
        return best_entry

    return next((e for e in _load_question_bank() if e["id"] == "general_behavioral"), None)


def _trend_excerpt(max_bullets: int = 4) -> str:
    lines = [l for l in _load_trends().splitlines() if l.strip().startswith("- ")]
    return "\n".join(lines[:max_bullets])


def _local_grounding_block(role_text: str) -> str:
    entry = _best_matching_role(role_text)
    if entry is None:
        return ""

    topics = entry.get("core_topics", [])[:5]
    questions = entry.get("sample_question_themes", [])[:4]
    trends = _trend_excerpt()

    parts = ["REFERENCE MATERIAL (curated question bank -- use as inspiration, not a script):"]
    if topics:
        parts.append("Commonly-tested topics for this role:\n" + "\n".join(f"- {t}" for t in topics))
    if questions:
        parts.append("Representative real-world question themes:\n" + "\n".join(f"- {q}" for q in questions))
    if trends:
        parts.append("Current interview trends worth reflecting in strategy:\n" + trends)
    return "\n\n".join(parts)


def _web_search_grounding(role_text: str) -> str | None:
    """Best-effort live web search via Tavily. Returns None on any failure."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        query = f"{role_text} job interview questions what to expect"
        response = client.search(query, max_results=_MAX_WEB_RESULTS, search_depth="basic")
        results = response.get("results", [])
        if not results:
            return None

        snippets = [
            r.get("content", "")[:_MAX_WEB_CHARS_PER_RESULT]
            for r in results
            if r.get("content")
        ]
        if not snippets:
            return None

        trends = _trend_excerpt()
        parts = [
            "REFERENCE MATERIAL (live web search results -- use as inspiration, not a script):",
            "\n\n".join(f"- {s}" for s in snippets),
        ]
        if trends:
            parts.append("Current interview trends worth reflecting in strategy:\n" + trends)
        return "\n\n".join(parts)
    except Exception:  # noqa: BLE001 - grounding must never break the interview
        return None


def get_grounding_context(role_text: str) -> GroundingContext:
    """Main entry point used by the Planner Agent."""
    if os.getenv("ENABLE_GROUNDING", "true").strip().lower() in ("false", "0", "no"):
        return GroundingContext(prompt_block="", source="none")

    web_block = _web_search_grounding(role_text)
    if web_block:
        return GroundingContext(prompt_block=web_block, source="web_search")

    local_block = _local_grounding_block(role_text)
    if local_block:
        return GroundingContext(prompt_block=local_block, source="local_question_bank")

    return GroundingContext(prompt_block="", source="none")
