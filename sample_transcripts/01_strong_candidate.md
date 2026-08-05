# Sample Transcript 1 — Strong Candidate

**Target Role:** Frontend Engineer Intern
**Background:** "Built React projects and learned JavaScript in coursework. Contributed a
small feature to an open-source component library over the summer."
**Focus Area:** Technical

---

## Planner Agent Output

```json
{
  "difficulty": "easy",
  "focus": "technical",
  "topics": [
    "React component lifecycle and state management",
    "JavaScript closures and asynchronous behavior (promises/async-await)",
    "Debugging a broken UI given a described symptom",
    "Basic HTML/CSS layout reasoning (flexbox/box model)",
    "Explaining a personal React project's architecture and one tradeoff made"
  ],
  "strategy": "Start with fundamentals to establish a baseline, then use the candidate's own open-source contribution to test real depth versus tutorial-following. Escalate difficulty if early answers are strong.",
  "reasoning": "Background suggests early-career/intern level with some real-world open-source exposure beyond coursework, so start easy with room to move to medium quickly."
}
```

---

## Interview

**Q1 (technical / React component lifecycle, easy):**
> Can you explain what happens when a piece of state changes in a React functional component?

**A1:**
> When state changes via `useState`'s setter, React schedules a re-render of that component
> and its children. React compares the new virtual DOM output to the previous one (reconciliation)
> and only applies the minimal set of real DOM updates needed. If the state setter is called with
> the same value (by `Object.is` comparison), React can bail out and skip the re-render entirely.

*Evaluator:* `technical=9, accuracy=9, depth=8, next_action=next_concept` — "Correct, specific, and mentions the bail-out optimization most candidates miss."

**Q2 (technical / debugging, medium — escalated after strong Q1):**
> Let's go a level deeper: suppose a component re-renders on every keystroke in an unrelated
> sibling input, even though this component doesn't use that input's state. How would you debug that?

**A2:**
> First I'd check if the component is wrapped in `React.memo` — if not, and it's re-rendering because
> its *parent* re-renders on every keystroke, that's expected React behavior, not a bug. I'd check
> React DevTools' "highlight updates" to confirm the parent is the trigger. If it does need to stop,
> I'd either wrap the component in `memo`, lift the input's state down closer to where it's used,
> or use a context selector library if the state is in context.

*Evaluator:* `technical=8, problem_solving=9, depth=8, next_action=next_concept` — "Real debugging methodology, not just a definition. Ready to escalate further."

**Q3 (technical / JS async, medium):**
> What's the difference between how `Promise.all` and `Promise.allSettled` handle one failing promise in an array of five?

**A3:**
> `Promise.all` rejects immediately as soon as any one promise rejects — you lose the results of the
> other four even if they eventually succeed. `Promise.allSettled` always resolves once all five are
> done, and gives you an array of `{status, value}` or `{status, reason}` per promise, so you can see
> which succeeded and which failed without an early bailout.

*Evaluator:* `technical=9, accuracy=10, clarity=9, next_action=next_concept` — "Precise and complete."

**Q4 (technical / own project, medium→hard escalation):**
> Tell me about the open-source component you contributed. What was the trickiest tradeoff you had to make?

**A4:**
> I added a virtualized-list mode to a table component so it could render 10k+ rows without lagging.
> The tradeoff was between using a fixed row height (simple, fast, but couldn't support variable-height
> content) versus dynamic row height measurement (flexible, but requires an extra measurement pass and
> a resize observer, adding complexity and a small layout-shift risk on first render). I went with fixed
> height for the initial PR since 95% of the library's use cases had uniform rows, and left dynamic
> height as a documented follow-up.

*Evaluator:* `technical=9, problem_solving=9, communication=9, next_action=next_concept` — "Genuine tradeoff reasoning with real constraints, not hypothetical."

**Q5 (technical / CSS layout, hard — escalated again):**
> Given a flex container with three children where the middle child needs to grow to fill remaining space while the outer two stay fixed-width, how do you achieve that?

**A5:**
> Set `flex-shrink: 0` and a fixed `width` (or `flex-basis`) on the two outer children, and
> `flex-grow: 1` on the middle one (or just `flex: 1`). The middle child will absorb all remaining
> space in the row while the outer two hold their width.

*Evaluator:* `technical=8, accuracy=8, next_action=next_concept` — "Correct and concise."

**Q6 (closing question):**
> Last one — is there anything about your React or JavaScript experience you'd want a hiring manager to know that we haven't covered?

**A6:**
> I'd mention that I've started writing basic unit tests with React Testing Library for the
> components I build now, focused on testing behavior from the user's perspective rather than
> implementation details — it's changed how I structure components to be more testable.

*Evaluator:* `communication=8, next_action=end_interview`

---

## Coach Agent Report (abridged)

- **Overall Score:** 8.7 / 10 (87%) — **Readiness: Outstanding**
- **Hire Recommendation:** Strong Hire
- **Strengths:** Deep, accurate React internals knowledge; real debugging methodology; genuine
  tradeoff articulation from actual project work; concise, confident communication throughout.
- **Weaknesses:** Testing experience is early-stage and self-taught; hasn't yet worked with
  larger codebases or cross-team code review processes.
- **Top 5 Concepts to Study:** React Testing Library patterns, Context selector performance,
  Web accessibility (ARIA) basics, CSS Grid vs Flexbox decision-making, Basic Big-O for list rendering.
- **Motivational Closing Note:** "You're already answering at the level of someone with real
  production exposure, not just tutorials — the virtualized-list tradeoff answer in particular is
  the kind of thing that gets an intern noticed. Keep leaning into real projects over more courses."
