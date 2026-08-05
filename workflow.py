"""LangGraph orchestration for the AI Mock Interview Coach.

Wires the four agents into a graph:

    START -> planner -> generate_question -> await_answer -> evaluate -> should_continue?
                              ^                                              |
                              |------------------- continue -----------------|
                                                     |
                                                    done
                                                     v
                                                   coach -> END

`await_answer` pauses execution via LangGraph's `interrupt()` so the graph
can be driven turn-by-turn from a UI (Streamlit) without the UI needing to
know anything about LangGraph internals -- see `InterviewSession` below,
which is the only class `app.py` talks to.

Note on design: question generation and answer-waiting are deliberately
split into two separate nodes. `interrupt()` re-runs its enclosing node
from the top on resume, so anything with a side effect (like the
Interviewer's LLM call) must happen in a node *before* the one that calls
`interrupt()` -- otherwise every resume would silently re-generate the
question and waste an API call.
"""

from __future__ import annotations

import uuid
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agents import coach as coach_agent
from agents import evaluator as evaluator_agent
from agents import interviewer as interviewer_agent
from agents import planner as planner_agent
from models.schemas import CandidateProfile, Difficulty, InterviewState, NextAction, QARecord

_DIFFICULTY_ORDER = [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD]

# Real interviewers don't grind on a question the candidate can't answer.
# After this many consecutive stuck responses (weak/hint/off-topic) on the
# same topic, force a pivot to a different topic instead of trusting the
# LLM's own judgment to notice and move on -- see generate_question_node
# and agents/interviewer.py for how this directive is consumed.
MOVE_ON_THRESHOLD = 2


def _shift_difficulty(current: Difficulty, delta: int) -> Difficulty:
    idx = _DIFFICULTY_ORDER.index(current)
    new_idx = max(0, min(len(_DIFFICULTY_ORDER) - 1, idx + delta))
    return _DIFFICULTY_ORDER[new_idx]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def planner_node(state: InterviewState) -> dict:
    """Runs once at the start of the interview."""
    plan = planner_agent.create_plan(state.candidate)
    return {"plan": plan, "current_difficulty": plan.difficulty}


def generate_question_node(state: InterviewState) -> dict:
    """Calls the Interviewer Agent to produce the next question.

    `force_new_topic` is a one-shot directive: it's read here (via the
    Interviewer Agent, which injects an override instruction when set) and
    then cleared immediately, so it only affects this single question.
    """
    turn = interviewer_agent.ask_next_question(state)
    return {
        "current_question": turn,
        "question_count": state.question_count + 1,
        "force_new_topic": False,
    }


def await_answer_node(state: InterviewState) -> dict:
    """Pauses the graph until the UI supplies the candidate's answer.

    Contains no LLM calls -- only cheap, deterministic work -- so that
    LangGraph re-running this node on resume is safe and free.
    """
    question = state.current_question
    assert question is not None
    answer = interrupt(
        {
            "type": "question",
            "question": question.question,
            "question_type": question.question_type,
            "topic": question.topic,
            "question_number": state.question_count,
            "max_questions": state.max_questions,
            "is_final_question": question.is_final_question,
            "difficulty": state.current_difficulty.value,
        }
    )
    return {"pending_answer": answer}


