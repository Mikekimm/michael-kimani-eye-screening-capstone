# Risk policy: from a model score to a screening decision

Code: `backend/app/ml/risk_policy.py`. Numbers: `backend/config/risk_policy.json` (margins, referral
switches, wording) and each model's `models/<condition>/model_card.json` (decision threshold).
Tests: `backend/tests/ml/test_risk_policy.py`.

## Why a policy object

The DR model outputs one number, the probability that DR is present. A health worker needs a
decision: refer or not, how urgently, and what to say to the patient. Putting that translation in one
`RiskPolicy` class (Strategy pattern, one policy per condition) keeps clinical wording and cut-offs out
of the API and UI, lets each condition have its own settings, and lets the numbers change without code
changes.

## The rule

With threshold `t` (from the model card) and uncertainty margin `m` (from the config):

| Score `p` | Positive? | Uncertain? | Estimated severity band | Risk level | Referred? |
|---|---|---|---|---|---|
| `p < (t - m) / 2` | no | no | 1 | low | no |
| `(t - m) / 2 <= p < t - m` | no | no | 2 | low | no |
| `t - m <= p < t` | no | **yes** | 3 | medium | **yes** (uncertain) |
| `t <= p <= t + m` | yes | **yes** | 3 | medium | yes |
| `t + m < p < (1 + t + m) / 2` | yes | no | 4 | high | yes (positive) |
| `p >= (1 + t + m) / 2` | yes | no | 5 | high | yes (positive) |

With the current values (`t = 0.5`, `m = 0.10`): band 1 below 0.20, band 2 to 0.40, band 3 from 0.40 to
0.60, band 4 to 0.80, band 5 from 0.80.

## Reasoning

* **Bands are anchored on the threshold**, not fixed probabilities. If calibration lowers `t` to reach
  85% sensitivity, a fixed scale could show "band 2 (low)" next to "DR detected". Anchoring makes that
  impossible (`test_bands_never_contradict_the_decision` checks all 1,001 scores from 0 to 1 in 0.001 steps).
* **Borderline scores go to a specialist.** A score just under the threshold is not a confident
  negative. Sensitivity is the proposal's main metric because a missed case costs more than an extra
  referral, so the policy refers the uncertain zone (`refer_when_uncertain`).
* **`m = 0.10`** matches the margin used since the MVP. It has not been tuned on data. Once hold-out
  predictions exist, it can be chosen from the score distribution near the threshold.
* **The 1-5 band is an estimate, not a clinical grade.** The model is binary (no DR vs DR grades 1-4).
  Higher scores mean the model is more confident that DR is present, not that the disease is more
  severe. The UI labels it "Estimated severity band" and the disclaimer says it is not a diagnosis.
  Calibration of the probabilities has **not** been measured.

## Changing it

Edit `backend/config/risk_policy.json` (all conditions under `default`, or one condition under
`conditions.<name>`), then restart the API. The calibrated threshold is written to the model card by
`scripts/calibrate_threshold.py`.
