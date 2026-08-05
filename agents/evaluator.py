"""Evaluator Agent: scores a single candidate answer against the rubric."""

from __future__ import annotations

from models.schemas import Evaluation, InterviewerTurn, InterviewState
from utils.llm import call_llm_json, load_prompt
from utils.parser import truncate_for_prompt

_SYSTEM_PROMPT = load_prompt("evaluator_prompt.txt")


def evaluate_answer(state: InterviewState, question: InterviewerTurn, answer: str) -> Evaluation:
    """Evaluate `answer` against `question`, using prior history for context.

    Empty/whitespace-only answers are passed through to the LLM as-is (per
    the prompt's FAILURE HANDLING section) rather than special-cased here,
    so scoring stays centralized in one place.
    """
    plan = state.plan
    assert plan is not None, "Planner must run before the Evaluator."

    prior_answers = "\n".join(
        f"Q{qa.index}: {truncate_for_prompt(qa.answer, 400)}" for qa in state.history
    ) or "(none)"

    cleaned_answer = answer.strip() or "(The candidate submitted no answer / blank input.)"

    user_prompt = (
        f"INTERVIEW CONTEXT\n"
        f"target focus: {plan.focus.value}, current difficulty: {state.current_difficulty.value}\n\n"
        f"QUESTION ASKED\n"
        f"[{question.question_type} / {question.topic}] {question.question}\n"
        f"is_final_question: {question.is_final_question}\n\n"
        f"CANDIDATE ANSWER\n{truncate_for_prompt(cleaned_answer, 4000)}\n\n"
        f"PRIOR ANSWERS THIS INTERVIEW (for repetition/consistency checks)\n{prior_answers}\n\n"
        "Produce the evaluation JSON now."
    )

    evaluation = call_llm_json(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=Evaluation,
        temperature=0.2,
    )

    if question.is_final_question:
        from models.schemas import NextAction

        evaluation.next_action = NextAction.END_INTERVIEW

    return evaluation
