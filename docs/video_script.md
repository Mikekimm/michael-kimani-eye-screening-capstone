# Walkthrough video script (about 10-12 minutes)

Record the screen at 1080p with your voice. Before recording: start the backend and frontend
(README section 7), sign in once as each demo user so consent is accepted, have 2-3 **public dataset**
fundus images ready (e.g. from APTOS 2019 on Kaggle, one with DR and one without) and one blank image.
Never show a real patient photo or your `.env` file.

| Time | Show | Say (in your own words) |
|---|---|---|
| 0:00-0:45 | Title slide or README top | Problem (preventable blindness, few specialists, weak internet), who it is for, and that it is screening support, not diagnosis. |
| 0:45-1:30 | `docs/scope_table.md` | What the proposal planned, what is completed, partial, not implemented, and why (supervisor feedback, one complete DR workflow; glaucoma/cataract honestly "not available"). |
| 1:30-2:15 | `docs/diagrams/architecture.png`, then folders in VS Code | PWA -> API -> services -> repositories; ScreeningPipeline, ModelRegistry, RiskPolicy. |
| 2:15-4:30 | Phone-sized browser (DevTools device mode, Pixel 5): sign up, consent, register patient, Screen -> eye -> upload a public DR image -> result | **Core functionality.** Explain the request: multipart upload with a client UUID; the server checks the file, runs the quality gate, runs the verified model, applies the risk policy. Point at: estimated band (not a grade), model version, score explanation, glaucoma/cataract "Model not available yet", disclaimer. |
| 4:30-5:15 | Same flow with the **blank image**, then with a name-like patient code | **Different inputs and error handling:** 422 "cannot be screened ... blank", form validation. Then a non-DR image to show a low band and "routine screening". |
| 5:15-6:15 | DevTools -> Network -> Offline; capture a photo; History shows "Waiting to sync"; go online; it syncs | **Offline queue:** saved in IndexedDB, retried with exponential backoff, no duplicates because the server is idempotent on the UUID. Be clear that analysis happens after sync. |
| 6:15-7:15 | Sign in as specialist: queue -> case -> approve with note -> comment | Referral loop; append-only history (show `review_events` guard in `entities.py` briefly). |
| 7:15-7:45 | Sign in as admin: Users (change a role), Analytics | RBAC; aggregates only. Show a health worker opening `/admin/users` being redirected. |
| 7:45-8:15 | About screen | Model card: provenance, threshold source, limitations, metrics status. |
| 8:15-9:45 | Terminal: `pytest -q`, `npm.cmd test`, `npx playwright test` (or show the recorded HTML report) | **Testing strategies:** unit (risk policy boundaries, sync queue lost-reply test), integration (RBAC matrix, real model), end-to-end and compatibility (Chromium, Firefox, WebKit). Say why each was chosen and one bug each found (password field ref, calibration script, result order). |
| 9:45-10:45 | `docs/testing_report.md` section 5, Lighthouse HTML report | **Performance and compatibility:** 74 ms pipeline, 1-thread vs all cores, 0.5 s vs 3.1 s on an emulated low-end phone with slow 3G, Lighthouse 96-100; state what is emulated and what is not tested. |
| 10:45-11:30 | `registry.py`, `risk_policy.py`, `syncQueue.ts` | **Code quality and algorithms:** interface + polymorphism, strategy, repository, DI; threshold search, quality gate, backoff with jitter, checksum. |
| 11:30-12:00 | README known issues | Limitations and next steps (hold-out metrics if not yet run, glaucoma/cataract models, usability study). |

Upload as **unlisted** on YouTube (or Google Drive with "anyone with the link"), test the link in a
private browser window, then paste it into the README and the report.
