# Changelog

## 0.2.0 (14 Nov 2026)

Driven by the first rehearsal that pinned an existing flow to measured numbers and compared new designs against it.

New in the model

- `scenarios`: the same design under other assumptions about users and the world. Same patch format as variants. The report gets a section "If the guesses are wrong". A scenario can be tied to one variant with `"on"`.
- `feature.volume`: a measured count of eligible users per period, so the report gives counts beside shares.
- Several success steps: the report shows how finishers divide between them, and how each variant and scenario moves each ending.
- `step_reach:<step id>` as a hypothesis metric (share of starters who get that far). `segment` now works with step metrics too; before, it was ignored for `step_continue`.
- Hypotheses can be tied to a variant with `"on"`, so they can name steps that exist only in that design.
- `observed_continue` can be one rate per segment.
- Variant patches can add entry points (`add_entry_points`) and can add or remove success steps.
- `score` also reads `reach:<step id>` and `entry:<entry id>` rows.

Changed behaviour (numbers from 0.1.0 runs will differ slightly)

- Waits now cost something. On `wait` and `external` steps, time beyond about ten seconds times the user's patience makes people leave, and the report names the cause ("the wait was too long"). Before, a 3-second and a 40-second wait kept the same share of users unless the session ran out of time.
- Going round a loop tires users: fatigue counts every step taken, repeats included. Before, only distinct steps counted, so a retry loop could run until the step limit.
- A drop at a step pinned to a real rate is labelled "measured, cause not modelled" instead of being given a cause from scores the step does not use.

Checks

- Lint applies every variant and scenario and reports a patch that cannot be applied or that breaks the model.
- 28 tests (16 in 0.1.0).

Guidance added to the skill: model today's flow first when the feature changes an existing one; give a new step the measured rate of its nearest relative and put the hoped-for improvement in a scenario.

## 0.1.0 (12 Nov 2026)

First version: feature model, lint, seeded simulation, ranges, hypotheses, levers, variants, edge cases and combinations, reports, calibration, scoring, local web app, Claude skill.
