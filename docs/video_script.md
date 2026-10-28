# Walkthrough video script (about 12 minutes)

Record the screen at 1080p with your voice. Never show a real patient photo, your `.env` file or any
screenshot that contains a secret.

## Before recording

1. Stop the backend, then reset to clean demo data: `.venv\Scripts\python scripts\reset_demo_data.py --yes`
   (backs up `data/app.db`, deletes it and the stored photos, re-runs the migrations and the seed).
2. Start the backend and frontend (README section 7).
3. Sign in once as each demo account so the consent screen is already accepted.
4. Have ready: 2 **public dataset** fundus photos (one with DR, one without), one non-eye image (for example a
   photo of a desk or a document with nothing private on it), one blank image.
5. Use two browser windows (one normal, one private) so the new applicant and the admin are side by side.
   Set the health worker window to a phone size (DevTools, Pixel 5).

## Demo accounts (synthetic demo data only)

| Role | Email | Password |
|---|---|---|
| Admin | `admin@example.org` | `DemoAdmin2026!` |
| Specialist | `specialist@example.org` | `DemoSpecialist2026!` |
| Health worker (approved) | `nurse@example.org` | `DemoNurse2026!` |
| New applicant (made during the video) | e.g. `new.nurse@example.org` | any password with a letter and a number |

