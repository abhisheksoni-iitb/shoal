# ShadowMux: Co-Browsing Lease & Conflict Sentinel (spec summary)

Extracted from the ShadowMux product proposal and specs (a Kiroween 2026 hackathon concept, not included in this repository).

**Idea.** Autonomous agents (like JobPilot or MiroFish) need authenticated browser sessions without stealing focus or clobbering the user's open tabs (as happened in the Nov 5, 2026 Gmail draft incident). ShadowMux provides atomic SQLite domain leases, cookie mirroring from the default Chrome profile, detached off-screen Chrome viewports at `(-3200, -3200)`, and a Live Conflict Sentinel that pauses background work in <50ms if the human opens the same domain.

**Where it shows up.** Triggered automatically whenever JobPilot/MiroFish opens a web domain, with a desktop notification pill (`ShadowMux: Paused Agent (Human Active) [Resume ▶]`) when a conflict occurs.

**Flow.**
1. Background agent requests atomic SQLite domain lease (`acquire_lease`).
2. Cookie synchronizer mirrors encrypted cookies/localStorage from default Chrome profile into ephemeral shadow profile (`sync_cookies`, requires OS Keychain decryption permission on macOS).
3. Detached Chrome launches at `(-3200, -3200)` and executes workflow (`run_detached_task`).
4. If the human switches to or types in the same domain (e.g. `mail.google.com` or `greenhouse.io`), Conflict Sentinel pauses the agent and displays an arbitration notification pill (`conflict_sentinel_pause`).
5. Human finishes their tab work and clicks Resume (or cancels) (`arbitrate_handoff`).
6. Agent completes task, releases SQLite lease, closes detached viewport, and logs audit entry (`release_lease` -> `task_completed`).

**Not decided in spec.**
- How a first-time macOS user grants Keychain cookie decryption permission without a scary system prompt loop.
- What happens if a human clicks Resume while still on the same domain, or forgets to click Resume (stuck `PAUSED_FOR_HUMAN` forever?).
- What happens if Chrome updates or locks the default `Cookies` SQLite file while copying.
- What happens if the user is on a multi-monitor setup where `(-3200, -3200)` is actually inside a virtual/extended monitor arrangement!

**Hypotheses in proposal.**
- H1: >= 85% of agent browser tasks complete cleanly without human clobbering.
- H2: Human arbitration (`conflict_sentinel_pause` -> `arbitrate_handoff`) resolves cleanly >= 80% of the time.
- H3: Median total background cycle stays under 60 seconds.
