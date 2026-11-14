# Shoal rehearsal: JobPilot: Daily 09:00 AM Curation & 1-Tap Apply

5,000 synthetic users, seed 7, 24 replications, 2026-11-13 12:06.

## What it says

- Out of 100 eligible users, about 4 are predicted to finish (range 3–6%).
- The biggest loss is at “Reads daily Telegram match card”: 32% of everyone who started leaves there, mostly because they could not proceed (blocked).
- 65% of eligible users never see the feature at all. Discovery, not the flow, caps adoption.
- Best single fix: Give users without shadowmux_online a way through 'Acquires ShadowMux desktop lease & cookies' (+3.0 points of adoption).
- 18 high-severity edge cases are not covered by the spec (18 confirmed in review).
- Hypothesis H1 looks wrong: “Daily Engagement: at least 85% of eligible candidates open and review the 09:00 AM Telegram card.” (predicted 36%).
- Hypothesis H2 looks wrong: “Application Confirmation Rate: at least 40% of candidates who open a card finish applying.” (predicted 12%).
- Hypothesis H3 looks wrong: “Execution Cycle Time: median time from opening the card to stamped receipt is 45 seconds or less.” (predicted 73s).

## Headline numbers (predicted)

| Metric | Predicted | Range |
|---|---:|---:|
| Adoption (of everyone eligible) | 4% | 3–6% |
| Discovery (saw it and started) | 36% | 29–43% |
| Completion (of those who started) | 12% | 9–14% |
| Hit at least one error | 9% | 7–11% |
| Blocked (could not proceed) | 45% | 43–50% |
| Median time to finish | 73s | 70–80s |

## Hypotheses

| ID | Hypothesis | Predicted | Verdict |
|---|---|---:|---|
| H1 | Daily Engagement: at least 85% of eligible candidates open and review the 09:00 AM Telegram card. | 36% | contradicted |
| H2 | Application Confirmation Rate: at least 40% of candidates who open a card finish applying. | 12% | contradicted |
| H3 | Execution Cycle Time: median time from opening the card to stamped receipt is 45 seconds or less. | 73s | contradicted |
| H4 | Trust threshold: at least half of candidates who reach 1-Tap Apply proceed to submit. | 68% | supported |

## Funnel

| Step | Reached | Carried on | Left here | Main reason |
|---|---:|---:|---:|---|
| Reads daily Telegram match card | 100% | 68% | 32.0% | Blocked |
| Picks Preview PDF or direct 1-Tap Apply | 68% | 92% | 5.3% | Confusing |
| Previews single-page LaTeX PDF in Telegram | 41% | 92% | 3.3% | Error |
| Taps 1-Tap Apply Now | 59% | 68% | 19.0% | Did not trust it |
| Acquires ShadowMux desktop lease & cookies | 40% | 53% | 18.9% | Blocked |
| Off-screen browser fills ATS form & uploads PDF | 22% | 94% | 1.3% | Ran out of steam |
| Submits form, captures screenshot & stamps SQLite audit | 13% | 91% | 1.2% | Error |
| Solves CAPTCHA or custom question via Telegram link | 9% | 26% | 7.0% | Too much effort |
| Application submitted with confirmation receipt | 12% | — | — |  |

## Biggest levers

| Change | Adoption |
|---|---:|
| Give users without shadowmux_online a way through 'Acquires ShadowMux desktop lease & cookies' | +3.0 pts |
| Make the 'Daily 09:00 AM Telegram role card' entry point easier to find | +1.6 pts |
| Give users without verified_vault a way through 'Reads daily Telegram match card' | +1.0 pts |
| Cut the effort of 'Taps 1-Tap Apply Now' | +0.6 pts |
| Make the 'Paste ATS URL into Telegram chat' entry point easier to find | +0.5 pts |
| Make 'Taps 1-Tap Apply Now' clearer | +0.4 pts (within noise) |
| Halve the errors at 'Acquires ShadowMux desktop lease & cookies' | +0.3 pts (within noise) |
| Halve the errors at 'Off-screen browser fills ATS form & uploads PDF' | +0.3 pts (within noise) |

