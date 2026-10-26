import numpy as np
import pytest

from app.ml.evaluation import bootstrap_metric_ci, roc_auc, stratified_split


def test_auc_known_values():
    assert roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert roc_auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0
    assert roc_auc([0, 1], [0.5, 0.5]) == pytest.approx(0.5)  # a tie counts half


def test_auc_with_many_ties_matches_scikit_learn():
    metrics = pytest.importorskip("sklearn.metrics")
    rng = np.random.default_rng(1)
    y = np.r_[np.ones(300), np.zeros(400)].astype(int)
    p = np.round(np.r_[rng.beta(3, 2, 300), rng.beta(2, 3, 400)], 2)
    assert roc_auc(y, p) == pytest.approx(metrics.roc_auc_score(y, p), abs=1e-12)


def test_auc_requires_both_classes():
    with pytest.raises(ValueError):
        roc_auc([1, 1, 1], [0.2, 0.4, 0.6])


def test_split_is_disjoint_stratified_and_deterministic():
    y = np.r_[np.ones(200), np.zeros(300)].astype(int)
    tune, test = stratified_split(y, 0.5, seed=3)
    assert not set(tune) & set(test) and len(tune) + len(test) == len(y)
    assert y[tune].mean() == pytest.approx(y[test].mean(), abs=0.01)
    again_tune, again_test = stratified_split(y, 0.5, seed=3)
    assert (tune == again_tune).all() and (test == again_test).all()
    other_tune, _ = stratified_split(y, 0.5, seed=4)
    assert not (tune == other_tune).all()


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.2, 1.5])
def test_split_rejects_invalid_fraction(fraction):
    with pytest.raises(ValueError):
        stratified_split([0, 1, 0, 1], fraction)


def make_scores(n_pos=400, n_neg=600, seed=0):
    rng = np.random.default_rng(seed)
    y = np.r_[np.ones(n_pos), np.zeros(n_neg)].astype(int)
    return y, np.r_[rng.beta(4, 2, n_pos), rng.beta(2, 4, n_neg)]


def test_bootstrap_interval_contains_estimate_and_is_reproducible():
    y, p = make_scores()
    interval = bootstrap_metric_ci(y, p, 0.4, "sensitivity", n_boot=300, seed=5)
    assert interval.low <= interval.estimate <= interval.high
    assert interval == bootstrap_metric_ci(y, p, 0.4, "sensitivity", n_boot=300, seed=5)


def test_bootstrap_interval_narrows_with_more_data():
    small = bootstrap_metric_ci(*make_scores(40, 60), 0.4, "specificity", n_boot=400, seed=1)
    large = bootstrap_metric_ci(*make_scores(4000, 6000), 0.4, "specificity", n_boot=400, seed=1)
    assert (large.high - large.low) < (small.high - small.low)


def test_bootstrap_rejects_unknown_metric():
    y, p = make_scores()
    with pytest.raises(ValueError):
        bootstrap_metric_ci(y, p, 0.4, "f1")
