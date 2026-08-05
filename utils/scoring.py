"""Deterministic scoring/aggregation logic.

Per-answer scores come from the Evaluator agent (LLM judgment). Aggregating
those into a final readiness level is deliberately kept as *plain Python*,
not another LLM call -- it should be reproducible, auditable, and free.
"""

from __future__ import annotations

from models.schemas import Evaluation, QARecord, ReadinessLevel

# Weights mirror the rubric in the assignment spec: Technical, Communication,
# Confidence, Problem Solving, Depth, Accuracy -- each out of 10.
RUBRIC_DIMENSIONS = [
    "technical_score",
    "communication",
    "confidence",
    "accuracy",
    "clarity",
    "problem_solving",
    "depth",
]


def aggregate_scores(history: list[QARecord]) -> dict[str, float]:
    """Average each rubric dimension across all evaluated answers."""
    evaluated = [qa.evaluation for qa in history if qa.evaluation is not None]
    if not evaluated:
        return {dim: 0.0 for dim in RUBRIC_DIMENSIONS}

    totals = {dim: 0.0 for dim in RUBRIC_DIMENSIONS}
    for ev in evaluated:
        for dim in RUBRIC_DIMENSIONS:
            totals[dim] += getattr(ev, dim)

    n = len(evaluated)
    return {dim: round(totals[dim] / n, 2) for dim in RUBRIC_DIMENSIONS}


def overall_score(history: list[QARecord]) -> float:
    """Single 0-10 score: the mean of all rubric-dimension averages."""
    dims = aggregate_scores(history)
    if not dims:
        return 0.0
    return round(sum(dims.values()) / len(dims), 2)


def overall_percentage(history: list[QARecord]) -> float:
    return round(overall_score(history) * 10, 1)


def readiness_level(score_out_of_10: float) -> ReadinessLevel:
    """Map an overall 0-10 score to a readiness bucket.

    Thresholds:
      < 4.0            -> Beginner
      4.0 - 6.4         -> Intermediate
      6.5 - 8.4         -> Job Ready
      >= 8.5            -> Outstanding
    """
    if score_out_of_10 >= 8.5:
        return ReadinessLevel.OUTSTANDING
    if score_out_of_10 >= 6.5:
        return ReadinessLevel.JOB_READY
    if score_out_of_10 >= 4.0:
        return ReadinessLevel.INTERMEDIATE
    return ReadinessLevel.BEGINNER


def hire_recommendation(score_out_of_10: float, red_flag_count: int) -> str:
    """A short human-readable recommendation string for the report header."""
    if red_flag_count >= 3:
        return "No Hire -- multiple red flags raised during the interview."
    level = readiness_level(score_out_of_10)
    mapping = {
        ReadinessLevel.OUTSTANDING: "Strong Hire",
        ReadinessLevel.JOB_READY: "Hire",
        ReadinessLevel.INTERMEDIATE: "Lean No Hire -- needs more preparation",
        ReadinessLevel.BEGINNER: "No Hire -- not yet ready for this role",
    }
    return mapping[level]


def count_red_flags(history: list[QARecord]) -> int:
    return sum(len(qa.evaluation.red_flags) for qa in history if qa.evaluation)


def score_trend(history: list[QARecord]) -> list[float]:
    """Per-question average score, used for the performance chart in the UI."""
    return [qa.evaluation.average_score for qa in history if qa.evaluation]
