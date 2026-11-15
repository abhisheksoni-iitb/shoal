# Shoal rehearsal: One-tap reorder, with word of mouth

5,000 synthetic users, seed 7, 24 replications, 2026-11-15 11:33.

## What it says

- Out of 100 active customers, about 10 are predicted to finish (range 9–12%).
- At 40,000 active customers a week, that is about 4,000 a week (range 3,411 to 4,605).
- The biggest loss is at “Opens the reorder sheet”: 22% of everyone who started leaves there, mostly because they could not proceed (blocked).
- 71% of eligible users never start: they do not see the entry point, or see it and pass. Discovery, not the flow, caps adoption.
- Best single fix: Give users without saved_card a way through 'Confirms payment with the saved card' (+3.3 points of adoption).
- Word of mouth: no clear effect over 8 weeks (10.8% adoption without talk, 12.3% with; change between -0.1 and +1.3 points).
- 9 high-severity edge cases are not covered by the spec (not yet reviewed).
- Hypothesis H1 looks wrong: “At least 60% of customers who open the sheet place the order.” (predicted 35%).
- Hypothesis H2 looks wrong: “At least 25% of all active customers use it.” (predicted 10%).
- Hypothesis H3 looks wrong: “It takes under a minute.” (predicted 68s).
- Hypothesis H4 looks wrong: “At least 10% of new customers use it.” (predicted 1%).

## Headline numbers (predicted)

| Metric | Predicted | Range |
|---|---:|---:|
| Adoption (of everyone eligible) | 10% | 9–12% |
| Discovery (saw it and started) | 28% | 25–32% |
| Completion (of those who started) | 35% | 32–39% |
| Hit at least one error | 8% | 5–10% |
| Blocked (could not proceed) | 38% | 35–42% |
| Median time to finish | 68s | 64–72s |

## Hypotheses

| ID | Hypothesis | Predicted | Verdict |
|---|---|---:|---|
| H1 | At least 60% of customers who open the sheet place the order. | 35% | contradicted |
| H2 | At least 25% of all active customers use it. | 10% | contradicted |
| H3 | It takes under a minute. | 68s | contradicted |
| H4 | At least 10% of new customers use it. | 1% | contradicted |

## Funnel

| Step | Reached | Carried on | Left here | Main reason |
|---|---:|---:|---:|---|
| Opens the reorder sheet | 100% | 78% | 22.3% | Blocked |
| Reviews the items and prices | 78% | 95% | 3.8% | Too much effort |
| Replaces or removes out-of-stock items | 28% | 75% | 7.0% | Too much effort |
| Picks a delivery slot | 67% | 89% | 7.4% | Too much effort |
| Confirms payment with the saved card | 60% | 69% | 18.2% | Blocked |
| Order is placed | 41% | 90% | 4.2% | Error |
| Sees the confirmation | 37% | — | — |  |

## Biggest levers

| Change | Adoption |
|---|---:|
| Give users without saved_card a way through 'Confirms payment with the saved card' | +3.3 pts |
| Make the 'Home banner' entry point easier to find | +3.1 pts |
| Make the 'Sunday push notification' entry point easier to find | +1.4 pts |
| Give users without past_order a way through 'Opens the reorder sheet' | +0.7 pts (within noise) |
| Make the 'Reorder button in order history' entry point easier to find | +0.7 pts (within noise) |
| Cut the effort of 'Confirms payment with the saved card' | +0.5 pts (within noise) |
| Make 'Confirms payment with the saved card' clearer | +0.5 pts (within noise) |
| Make 'Replaces or removes out-of-stock items' clearer | +0.4 pts (within noise) |

## Variants

| Variant | Adoption change | Beats base in | Verdict |
|---|---:|---:|---|
| Usual slot pre-selected | +0.9 pts | 88% | no clear difference |
| Add a card inline | +1.9 pts | 100% | better |

## If the guesses are wrong

| Scenario | Adoption | Range | Change from base |
|---|---:|---:|---:|
| As modelled | 10.0% | 9–12% | — |
| Fewer customers have a saved card than we think | 7.6% | 6.1–9.0% | -2.4 pts |
| The home banner is noticed twice as often | 16.7% | 15–19% | +7.0 pts |

