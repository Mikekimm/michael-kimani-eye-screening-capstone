# Progress notes (28 October 2026, afternoon)

Working notes for picking the work up again. Work since 27 October is on branch `wip-final-fixes` (pushed);
`main` is untouched until Michael types "OK, push" for the merge. No Co-Authored-By or Claude trailers on any
commit; AI help is acknowledged only in README section 11 ("I used Claude to help me build this project.").
Backup branches/tags and the `legacy-streamlit-prototype` tag are kept (not to be deleted for now).

## 1. Done today (28 October)
- Secret screenshot removed through the real "Remove screening" endpoint (`POST /api/screenings/{id}/discard`,
  as its owner): HTTP 204, `data/uploads/52a397510df6417e8033344d79b9afb4.png` deleted. **Rotate that secret.**
- Full test runs (see README section 8 and `docs/testing_report.md` for the counts).
- Borderline recommendation wording in `backend/config/risk_policy.json` no longer says "Sent for specialist
  review" (nothing is sent automatically).
- Docs updated: README ("How access is controlled", planned-vs-implemented table, fundus-check figures, demo
  reset), scope table, testing report (new section 7), risk policy (referral advice), video script (demo order),
  checklist (Kaggle hold-out superseded), CLAUDE.md, UML sources and PNGs, report + PDF.
- CI now also runs on `wip-final-fixes`: run #3 failed (Python 3.12 collection), fixed; run #4 green.
- Sign-up asks only name, email, password, requested role; the admin may set the facility on approval.
  Duplicate email refused with "already registered", existing account unchanged (backend + E2E tests).
- Lost account `mike4kimani@gmail.com`: deleted by `reset_demo_data.py` (run twice on 28 Oct), not by a
  duplicate sign-up. Restored from `data/app.db.bak-20261028-115318`; the reset now keeps approved own accounts.
- Demo credentials (demo-only): admin@example.org / DemoAdmin2026!, specialist@example.org /
  DemoSpecialist2026!, nurse@example.org / DemoNurse2026! (`init_env.py --demo-passwords`).
- Proposal compliance table in `docs/scope_table.md` and the report.
- Tests (28 Oct): pytest 277 passed (3.12: 276 + 1 skipped); Vitest 78; typecheck/lint clean; Playwright 47
  passed, 3 skipped, 0 failed on four profiles. Report PDF 5 pages.
- Demo path run against the real backend after the sign-up change: 10/10 steps passed. Demo data then reset
  (only the three demo accounts and Michael's account remain; 5 synthetic patients, no screenings).

## 2. Still to do
1. Rotate the secret that was in the uploaded screenshot.
2. Check CI on `wip-final-fixes`; after "OK, push": merge into `main` and push `main`.
3. Render HTTPS deploy + SMTP; iPhone 13 Pro and Android test; SUS usability test; video; README/report links;
   Attempt 2 ZIP (`git archive` of `main` + the video).

## 3. Honesty rules and agreed labels
- Real trained models only; never invent or estimate a number; only values from `results.json`, the model cards,
  `docs/metrics.json` or `docs/odir_metrics.json`.
- DR label: "held-out test split by image (no patient IDs available; near-duplicates could not be excluded); not
  external validation; not clinically validated". Sensitivity target met, specificity target (80%) not met.
- Glaucoma: below target, limited evidence, always shown with precision 0.103 (about 9 in 10 flags are false alarms).
  Cataract: meets targets, limited evidence (46 positive test eyes). ODIR labels may be noisy.
- Fundus check: 3 of 25 real fundus photos wrongly refused, 0 of 77 non-eye images accepted; tuned on the same
  images, no face photos tested: optimistic. A heuristic that can be fooled.
- The app verifies nobody's identity; sign-up is a request an admin approves. Never claim verification.
- Offline = capture and queue; scoring happens on the server after sync (no on-device inference).
- Review targets (urgent 24 h, routine 72 h) are a design decision, not a proposal requirement.
