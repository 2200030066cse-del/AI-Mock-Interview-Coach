# Sample Transcript 2 — Weak Candidate

**Target Role:** Data Analyst
**Background:** "Took an intro Excel and SQL course. No professional experience yet."
**Focus Area:** Technical

---

## Planner Agent Output

```json
{
  "difficulty": "easy",
  "focus": "technical",
  "topics": [
    "Basic SQL SELECT/WHERE/GROUP BY reasoning",
    "Explaining a chart/metric to a non-technical audience",
    "Identifying a data quality issue in a described dataset",
    "Difference between mean and median and when each misleads",
    "Prioritizing which of several dashboard requests to build first"
  ],
  "strategy": "Keep difficulty at the floor throughout given the candidate's coursework-only background; focus on checking foundational SQL and basic statistical reasoning rather than advanced topics.",
  "reasoning": "No professional experience and only intro-level coursework signals a true beginner; plan conservatively around fundamentals."
}
```

---

## Interview

**Q1 (technical / SQL, easy):**
> If you wanted to find the total sales per region from a `sales` table with columns `region` and `amount`, what SQL query would you write?

**A1:**
> Um, I think you use SELECT and then GROUP BY region? Something like `SELECT region, amount FROM sales GROUP BY region`.

*Evaluator:* `technical=4, accuracy=3, next_action=follow_up` — "Right idea (GROUP BY) but the query is invalid: `amount` isn't aggregated. Worth a targeted follow-up before moving on."

**Q2 (follow_up, same topic):**
> You're close on the GROUP BY idea — but if you group by region while also selecting `amount` directly, most databases will reject that query. What would you need to wrap `amount` in to get a total per region?

**A2:**
> I don't know.

*Evaluator:* `technical=1, accuracy=1, next_action=give_hint` — "Honest 'I don't know,' not penalized as a red flag. Give a hint and move on rather than a second follow-up."

**Q3 (hint given, same topic, still easy):**
> Here's a hint: the function you need adds up all the values in a group — it starts with "S". With that, how would you rewrite the query?

**A3:**
> SELECT region, SUM(amount) FROM sales GROUP BY region

*Evaluator:* `technical=7, accuracy=8, next_action=next_concept` — "Correctly applied the hint. Credit the recovery, move to a new topic rather than lingering further."

**Q4 (technical / mean vs median, easy):**
> If your company's average (mean) employee salary is $95,000, does that tell you most employees earn close to that? Why or why not?

**A4:**
> I guess so? If the average is 95k then most people probably make around that.

*Evaluator:* `technical=3, accuracy=2, depth=2, next_action=follow_up` — "Misses that outliers (e.g. a few very high earners) can pull the mean up without most employees earning near it. Follow up to probe for the concept."

**Q5 (follow_up, same topic):**
> What if one executive earns $2,000,000 and everyone else earns close to $60,000 — what would that do to the average versus the median?

**A5:**
> Oh — the average would go up a lot because of that one big number, but the median would stay closer to $60,000 since it's just the middle value. So the average can be misleading with outliers.

*Evaluator:* `technical=7, problem_solving=6, next_action=next_concept` — "Got there with a concrete follow-up; genuine understanding once scaffolded, not just guessing."

**Q6 (closing question, difficulty de-escalated to floor after two early struggles):**
> Last question — if you had three dashboard requests from different teams and only time to build one this week, how would you decide which to prioritize?

**A6:**
> I'd probably ask my manager which one is most important and just do that one.

*Evaluator:* `problem_solving=3, depth=2, next_action=end_interview` — "Defers entirely to authority rather than showing any independent prioritization framework (urgency, impact, effort). Honest but underdeveloped answer."

---

## Coach Agent Report (abridged)

- **Overall Score:** 4.1 / 10 (41%) — **Readiness: Intermediate** (borderline Beginner)
- **Hire Recommendation:** Lean No Hire — needs more preparation
- **Strengths:** Recovers well once given a concrete hint or scenario (Q3, Q5); honest about
  gaps rather than bluffing.
- **Weaknesses:** Cannot independently write a correct aggregate SQL query; doesn't yet reason
  about statistical distributions without prompting; lacks a prioritization framework for
  ambiguous stakeholder requests.
- **Confidence Feedback:** Answers were hesitant and self-correcting ("I guess so?"), suggesting
  genuine uncertainty rather than overclaiming — a safer failure mode than false confidence, but
  worth building fluency to reduce hesitation.
- **Top 5 Concepts to Study:** SQL aggregate functions (SUM/COUNT/AVG) with GROUP BY, mean vs.
  median vs. outlier sensitivity, basic prioritization frameworks (impact vs. effort), reading
  query error messages, structuring an answer before speaking.
- **Motivational Closing Note:** "You recovered well every time you were given a concrete
  example instead of an abstract question — that's a real signal you can learn this, you just
  need more hands-on SQL and stats reps before your next interview. A few weeks of daily
  practice problems will close most of this gap."
