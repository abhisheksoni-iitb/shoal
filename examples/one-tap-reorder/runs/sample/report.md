# Shoal rehearsal: One-tap reorder

5,000 synthetic users, seed 7, 24 replications, 2026-11-14 12:14.

## What it says

- Out of 100 eligible users, about 10 are predicted to finish (range 9–12%).
- The biggest loss is at “Opens the reorder sheet”: 23% of everyone who started leaves there, mostly because they could not proceed (blocked).
- 71% of eligible users never start: they do not see the entry point, or see it and pass. Discovery, not the flow, caps adoption.
- Best single fix: Give users without saved_card a way through 'Confirms payment with the saved card' (+3.3 points of adoption).
- 9 high-severity edge cases are not covered by the spec (9 confirmed in review).
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
| Hit at least one error | 7% | 5–10% |
| Blocked (could not proceed) | 38% | 35–41% |
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
| Opens the reorder sheet | 100% | 77% | 22.6% | Blocked |
| Reviews the items and prices | 77% | 95% | 3.7% | Too much effort |
| Replaces or removes out-of-stock items | 28% | 74% | 7.2% | Too much effort |
| Picks a delivery slot | 67% | 89% | 7.2% | Too much effort |
| Confirms payment with the saved card | 59% | 69% | 18.3% | Blocked |
| Order is placed | 41% | 91% | 3.8% | Error |
| Sees the confirmation | 37% | — | — |  |

## Biggest levers

| Change | Adoption |
|---|---:|
| Give users without saved_card a way through 'Confirms payment with the saved card' | +3.3 pts |
| Make the 'Home banner' entry point easier to find | +3.2 pts |
| Make the 'Sunday push notification' entry point easier to find | +1.4 pts |
| Give users without past_order a way through 'Opens the reorder sheet' | +0.7 pts (within noise) |
| Make the 'Reorder button in order history' entry point easier to find | +0.6 pts (within noise) |
| Cut the effort of 'Confirms payment with the saved card' | +0.5 pts (within noise) |
| Make 'Confirms payment with the saved card' clearer | +0.5 pts (within noise) |
| Make 'Replaces or removes out-of-stock items' clearer | +0.4 pts (within noise) |

## Variants

| Variant | Adoption change | Beats base in | Verdict |
|---|---:|---:|---|
| Usual slot pre-selected | +0.8 pts | 83% | no clear difference |
| Add a card inline | +1.7 pts | 96% | better |

## Design gaps

- 'Opens the reorder sheet' needs past_order. About 21% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).
- 'Confirms payment with the saved card' needs saved_card. About 40% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).
- 'Order is placed' can fail (4%) but the model says nothing about what happens next. Fix: Define on_error: can the user retry, or where do they land?

## High-severity edge cases not covered (9)

- [gap] Order is placed: No connection. What does the user see offline, and is their work kept until they are back?
- [gap] Order is placed: No answer in time. After how long does it give up, and what can the user do then?
- [gap] Order is placed: The other system returns an error. Is the message specific, and is there a retry or another route?
- [gap] Order is placed: Button pressed twice. Can a double press create two records, charges or messages?
- [gap] Order is placed: Half of it worked. If only part succeeded, what state is the user left in and how do they finish?
- [gap] Order is placed: Data changed since the screen loaded. If price, stock, permissions or status changed meanwhile, who wins?
- [gap] Opens the reorder sheet: Nothing to show yet. What does a first-time or zero-data user see, and what should they do next?
- [gap] Confirms payment with the saved card: Saved card is expired or will be declined. When is the card checked, and what happens to the basket and slot if it fails?
- [gap] Reviews the items and prices: Customer wants only some of the items. Can items be unticked or quantities changed?

## Limits

- These are predictions from a model of your feature, not measurements of real people. Treat every number as a hypothesis to check.
- The ranges cover random variation and a ±10% wobble on the guessed inputs. They do not cover a wrong model (a missing step, a missing kind of user).
- Language models asked to play users tend to be more agreeable, more goal-directed and less varied than real people. Qualitative sessions find problems; they do not prove their absence.
- Rank order (which step is worst, which fix helps most) is more reliable than absolute levels. Calibrate with real data when you have any, and score the run after launch.
