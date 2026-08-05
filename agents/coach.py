"""Coach Agent: produces the final, detailed post-interview report.

Runs exactly once, after the interview is complete. Numeric scores are
computed deterministically by `utils/scoring.py` and handed to the LLM as
fixed facts to narrate around -- the LLM is never trusted to do arithmetic
or invent the final grade itself, only to write the qualitative analysis.
"""

from __future__ import annotations

from models.schemas import CoachReport, InterviewState
from utils.llm import call_llm_json, load_prompt
from utils.parser import truncate_for_prompt
from utils.scoring import (
    aggregate_scores,
    count_red_flags,
    hire_recommendation,
    overall_percentage,
    overall_score,
    readiness_level,
)

_SYSTEM_PROMPT = load_prompt("coach_prompt.txt")


def _format_transcript(state: InterviewState) -> str:
    lines: list[str] = []
    for qa in state.history:
        lines.append(f"Q{qa.index} [{qa.question_type} / {qa.topic}]: {qa.question}")
        lines.append(f"A{qa.index}: {truncate_for_prompt(qa.answer, 1000)}")
        if qa.evaluation:
            ev = qa.evaluation
            lines.append(
                f"  eval -> technical={ev.technical_score} communication={ev.communication} "
                f"confidence={ev.confidence} accuracy={ev.accuracy} clarity={ev.clarity} "
                f"problem_solving={ev.problem_solving} depth={ev.depth} "
                f"red_flags={ev.red_flags} strengths={ev.strengths} improvements={ev.improvements}"
            )
    return "\n".join(lines)


def generate_report(state: InterviewState) -> CoachReport:
    """Run the Coach Agent once, after the interview has ended."""
    plan = state.plan
    assert plan is not None, "Planner must run before the Coach."
    assert state.history, "Cannot coach an interview with no answered questions."

    score = overall_score(state.history)
    pct = overall_percentage(state.history)
    level = readiness_level(score)
    dims = aggregate_scores(state.history)
    flags = count_red_flags(state.history)
    recommendation = hire_recommendation(score, flags)

    user_prompt = (
        f"CANDIDATE\n"
        f"target role: {state.candidate.target_role}\n"
        f"background: {state.candidate.resume_snippet or '(none provided)'}\n"
        f"interview plan: difficulty={plan.difficulty.value}, focus={plan.focus.value}, "
        f"topics={plan.topics}, strategy='{plan.strategy}'\n\n"
        f"PRE-COMPUTED SCORES (use exactly as given, do not recompute)\n"
        f"overall_score: {score} / 10\n"
        f"overall_percentage: {pct}%\n"
        f"readiness_level: {level.value}\n"
        f"suggested hire_recommendation: {recommendation}\n"
        f"rubric dimension averages: {dims}\n"
        f"total red flags raised: {flags}\n\n"
        f"FULL TRANSCRIPT ({len(state.history)} questions)\n{_format_transcript(state)}\n\n"
        "Produce the full coaching report JSON now."
    )

    report = call_llm_json(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=CoachReport,
        temperature=0.5,
    )

    # Deterministic fields are enforced in code, never trusted to LLM arithmetic.
    report.overall_score = score
    report.overall_percentage = pct
    report.readiness_level = level
    if not report.hire_recommendation:
        report.hire_recommendation = recommendation

    return report
