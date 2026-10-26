"""Decision-threshold selection to meet a minimum sensitivity target.

Screening tools should favour sensitivity (missing a real case is worse than a
false alarm). Given validation labels and model scores, ``select_threshold``
finds the *highest* threshold that still reaches the target sensitivity, which
keeps specificity as high as possible for that sensitivity.
"""
from dataclasses import dataclass

import numpy as np



@dataclass(frozen=True)
class OperatingPoint:
    threshold: float
    sensitivity: float
    specificity: float
    precision: float
    f1: float
    accuracy: float
    tp: int
    fp: int
    tn: int
    fn: int


def _validate(y_true, y_prob):
    y_true = np.asarray(y_true).astype(int).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()
    if y_true.shape != y_prob.shape:
        raise ValueError("y_true and y_prob must have the same length.")
    if y_true.size == 0:
        raise ValueError("Inputs must not be empty.")
    if not np.isin(y_true, (0, 1)).all():
        raise ValueError("y_true must contain only 0 and 1.")
    if y_true.min() == y_true.max():
        raise ValueError("y_true must contain both classes.")
    if (y_prob < 0).any() or (y_prob > 1).any():
        raise ValueError("y_prob must lie in [0, 1].")
    return y_true, y_prob


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def metrics_at_threshold(y_true, y_prob, threshold: float) -> OperatingPoint:
    """Confusion-matrix metrics when predicting positive for prob >= threshold."""
    y_true, y_prob = _validate(y_true, y_prob)
    predicted = y_prob >= threshold
    actual = y_true == 1
    tp = int(np.sum(predicted & actual))
    fp = int(np.sum(predicted & ~actual))
    tn = int(np.sum(~predicted & ~actual))
    fn = int(np.sum(~predicted & actual))
    sensitivity = _safe_div(tp, tp + fn)
    precision = _safe_div(tp, tp + fp)
    return OperatingPoint(
        threshold=float(threshold),
        sensitivity=sensitivity,
        specificity=_safe_div(tn, tn + fp),
        precision=precision,
        f1=_safe_div(2 * precision * sensitivity, precision + sensitivity),
        accuracy=_safe_div(tp + tn, y_true.size),
        tp=tp, fp=fp, tn=tn, fn=fn,
    )


def select_threshold(y_true, y_prob, target_sensitivity: float = 0.85) -> OperatingPoint:
    """Highest threshold whose sensitivity is >= ``target_sensitivity``. O(n log n)."""
    if not 0.0 < target_sensitivity <= 1.0:
        raise ValueError("target_sensitivity must be in (0, 1].")
    y_true, y_prob = _validate(y_true, y_prob)

    positives = np.sort(y_prob[y_true == 1])
    n_pos = positives.size
    candidates = np.unique(y_prob)[::-1]  # descending
    # number of positives scoring >= each candidate threshold
    caught = n_pos - np.searchsorted(positives, candidates, side="left")
    sensitivity = caught / n_pos
    eligible = np.flatnonzero(sensitivity >= target_sensitivity)
    chosen = candidates[eligible[0]]  # eligible is never empty: the lowest score catches all
    return metrics_at_threshold(y_true, y_prob, float(chosen))
