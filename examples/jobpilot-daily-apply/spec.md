# JobPilot: Daily 09:00 AM Curation & 1-Tap Apply (spec summary)

Extracted from the JobPilot product proposal, specs and prototype code (a Kiroween 2026 hackathon concept, not included in this repository).

**Idea.** Instead of applying to hundreds of jobs manually, a candidate receives one high-conviction job card on Telegram at 09:00 AM, previews a hallucination-free single-page Tectonic LaTeX resume, taps `[⚡ 1-Tap Apply]`, and lets ShadowMux submit the application off-screen at `(-3200, -3200)` and stamp a SQLite SHA-256 audit receipt.

**Where it shows up.** Daily 09:00 AM Telegram notification card (`TelegramBotGateway.format_daily_job_card`), or manual ATS URL drop into the Telegram chat.

**Flow.**
1. Candidate opens the 09:00 AM Telegram card (requires an active verified profile and master bullet vault; `JobPilotAgent.perceive` raises `ValueError` if missing).
2. Candidate chooses `[📄 Preview Tailored PDF]` or goes straight to `[⚡ 1-Tap Apply]`.
3. Preview compiles and streams the single-page Carlito LaTeX PDF into Telegram (falls back to `.tex` path in code if `tectonic`/`pdflatex` is missing).
4. Candidate taps `[⚡ 1-Tap Apply]`.
5. JobPilot acquires a ShadowMux domain lease and mirrors desktop Chrome cookies (`-3200, -3200`).
6. Detached Chrome fills standard ATS fields and uploads the PDF. If CAPTCHA or an unmapped mandatory field (<95% confidence) appears, it pauses and sends a Telegram webview link (`hitl_escalation`, 180s timeout).
7. Browser clicks Submit, scrapes confirmation code, captures proof screenshot, and stamps `applications` in `jobpilot.db`.

**Not decided / exposed in code & spec.**
- What happens when a mobile commuter taps `[1-Tap Apply]` while their desktop Chrome / ShadowMux daemon is asleep or offline.
- What a newly onboarded user who has not yet verified >=15 bullets sees at 09:00 AM.
- What happens after the 180s HITL CAPTCHA/custom-question timeout expires.
- What happens if confirmation scraping fails *after* the ATS Submit click.
- No inline edit/swap of tailored bullets or custom ATS answers before submitting.

**Hypotheses in the proposal (Section 8.2 & 8.3).**
- H1: Daily Engagement >= 85% open and review rate of the 09:00 AM Telegram card.
- H2: Application Confirmation Rate >= 40% of delivered cards confirmed via 1-Tap Apply.
- H3: Execution Cycle Time <= 45 seconds median from card review to stamped receipt.
- H4: At least 50% of users who reach the 1-Tap Apply button confirm it.
