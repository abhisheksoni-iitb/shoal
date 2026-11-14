# JobPilot: Onboarding & Verified Vault Setup (spec summary)

Extracted from the JobPilot product proposal (a Kiroween 2026 hackathon concept, not included in this repository), Section 4.1 (Flow 1) and Section 8.2 (Activation).

**Idea.** A new JobPilot candidate runs `/start` in Telegram, uploads their existing PDF/DOCX resume, waits for Docling AST parsing into 110–118 char atomic bullets, verifies >=15 extracted bullets/metrics, seals their local SQLite vault with an AES-256-GCM passphrase, and arms the 09:00 AM daily delivery loop.

**Where it shows up.** Telegram bot `/start` or GitHub/Kiro CLI install prompt.

**Flow.**
1. Candidate runs `/start` in Telegram.
2. Bot asks for their master resume (PDF/DOCX). (Requires having the resume file accessible on the device they're messaging from.)
3. Docling parses the document, calibrates bullets to 110–118 chars, and extracts metrics/skills (`is_verified = 0`).
4. Candidate reviews 28 extracted bullets on Telegram and taps `[✅ Approve All Verified Facts]` (or fixes mis-parsed metrics/dates).
5. Candidate sets AES-256-GCM local vault passphrase and target role/comp/work-auth preferences.
6. Vault is locked and 09:00 AM daily delivery is scheduled.

**Not decided in spec.**
- What a mobile user does if their resume PDF is on Google Drive / desktop rather than their phone.
- How a user edits individual mis-parsed bullets if `[Approve All Verified Facts]` is inaccurate for 2 of 28 bullets.
- Passphrase recovery if the user forgets their AES-256-GCM passphrase.
- Whether desktop ShadowMux Chrome pairing happens during onboarding or only fails later on first apply.

**Hypothesis in proposal (Section 8.2).**
- H1: Activation >= 75% of onboarded users import a master resume and approve >=15 verified bullets.
- H2: Onboarding finishes within 3 minutes (180s).
