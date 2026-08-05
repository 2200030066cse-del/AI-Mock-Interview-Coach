# User Guide

A walkthrough of the AI Mock Interview Coach app, phase by phase. If you haven't installed it
yet, see [`SETUP.md`](SETUP.md) first.

## Overview

The app has three phases: **Setup → Interview → Report**. You move through them by filling in
the form and answering questions -- there's no back-and-forth navigation, mirroring a real
interview.

---

## 1. Setup: the intake form

When you open the app, you'll see a form asking for:

| Field | What to put | Notes |
|---|---|---|
| **Target Role** | The role you're practicing for, e.g. "Frontend Engineer Intern" | Required. Also drives which curated question bank entry gets used for grounding (see below). |
| **Background / Resume Snippet** | 2-3 lines about your experience | Optional. Helps the Planner calibrate difficulty (e.g. "no experience yet" vs. "2 years at a startup"). |
| **Focus Area** | Technical / Behavioral / System Design / Mixed | Shapes what kind of questions you get. |
| **Number of Questions** | 1-15 | How long the session runs. 5-7 is a good default for a realistic mock interview; use 1-2 for a quick single-topic drill. |

Click **Start Interview**. Behind the scenes, the Planner Agent designs a strategy (difficulty,
topics, approach) before your first question appears -- this usually takes a few seconds.

---

## 2. Interview: answering questions

One question appears at a time, styled as a card showing its **type**, **topic**, and current
**difficulty**. Type your answer in the box and click **Submit Answer**.

**A few things worth knowing:**

- **"I don't know" button.** If you're genuinely stuck, use this instead of typing a guess --
  it's scored honestly (not penalized like a wrong, overconfident answer would be) and the
  Interviewer will give you a hint rather than just moving on.
- **The timer.** A live stopwatch (`⏱️ Time on This Question`) tracks how long you spend on each
  question, visible above the question and in the sidebar. Useful for noticing which topics slow
  you down.
- **Adaptive follow-ups.** A strong answer moves you to a new topic (sometimes at higher
  difficulty). A weak or partial answer gets a follow-up on the same topic. This is normal --
  it's the system probing depth, not a sign you failed.
- **Stuck-topic pivoting.** If you can't progress on a topic after 2 attempts in a row (weak
  answers, hints, or going off-topic), the interviewer will deliberately pivot to a different,
  easier topic rather than grinding on a dead end -- exactly like a real interviewer would.
- **Off-topic answers.** If your answer doesn't address the question, you'll be redirected
  politely rather than scored harshly -- it's treated as a redirect, not an automatic failure.

**The sidebar** (left side) updates live throughout:

| Sidebar item | What it shows |
|---|---|
| Status / Progress | Question X of Y, complete or in-progress |
| Current Difficulty | easy / medium / hard, adjusts as you answer |
| Last Answer Score / Running Average | Out of 10, updates after each answer |
| Timing | Average time per question, total elapsed, per-question breakdown |
| Topics Covered | Running list of topics touched so far |
| Interview Plan (expander) | The Planner's strategy, planned topics, and **grounding source** -- shows whether questions were informed by the curated question bank, live web search, or the model's own knowledge |
| Token Usage (expander) | Running LLM token count, if you're curious about cost |

---

## 3. Report: your coaching feedback

After your final question, the Coach Agent generates a full report:

- **Top metrics**: overall score (/10), percentage, readiness level (Beginner / Intermediate /
  Job Ready / Outstanding), hire recommendation, and total time spent.
- **Rubric breakdown chart**: your average across all 7 scored dimensions (technical,
  communication, confidence, accuracy, clarity, problem solving, depth).
- **Score trend chart**: how your per-question average moved across the interview.
- **Time per question chart**: which questions took longest.
- **Strengths / Weaknesses**: concrete, specific observations tied to what you actually said.
- **Feedback by category**: communication, technical, behavioral, and confidence feedback, each
  in its own expander.
- **Question-by-question review**: a short note on every question asked.
- **Practice plan**: top 5 concepts to study, suggested resources, and a weekly improvement plan.
- **Downloads**: export the full transcript + report as `.txt`, `.md`, or `.pdf`.

Click **Start a New Interview** to reset and try again -- useful for practicing the same role at
a different focus area, or a different role entirely.

---

## Tips for getting the most out of a session

- **Answer like it's real.** The Evaluator credits genuine reasoning and honest uncertainty over
  confident-sounding padding -- there's no benefit to bluffing.
- **Use "I don't know" instead of guessing wildly.** A hedged, honest answer scores better than a
  confidently wrong one, and you'll get a hint instead of a harder follow-up.
- **Try a short session first.** Set Number of Questions to 2-3 to see the whole flow (including
  the final report) quickly before committing to a full-length mock interview.
- **Check the "Grounded via" line** in the sidebar's Interview Plan expander -- if it says the
  local question bank wasn't matched to your role, the Planner still works fine, just from the
  model's own knowledge instead of the curated bank.

## FAQ

**Why did the difficulty change mid-interview?**
Two strong answers in a row escalate difficulty one notch; two stuck answers in a row de-escalate
it one notch. It never jumps more than one level at a time, and only changes between topics, not
mid-follow-up.

**Why did it move to a new topic instead of trying my question a third time?**
By design -- see "Stuck-topic pivoting" above. It's a deliberate, code-enforced rule, not a bug.

**Can I go back and change a previous answer?**
No -- like a real interview, answers are final once submitted. Start a new session if you want a
clean retry.

**Does it remember previous sessions?**
Not currently -- each browser session is independent (see the README's Future Improvements for
planned session-history support).
