# Changelog

## 0.3.0 (15 Nov 2026)

Word of mouth: level 5 of the fidelity ladder, the part of MiroFish that Shoal had left out.

- New model block `spread`. The launch is followed over several periods instead of one moment. People who used the feature form an opinion from what happened to them and tell some of their contacts; a listener's opinion moves toward what they hear only when it is not too far from their own (bounded confidence, after Deffuant and Weisbuch). Opinion then feeds the two inputs the flow already had: whether someone finds the feature, and how much they trust it when they do. `"spread": true` uses the defaults.
- The report gets a section "Word of mouth": adoption with and without talk and the range of the difference, a period-by-period table, who it changes by segment, how each design does once talk is included, and a table of which talk assumption the answer depends on.
- New command `shoal spread <model>` for the word-of-mouth result alone. It works on a model with no `spread` block by using the defaults.
- Variant and scenario patches can change `spread`.
- Lint checks the block and notes when the rollout is one period long, because then bad word of mouth cannot reach anyone before the feature does.
- The simulation's walk through the flow is now a function (`sim.walk`) that both the launch-day run and the word-of-mouth run call. Launch-day numbers are unchanged: every example model gives byte-identical results to 0.2.2 on two seeds, and with no talk and a one-period rollout the word-of-mouth run reproduces the launch-day run exactly (a test holds this).
- The talk rates and the network are hand-set defaults, not measurements. The first sample run (`examples/one-tap-reorder/runs/word-of-mouth/`) says word of mouth has no clear effect on that feature and that the answer depends mostly on how much happy users talk.
- 45 tests.

## 0.2.2 (14 Nov 2026)

- New step field `otherwise`: where users go when they do not act at a step and the flow has a second route for them (a reminder email, another channel). Needed to model an ask followed by a reminder; before, not acting always meant leaving. The funnel shows the share sent on.
- `--rep-users` sets the size of each replication (default 1,500). Raise it for rare outcomes, where a few percent of 1,500 users is mostly noise.
- Shares under 10% are shown with one decimal in the headline, ranges and funnel.
- 33 tests.

## 0.2.1 (14 Nov 2026)

- New step field `background` for `wait` and `external` steps the user does not have to watch (an emailed code, a review, a job that runs meanwhile). The waiting cost added in 0.2.0 applied to every wait, which was wrong for these: re-running an earlier real rehearsal halved its predicted adoption because an emailed code and an approval were treated like a spinner. Found by re-running old models on the new engine before closing.
- Lint flags a watched wait of 15 seconds or more (`long-wait`).
- The JobPilot daily-apply and ShadowMux examples mark their off-screen steps as background. Their run folders dated 13 Nov were produced with 0.1.0 and are kept as they were.
- 30 tests.

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

- Waits now cost something. On `wait` and `external` steps, time beyond about ten seconds times the user's patience makes people leave, and the report names the cause ("the wait was too long"). Before, a 3-second and a 40-second wait kept the same share of users unless the session ran out of time. (0.2.1 limits this to waits the user has to watch.)
- Going round a loop tires users: fatigue counts every step taken, repeats included. Before, only distinct steps counted, so a retry loop could run until the step limit.
- A drop at a step pinned to a real rate is labelled "measured, cause not modelled" instead of being given a cause from scores the step does not use.

Checks

- Lint applies every variant and scenario and reports a patch that cannot be applied or that breaks the model.
- 28 tests (16 in 0.1.0).

Guidance added to the skill: model today's flow first when the feature changes an existing one; give a new step the measured rate of its nearest relative and put the hoped-for improvement in a scenario.

## 0.1.0 (12 Nov 2026)

First version: feature model, lint, seeded simulation, ranges, hypotheses, levers, variants, edge cases and combinations, reports, calibration, scoring, local web app, Claude skill.
