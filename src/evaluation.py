"""Evaluation utilities that keep claims honest: a tune/test split, AUC and
bootstrap confidence intervals. NumPy only, so they run on any machine.
"""
from dataclasses import dataclass
from typing import Tuple

import numpy as np

from .thresholding import _validate, metrics_at_threshold


def stratified_split(y_true, fraction: float = 0.5, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """Split indices into (tuning, test) keeping the class ratio in both parts.

    The threshold is chosen on the tuning part only; every reported number comes
    from the test part, which the threshold never saw.
    """
    if not 0.0 < fraction < 1.0:
        raise ValueError("fraction must be strictly between 0 and 1.")
    y = np.asarray(y_true).astype(int).ravel()
    rng = np.random.default_rng(seed)
    tuning, test = [], []
    for cls in (0, 1):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        cut = int(round(len(idx) * fraction))
        tuning.append(idx[:cut])
        test.append(idx[cut:])
    return np.sort(np.concatenate(tuning)), np.sort(np.concatenate(test))


def roc_auc(y_true, y_prob) -> float:
    """Area under the ROC curve via the rank-sum (Mann-Whitney U) identity.

    Tied scores receive their average rank, so ties count as half a win.
    O(n log n).
    """
    y, p = _validate(y_true, y_prob)
    order = np.argsort(p, kind="mergesort")
    sorted_p = p[order]
    ranks = np.empty(len(p), dtype=float)
    # average ranks over runs of equal scores
    boundaries = np.flatnonzero(np.diff(sorted_p)) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [len(p)]))
    for start, end in zip(starts, ends):
        ranks[order[start:end]] = (start + end + 1) / 2.0  # mean of ranks start+1..end
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    rank_sum_pos = ranks[y == 1].sum()
    return float((rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float

    def __str__(self) -> str:
        return f"{self.estimate:.3f} (95% CI {self.low:.3f}-{self.high:.3f})"


def bootstrap_metric_ci(y_true, y_prob, threshold: float, metric: str,
                        n_boot: int = 1000, seed: int = 42, level: float = 0.95) -> Interval:
    """Percentile bootstrap interval for ``sensitivity``, ``specificity`` or ``precision``.

    Positives and negatives are resampled separately so every resample has both classes.
    """
    if metric not in ("sensitivity", "specificity", "precision"):
        raise ValueError("metric must be sensitivity, specificity or precision.")
    y, p = _validate(y_true, y_prob)
    rng = np.random.default_rng(seed)
    pos, neg = p[y == 1], p[y == 0]
    estimate = getattr(metrics_at_threshold(y, p, threshold), metric)
    values = np.empty(n_boot)
    for i in range(n_boot):
        pos_s = rng.choice(pos, size=len(pos), replace=True)
        neg_s = rng.choice(neg, size=len(neg), replace=True)
        tp = np.count_nonzero(pos_s >= threshold)
        fn = len(pos_s) - tp
        fp = np.count_nonzero(neg_s >= threshold)
        tn = len(neg_s) - fp
        if metric == "sensitivity":
            values[i] = tp / (tp + fn)
        elif metric == "specificity":
            values[i] = tn / (tn + fp)
        else:
            values[i] = tp / (tp + fp) if (tp + fp) else 0.0
    alpha = (1.0 - level) / 2.0
    low, high = np.quantile(values, [alpha, 1.0 - alpha])
    return Interval(float(estimate), float(low), float(high))
