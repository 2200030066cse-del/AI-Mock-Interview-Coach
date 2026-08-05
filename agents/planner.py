"""Planner Agent: turns a candidate profile into a structured interview plan."""

from __future__ import annotations

from models.schemas import CandidateProfile, InterviewPlan
from utils.grounding import get_grounding_context
from utils.llm import call_llm_json, load_prompt

_SYSTEM_PROMPT = load_prompt("planner_prompt.txt")


def create_plan(candidate: CandidateProfile) -> InterviewPlan:
    """Run the Planner Agent once, at the start of the interview.

    Raises:
        ValueError: if the LLM cannot produce a schema-valid plan after retries.
    """
    resume = candidate.resume_snippet.strip() or "(No background provided.)"
    grounding = get_grounding_context(candidate.target_role)

    user_prompt = (
        f"Target Role: {candidate.target_role}\n"
        f"Background: {resume}\n"
        f"Focus: {candidate.focus_area.value}\n\n"
        f"{grounding.prompt_block}\n\n"
        "Produce the interview plan JSON now."
    )
    plan = call_llm_json(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=InterviewPlan,
        temperature=0.3,
    )

    # Set deterministically in code, same pattern as the Coach's numeric
    # fields -- the LLM never reports its own grounding source.
    plan.grounding_source = grounding.source
    return plan
