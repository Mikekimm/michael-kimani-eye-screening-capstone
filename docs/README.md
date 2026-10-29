# Documentation

Start with the [technical report](report/report.pdf). Screening support only; not a diagnostic device.

## Design (at this level because the report cites these paths)

- [architecture.md](architecture.md): architecture, use cases, classes, database and sequence diagrams with explanations
- [scope_table.md](scope_table.md): every proposal item, what was delivered, and each deviation with its reason
- [diagrams/](diagrams/): the diagram images (PNG); [diagrams/src/](diagrams/src/) holds their Mermaid sources
- [cleanup_report.md](cleanup_report.md): what the repository clean-up deleted or moved, with the evidence

## report/

- [report/report.pdf](report/report.pdf): the submitted technical report (5 pages)
- [report/report.html](report/report.html): its source (rendered by `frontend/scripts/build-report.mjs`)
- [report/report_editable.docx](report/report_editable.docx): editable Word version, same wording
- [report/figures/](report/figures/): the three figures used in the Word version
- [report/video_script.md](report/video_script.md): walkthrough video script and demo accounts

## testing/

- [testing/testing_report.md](testing/testing_report.md): testing strategies, real results and the fixes they led to
- [testing/accessibility/](testing/accessibility/): axe results (desktop and mobile), written by `frontend/e2e/accessibility.spec.ts`
- [testing/benchmarks/](testing/benchmarks/): server inference timings (`scripts/benchmark.py`) and browser timings (`frontend/e2e/performance.spec.ts`)
- [testing/lighthouse/](testing/lighthouse/): Lighthouse reports of the sign-in page (HTML to view, JSON raw data)
- [screenshots/e2e/](screenshots/e2e/): screenshots written by the Playwright tests (iPhone 13 set and the report's Figure 3; the other browser profiles are git-ignored). Kept at this path because the report links to it

## models/

- [models/data_and_evaluation.md](models/data_and_evaluation.md): datasets, splits, how each model was evaluated, research questions
- [models/risk_policy.md](models/risk_policy.md): how a model score becomes a recommendation, band and referral advice (numbers in `backend/config/risk_policy.json`)
- [models/metrics.json](models/metrics.json): DR v2 metrics, recomputed by `scripts/dr_v2_metrics.py`
- [models/odir_metrics.json](models/odir_metrics.json): glaucoma and cataract metrics from the ODIR notebook
- [models/evaluation/dr_v2/](models/evaluation/dr_v2/): DR v2 notebook outputs: results, training history, validation and test predictions, parity scores
- [models/evaluation/dr_v1_metrics.json](models/evaluation/dr_v1_metrics.json): retired DR v0.3 validation figures (history only)

## usability/

- [usability/README.md](usability/README.md): usability test plan and tasks
- [usability/remote_testing.md](usability/remote_testing.md): how to run a remote session (tunnel, safety checklist, moderator script)
- [usability/sus_questionnaire.md](usability/sus_questionnaire.md): the 10 SUS statements
- [usability/results.csv](usability/results.csv): one row per tester, scored by `scripts/sus_score.py`
