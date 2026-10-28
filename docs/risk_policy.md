# Risk policy: from a model score to a screening decision

Code: `backend/app/ml/risk_policy.py`. Numbers: `backend/config/risk_policy.json` (margins, referral-suggestion
switches, wording) and each model's `models/<condition>/model_card.json` (decision threshold).
Tests: `backend/tests/ml/test_risk_policy.py`.

## Why a policy object

The DR model outputs one number, the probability that DR is present. A health worker needs a
recommendation: whether to ask a specialist, how urgently, and what to say to the patient. Putting that
translation in one
`RiskPolicy` class (Strategy pattern, one policy per condition) keeps clinical wording and cut-offs out
of the API and UI, lets each condition have its own settings, and lets the numbers change without code
changes.

## The rule

With threshold `t` (from the model card) and uncertainty margin `m` (from the config):

| Score `p` | Positive? | Uncertain? | Estimated severity band | Risk level | Suggests a specialist? |
|---|---|---|---|---|---|
| `p < (t - m) / 2` | no | no | 1 | low | no |
| `(t - m) / 2 <= p < t - m` | no | no | 2 | low | no |
| `t - m <= p < t` | no | **yes** | 3 | medium | **yes** (consider) |
| `t <= p <= t + m` | yes | **yes** | 3 | medium | yes (consider) |
| `t + m < p < (1 + t + m) / 2` | yes | no | 4 | high | yes (recommended) |
| `p >= (1 + t + m) / 2` | yes | no | 5 | high | yes (recommended) |

With the current DR values (`t = 0.418` from the DR v2 model card, chosen on the validation split for
85% sensitivity; `m = 0.10`): band 1 below 0.159, band 2 to 0.318, band 3 from 0.318 to 0.518, band 4 to
0.759, band 5 from 0.759. Glaucoma uses `t = 0.320` and cataract `t = 0.541` (their model cards), with
the same margin and no band.

## From per-condition results to one recommendation (nothing is sent automatically)

`ReferralAdvisor` (same file) combines the per-condition results and the photo's quality warnings into
one recommendation for the screening:

| Situation | Recommendation shown |
|---|---|
| Any condition clearly positive (band 4-5, or positive outside the margin) | **Refer recommended** |
| Any borderline result (within the margin either side of the threshold) | **Uncertain, consider asking a specialist** |
| All negative, but the photo has quality warnings (blur, darkness) | **Uncertain, consider asking a specialist** (`referral_advice.low_quality_photo`) |
| All negative, good photo | **No referral needed** |

This is advice only. **No case is sent to a specialist automatically.** The health worker reads the
result and, if they want a specialist's opinion, presses **Ask a specialist** and types a question
(`POST /api/screenings/{id}/ask-specialist`). Only then is a referral created and the case shown as
"Awaiting specialist"; afterwards it shows "Reviewed" or, if the specialist asked for a new photo,
"Retake needed". A health worker may also ask about a negative result. Reason: the health worker, not
the software, stays responsible for the referral decision, and the specialist queue holds only cases a
person chose to send, each with a question.

## Reasoning

* **Bands are anchored on the threshold**, not fixed probabilities. If calibration lowers `t` to reach
  85% sensitivity, a fixed scale could show "band 2 (low)" next to "DR detected". Anchoring makes that
  impossible (`test_bands_never_contradict_the_decision` checks all 1,001 scores from 0 to 1 in 0.001 steps).
* **Borderline scores suggest asking a specialist.** A score just under the threshold is not a confident
  negative. Sensitivity is the proposal's main metric because a missed case costs more than an extra
  referral, so the policy flags the uncertain zone (`refer_when_uncertain`) and the screen recommends
  asking a specialist; the health worker decides.
* **`m = 0.10`** matches the margin used since the MVP. It has not been tuned on data; the DR v2
  validation predictions (`docs/evaluation/dr_v2/val_predictions.csv`) would allow choosing it from the
  score distribution near the threshold.
* **The 1-5 band is an estimate, not a clinical grade.** The model is binary (no DR vs DR grades 1-4).
  Higher scores mean the model is more confident that DR is present, not that the disease is more
  severe. The UI labels it "Estimated severity band" and the disclaimer says it is not a diagnosis.
  Calibration of the probabilities has **not** been measured.

## Binary-only conditions

Glaucoma and cataract are configured with `"severity_bands": false`, because their training data
(ODIR-5K) has no severity grades. They still get positive / borderline / negative, a risk level and
referral suggestion by the same rule, but no 1-5 band, and the result card says "binary result only".

## Changing it

Edit `backend/config/risk_policy.json` (all conditions under `default`, or one condition under
`conditions.<name>`), then restart the API. The DR threshold is written to the model card by
`scripts/dr_v2_metrics.py` from the notebook's validation predictions; the glaucoma and cataract
thresholds come from their notebook.

## Review targets (a design decision, not a proposal requirement)

The proposal makes specialist review asynchronous: a case the health worker sends is queued, synced,
reviewed when a specialist next signs in, and the decision is pulled back at the next sync. It sets no time limit. So
that no case waits unnoticed, the app adds configurable targets (`backend/app/services/review_targets.py`):

| Referral | Priority | Default target | Setting |
|---|---|---|---|
| Sent while the recommendation was "Refer recommended" (a model detected signs) | urgent | 24 hours | `REVIEW_TARGET_URGENT_HOURS` |
| Sent while "Uncertain, consider asking a specialist" or "No referral needed" | routine | 72 hours | `REVIEW_TARGET_ROUTINE_HOURS` |

A case past its target is flagged **overdue**: it moves to the top of the specialist queue, the health
worker's screening shows "Review overdue", and the admin dashboard counts overdue reviews. A case
sent at midnight is therefore not lost: the worker gets the model result and recommended action at
once, sees "Awaiting specialist" with how long it has waited, and the specialist sees it when they next
sign in. For high-risk results the screen also tells the worker to refer directly by the local emergency
protocol for sudden vision loss, eye pain or injury, because the app does not replace emergency care.