def evaluate_node(state: InterviewState) -> dict:
    """Calls the Evaluator Agent and folds the result into interview state."""
    question = state.current_question
    assert question is not None
    answer = state.pending_answer or ""

    evaluation = evaluator_agent.evaluate_answer(state, question, answer)

    record = QARecord(
        index=state.question_count,
        question=question.question,
        question_type=question.question_type,
        topic=question.topic,
        answer=answer,
        evaluation=evaluation,
    )
    new_history = state.history + [record]

    topics = list(state.topics_covered)
    if question.topic and question.topic not in topics:
        topics.append(question.topic)

    # "Stuck" covers not-progressing (weak/hint) AND repeatedly dodging the
    # question (redirect) -- both waste time the same way a real interviewer
    # wouldn't tolerate for long.
    is_stuck = evaluation.next_action in (NextAction.FOLLOW_UP, NextAction.GIVE_HINT, NextAction.REDIRECT)
    is_idk = evaluation.next_action == NextAction.GIVE_HINT

    consecutive_weak = state.consecutive_weak_answers + 1 if is_stuck else 0
    consecutive_idk = state.consecutive_idk + 1 if is_idk else 0

    new_difficulty = state.current_difficulty
    if evaluation.next_action == NextAction.NEXT_CONCEPT and evaluation.average_score >= 8:
        new_difficulty = _shift_difficulty(state.current_difficulty, +1)
    elif consecutive_weak >= 2:
        new_difficulty = _shift_difficulty(state.current_difficulty, -1)

    force_new_topic = consecutive_weak >= MOVE_ON_THRESHOLD
    if force_new_topic:
        # Reset here (not just next cycle) so the forced pivot always starts
        # the new topic's own fresh counter, rather than inheriting a streak
        # that's about to become irrelevant.
        consecutive_weak = 0
        consecutive_idk = 0

    return {
        "history": new_history,
        "topics_covered": topics,
        "consecutive_weak_answers": consecutive_weak,
        "consecutive_idk": consecutive_idk,
        "current_difficulty": new_difficulty,
        "pending_answer": None,
        "force_new_topic": force_new_topic,
    }


def should_continue(state: InterviewState) -> Literal["continue", "coach"]:
    """Conditional edge: loop back for another question, or hand off to the Coach."""
    if state.current_question and state.current_question.is_final_question:
        return "coach"
    if state.question_count >= state.max_questions:
        return "coach"
    return "continue"


def coach_node(state: InterviewState) -> dict:
    """Runs once at the end of the interview."""
    report = coach_agent.generate_report(state)
    return {"report": report, "is_complete": True}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph():
    graph = StateGraph(InterviewState)
    graph.add_node("planner", planner_node)
    graph.add_node("generate_question", generate_question_node)
    graph.add_node("await_answer", await_answer_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("coach", coach_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "generate_question")
    graph.add_edge("generate_question", "await_answer")
    graph.add_edge("await_answer", "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        should_continue,
        {"continue": "generate_question", "coach": "coach"},
    )
    graph.add_edge("coach", END)

    # Explicitly allow-list our own Pydantic models/Enums (models.schemas.*)
    # for the checkpoint serializer -- without it, langgraph emits a
    # future-deprecation warning on every checkpoint write for any type it
    # doesn't recognize out of the box.
    _SCHEMA_TYPES = [
        "CandidateProfile", "Difficulty", "FocusArea", "ReadinessLevel",
        "NextAction", "InterviewPlan", "InterviewerTurn", "Evaluation",
        "QARecord", "CoachReport", "InterviewState",
    ]
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[("models.schemas", name) for name in _SCHEMA_TYPES]
    )
    return graph.compile(checkpointer=MemorySaver(serde=serde))


# ---------------------------------------------------------------------------
# UI-facing wrapper
# ---------------------------------------------------------------------------


class InterviewSession:
    """Turn-by-turn wrapper around the compiled LangGraph graph.

    Hides LangGraph's interrupt/resume mechanics behind two calls --
    `start()` and `answer()` -- so `app.py` never touches LangGraph
    primitives directly.
    """

    def __init__(self, max_questions: int = 6) -> None:
        self._graph = build_graph()
        self._thread_id = str(uuid.uuid4())
        self._max_questions = max_questions

    @property
    def config(self) -> dict:
        return {"configurable": {"thread_id": self._thread_id}}

    def start(self, candidate: CandidateProfile) -> dict:
        """Kick off the interview: runs the Planner and the first question."""
        result = self._graph.invoke(
            {"candidate": candidate, "max_questions": self._max_questions},
            config=self.config,
        )
        return self._interpret(result)

    def answer(self, answer_text: str) -> dict:
        """Submit the candidate's answer and advance the graph."""
        result = self._graph.invoke(Command(resume=answer_text), config=self.config)
        return self._interpret(result)

    def current_state(self) -> InterviewState:
        snapshot = self._graph.get_state(self.config)
        return InterviewState.model_validate(snapshot.values)

    def _interpret(self, result: dict) -> dict:
        if "__interrupt__" in result and result["__interrupt__"]:
            payload = result["__interrupt__"][0].value
            return {"status": "awaiting_answer", **payload}

        state = self.current_state()
        return {"status": "complete", "report": state.report, "state": state}
