"""Boundary tests for every severity band, the uncertain zone and the auto-refer rule."""
import json

import pytest

from app.core.config import BACKEND_ROOT
from app.ml.risk_policy import RiskPolicy, RiskPolicyFactory
from app.models.enums import RiskLevel

# t = 0.5, m = 0.1  ->  band 1 < 0.2 <= band 2 < 0.4 <= band 3 <= 0.6 < band 4 < 0.8 <= band 5
POLICY = RiskPolicy(threshold=0.5, uncertainty_margin=0.1,
                    recommendations={"low": "L", "medium": "M", "high": "H"})


@pytest.mark.parametrize("probability, band", [
    (0.0, 1), (0.1999, 1),
    (0.2, 2), (0.3999, 2),
    (0.4, 3), (0.5, 3), (0.6, 3),
    (0.6001, 4), (0.7999, 4),
    (0.8, 5), (1.0, 5),
])
def test_band_boundaries(probability, band):
    assert POLICY.assess(probability).severity_band == band


@pytest.mark.parametrize("probability, positive, uncertain, refer, risk", [
    (0.10, False, False, False, RiskLevel.LOW),     # confident negative: routine follow-up
    (0.45, False, True, True, RiskLevel.MEDIUM),    # borderline negative: still referred
    (0.50, True, True, True, RiskLevel.MEDIUM),     # exactly at the threshold counts as positive
    (0.55, True, True, True, RiskLevel.MEDIUM),
    (0.95, True, False, True, RiskLevel.HIGH),      # confident positive
])
def test_decision_and_auto_refer(probability, positive, uncertain, refer, risk):
    result = POLICY.assess(probability)
    assert (result.positive, result.uncertain, result.auto_refer, result.risk_level) == (positive, uncertain, refer, risk)
    assert result.recommendation == {"low": "L", "medium": "M", "high": "H"}[risk.value]


def test_bands_never_contradict_the_decision():
    for i in range(1001):
        p = i / 1000
        result = POLICY.assess(p)
        if result.severity_band <= 2:
            assert not result.positive
        if result.severity_band >= 4:
            assert result.positive


def test_bands_follow_a_calibrated_threshold():
    low_threshold = RiskPolicy(threshold=0.3, uncertainty_margin=0.1)
    assert low_threshold.assess(0.25).severity_band == 3
    assert low_threshold.assess(0.45).severity_band == 4
    assert low_threshold.assess(0.45).positive


def test_auto_refer_switches_are_configurable():
    no_uncertain_referral = RiskPolicy(threshold=0.5, uncertainty_margin=0.1, refer_when_uncertain=False)
    assert not no_uncertain_referral.assess(0.45).auto_refer
    assert no_uncertain_referral.assess(0.55).auto_refer  # still positive


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_rejects_out_of_range_probability(bad):
    with pytest.raises(ValueError):
        POLICY.assess(bad)


@pytest.mark.parametrize("threshold, margin", [(0.0, 0.1), (1.0, 0.1), (0.5, 0.5), (0.5, -0.1)])
def test_rejects_invalid_configuration(threshold, margin):
    with pytest.raises(ValueError):
        RiskPolicy(threshold=threshold, uncertainty_margin=margin)


def test_factory_reads_the_shipped_config_and_merges_condition_overrides():
    factory = RiskPolicyFactory.from_file(BACKEND_ROOT / "config" / "risk_policy.json")
    dr = factory.for_condition("dr", threshold=0.5)
    other = factory.for_condition("glaucoma", threshold=0.5)
    config = json.loads((BACKEND_ROOT / "config" / "risk_policy.json").read_text(encoding="utf-8"))
    assert dr.uncertainty_margin == config["default"]["uncertainty_margin"]
    assert "diabetic retinopathy" in dr.recommendations["high"]
    assert other.recommendations["high"] == config["default"]["recommendations"]["high"]
