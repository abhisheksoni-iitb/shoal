# Shoal rehearsal: ShadowMux: Off-Screen Lease & Conflict Sentinel

5,000 synthetic users, seed 7, 24 replications, 2026-11-13 12:07.

## What it says

- Out of 100 eligible users, about 34 are predicted to finish (range 28–37%).
- The biggest loss is at “Mirrors Chrome profile cookies & storage (OS Keychain)”: 45% of everyone who started leaves there, mostly because they could not proceed (blocked).
- Best single fix: Give users without keychain_cookie_access a way through 'Mirrors Chrome profile cookies & storage (OS Keychain)' (+13.1 points of adoption).
- 13 high-severity edge cases are not covered by the spec (13 confirmed in review).
- Hypothesis H1 looks wrong: “At least 85% of invoked ShadowMux sessions complete without blocking or error.” (predicted 40%).

## Headline numbers (predicted)

| Metric | Predicted | Range |
|---|---:|---:|
| Adoption (of everyone eligible) | 34% | 28–37% |
| Discovery (saw it and started) | 88% | 70–92% |
| Completion (of those who started) | 40% | 37–43% |
| Hit at least one error | 15% | 12–16% |
| Blocked (could not proceed) | 36% | 33–37% |
| Median time to finish | 48s | 46–50s |

## Hypotheses

| ID | Hypothesis | Predicted | Verdict |
|---|---|---:|---|
| H1 | At least 85% of invoked ShadowMux sessions complete without blocking or error. | 40% | contradicted |
| H2 | When human conflict occurs, at least 80% of sessions resume cleanly through arbitration. | 85% | supported |
| H3 | Median session time stays under 60 seconds. | 48s | supported |

## Funnel

| Step | Reached | Carried on | Left here | Main reason |
|---|---:|---:|---:|---|
| Acquires atomic SQLite domain lease | 100% | 95% | 5.1% | Error |
| Mirrors Chrome profile cookies & storage (OS Keychain) | 95% | 52% | 45.2% | Blocked |
| Spawns Chrome at (-3200,-3200) & runs agent workflow | 50% | 96% | 1.9% | Error |
| Releases SQLite lease & writes SHA-256 audit log | 41% | 95% | 1.9% | Error |
| Conflict Sentinel freezes agent & shows pause pill | 19% | 75% | 4.8% | Blocked |
| Background browser task finished with zero clobbering | 39% | — | — |  |
| Human finishes active tab & clicks Resume on pill | 15% | 88% | 1.7% | Too much effort |

## Biggest levers

| Change | Adoption |
|---|---:|
| Give users without keychain_cookie_access a way through 'Mirrors Chrome profile cookies & storage (OS Keychain)' | +13.1 pts |
| Cut the effort of 'Mirrors Chrome profile cookies & storage (OS Keychain)' | +2.8 pts |
| Make 'Mirrors Chrome profile cookies & storage (OS Keychain)' clearer | +2.6 pts |
| Give users without chrome_extension_installed a way through 'Conflict Sentinel freezes agent & shows pause pill' | +2.2 pts |
| Halve the errors at 'Mirrors Chrome profile cookies & storage (OS Keychain)' | +1.2 pts (within noise) |
| Halve the errors at 'Spawns Chrome at (-3200,-3200) & runs agent workflow' | +0.6 pts (within noise) |
| Make 'Releases SQLite lease & writes SHA-256 audit log' clearer | +0.6 pts (within noise) |
| Halve the errors at 'Acquires atomic SQLite domain lease' | +0.5 pts (within noise) |

## Variants

| Variant | Adoption change | Beats base in | Verdict |
|---|---:|---:|---|
| Guided Keychain grant + unauthenticated fallback | +10.0 pts | 100% | better |
| Auto-resume agent when human closes or leaves conflicted domain | +1.3 pts | 96% | better |

## Design gaps

- 'Mirrors Chrome profile cookies & storage (OS Keychain)' needs keychain_cookie_access. About 34% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).
- 'Conflict Sentinel freezes agent & shows pause pill' needs chrome_extension_installed. About 30% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).
- 'Releases SQLite lease & writes SHA-256 audit log' can fail (2%) but the model says nothing about what happens next. Fix: Define on_error: can the user retry, or where do they land?

## High-severity edge cases not covered (13)

- [gap] Whole flow: Signed out while in the flow. After signing in again, do they return to where they were?
- [gap] Acquires atomic SQLite domain lease: The other system returns an error. Is the message specific, and is there a retry or another route?
- [gap] Mirrors Chrome profile cookies & storage (OS Keychain): No answer in time. After how long does it give up, and what can the user do then?
- [gap] Mirrors Chrome profile cookies & storage (OS Keychain): The other system returns an error. Is the message specific, and is there a retry or another route?
- [gap] Mirrors Chrome profile cookies & storage (OS Keychain): Half of it worked. If only part succeeded, what state is the user left in and how do they finish?
- [gap] Spawns Chrome at (-3200,-3200) & runs agent workflow: Connection drops while waiting. Does the wait resume, restart or fail silently?
- [gap] Spawns Chrome at (-3200,-3200) & runs agent workflow: The thing being waited for never arrives. Is there a time limit and a next step when it runs out?
- [gap] Releases SQLite lease & writes SHA-256 audit log: No answer in time. After how long does it give up, and what can the user do then?
- [gap] Releases SQLite lease & writes SHA-256 audit log: The other system returns an error. Is the message specific, and is there a retry or another route?
- [gap] Releases SQLite lease & writes SHA-256 audit log: Half of it worked. If only part succeeded, what state is the user left in and how do they finish?
- [gap] Releases SQLite lease & writes SHA-256 audit log: Data changed since the screen loaded. If price, stock, permissions or status changed meanwhile, who wins?
- [gap] Spawns Chrome at (-3200,-3200) & runs agent workflow: Multi-monitor arrangement overlaps (-3200, -3200). What if a user has a 4K external monitor positioned top-left at negative coordinates, or macOS clamps the window back on-screen?
- [gap] Human finishes active tab & clicks Resume on pill: Lease TTL (120s) expires while PAUSED_FOR_HUMAN. If a human takes 3 minutes in Gmail while the agent is paused, does the stale lock scavenger expire the lease and discard the checkpoint?

## Limits

- These are predictions from a model of your feature, not measurements of real people. Treat every number as a hypothesis to check.
- The ranges cover random variation and a ±10% wobble on the guessed inputs. They do not cover a wrong model (a missing step, a missing kind of user).
- Language models asked to play users tend to be more agreeable, more goal-directed and less varied than real people. Qualitative sessions find problems; they do not prove their absence.
- Rank order (which step is worst, which fix helps most) is more reliable than absolute levels. Calibrate with real data when you have any, and score the run after launch.
