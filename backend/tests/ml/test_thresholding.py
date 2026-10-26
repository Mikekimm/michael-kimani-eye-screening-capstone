import numpy as np
import pytest

from app.ml.thresholding import load_threshold, metrics_at_threshold, save_threshold, select_threshold


def test_perfect_separation_picks_highest_threshold_with_full_recall():
    y_true = [0, 0, 0, 1, 1, 1]
    y_prob = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
    point = select_threshold(y_true, y_prob, target_sensitivity=0.85)
    assert point.threshold == 0.7
    assert point.sensitivity == 1.0 and point.specificity == 1.0


def test_known_confusion_matrix_values():
    y_true = [1, 1, 1, 1, 0, 0, 0, 0]
    y_prob = [0.9, 0.8, 0.4, 0.2, 0.6, 0.3, 0.2, 0.1]
    point = metrics_at_threshold(y_true, y_prob, 0.5)
    assert (point.tp, point.fn, point.fp, point.tn) == (2, 2, 1, 3)
    assert point.sensitivity == pytest.approx(0.5)
    assert point.specificity == pytest.approx(0.75)
    assert point.precision == pytest.approx(2 / 3)


def test_selected_threshold_meets_target_and_is_the_highest_that_does():
    rng = np.random.default_rng(7)
    y_true = rng.integers(0, 2, 2000)
    y_prob = np.clip(y_true * 0.25 + rng.normal(0.4, 0.2, 2000), 0, 1)
    target = 0.85
    point = select_threshold(y_true, y_prob, target)
    assert point.sensitivity >= target
    higher = np.unique(y_prob[y_prob > point.threshold])
    for candidate in higher:
        assert metrics_at_threshold(y_true, y_prob, candidate).sensitivity < target


def test_lower_target_gives_higher_or_equal_threshold():
    rng = np.random.default_rng(3)
    y_true = rng.integers(0, 2, 500)
    y_prob = np.clip(y_true * 0.3 + rng.normal(0.35, 0.2, 500), 0, 1)
    assert select_threshold(y_true, y_prob, 0.6).threshold >= select_threshold(y_true, y_prob, 0.95).threshold


@pytest.mark.parametrize(
    "y_true,y_prob,target",
    [
        ([1, 1, 1], [0.1, 0.2, 0.3], 0.85),    # one class only
        ([0, 1], [0.1], 0.85),                  # length mismatch
        ([0, 1], [0.1, 1.5], 0.85),             # prob out of range
        ([0, 2], [0.1, 0.5], 0.85),             # bad labels
        ([], [], 0.85),                         # empty
        ([0, 1], [0.1, 0.9], 0.0),              # bad target
    ],
)
def test_invalid_inputs_raise(y_true, y_prob, target):
    with pytest.raises(ValueError):
        select_threshold(y_true, y_prob, target)


def test_save_and_load_round_trip(tmp_path):
    point = select_threshold([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9], 0.85)
    path = tmp_path / "threshold.json"
    save_threshold(point, 0.85, path)
    assert load_threshold(path) == pytest.approx(point.threshold)


def test_load_threshold_falls_back_when_missing_or_invalid(tmp_path):
    assert load_threshold(tmp_path / "missing.json", default=0.5) == 0.5
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert load_threshold(bad, default=0.5) == 0.5
    out_of_range = tmp_path / "range.json"
    out_of_range.write_text('{"threshold": 7}')
    assert load_threshold(out_of_range, default=0.5) == 0.5
