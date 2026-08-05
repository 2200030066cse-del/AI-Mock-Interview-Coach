"""Streamlit front-end for the AI Mock Interview Coach.

Three phases, driven entirely by `st.session_state`:
  1. "form"      -- collect target role / resume / focus area.
  2. "interview" -- one question at a time, adaptive, via `InterviewSession`.
  3. "report"    -- the Coach Agent's final structured report + downloads.

This file contains no LLM or LangGraph logic itself -- it only renders
state produced by `workflow.InterviewSession` and turns button clicks into
`session.start(...)` / `session.answer(...)` calls.
"""

from __future__ import annotations

import os
import io
import re
import textwrap
import time
from datetime import datetime

import streamlit as st

# Bridge Streamlit Community Cloud's secrets manager to os.environ BEFORE
# importing any project modules below -- utils/llm.py reads LLM_PROVIDER
# and the API keys at *import time* (module-level constants), so injecting
# secrets any later would be too late for that first read. Locally, this is
# a no-op: there's no secrets.toml, so it silently falls through and
# python-dotenv's .env loading (inside utils/llm.py) takes over instead.
try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except Exception:
    pass

from models.schemas import CandidateProfile, FocusArea, InterviewState
from utils.llm import usage_tracker
from utils.scoring import aggregate_scores, score_trend
from workflow import InterviewSession

