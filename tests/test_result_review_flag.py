"""Borderline scores must be queued for specialist review, not silently cleared."""
import pytest

from tests.conftest import make_result


def test_high_score_is_flagged_and_needs_review():
    result = make_result(0.9, 0.5)
    assert result.dr_detected and result.needs_review and not result.uncertain


def test_clear_low_score_needs_no_review():
    result = make_result(0.1, 0.5)
    assert not result.dr_detected and not result.needs_review
    assert "routine" in result.recommendation.lower()


def test_borderline_below_threshold_is_queued_for_review():
    result = make_result(0.45, 0.5)
    assert not result.dr_detected and result.uncertain and result.needs_review
    assert "specialist" in result.recommendation.lower()


@pytest.mark.parametrize("probability,expected", [(0.39, False), (0.40, True), (0.50, True)])
def test_uncertainty_margin_boundary(probability, expected):
    assert make_result(probability, 0.5).needs_review is expected


def test_headline_never_presents_a_borderline_score_as_a_clear_negative():
    assert make_result(0.9, 0.5).headline == "Signs of DR detected"
    assert make_result(0.1, 0.5).headline == "No signs of DR detected"
    assert "Borderline" in make_result(0.45, 0.5).headline
