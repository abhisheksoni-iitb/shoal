---
name: shoal
description: Rehearse a feature with synthetic users before real ones see it. Turns a feature idea, PRD or spec into an explicit feature model, runs thousands of simulated users through it, and reports predicted funnel and adoption with ranges, where and why people drop, which fix helps most, hypothesis verdicts, edge cases the spec does not cover, a tracking plan and a launch watchlist. Adds persona think-aloud walkthroughs and an edge-case review. Use when asked to test, simulate, rehearse, pre-mortem or stress-test a feature, flow, onboarding, pricing step or product idea; to predict usage or drop-off before launch; to find edge cases in a spec; to compare design variants before building; or when the user says "shoal", "synthetic users", "simulate users" or "MiroFish for features". After launch, use it to calibrate with real funnel numbers and score how good the prediction was.
---

# Shoal: feature rehearsal

Shoal answers "what will happen when people use this?" before anything ships. It has two halves that you must keep separate:

- **Numbers come from code.** A seeded simulation over an explicit feature model. Reproducible, every assumption readable. Never invent, round up or "adjust" a number yourself; quote what the engine printed.
- **Words come from you.** You write the feature model from the spec, play synthetic users in think-aloud sessions, and review edge cases. This is judgment and is labelled as such in the report.

Everything Shoal produces is a prediction to check, not a measurement. Say so once, plainly, when you present results.

## The engine

```bash
SHOAL="$HOME/.claude/skills/shoal/scripts/shoal.sh"
"$SHOAL" init <folder>                 # starter feature.json
"$SHOAL" lint <feature.json>           # model errors + design gaps, no simulation
"$SHOAL" run <feature.json> --out <run folder>   # simulate, analyse, write report (add --quick while iterating)
"$SHOAL" report <run folder>           # rebuild after adding sessions.json / edge_review.json (numbers do not change)
"$SHOAL" edges <feature.json>          # edge-case list only
"$SHOAL" calibrate <feature.json> <observed.csv>   # pin steps to real conversion numbers
"$SHOAL" score <run folder> <observed.csv>         # after launch: predicted vs actual
"$SHOAL" serve --root <folder>         # local web app at http://127.0.0.1:8787
```

Python 3.9+, standard library only, no network, no API key. A full run takes a few seconds.

## Workflow

Work through these in order. Do not skip step 2: a wrong model gives confident wrong numbers.

### 1. Gather the input

You need: what the feature does, who it is for, where users first meet it, the steps, and what "success" is. Read the PRD/spec/design if one was given. If the user gave only an idea, write a half-page spec yourself first and state the assumptions you made. Ask a question only if the main flow or the target user is truly unknowable from what you have; otherwise proceed and list assumptions.

If real data exists for a similar flow (analytics, a previous launch, support tickets), get it now. It is worth more than any guess.

### 2. Write the feature model

Read `references/feature-model.md` (field reference and scoring guide) before writing. Then write `feature.json` in the user's project (a folder such as `shoal/<feature-id>/`), not in the skill folder.

Rules that matter most:

- **Model the flow the spec actually describes**, including the unhappy branches it mentions. Do not add recovery paths, fallbacks or handled edge cases the spec does not state. Gaps must stay visible: that is the product.
- **One step = one thing the user does or waits for.** Typically 4 to 12 steps.
- **Segments are kinds of user that behave differently**, with shares that add to 1. Always include the least-prepared realistic user (new, low skill, missing a prerequisite).
- **Score effort, clarity and value from the user's side, per the scoring guide.** When unsure, score less favourably; teams overrate their own clarity.
- **Discovery is usually the largest lever and the most overrated.** Use the guide's base rates unless there is data.
- **Turn every belief in the spec into a hypothesis** with a metric, operator and number. If the spec has none, write 2 to 4 that the team would care about and mark them as yours.
- **If the user is choosing between designs**, add them as `variants` in the same model so they run on the same synthetic users.
- **Use real numbers where they exist**: set `observed_continue` on steps and `discovery` on entry points, or run `calibrate` with a CSV.

Then run `lint`. Fix every error. Do **not** "fix" design findings (blocked users, no recovery, not tracked) by editing the model: those are results to report.

### 3. Run it

```bash
"$SHOAL" run <feature.json> --out <project>/shoal/<feature-id>/runs/<YYYY-MM-DD-label>
```

Read the printed summary. Sanity-check before going further: do the step scores you gave explain the biggest drop? If a number looks absurd, the cause is nearly always a mis-scored step or a wrong share; correct the model and say what you changed.

### 4. Walk it as users (qualitative sessions)

Read `references/persona-protocol.md`, then write `sessions.json` into the run folder: 5 to 8 think-aloud sessions, themes and spec gaps. Pick personas from the simulation's own sample journeys (`events.sample.jsonl`) so the sessions cover the outcomes that actually occurred, weighted toward failures.

### 5. Review the edge cases

Open `edge_cases.json` in the run folder. For every **high** severity open case, and any other you judge important, decide against the spec: `gap` (spec does not say what happens), `handled`, or `not_applicable`. Add cases the checklist missed, specific to this feature's domain (money, permissions, other people affected, time, limits). Write `edge_review.json` as described in `references/persona-protocol.md`. Also look at the combinations table and call out any combination the spec clearly breaks on.

### 6. Rebuild and present

```bash
"$SHOAL" report <run folder>
```

Then tell the user, briefly and in this order:

1. The one-line answer: predicted adoption with its range, and whether their hypotheses held.
2. The biggest loss and why; the single best fix and what it is worth.
3. Confirmed gaps in the spec (count, and the 3 most serious).
4. Where numbers and voices agree (fix first) and where they disagree (check the model).
5. One sentence on limits: predictions from a model; ranks are more reliable than levels.
6. The path to `report.html`.

Do not paste the whole report into chat.

### 7. After launch (when real numbers exist)

Export a CSV `id,entered,continued` per step (and `entry:<id>` rows for discovery), then `score` the old run and `calibrate` the model for the next one. Report fidelity and coverage honestly; a low coverage means the ranges were too narrow, so say so.

## Honesty rules

- Never present simulated figures as user research or as measured data.
- Always give the range with the number.
- Rank order is more trustworthy than absolute level; lead with ranks when the model is uncalibrated.
- A synthetic session can show that a problem exists. It cannot show that none exists.
- If you changed the model after seeing results, say what and why.
- If the spec is too thin to model, say that instead of inventing a flow.

## Files in a run folder

`report.html` (open this), `report.md`, `summary.json` (all numbers), `model.json` (the exact model used), `edge_cases.json`, `events.sample.jsonl` (300 individual simulated journeys), `lint.json`, plus your `sessions.json` and `edge_review.json`.