st.set_page_config(
    page_title="AI Mock Interview Coach",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
.block-container { padding-top: 2rem; max-width: 1100px; }
.question-card {
    padding: 1.5rem 1.75rem; border-radius: 0.75rem;
    background: rgba(120, 120, 255, 0.08); border: 1px solid rgba(120,120,255,0.25);
    margin-bottom: 1rem;
}
.question-meta { font-size: 0.8rem; opacity: 0.7; margin-bottom: 0.5rem; }
.report-section { margin-top: 1.25rem; }
.stButton>button { border-radius: 0.5rem; font-weight: 600; }

.status-card {
    padding: 1.25rem 1.5rem; border-radius: 0.75rem;
    background: rgba(255, 255, 255, 0.035); border: 1px solid rgba(255, 255, 255, 0.08);
    border-left: 4px solid var(--status-accent, #888); margin: 0.5rem 0 1rem 0;
}
.status-card-header { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; }
.status-card-icon { font-size: 1.5rem; line-height: 1; }
.status-card-title { font-size: 1.1rem; font-weight: 700; }
.status-card-message { margin: 0 0 0.6rem 0; opacity: 0.9; line-height: 1.5; }
.status-card-tips { margin: 0; padding-left: 1.2rem; opacity: 0.85; line-height: 1.6; }
.status-card-tips li { margin-bottom: 0.15rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------


def _init_state() -> None:
    st.session_state.setdefault("phase", "form")
    st.session_state.setdefault("session", None)
    st.session_state.setdefault("turn", None)
    st.session_state.setdefault("candidate", None)
    st.session_state.setdefault("interview_start_time", None)
    st.session_state.setdefault("question_start_time", None)
    st.session_state.setdefault("timed_question_num", None)
    st.session_state.setdefault("question_times", {})


def _reset() -> None:
    st.session_state["phase"] = "form"
    st.session_state["session"] = None
    st.session_state["turn"] = None
    st.session_state["candidate"] = None
    st.session_state["interview_start_time"] = None
    st.session_state["question_start_time"] = None
    st.session_state["timed_question_num"] = None
    st.session_state["question_times"] = {}
    usage_tracker.reset()


def _ensure_timer_started(question_number: int) -> None:
    """Starts the stopwatch the first time a given question is rendered.

    Guarded by `timed_question_num` so re-runs caused by the ticking
    fragment (or other widget interactions) don't reset the clock -- only
    a genuinely new question does.
    """
    if st.session_state.get("timed_question_num") != question_number:
        st.session_state["question_start_time"] = time.time()
        st.session_state["timed_question_num"] = question_number


def _format_mmss(seconds: float) -> str:
    total = max(0, int(seconds))
    mm, ss = divmod(total, 60)
    return f"{mm:02d}:{ss:02d}"


@st.fragment(run_every=1)
def _render_live_timer() -> None:
    start = st.session_state.get("question_start_time")
    if start is None:
        return
    st.metric("⏱️ Time on This Question", _format_mmss(time.time() - start))


def _current_interview_state() -> InterviewState | None:
    session: InterviewSession | None = st.session_state.get("session")
    if session is None:
        return None
    try:
        return session.current_state()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar() -> None:
    st.sidebar.title("🎯 Interview Status")
    state = _current_interview_state()

    if state is None or state.plan is None:
        st.sidebar.info("Fill out the form to begin your mock interview.")
        return

    status = "Complete ✅" if state.is_complete else "In Progress 🟢"
    st.sidebar.metric("Status", status)
    st.sidebar.metric("Progress", f"Question {min(state.question_count, state.max_questions)} / {state.max_questions}")
    st.sidebar.metric("Current Difficulty", state.current_difficulty.value.title())

    if state.history:
        latest_avg = state.history[-1].evaluation.average_score if state.history[-1].evaluation else None
        if latest_avg is not None:
            st.sidebar.metric("Last Answer Score", f"{latest_avg} / 10")

        running_avg = sum(qa.evaluation.average_score for qa in state.history if qa.evaluation) / max(
            1, sum(1 for qa in state.history if qa.evaluation)
        )
        st.sidebar.metric("Running Average", f"{running_avg:.1f} / 10")

    question_times = st.session_state.get("question_times", {})
    interview_start = st.session_state.get("interview_start_time")
    if question_times or (interview_start and not state.is_complete):
        st.sidebar.markdown("**⏱️ Timing**")
        if question_times:
            avg_time = sum(question_times.values()) / len(question_times)
            st.sidebar.metric("Avg. Time / Question", _format_mmss(avg_time))
        total_elapsed = (
            sum(question_times.values())
            if state.is_complete
            else (time.time() - interview_start if interview_start else 0)
        )
        st.sidebar.metric("Total Interview Time", _format_mmss(total_elapsed))
        with st.sidebar.expander("Time per question"):
            for qn in sorted(question_times):
                st.write(f"Q{qn}: {_format_mmss(question_times[qn])}")

    st.sidebar.markdown("**Topics Covered**")
    if state.topics_covered:
        for t in state.topics_covered:
            st.sidebar.markdown(f"- {t}")
    else:
        st.sidebar.caption("None yet")

    with st.sidebar.expander("Interview Plan"):
        st.write(f"**Focus:** {state.plan.focus.value}")
        st.write(f"**Strategy:** {state.plan.strategy}")
        st.write("**Planned topics:**")
        for t in state.plan.topics:
            st.write(f"- {t}")
        grounding_labels = {
            "web_search": "🌐 Live web search",
            "local_question_bank": "📚 Curated question bank",
            "none": "🧠 Model's own knowledge (no grounding match)",
        }
        st.caption(f"Grounded via: {grounding_labels.get(state.plan.grounding_source, state.plan.grounding_source)}")

    usage = usage_tracker.snapshot()
    with st.sidebar.expander("Token Usage (bonus metric)"):
        st.write(f"Prompt tokens: {usage['prompt_tokens']}")
        st.write(f"Completion tokens: {usage['completion_tokens']}")
        st.write(f"Total: {usage['total_tokens']} across {usage['total_calls']} calls")

    if st.sidebar.button("🔄 Start Over", use_container_width=True):
        _reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Phase 1: intake form
# ---------------------------------------------------------------------------


def render_form() -> None:
    st.title("🎯 AI Mock Interview Coach")
    st.caption("A multi-agent interview simulator: Planner → Interviewer → Evaluator → Coach")

    with st.form("intake_form"):
        role = st.text_input("Target Role", placeholder="e.g. Frontend Engineer Intern")
        resume = st.text_area(
            "Background / Resume Snippet (optional)",
            placeholder="e.g. Built React projects and learned JavaScript in coursework.",
            height=100,
        )
        focus = st.selectbox(
            "Focus Area",
            options=[f.value for f in FocusArea],
            format_func=lambda v: v.replace("_", " ").title(),
            index=3,
        )
        max_q = st.slider("Number of Questions", min_value=1, max_value=15, value=6)
        submitted = st.form_submit_button("🚀 Start Interview", use_container_width=True)

    if submitted:
        if not role.strip():
            st.error("Please enter a target role before starting.")
            return

        candidate = CandidateProfile(target_role=role, resume_snippet=resume, focus_area=FocusArea(focus))
        session = InterviewSession(max_questions=max_q)

        with st.spinner("Planner Agent is designing your interview strategy..."):
            turn = session.start(candidate)

        st.session_state["session"] = session
        st.session_state["candidate"] = candidate
        st.session_state["turn"] = turn
        st.session_state["interview_start_time"] = time.time()
        st.session_state["question_times"] = {}
        st.session_state["timed_question_num"] = None
        st.session_state["phase"] = "report" if turn["status"] == "complete" else "interview"
        st.rerun()


# ---------------------------------------------------------------------------
# Phase 2: interview loop
# ---------------------------------------------------------------------------


def render_interview() -> None:
    session: InterviewSession = st.session_state["session"]
    turn = st.session_state["turn"]

    st.title("🎯 Mock Interview in Progress")

    q_num = turn.get("question_number", 1)
    max_q = turn.get("max_questions", 6)
    _ensure_timer_started(q_num)

    st.progress(min(q_num / max_q, 1.0), text=f"Question {q_num} / {max_q}")
    _render_live_timer()

    st.markdown(
        f"""<div class="question-card">
        <div class="question-meta">{turn.get('question_type', 'technical').replace('_', ' ').title()}
        &middot; Topic: {turn.get('topic', 'general')} &middot; Difficulty: {turn.get('difficulty', 'medium').title()}</div>
        <h4>{turn['question']}</h4>
        </div>""",
        unsafe_allow_html=True,
    )

    with st.form(f"answer_form_{q_num}"):
        answer = st.text_area("Your Answer", height=160, placeholder="Type your answer here...")
        col1, col2 = st.columns([1, 5])
        with col1:
            submitted = st.form_submit_button("Submit Answer ➡️", use_container_width=True)
        with col2:
            idk = st.form_submit_button("I don't know", use_container_width=False)

    if submitted or idk:
        final_answer = "I don't know." if idk else answer
        if not final_answer.strip():
            st.warning("Empty answer submitted — treated the same as 'I don't know'.")
            final_answer = final_answer or ""

        start = st.session_state.get("question_start_time") or time.time()
        st.session_state.setdefault("question_times", {})[q_num] = round(time.time() - start, 1)

        with st.spinner("Evaluator Agent is scoring your answer... (Coach Agent will run too if this was the last question)"):
            result = session.answer(final_answer)

        st.session_state["turn"] = result
        if result["status"] == "complete":
            st.session_state["phase"] = "report"
        st.rerun()


# ---------------------------------------------------------------------------
# Phase 3: final report
# ---------------------------------------------------------------------------


def _build_transcript_text(state: InterviewState, question_times: dict[int, float] | None = None) -> str:
    question_times = question_times or {}
    lines = [
        f"AI Mock Interview Coach -- Transcript",
        f"Role: {state.candidate.target_role}",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        "=" * 60,
        "",
    ]
    for qa in state.history:
        lines.append(f"Q{qa.index} ({qa.question_type} / {qa.topic}): {qa.question}")
        lines.append(f"A{qa.index}: {qa.answer}")
        if qa.index in question_times:
            lines.append(f"   time taken: {_format_mmss(question_times[qa.index])}")
        if qa.evaluation:
            ev = qa.evaluation
            lines.append(
                f"   scores -> technical={ev.technical_score} communication={ev.communication} "
                f"confidence={ev.confidence} accuracy={ev.accuracy} clarity={ev.clarity} "
                f"problem_solving={ev.problem_solving} depth={ev.depth}"
            )
        lines.append("")

    if question_times:
        total = sum(question_times.values())
        avg = total / len(question_times)
        lines += [
            f"Total time: {_format_mmss(total)} across {len(question_times)} questions "
            f"(avg {_format_mmss(avg)}/question)",
            "",
        ]

    if state.report:
        r = state.report
        lines += [
            "=" * 60,
            "COACHING REPORT",
            "=" * 60,
            f"Overall Score: {r.overall_score}/10 ({r.overall_percentage}%)",
            f"Readiness: {r.readiness_level.value}",
            f"Recommendation: {r.hire_recommendation}",
            "",
            "Strengths:",
            *[f"  - {s}" for s in r.strengths],
            "",
            "Weaknesses:",
            *[f"  - {w}" for w in r.weaknesses],
            "",
            "Top 5 Concepts to Study:",
            *[f"  - {c}" for c in r.top_5_concepts_to_study],
        ]
    return "\n".join(lines)


def _build_pdf_bytes(state: InterviewState, question_times: dict[int, float] | None = None) -> bytes | None:
    """Best-effort PDF export using fpdf2. Returns None if unavailable or if
    generation fails for any reason -- PDF export is a nice-to-have and must
    never take down the rest of the report page.
    """
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
    except ImportError:
        return None

    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        # fpdf2's multi_cell defaults to new_x=XPos.RIGHT, which leaves the
        # cursor near the right margin instead of resetting it -- every
        # subsequent multi_cell(0, ...) call then sees almost zero available
        # width and raises "Not enough horizontal space to render a single
        # character", even for ordinary short text. Explicitly reset to the
        # left margin / next line after every call.
        pdf.multi_cell(0, 10, "AI Mock Interview Coach -- Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        text = _build_transcript_text(state, question_times)
        pdf.set_font("Courier", "", 9)
        # Belt and suspenders: also hard-wrap every line so an unusually
        # long unbroken token (a URL, a long identifier) can never exceed a
        # safe width on its own, regardless of the cursor-reset fix above.
        for raw_line in text.split("\n"):
            safe = raw_line.encode("latin-1", "replace").decode("latin-1")
            for wrapped in textwrap.wrap(safe, width=95, break_long_words=True, break_on_hyphens=False) or [""]:
                pdf.multi_cell(0, 5, wrapped, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        return bytes(pdf.output(dest="S"))
    except Exception:  # noqa: BLE001 - PDF export must degrade gracefully, never crash the page
        return None


def render_report() -> None:
    state = _current_interview_state()
    if state is None or state.report is None:
        st.error("No report available.")
        return
    r = state.report

    st.title("📊 Your Coaching Report")

    question_times: dict[int, float] = st.session_state.get("question_times", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall Score", f"{r.overall_score} / 10")
    c2.metric("Percentage", f"{r.overall_percentage}%")
    c3.metric("Readiness", r.readiness_level.value)
    if question_times:
        c4.metric("Total Time", _format_mmss(sum(question_times.values())))
    st.info(f"**Hire Recommendation:** {r.hire_recommendation}")

    st.markdown("### Rubric Breakdown")
    dims = aggregate_scores(state.history)
    st.bar_chart(dims)

    trend = score_trend(state.history)
    if len(trend) > 1:
        st.markdown("### Score Trend Across Questions")
        st.line_chart({"average score": trend})

    if question_times:
        st.markdown("### ⏱️ Time Spent Per Question")
        ordered = {f"Q{qn}": question_times[qn] for qn in sorted(question_times)}
        st.bar_chart(ordered)
        avg_time = sum(question_times.values()) / len(question_times)
        tc1, tc2 = st.columns(2)
        tc1.metric("Avg. Time / Question", _format_mmss(avg_time))
        tc2.metric("Slowest Question", f"Q{max(question_times, key=question_times.get)} ({_format_mmss(max(question_times.values()))})")

    col_s, col_w = st.columns(2)
    with col_s:
        st.markdown("### ✅ Strengths")
        for s in r.strengths:
            st.markdown(f"- {s}")
    with col_w:
        st.markdown("### ⚠️ Weaknesses")
        for w in r.weaknesses:
            st.markdown(f"- {w}")

    st.markdown("### Feedback by Category")
    with st.expander("💬 Communication", expanded=True):
        st.write(r.communication_feedback)
    with st.expander("🛠️ Technical"):
        st.write(r.technical_feedback)
    with st.expander("🤝 Behavioral"):
        st.write(r.behavioral_feedback)
    with st.expander("💪 Confidence"):
        st.write(r.confidence_feedback)

    st.markdown("### Question-by-Question Review")
    for i, review in enumerate(r.question_by_question_review, start=1):
        st.markdown(f"**Q{i}.** {review}")

    st.markdown("### 📚 Practice Plan")
    st.markdown("**Top 5 Concepts to Study**")
    for c in r.top_5_concepts_to_study:
        st.markdown(f"- {c}")
    st.markdown("**Resources**")
    for res in r.resources:
        st.markdown(f"- {res}")
    st.markdown("**Weekly Improvement Plan**")
    for step in r.weekly_improvement_plan:
        st.markdown(f"- {step}")

    st.success(r.motivational_closing_note)

    st.markdown("### Downloads")
    dl1, dl2, dl3 = st.columns(3)
    transcript_text = _build_transcript_text(state, question_times)
    with dl1:
        st.download_button(
            "⬇️ Transcript (.txt)",
            data=transcript_text,
            file_name="interview_transcript.txt",
            use_container_width=True,
        )
    with dl2:
        st.download_button(
            "⬇️ Report (.md)",
            data=transcript_text,
            file_name="interview_report.md",
            use_container_width=True,
        )
    with dl3:
        pdf_bytes = _build_pdf_bytes(state, question_times)
        if pdf_bytes:
            st.download_button(
                "⬇️ Report (.pdf)",
                data=pdf_bytes,
                file_name="interview_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.caption("PDF export unavailable for this report (transcript/report downloads above still work).")

    if st.button("🔄 Start a New Interview"):
        _reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Error presentation
# ---------------------------------------------------------------------------

_SEVERITY_ACCENT = {"warning": "#F59F00", "error": "#E03131", "info": "#4263EB"}


def _extract_retry_after(text: str) -> str | None:
    """Turn a provider's 'try again in 25m31.008s' into 'about 26 minutes'."""
    match = re.search(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", text, re.IGNORECASE)
    if not match:
        return None
    minutes = int(match.group(1)) if match.group(1) else 0
    seconds = float(match.group(2))
    if not minutes:
        return f"about {max(1, round(seconds))} seconds"
    if seconds >= 30:
        minutes += 1
    return f"about {minutes} minute{'s' if minutes != 1 else ''}"


def _classify_error(exc: Exception) -> dict:
    """Map a raw exception to a friendly, actionable explanation.

    Matches on message text rather than provider-specific exception classes
    so this stays agnostic to whichever LLM_PROVIDER is active.
    """
    text = str(exc)
    lower = text.lower()

    if "rate_limit" in lower or "rate limit" in lower or "429" in text:
        retry_phrase = _extract_retry_after(text)
        return {
            "icon": "⏳",
            "title": "Free usage limit reached for today",
            "message": (
                "Your LLM provider's free-tier token quota is used up for now. This isn't a "
                "bug in the app -- it's a quota on the API key, and it resets on its own."
            ),
            "tips": [
                f"It resets in {retry_phrase}." if retry_phrase else "It typically resets within a day.",
                "Or set LLM_PROVIDER to a different provider in your .env to keep going right now.",
            ],
            "severity": "warning",
            "raw": text,
        }

    if "api_key" in lower or "unauthorized" in lower or "401" in text or "invalid_api_key" in lower:
        return {
            "icon": "🔑",
            "title": "API key issue",
            "message": "The LLM provider rejected the request -- the API key is missing, invalid, or expired.",
            "tips": [
                "Check that OPENAI_API_KEY or GROQ_API_KEY (matching LLM_PROVIDER) is set in your .env file.",
                "Make sure there's no extra whitespace or stray quotes around the key.",
            ],
            "severity": "error",
            "raw": text,
        }

    if "connection" in lower or "timeout" in lower or "timed out" in lower:
        return {
            "icon": "📡",
            "title": "Connection hiccup",
            "message": "Couldn't reach the LLM provider -- most likely a temporary network issue.",
            "tips": ["Check your internet connection, then try again."],
            "severity": "warning",
            "raw": text,
        }

    if "failed to produce valid" in lower or "could not be parsed" in lower:
        return {
            "icon": "🧩",
            "title": "The model's response didn't come back in the expected format",
            "message": "One of the agents returned output that couldn't be understood, even after retrying. This is rare and usually resolves itself.",
            "tips": ["Try submitting your answer again."],
            "severity": "warning",
            "raw": text,
        }

    return {
        "icon": "⚠️",
        "title": "Something unexpected happened",
        "message": "An unhandled error interrupted the interview.",
        "tips": ["Try again, or reset the session if it keeps happening."],
        "severity": "error",
        "raw": text,
    }


def render_error_card(info: dict) -> None:
    accent = _SEVERITY_ACCENT.get(info["severity"], "#888888")
    tips_html = "".join(f"<li>{t}</li>" for t in info["tips"])
    st.markdown(
        f"""<div class="status-card" style="--status-accent: {accent};">
        <div class="status-card-header">
            <span class="status-card-icon">{info['icon']}</span>
            <span class="status-card-title">{info['title']}</span>
        </div>
        <p class="status-card-message">{info['message']}</p>
        <ul class="status-card-tips">{tips_html}</ul>
        </div>""",
        unsafe_allow_html=True,
    )

    with st.expander("Technical details"):
        st.code(info["raw"], language="text")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Try again", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🧹 Reset session", use_container_width=True):
            _reset()
            st.rerun()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    _init_state()
    render_sidebar()

    phase = st.session_state["phase"]
    try:
        if phase == "form":
            render_form()
        elif phase == "interview":
            render_interview()
        elif phase == "report":
            render_report()
    except Exception as exc:  # noqa: BLE001
        render_error_card(_classify_error(exc))


if __name__ == "__main__":
    main()