**Demo-only credentials** for synthetic data on a local machine. They come from
`scripts/init_env.py --demo-passwords` (already set in this machine's `.env`) and are created by `scripts/seed.py`;
checked after a clean reset on 28 October (all three sign in). Never use them on a hosted deployment.

## Click-by-click demo order

1. **README** top: problem, intended users, "screening support only, not a diagnostic device".
2. **docs/scope_table.md**: planned vs delivered. The proposal says React Native with on-device TensorFlow Lite;
   the app is a PWA with server-side inference, and offline covers capture and queueing only. Load balancer and
   usability study not done.
3. **Sign-up (private window):** Sign up -> full name, email, password, "I am requesting access as" = Health
   worker -> Create -> "Your request is pending". Point out: no facility, no ID number is asked.
4. **Sign in** with a wrong password -> "Incorrect email or password." Then the right password -> "Your account is
   waiting for administrator approval."
5. Sign up again with the **same email** and another name -> "This email is already registered" (nothing changed).
6. **Admin (normal window):** sign in as admin -> Users -> the pending card shows the requested role. Press
   **Reject** with no reason -> refused ("Give a reason"). Then type a facility (optional) and **Approve** (role to
   grant: Health worker). Say: the app does not verify identity; the admin checks it outside the app; every
   decision is in the audit log. Show that for a **specialist** the admin also ticks specialties (DR, glaucoma,
   cataract, general); the demo specialist already has all four.
7. **Private window:** sign in again -> accept consent -> home screen. Sign out.
8. **Health worker (phone size), `nurse@example.org`:** Patients -> **Register patient** -> app-generated code.
9. **Screen** -> the patient -> **Left eye** -> **From gallery** -> choose the **non-eye image** -> preview with
   **Cancel** / **Analyse** -> tick consent -> **Analyse** -> refused: "does not look like a retinal fundus
   photograph ... Nothing was saved", with **Retake** / **Upload another**.
10. **Upload another** -> the **blank image** -> Analyse -> refused "blank or uniform".
11. **Upload another** -> the **DR fundus photo** -> Analyse -> result page. Point at: DR v2.0 card with the
    estimated band (not a grade), glaucoma and cataract "binary result only", "How reliable is this model?"
    (glaucoma: about 9 in 10 flags are false alarms), the recommendation ("Refer recommended" or "Uncertain,
    consider asking a specialist"), the disclaimer. Say: **nothing has been sent to a specialist**.
12. **Ask a specialist** -> the flagged conditions are pre-ticked (keep Diabetic retinopathy) -> type a question
    ("Is this referable DR?") -> **How soon?** Urgent -> **Send to specialist** -> status "Awaiting specialist", the
    question and its conditions, waiting time and review target (urgent 24 h / routine 72 h).
13. **Screen** again -> same patient -> **Right eye** -> the **non-DR photo** -> Analyse -> "No referral needed" ->
    **Save** -> History shows it and today's count. If you have a borderline photo, show that it is **Queued
    automatically** (uncertain case, as in the proposal) and that **Add a question** still works.
14. **Specialist** (`specialist@example.org`): Review queue -> **My specialties** tab (and **All cases**) -> the case
    with the question -> **Take this case** -> "Taken by you". Say: specialty routing is an extension beyond the
    proposal, which has a single Specialist role.
15. **Health worker:** open the case -> "Being reviewed by Demo Specialist".
16. **Specialist:** open the case -> **Decision: Override** glaucoma with a reason -> **Save review** -> **Decision:
    Approve** with a note -> **Save review**. History is append-only.
17. **Health worker:** Home -> **New decisions: 1** (no reload needed: the screens refresh every 30 s) -> History ->
    the case shows **Reviewed** and **New decision**; open it (the mark clears) -> the specialist's decisions. Then try
    `/admin/users` in the address bar -> sent back home (the API returns 403).
18. **Offline:** DevTools -> Network -> Offline -> capture a photo -> History "Waiting to sync" -> back online ->
    it syncs and is scored. Say: no on-device inference.
19. **Admin:** Analytics: people who can use the system (health workers, specialists, admins) and requests waiting for approval at the top; then aggregates only, overdue reviews per priority. Say: the admin controls who can use the system (a human, logged decision, effective immediately) and keeps the records and the **About** screen (model cards, test-split
    figures and caveats).
20. **Terminal:** `pytest -q`, `npm.cmd test`, the Playwright HTML report (four profiles), the GitHub Actions run.
21. **docs/testing_report.md** section 5: performance and compatibility figures.
22. **Code:** `registry.py`, `risk_policy.py` (`RiskPolicy`, `ReferralAdvisor`), `quality.py` (`FundusCheck`),
    `review_targets.py`, `syncQueue.ts`.
23. **README known issues.**

## Script against the grading criteria

| Time | Steps | Criterion covered | Say (in your own words) |
|---|---|---|---|
| 0:00-1:15 | 1-2 | Problem, scope alignment | Who it is for; planned vs delivered and why (PWA, server-side inference, offline = capture and queue). |
| 1:15-3:15 | 3-7 | Core features; access control | Sign-up is a request; the requested role grants nothing; one account per email; admin approves or rejects with a reason; no claim that anyone is verified. |
| 3:15-5:00 | 8-11 | Core features; **backend/frontend interaction** | Multipart upload with a client UUID; the server checks type and size, runs the quality gate and the fundus check, then all three checksum-verified models, each with the resize from its card, then the risk policy and `ReferralAdvisor`; the typed API client turns errors into plain language. |
| 5:00-6:00 | 4-5, 9-10, invalid form input | **Error handling with different inputs** | Wrong password vs pending account, duplicate email, non-eye photo (hard stop, nothing saved), blank photo, invalid form input; the fundus check figures: 3 of 25 real fundus photos wrongly refused, 0 of 77 non-eye images accepted, tuned on the same images, no face photos tested, so optimistic. |
| 6:00-8:30 | 12-17 | Core features (referral loop) | The health worker gives the advice at once; the review is a later confirmation, not a gate. As in the proposal, an uncertain case is queued automatically (configurable); a clear positive is sent by the health worker with its conditions and routine or urgent (severe = urgent by default). Review is asynchronous from a shared queue: one "general" specialist sees every case, a district specialist can serve several clinics; specialists do not prescribe, they approve, override with a reason, request a retake or comment. SMS/email notifications are future work; screens refresh every 30 s; specialty routing (extension beyond the proposal) puts it in the right specialist's tab, Take this case shows who is reviewing it; asynchronous review as in the proposal; the 24 h / 72 h targets are my design decision; the decision comes back; RBAC on the server. |
| 8:30-9:00 | 18-19 | Offline, analytics | IndexedDB queue, backoff with jitter, idempotent on the UUID; aggregates only. |
| 9:00-10:30 | 20 | **Testing strategies (at least two)** | Unit (risk policy boundaries, fundus check, review targets, daily counts at 23:59 vs 00:01), integration (role matrix, real models, approval rules, PostgreSQL in CI), end-to-end on four profiles, model parity (24 photos, max 0.021, no decision changed). One bug each found. |
| 10:30-11:15 | 21 | **Performance and compatibility** | Server timing, 0.44 s vs 2.73 s round trip on an emulated low-end phone with slow 3G, Lighthouse, axe-core; Chromium, Firefox and WebKit; say what is emulated and what is not tested yet (physical phone). |
| 11:15-12:00 | 22-23 | Code quality; honest limits | Patterns and algorithms; DR specificity 0.748 below the 80% target, glaucoma below target (precision about 10%), cataract only 46 positive test eyes; no on-device inference, no load balancer, no usability study yet. |

Upload as **unlisted** on YouTube (or Google Drive with "anyone with the link"), test the link in a
private browser window, then paste it into the README and the report.
