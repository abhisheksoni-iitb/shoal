# Shoal rehearsal: JobPilot: Onboarding & Verified Vault Setup

5,000 synthetic users, seed 7, 24 replications, 2026-11-13 12:07.

## What it says

- Out of 100 eligible users, about 12 are predicted to finish (range 9–13%).
- The biggest loss is at “Uploads master resume (PDF/DOCX)”: 60% of everyone who started leaves there, mostly because they could not proceed (blocked).
- 42% of eligible users never see the feature at all. Discovery, not the flow, caps adoption.
- Best single fix: Give users without resume_file_ready a way through 'Uploads master resume (PDF/DOCX)' (+4.2 points of adoption).
- 7 high-severity edge cases are not covered by the spec (7 confirmed in review).
- Hypothesis H1 looks wrong: “Activation: at least 75% of users who start onboarding finish verifying their vault.” (predicted 20%).
- Hypothesis H3 looks wrong: “Mobile Telegram seekers activate at least 50% of the time.” (predicted 5%).

## Headline numbers (predicted)

| Metric | Predicted | Range |
|---|---:|---:|
| Adoption (of everyone eligible) | 12% | 9–13% |
| Discovery (saw it and started) | 57% | 51–64% |
| Completion (of those who started) | 20% | 17–22% |
| Hit at least one error | 11% | 9–13% |
| Blocked (could not proceed) | 38% | 36–42% |
| Median time to finish | 146s | 141–150s |

## Hypotheses

| ID | Hypothesis | Predicted | Verdict |
|---|---|---:|---|
| H1 | Activation: at least 75% of users who start onboarding finish verifying their vault. | 20% | contradicted |
| H2 | Onboarding completes in 3 minutes (180s) or less. | 146s | supported |
| H3 | Mobile Telegram seekers activate at least 50% of the time. | 5% | contradicted |

## Funnel

| Step | Reached | Carried on | Left here | Main reason |
|---|---:|---:|---:|---|
| Uploads master resume (PDF/DOCX) | 100% | 40% | 60.1% | Blocked |
| Docling parses & calibrates 28 bullets (110-118 chars) | 40% | 91% | 3.6% | Error |
| Reviews extracted bullets & approves verified facts | 36% | 84% | 5.9% | Too much effort |
| Sets AES-256 passphrase & target role/comp preferences | 30% | 65% | 10.8% | Too much effort |
| Vault locked & 09:00 AM daily loop scheduled | 20% | — | — |  |

## Biggest levers

| Change | Adoption |
|---|---:|
| Give users without resume_file_ready a way through 'Uploads master resume (PDF/DOCX)' | +4.2 pts |
| Cut the effort of 'Sets AES-256 passphrase & target role/comp preferences' | +2.3 pts |
| Make 'Sets AES-256 passphrase & target role/comp preferences' clearer | +2.2 pts |
| Make the 'README / Kiro CLI setup link' entry point easier to find | +1.7 pts |
| Cut the effort of 'Uploads master resume (PDF/DOCX)' | +1.3 pts |
| Make the 'Telegram /start onboarding prompt' entry point easier to find | +1.2 pts |
| Make 'Uploads master resume (PDF/DOCX)' clearer | +1.2 pts |
| Cut the effort of 'Reviews extracted bullets & approves verified facts' | +0.7 pts (within noise) |

## Variants

| Variant | Adoption change | Beats base in | Verdict |
|---|---:|---:|---|
| Allow pasting resume text or LinkedIn URL when PDF is not on phone | +6.4 pts | 100% | better |
| Grouped verification + per-bullet tap-to-edit | +1.4 pts | 100% | better |

## Design gaps

- 'Uploads master resume (PDF/DOCX)' needs resume_file_ready. About 37% of users lack it and have nowhere to go. Fix: Add a fallback step (set it up, request it, or explain why not).

## High-severity edge cases not covered (7)

- [gap] Uploads master resume (PDF/DOCX): Typed data lost on error or navigation. If the step fails or the user steps back, is what they typed kept?
- [gap] Docling parses & calibrates 28 bullets (110-118 chars): Connection drops while waiting. Does the wait resume, restart or fail silently?
- [gap] Docling parses & calibrates 28 bullets (110-118 chars): The thing being waited for never arrives. Is there a time limit and a next step when it runs out?
- [gap] Sets AES-256 passphrase & target role/comp preferences: Typed data lost on error or navigation. If the step fails or the user steps back, is what they typed kept?
- [gap] Docling parses & calibrates 28 bullets (110-118 chars): Two-column PDF merges unrelated columns into bullets. How does the user detect and fix merged column text before locking verified bullets?
- [gap] Reviews extracted bullets & approves verified facts: Candidate resume has fewer than 15 bullets. Activation target mentions >=15 verified bullets. Are junior candidates with 8-12 bullets blocked from activating?
- [gap] Sets AES-256 passphrase & target role/comp preferences: Passphrase typed into Telegram chat persists in chat history. Where is the AES-256 passphrase entered so Telegram cloud servers never see it?

## Limits

- These are predictions from a model of your feature, not measurements of real people. Treat every number as a hypothesis to check.
- The ranges cover random variation and a ±10% wobble on the guessed inputs. They do not cover a wrong model (a missing step, a missing kind of user).
- Language models asked to play users tend to be more agreeable, more goal-directed and less varied than real people. Qualitative sessions find problems; they do not prove their absence.
- Rank order (which step is worst, which fix helps most) is more reliable than absolute levels. Calibrate with real data when you have any, and score the run after launch.
