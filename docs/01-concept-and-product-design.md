# Shoal: rehearse a feature with synthetic users before real ones see it

Concept, product design and build notes. Written 12 Nov 2026 by Claude (Fable 5.2) for Abhishek Soni, expanding a MiroFish-style swarm simulation proposal written for the Kiroween 2026 hackathon.

## 1. The idea in one paragraph

You describe a feature you want to release. A shoal of synthetic users, built to look like your real mix of customers, then *uses* it: they find it or miss it, start, get confused, hit errors, lack a prerequisite, give up, or finish. From that you get, before writing code: a predicted funnel with honest ranges, where and why people drop, which single fix helps most, a verdict on each belief in your spec, a list of edge cases the spec forgot, a tracking plan, and the ranges to watch at launch. After launch you feed the real numbers back, score the prediction, and the next one gets better.

## 2. Where MiroFish stops

MiroFish (open source, original repo `666ghj/MiroFish`, built on CAMEL-AI's OASIS) takes documents, builds a knowledge graph, generates personas, and lets them post and reply on a Twitter-like and a Reddit-like platform. A report agent then summarises the discussion. That hackathon proposal adds bounded-confidence opinion maths so the agents do not all agree by round three.

That answers **"what will people say about this?"** It is a discourse simulator. For a product team it leaves the bigger questions open:

| Question a PM has before release | MiroFish-style discourse sim | What is needed |
|---|---|---|
| How many people will find it, start it, finish it? | No | A model of the flow and a population walking it |
| At which step do they drop, and why? | Indirectly, as complaints | Step-level behaviour with causes |
| Which change is worth building first? | No | One-at-a-time sensitivity on the flow |
| What happens offline, on a double tap, with an expired card? | Only if an agent happens to mention it | A systematic edge-case generator |
| Is my success hypothesis plausible? | No | Testable metrics with ranges |
| What should I track, and what number means "something is wrong"? | No | Tracking plan and expected ranges |
| Was the prediction any good? | No published validation that I could find | Scoring against real data |

Opinion is one input to usage (it drives discovery and trust). It is not usage.

## 3. The reframe

**From "release the spec into a debate" to "release the feature into a rehearsal".**

Three design decisions follow from that:

1. **An explicit feature model sits between the spec and the simulation.** The spec is compiled into a small JSON file: kinds of user, entry points, steps, what each step asks and gives, what can fail, what is required. Everyone can read it and argue with it. A wrong assumption is visible as a number in a file, not hidden in a prompt.
2. **Numbers come from code, words come from a language model.** The funnel, ranges, levers and verdicts come from a seeded simulation that anyone can re-run and get the same answer. The language model does what it is good at: reading the spec, playing individual users aloud, and judging edge cases. The report keeps the two apart.
3. **It is built to be proven wrong.** Every prediction ships with a range and the event that will measure it. After launch, `score` says how far off it was. That loop, not the simulation, is the long-term value.

## 4. What you get from one run

| Output | What it tells you | How it is produced |
|---|---|---|
| Headline numbers | Discovery, completion, adoption, errors, blocked, time to finish, each with a 5th to 95th percentile range | Simulation, 24 replications |
| Funnel | Share reaching each step, carry-on rate, loss, main reason, time | Simulation |
| Where and why people leave | Loss per step split by cause: effort, confusion, trust, fatigue, low motivation, out of time, blocked, error | Simulation, each exit tagged with its largest cause |
| By kind of user and situation | The same metrics per segment, device, network and any other condition | Simulation |
| Hypothesis verdicts | Supported, contradicted or uncertain for each belief in the spec | Share of replications in which it holds |
| Biggest levers | Points of adoption gained by each single change | One-at-a-time re-simulation |
| Variants | Alternative designs against the base, on the same users | Paired replications |
| Design gaps | Dead ends, unreachable steps, errors with no recovery, users blocked with nowhere to go, untracked steps | Reading the flow graph; no simulation needed |
| Edge cases | Every checklist situation per step, open unless the spec covers it; plus domain-specific ones | Checklist by step type + language-model review |
| Combinations | The smallest set of test situations covering every pair of conditions | All-pairs generation |
| What the users said | Think-aloud sessions, themes, gaps in the spec | Language model in persona, under strict rules |
| Where numbers and voices agree | Steps flagged by both the simulation and the sessions | Cross-check |
| Tracking plan and launch watchlist | Events to add, and the range each step should land in | From the model and the replications |
| Fidelity score (after launch) | How close the prediction was, step by step | Comparison with real numbers |

## 5. How it works

```
   spec / PRD / idea
          │   (language model: compile, state assumptions)
          ▼
   ┌──────────────────┐
   │  feature model   │  JSON: segments, entry points, steps, requirements,
   │  (feature.json)  │  errors, events, dimensions, hypotheses, variants
   └────────┬─────────┘
            │
   ┌────────┼──────────────┬─────────────────────┬──────────────────────┐
   ▼        ▼              ▼                     ▼                      ▼
 lint    simulate       edge cases          think-aloud            calibrate
 (graph) (seeded        (checklist +        sessions               (real data in,
         agents)        all-pairs)          (language model)       before launch)
   │        │              │                     │
   │        ▼              ▼                     ▼
   │   analytics       review by            themes, gaps
   │   ranges, levers, language model
   │   hypotheses,
   │   variants
   └────────┴──────────────┴─────────────────────┘
                           ▼
                 report.html / report.md / summary.json
                           │
                  launch → real numbers → score → better priors
```

### 5.1 The feature model

Full reference: `skill/shoal/references/feature-model.md`. In short:

- **Segments**: kinds of user, each with a share, four traits (motivation, skill, patience, trust), situations (device, network, anything else) and capabilities (has a saved card, is an admin).
- **Entry points**: where the feature is met, with a discovery rate.
- **Steps**: one thing the user does or waits for. Each has a type, effort, clarity, visible value, time, error rate, what it requires, where errors lead, which events it fires, and which edge cases the spec covers.
- **Dimensions**: conditions worth combining for testing.
- **Hypotheses**: beliefs as metric, operator, number.
- **Variants**: alternative designs as patches.

The rule when writing it: model what the spec says, not what a good team would build. Gaps must stay gaps.

### 5.2 The simulation

Each synthetic user is drawn from a segment, with traits that vary around the segment average, a situation and a set of capabilities. They may never notice the feature. If they start, then at each step:

1. Missing a requirement → they go to the fallback, or are blocked.
2. Time passes (longer for low skill and poor networks).
3. An error may occur; whether they retry depends on patience and on whether the spec allows recovery.
4. They carry on with a probability that rises with motivation, visible value and trust, and falls with effort, unclear screens, earlier errors and fatigue. If they quit, the exit is tagged with its largest cause.

All of it is about 320 lines in `shoal/sim.py`, with the formula written out in the model reference. Nothing is learned or hidden.

**Ranges.** The run is repeated 24 times. Each time the users are different *and* every guessed input is nudged (effort, clarity and value by up to ±0.1; error and discovery rates by up to ±20%). The reported range therefore covers both chance and "we guessed the inputs". It does not cover a wrong model, which is why scoring exists.

**Calibration.** Any step can be pinned to a real carry-on rate (`observed_continue`) and any entry point to a real discovery rate. Pinned steps reproduce the real number and are no longer nudged. A feature that reuses three existing steps and adds two new ones is then mostly measurement and only partly guess.

### 5.3 Edge cases, from four directions

1. **Reading the flow** (`lint`): dead ends, unreachable steps, loops, errors with no recovery, steps that need something some users lack with no way to get it, steps that fire no event. These are true however users behave.
2. **Checklist by step type**: 14 whole-flow situations and 3 to 10 per step type (input, external call, wait, decision, view, success): empty input, double submit, timeout, stale data, back button, session expiry, screen reader and so on. Each is open unless the model says the spec covers it.
3. **Combinations**: for the conditions you list (basket state × card state × slot state × network), the smallest set of situations in which every pair appears together. Fourteen combinations instead of 108 in the sample.
4. **Domain review by the language model**: verdict on each important case against the spec text (gap, handled, not applicable) with the expected behaviour, plus cases the checklist cannot know (minimum order value, expired card, partial reorder).

The simulation adds a fifth: it shows how many users each gap actually hits (in the sample, about nine in ten new customers who start are blocked).

### 5.4 Think-aloud sessions and the agreeableness problem

Research on language models as stand-ins for people is consistent on the risks: answers cluster around the typical response, so variety is lost (arXiv 2507.02919); small setup choices can change the conclusion (Advances in Methods and Practices in Psychological Science, 2026); matching humans on some tasks does not rule out systematic bias, and calibration against real data is the proposed remedy (arXiv 2602.15785). In Amazon's AgentA/B study, 1,000 agents shopping on a live site were more goal-directed than people and took fewer actions (arXiv 2504.09723).

Shoal's response is structural:

- Sessions never produce numbers. They find problems; they do not count them.
- Personas are taken from the simulation's own sample of users, so two thirds are people who failed, with their low skill and low patience kept.
- The protocol (`skill/shoal/references/persona-protocol.md`) bans insider knowledge, requires a real situation, treats "I'll do it the old way" as a normal ending, and forbids padding with praise.
- Each remark is tied to a step id, so sessions can be laid against the funnel.

### 5.5 Where numbers and voices agree

For each step, the report compares simulated loss with how many sessions had trouble there. Both high: fix first. Numbers only: re-check the step's scores. Voices only: the model is probably underrating that step. Disagreement is useful; it tells you which half to distrust.

### 5.6 The learning loop

```
predict (run) → launch with the tracking plan → export real funnel → score → calibrate → predict the next feature
```

`score` reports the mean error per step, a fidelity figure, and coverage: the share of real numbers that fell inside the predicted range. Low coverage means the ranges were too narrow, and says so. Over many features this becomes a library of base rates for *your* product and users (how discoverable a home banner really is, what a five-field form really costs), which is the part a competitor cannot copy.

### 5.7 Word of mouth

The rehearsal above treats every user as alone and the launch as one moment. Add a `spread` block and the launch is followed over several periods, with users joined in a network of contacts.

1. The feature's own entry points reach people over the first few periods (`rollout_periods`), not all at once.
2. Everyone who uses the feature forms an opinion from what happened to them. Finishing smoothly gives a high opinion; giving up, being blocked or hitting an error gives a low one.
3. Each period, some of them tell a few contacts. The chance depends on what happened (people stopped by an error talk more than people who drifted away) and fades with time.
4. A listener's opinion moves toward what they hear, but only if it is not too far from their own. This is the bounded-confidence rule (Deffuant and Weisbuch) that the MiroFish proposal used to stop its agents all agreeing. Here it has a practical meaning: someone who heard two bad reports stops listening to the enthusiast.
5. Opinion feeds the flow model's two existing inputs. A good opinion can make someone try the feature on a recommendation; a bad one lowers the chance they tap the entry point when it reaches them; either way it shifts how much they trust the feature once inside.

The report shows adoption with and without talk and the range of the difference, the period-by-period table, which kinds of user it changes, how each design does once talk is counted, and which talk assumption the answer depends on. `shoal spread <model>` gives the same result on its own.

What it does not do: there is no language model in this step, so nobody writes posts or argues. It models how much is said and which way it pushes, not what is said. The talk rates and the network are hand-set defaults. With no talk and a one-period rollout the run reproduces the launch-day numbers exactly, which is tested.

## 6. Fidelity ladder

| Level | What the users act on | Needs | Status |
|---|---|---|---|
| 0. Flow reading | The flow graph | A spec | **Built** (`lint`, `edges`) |
| 1. Model rehearsal | The feature model | A spec | **Built** (`run`) |
| 2. Persona walkthroughs | The spec, step by step, in character | A language model | **Built** as the skill's steps 4 and 5 |
| 3. Calibrated rehearsal | The model, pinned to real rates | Analytics for similar steps | **Built** (`calibrate`, `score`); connectors not built |
| 4. Prototype driving | A real prototype or staging URL, through a browser | A build; browser agents | Not built. UXAgent and AgentA/B show the approach works on live sites |
| 5. Social spread | Opinion and word of mouth feeding discovery and trust | A `spread` block in the model | **Built** in 0.3.0 (`spread`), with hand-set talk rates. See 5.7 |

Levels 0 to 3 and level 5 need no build of the feature, which is the point: they run at spec time, when changes are cheap.

## 7. Skill, tool or platform?

All three, in this order, because each earns the next.

**1. Skill (built).** The natural home. The hard part of the job, turning a messy spec into a model, playing users, judging edge cases, is language-model work that an agent already in your editor or chat can do with your files and your analytics tools at hand. It costs nothing to distribute and needs no API key: the agent is the model. `skill/shoal/` installs with one script.

**2. Engine and command line (built).** Standard-library Python, no dependencies, no network. This is what makes the numbers trustworthy and lets the same rehearsal run in a terminal, a CI job ("fail the PR if the spec has a dead end or an untracked success step") or another agent.

**3. Local web app (built, basic).** `shoal serve` lists rehearsals, runs new ones from a pasted model, and compares two. Enough for a PM who does not live in a terminal.

**4. Hosted platform (not built; only worth it later).** A platform is justified by what a skill cannot hold: shared history across a team, connectors that pull real funnels from PostHog or Amplitude and calibrate automatically, a base-rate library that improves with every launch, prototype-driving agents at scale, and review workflows. The asset is the calibration data, not the simulator. Building the platform before there are scored predictions would be building the shell without the thing that makes it valuable.

Recommendation: use the skill on real features now, score every one after launch, and let the accumulating scores decide whether a platform is warranted.

## 8. Sample run: one-tap reorder

Spec: `examples/one-tap-reorder/spec.md` (grocery app; repeat the last order in a few taps). Model: `feature.json` next to it. 5,000 synthetic users, seed 7, 24 replications, about 3 seconds.

| Metric | Predicted | Range |
|---|---:|---:|
| Adoption (of everyone eligible) | 10% | 9 to 12% |
| Discovery | 28% | 25 to 32% |
| Completion (of those who started) | 35% | 32 to 39% |
| Blocked | 38% | 35 to 41% |
| Median time to finish | 68s | 64 to 72s |

- All four hypotheses in the spec were contradicted (60% completion, 25% adoption, under a minute, 10% of new customers).
- 71% of eligible users never see the feature. About nine in ten new customers who start are blocked, most at the first step because they have no past order, and the spec does not say what they see.
- Customers without a saved card walk to the second-last step and are stopped. Giving them a way through is the largest single lever (+3.3 points of adoption if frictionless; +1.7 points, better in 96% of replications, for the realistic "add a card inline" variant).
- Pre-selecting the usual slot: +0.8 points, better in 83% of replications, so no clear difference on adoption alone.
- Offline users: none finish.
- Edge cases: 62 situations checked, 14 confirmed gaps after review (double submit, timeout, partial success, stale prices, expired card, partial reorder, minimum order value), 44 still open, 4 handled.
- Flow reading alone found: two requirements with no fallback, an order-placement error with no defined recovery, and a payment step that fires no event.

Open `examples/one-tap-reorder/runs/sample/report.html` for the full report. These figures describe a made-up feature with guessed inputs; they show what the tool produces, not a finding about grocery apps.

## 9. Limits, stated plainly

- A prediction from a model is not a measurement. The uncalibrated numbers are hypotheses with reasons attached.
- The ranges cover chance and input wobble, not a missing step or a missing kind of user.
- Rank order (worst step, best fix) is more reliable than level (10% vs 14%).
- The behaviour rule is simple and hand-set. It has not yet been fitted to real launches. Until several runs have been scored, treat the weights as reasonable defaults, not as validated.
- Synthetic sessions inherit the known biases of language models playing people. They can show that a problem exists, never that none does.
- None of this replaces talking to five real users. It decides what to ask them and what to fix before you waste their time.

## 10. Landscape

| | What it does | Difference |
|---|---|---|
| MiroFish / OASIS | Thousands of agents discussing a scenario on simulated social platforms | Predicts discourse, not usage. Complementary: could drive Shoal's discovery and trust inputs |
| AgentA/B, UXAgent (research) | Agents drive real web pages for A/B and usability tests | Needs a built page. Shoal works from the spec; these are the model for its level 4 |
| Synthetic Users, Uxia, Articos, Brox.ai | AI personas for interviews and UX feedback | Mostly qualitative. Shoal ties sessions to a quantified, reproducible funnel and to edge cases |
| Aaru, Vectorial | Populations modelled from real data to predict responses | Closest in ambition; proprietary and data-heavy. Shoal is transparent, runs locally, and starts without data |
| Analytics tools (PostHog, Amplitude) | Measure what happened | Shoal is the "before" to their "after", and uses their data to calibrate |

Sources for this section were a short web search on 12 Nov 2026; company details come from secondary coverage and were not checked against primary pages.

## 11. Roadmap

1. **Use it on three real features and score them.** Nothing else matters more.
2. **Analytics import**: pull step counts from PostHog or Amplitude into the `calibrate` and `score` CSV automatically.
3. **Base-rate library**: store scored steps by type (banner discovery, short form, payment) and suggest them when writing a new model.
4. **Fit the behaviour weights** to scored launches instead of hand-set values.
5. **MCP server** so any agent can call lint, run and report as tools.
6. **CI check**: lint specs in pull requests.
7. **Prototype driving** (level 4): browser agents on a staging URL, writing real events into the same report.
8. **Social spread** (level 5): done in 0.3.0 as the `spread` block, with bounded-confidence opinion and hand-set talk rates. Still open: fit the talk rates to a real launch, and let a language model write what is said.
9. **Headless language-model mode** (API key) so the qualitative steps run without an agent session.

## 12. How it fits next to MiroFish

Shoal can stand as the "usage mode" of MiroFish Swarm: the same promise (pre-mortem before launch) with a second, more concrete engine. It follows the same lifecycle as the hackathon's agent foundation: perception (spec → model), cognition (simulate), verification (lint, hypotheses, scoring), execution (report), audit (seeded, reproducible runs with the exact model saved beside each report).

## Sources

- [MiroFish overview (emelia.io)](https://emelia.io/hub/mirofish-ai-swarm-prediction), [MiroFish write-up (themenonlab)](https://themenonlab.blog/blog/mirofish-swarm-intelligence-prediction-engine), [fork README](https://github.com/amadad/mirofish)
- [AgentA/B: Automated and Scalable Web A/B Testing with Interactive LLM Agents (arXiv 2504.09723)](https://arxiv.org/html/2504.09723v1)
- [UXAgent: Simulating Usability Testing of Web Design with LLM Agents (arXiv 2504.09407)](https://arxiv.deeppaper.ai/papers/2504.09407v2?locale=en)
- [Guidelines for using silicon samples in marketing research (NIM)](https://www.nim.org/en/publications/detail/using-silicon-samples-in-marketing-research)
- [LLM-generated samples and representativeness (arXiv 2507.02919)](https://web3.arxiv.org/pdf/2507.02919)
- [Statistical calibration of LLM simulations (arXiv 2602.15785)](https://arxiv.org/html/2602.15785v1)
- [Analytic flexibility in silicon samples (AMPPS)](https://www.psychologicalscience.org/journals/ampps/25152459261461505/)
- [Synthetic users landscape (AIMultiple)](https://aimultiple.com/synthetic-users), [Vectorial (Sovereign Magazine)](https://www.sovereignmagazine.com/article/synthetic-users-vectorial)