## Word of mouth (8 weeks)

- Word of mouth: no clear effect over 8 weeks (10.8% adoption without talk, 12.3% with; change between -0.1 and +1.3 points).
- 290 of 5,000 users heard a recommendation before trying; 93 tried it because of one and 60 finished.
- 49% of what was said was negative; 234 people who never tried it ended up thinking worse of it than they started.
- The answer depends most on this assumption: happy users talk twice as much would move adoption by +1.0 points.

| Week | Started on their own | Started on a recommendation | Finished | Adoption with talk | Without talk | Said: good / bad |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 405 | 17 | 157 | 3.1% | 3.0% | 68 / 66 |
| 2 | 357 | 18 | 156 | 6.3% | 5.6% | 92 / 86 |
| 3 | 359 | 20 | 148 | 9.2% | 8.2% | 114 / 114 |
| 4 | 355 | 20 | 146 | 12.1% | 10.8% | 116 / 106 |
| 5 | 0 | 7 | 3 | 12.2% | 10.8% | 48 / 48 |
| 6 | 0 | 3 | 1 | 12.2% | 10.8% | 22 / 32 |
| 7 | 0 | 7 | 5 | 12.3% | 10.8% | 18 / 10 |
| 8 | 0 | 1 | 1 | 12.3% | 10.8% | 10 / 16 |

| If instead | Adoption | Change |
|---|---:|---:|
| Happy users talk twice as much | 12.4% | +1.0 pts |
| Each person who talks tells twice as many people | 12.1% | +0.7 pts |
| Unhappy users say nothing | 11.3% | -0.1 pts (within noise) |
| The feature reaches everyone in the first week | 11.3% | -0.1 pts (within noise) |
| Unhappy users talk twice as much | 11.4% | +0.0 pts (within noise) |
| Listeners accept any opinion, however far from their own | 11.4% | +0.0 pts (within noise) |

| Design | Without talk | With talk | Talk adds |
|---|---:|---:|---:|
| Base design | 10.5% | 11.4% | +0.9 pts |
| Usual slot pre-selected | 11.4% | 12.3% | +0.9 pts |
| Add a card inline | 12.5% | 13.2% | +0.7 pts |

## Design gaps

- 'Opens the reorder sheet' needs past_order. About 21% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).
- 'Confirms payment with the saved card' needs saved_card. About 40% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).
- 'Order is placed' can fail (4%) but the model says nothing about what happens next. Fix: Define on_error: can the user retry, or where do they land?

## High-severity edge cases not covered (9)

- [open] Whole flow: Signed out while in the flow. After signing in again, do they return to where they were?
- [open] Picks a delivery slot: Typed data lost on error or navigation. If the step fails or the user steps back, is what they typed kept?
- [open] Confirms payment with the saved card: Typed data lost on error or navigation. If the step fails or the user steps back, is what they typed kept?
- [open] Order is placed: No connection. What does the user see offline, and is their work kept until they are back?
- [open] Order is placed: No answer in time. After how long does it give up, and what can the user do then?
- [open] Order is placed: The other system returns an error. Is the message specific, and is there a retry or another route?
- [open] Order is placed: Button pressed twice. Can a double press create two records, charges or messages?
- [open] Order is placed: Half of it worked. If only part succeeded, what state is the user left in and how do they finish?
- [open] Order is placed: Data changed since the screen loaded. If price, stock, permissions or status changed meanwhile, who wins?

## Limits

- These are predictions from a model of your feature, not measurements of real people. Treat every number as a hypothesis to check.
- The ranges cover random variation and a ±10% wobble on the guessed inputs. They do not cover a wrong model (a missing step, a missing kind of user).
- Language models asked to play users tend to be more agreeable, more goal-directed and less varied than real people. Qualitative sessions find problems; they do not prove their absence.
- Rank order (which step is worst, which fix helps most) is more reliable than absolute levels. Calibrate with real data when you have any, and score the run after launch.
- The word-of-mouth section rests on guessed talk rates and a random network of contacts. It shows which way talk pushes and which assumption matters, not how many people will hear about the feature.