## Variants

| Variant | Adoption change | Beats base in | Verdict |
|---|---:|---:|---|
| Queue application when desktop ShadowMux is asleep | +2.0 pts | 100% | better |
| Show tailored bullets & custom answers before 1-Tap Apply | +0.7 pts | 96% | better |
| Pre-draft grounded answers for custom ATS questions | +0.7 pts | 100% | better |

## Design gaps

- 'Reads daily Telegram match card' needs verified_vault. About 30% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).
- 'Acquires ShadowMux desktop lease & cookies' needs shadowmux_online. About 41% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).
- 'Solves CAPTCHA or custom question via Telegram link' can fail (10%) but the model says nothing about what happens next. Fix: Define on_error: can the user retry, or where do they land?
- 'Submits form, captures screenshot & stamps SQLite audit' can fail (4%) but the model says nothing about what happens next. Fix: Define on_error: can the user retry, or where do they land?

## High-severity edge cases not covered (18)

- [gap] Whole flow: Signed out while in the flow. After signing in again, do they return to where they were?
- [gap] Previews single-page LaTeX PDF in Telegram: The other system returns an error. Is the message specific, and is there a retry or another route?
- [gap] Acquires ShadowMux desktop lease & cookies: No connection. What does the user see offline, and is their work kept until they are back?
- [gap] Acquires ShadowMux desktop lease & cookies: The other system returns an error. Is the message specific, and is there a retry or another route?
- [gap] Acquires ShadowMux desktop lease & cookies: Half of it worked. If only part succeeded, what state is the user left in and how do they finish?
- [gap] Off-screen browser fills ATS form & uploads PDF: No connection. What does the user see offline, and is their work kept until they are back?
- [gap] Off-screen browser fills ATS form & uploads PDF: The other system returns an error. Is the message specific, and is there a retry or another route?
- [gap] Off-screen browser fills ATS form & uploads PDF: Button pressed twice. Can a double press create two records, charges or messages?
- [gap] Off-screen browser fills ATS form & uploads PDF: Half of it worked. If only part succeeded, what state is the user left in and how do they finish?
- [gap] Off-screen browser fills ATS form & uploads PDF: Data changed since the screen loaded. If price, stock, permissions or status changed meanwhile, who wins?
- [gap] Submits form, captures screenshot & stamps SQLite audit: No connection. What does the user see offline, and is their work kept until they are back?
- [gap] Submits form, captures screenshot & stamps SQLite audit: No answer in time. After how long does it give up, and what can the user do then?
- [gap] Submits form, captures screenshot & stamps SQLite audit: The other system returns an error. Is the message specific, and is there a retry or another route?
- [gap] Submits form, captures screenshot & stamps SQLite audit: Half of it worked. If only part succeeded, what state is the user left in and how do they finish?
- [gap] Solves CAPTCHA or custom question via Telegram link: Typed data lost on error or navigation. If the step fails or the user steps back, is what they typed kept?
- [gap] Solves CAPTCHA or custom question via Telegram link: 180-second HITL timer expires before user finishes. What happens to the detached browser tab, lease, and typed answers when the 180s timeout fires?
- [gap] Off-screen browser fills ATS form & uploads PDF: ATS sponsorship / visa question does not match boolean preset. How are nuanced multi-option work authorization dropdowns mapped when preset is a single string?
- [gap] Previews single-page LaTeX PDF in Telegram: Tectonic/pdflatex binary missing on host. apps/jobpilot/compiler.py falls back to writing .tex path into pdf_path. What does Telegram send?

## Limits

- These are predictions from a model of your feature, not measurements of real people. Treat every number as a hypothesis to check.
- The ranges cover random variation and a ±10% wobble on the guessed inputs. They do not cover a wrong model (a missing step, a missing kind of user).
- Language models asked to play users tend to be more agreeable, more goal-directed and less varied than real people. Qualitative sessions find problems; they do not prove their absence.
- Rank order (which step is worst, which fix helps most) is more reliable than absolute levels. Calibrate with real data when you have any, and score the run after launch.
