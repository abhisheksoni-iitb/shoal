# Playing synthetic users and reviewing edge cases

Language models asked to "be a user" drift toward being agreeable, articulate, goal-directed and average. The rules below exist to push against that. Follow them literally.

## Think-aloud sessions (`sessions.json`)

### Choosing who to play

1. Open `events.sample.jsonl` in the run folder. Each line is one simulated user with traits, situation, capabilities, outcome and path.
2. Pick 5 to 8 that together cover: every outcome that occurred (gave up, blocked, error, finished), every segment, and at least one awkward situation (flaky network, missing prerequisite, small screen).
3. At least two thirds must be users who did **not** finish. Failures carry the information.
4. Give each a name, a one-line life context and a concrete goal for today. Keep the simulated traits: a low-skill, impatient user stays that way.

### Playing one

Work step by step through the flow **as written in the spec**, not as you would fix it. At each step, as that person:

- What do I see, and what do I think it means? (Use only what the spec says is on screen. If the spec does not say, that is a finding: "the spec does not say what I see here".)
- What do I do, and what do I expect to happen?
- What would make me stop here?

Rules:

- **No insider knowledge.** The persona has not read the spec and does not know the team's words for things.
- **Stay in situation.** On a train with one hand, in a queue, mid-task, interrupted. People do not give a flow their full attention.
- **Low motivation is normal.** Most users have an alternative that already works. "This is fine, I'll do it the old way" is a legitimate ending.
- **Follow the simulated outcome unless the spec contradicts it.** If the simulation says this user was blocked at a step, find out what that moment is like. If you conclude the user would in fact get through, or fail somewhere else, say so in the session and note it: that is a signal the model is wrong.
- **One real objection beats five polite observations.** Do not pad with praise. Do not have the persona suggest features in product language.
- **No statistics from sessions.** Never write "most users would…". A session is one person.

### File format

```json
{
  "sessions": [
    {
      "persona": "Sana, occasional shopper, orders once a month",
      "segment": "occasional",
      "context": "mobile, good network, no saved card",
      "goal": "Top up the basics",
      "outcome": "blocked",
      "at": "confirm_pay",
      "moments": [
        {"step": "review_items", "kind": "question", "thought": "Last order was for a party. Can I untick things?", "severity": 2},
        {"step": "confirm_pay", "kind": "confusion", "thought": "It says pay with saved card but I never saved one.", "severity": 3}
      ],
      "quote": "It walked me all the way to the end and then shut the door.",
      "would_use_again": "no",
      "unmet_need": "Add a card here, or tell me at the start."
    }
  ],
  "themes": [
    {"title": "…", "evidence": "who hit it and how", "steps": ["confirm_pay"], "recommendation": "…"}
  ],
  "spec_gaps": [
    {"title": "…", "detail": "what the spec does not say", "severity": "high", "step": "review_items"}
  ]
}
```

- `outcome`: `success`, `abandoned`, `blocked`, `error_exit`.
- `step` must be a step id from the model, so sessions line up with the funnel.
- `kind`: `confusion`, `hesitation`, `question`, `error`, `frustration`, `workaround`, `delight`. All except `delight` count as trouble in the "where numbers and voices agree" table.
- `severity`: 1 noticed it, 2 slowed down, 3 stopped or nearly stopped.
- `themes`: 3 to 5, each backed by at least one session. `spec_gaps`: things the spec leaves undecided that a builder would have to guess.

## Edge-case review (`edge_review.json`)

`edge_cases.json` lists every checklist situation per step, `open` unless the model's `handles` says the spec covers it. Your job is to judge the important ones against the spec text.

For each case you review:

- `gap`: the spec does not say what happens, and it matters. Write what should happen in `expected` (one or two sentences, concrete).
- `handled`: the spec does say. Quote or point to where in `note`.
- `not_applicable`: cannot occur in this flow. Say why in `note`.

You may change `severity` with a reason. Review all `high` cases; review `med` cases where money, data loss, other people or irreversible actions are involved.

Then add what the checklist cannot know: cases specific to this domain. Prompts that usually find some:

- Money: refunds, partial payment, currency, limits, minimums, expired or declined methods.
- Other people: who else is affected, notified, or needs to approve; what they see.
- State that changes underneath: stock, price, permissions, availability, someone else editing.
- Limits: zero, one, the maximum, one past the maximum.
- Time: deadlines, expiry, things done twice, things done out of order, coming back much later.
- The first time and the hundredth time.
- Abuse and mistakes: wrong account, wrong recipient, accidental taps, deliberate misuse.

New cases use an id starting with `X-`:

```json
{
  "cases": [
    {"id": "E-place_order-double_submit", "verdict": "gap", "severity": "high",
     "expected": "A second press must not create a second order or charge."},
    {"id": "E-confirm_pay-progress_lost", "verdict": "not_applicable", "note": "Nothing is typed at this step."},
    {"id": "X-card-expired", "step": "confirm_pay", "step_name": "Confirms payment", "title": "Saved card is expired",
     "question": "When is the card checked, and what happens to the basket and slot if it fails?",
     "verdict": "gap", "severity": "high", "expected": "Check expiry when the sheet opens; on decline keep the user in the flow."}
  ]
}
```

After writing either file, run `shoal report <run folder>`.
