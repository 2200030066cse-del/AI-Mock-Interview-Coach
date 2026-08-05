"""Pydantic data models shared across all agents and the orchestration layer.

Every LLM-facing agent produces output that is parsed into one of these
models. Keeping the schemas centralized ensures the Planner, Interviewer,
Evaluator, and Coach agents all agree on a single contract for interview
state, and gives us free validation at every hand-off in the LangGraph
workflow.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Difficulty(str, Enum):
    """Interview difficulty levels the Planner/Interviewer can select."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class FocusArea(str, Enum):
    """High-level focus areas an interview can target."""

    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SYSTEM_DESIGN = "system_design"
    MIXED = "mixed"


class ReadinessLevel(str, Enum):
    """Overall readiness bucket assigned by the Coach agent."""

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    JOB_READY = "Job Ready"
    OUTSTANDING = "Outstanding"


class NextAction(str, Enum):
    """Instruction the Evaluator hands back to the Interviewer."""

    NEXT_CONCEPT = "next_concept"
    FOLLOW_UP = "follow_up"
    GIVE_HINT = "give_hint"
    REDIRECT = "redirect"
    END_INTERVIEW = "end_interview"


class CandidateProfile(BaseModel):
    """Raw input collected from the candidate before the interview starts."""

    target_role: str = Field(..., min_length=2, description="Role the candidate is interviewing for.")
    resume_snippet: str = Field(default="", description="Short resume / background snippet.")
    focus_area: FocusArea = Field(default=FocusArea.MIXED)

    @field_validator("target_role")
    @classmethod
    def strip_role(cls, v: str) -> str:
        return v.strip()


class InterviewPlan(BaseModel):
    """Structured output of the Planner agent."""

    difficulty: Difficulty
    focus: FocusArea
    topics: list[str] = Field(default_factory=list, min_length=1)
    strategy: str = Field(..., min_length=5)
    reasoning: str = Field(default="", description="Short justification the planner used internally.")
    grounding_source: str = Field(
        default="none",
        description="Set programmatically after parsing, not by the LLM: "
        "'web_search', 'local_question_bank', or 'none'.",
    )


class InterviewerTurn(BaseModel):
    """A single output from the Interviewer agent."""

    question: str = Field(..., min_length=3)
    question_type: str = Field(default="technical", description="e.g. technical, behavioral, follow_up, hint")
    topic: str = Field(default="")
    is_final_question: bool = False
    interviewer_note: str = Field(default="", description="Internal reasoning, not shown to candidate.")


class Evaluation(BaseModel):
    """Structured output of the Evaluator agent for a single answer."""

    technical_score: int = Field(..., ge=0, le=10)
    communication: int = Field(..., ge=0, le=10)
    confidence: int = Field(..., ge=0, le=10)
    accuracy: int = Field(..., ge=0, le=10)
    clarity: int = Field(..., ge=0, le=10)
    problem_solving: int = Field(default=5, ge=0, le=10)
    depth: int = Field(default=5, ge=0, le=10)
    red_flags: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    next_action: NextAction = NextAction.NEXT_CONCEPT
    feedback_note: str = Field(default="", description="One-line internal note used to steer the next question.")

    @property
    def average_score(self) -> float:
        scores = [
            self.technical_score,
            self.communication,
            self.confidence,
            self.accuracy,
            self.clarity,
            self.problem_solving,
            self.depth,
        ]
        return round(sum(scores) / len(scores), 2)


class QARecord(BaseModel):
    """One question/answer/evaluation triple, the atomic unit of transcript history."""

    index: int
    question: str
    question_type: str = "technical"
    topic: str = ""
    answer: str
    evaluation: Optional[Evaluation] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CoachReport(BaseModel):
    """Final structured report produced by the Coach agent."""

    overall_score: float = Field(..., ge=0, le=10)
    overall_percentage: float = Field(..., ge=0, le=100)
    readiness_level: ReadinessLevel
    hire_recommendation: str

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)

    communication_feedback: str = ""
    technical_feedback: str = ""
    behavioral_feedback: str = ""
    confidence_feedback: str = ""

    question_by_question_review: list[str] = Field(default_factory=list)

    top_5_concepts_to_study: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    weekly_improvement_plan: list[str] = Field(default_factory=list)

    motivational_closing_note: str = ""


class InterviewState(BaseModel):
    """The single source of truth threaded through every LangGraph node.

    LangGraph nodes receive this as a dict (via `.model_dump()`) and return
    partial updates that get merged back in by the graph runner.
    """

    candidate: CandidateProfile
    plan: Optional[InterviewPlan] = None

    history: list[QARecord] = Field(default_factory=list)
    current_question: Optional[InterviewerTurn] = None
    pending_answer: Optional[str] = None

    question_count: int = 0
    max_questions: int = 6
    current_difficulty: Difficulty = Difficulty.MEDIUM

    consecutive_weak_answers: int = 0
    consecutive_idk: int = 0
    topics_covered: list[str] = Field(default_factory=list)

    force_new_topic: bool = Field(
        default=False,
        description="One-shot directive set by evaluate_node when the candidate has been "
        "stuck (weak/hint/redirect) for MOVE_ON_THRESHOLD answers in a row. Consumed and "
        "cleared by generate_question_node on the very next question.",
    )

    is_complete: bool = False
    report: Optional[CoachReport] = None

    class Config:
        use_enum_values = False
