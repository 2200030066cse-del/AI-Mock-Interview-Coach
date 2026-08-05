"""Interviewer Agent: asks one adaptive question at a time.

Reads the interview plan, full history, and the Evaluator's assessment of
the most recent answer to decide whether to escalate, follow up, hint, or
redirect -- per the adaptive rules in `prompts/interviewer_prompt.txt`.
"""

from __future__ import annotations

from models.schemas import InterviewerTurn, InterviewState
from utils.llm import call_llm_json, load_prompt
from utils.parser import truncate_for_prompt

_SYSTEM_PROMPT = load_prompt("interviewer_prompt.txt")


def _format_history(state: InterviewState) -> str:
    if not state.history:
        return "(No questions asked yet -- this is the opening question.)"

    lines: list[str] = []
    for qa in state.history:
        lines.append(f"Q{qa.index} [{qa.question_type} / {qa.topic}]: {qa.question}")
        lines.append(f"A{qa.index}: {truncate_for_prompt(qa.answer, 800)}")
        if qa.evaluation:
            ev = qa.evaluation
            lines.append(
                f"  -> eval: technical={ev.technical_score} accuracy={ev.accuracy} "
                f"depth={ev.depth} next_action={ev.next_action.value} "
                f"red_flags={ev.red_flags or 'none'} note='{ev.feedback_note}'"
            )
    return "\n".join(lines)


def ask_next_question(state: InterviewState) -> InterviewerTurn:
    """Generate the next question given the current interview state."""
    plan = state.plan
    assert plan is not None, "Planner must run before the Interviewer."

    last_eval = state.history[-1].evaluation if state.history else None
    last_eval_block = (
        f"Most recent evaluation: next_action={last_eval.next_action.value}, "
        f"scores(technical={last_eval.technical_score}, accuracy={last_eval.accuracy}, "
        f"depth={last_eval.depth}), red_flags={last_eval.red_flags}, "
        f"note='{last_eval.feedback_note}'"
        if last_eval
        else "Most recent evaluation: (none -- this is the first question.)"
    )

    force_new_topic_block = ""
    if state.force_new_topic:
        stuck_topic = state.history[-1].topic if state.history else "the current topic"
        force_new_topic_block = (
            "\nHARD OVERRIDE -- MOVE TO A NEW TOPIC NOW\n"
            f"The candidate has not been able to progress on '{stuck_topic}' after multiple "
            "attempts (follow-up and/or hint already given). Do NOT ask another question on "
            "this topic, and do not go deeper on it. Pick a different topic from the plan "
            "(prefer one not yet covered) and ask a fresh, comparatively approachable question "
            "on it to rebuild momentum. Give a brief, kind transition -- do not dwell on the "
            "struggle or make the candidate feel worse about it, and do not imply the previous "
            "answer was strong. Do not escalate difficulty for this question.\n"
        )

    user_prompt = (
        f"INTERVIEW PLAN\n"
        f"difficulty (planned baseline): {plan.difficulty.value}\n"
        f"current difficulty: {state.current_difficulty.value}\n"
        f"focus: {plan.focus.value}\n"
        f"topics: {plan.topics}\n"
        f"strategy: {plan.strategy}\n"
        f"topics covered so far: {state.topics_covered or 'none'}\n"
        f"{force_new_topic_block}\n"
        f"PROGRESS\n"
        f"question_count so far: {state.question_count} / target {state.max_questions}\n\n"
        f"{last_eval_block}\n\n"
        f"CONVERSATION HISTORY\n{_format_history(state)}\n\n"
        "Generate the next interviewer turn JSON now."
    )

    return call_llm_json(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=InterviewerTurn,
        temperature=0.6,
    )
