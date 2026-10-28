"""RiskPolicy: turns one model score into a screening decision (Strategy pattern).

For a binary model the five-band scale is an *estimate* derived from the score, anchored on
the decision threshold ``t`` and the uncertainty margin ``m`` so bands can never contradict
the positive/negative call:

    score:   0 ........ (t-m)/2 ........ t-m ====== t ====== t+m ........ (1+t+m)/2 ........ 1
    band:         1              2           3 (uncertain)          4                5
    risk:        low            low        medium                 high             high

Conditions whose training data has no severity grades (glaucoma and cataract from ODIR-5K) set
``severity_bands: false``: they get a binary result (positive / borderline / negative) and no band.

A policy only *suggests* referral (``refer_suggested``); ``ReferralAdvisor`` turns the suggestions of all
conditions and the photo quality into one recommendation, and decides from the config which recommendations
are queued for a specialist automatically (default: uncertain cases only, as in the proposal).

Every number comes from ``config/risk_policy.json`` and the model card; see docs/risk_policy.md.
"""
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..models.enums import ReferralAdvice, ReviewPriority, RiskLevel


@dataclass(frozen=True)
class RiskAssessment:
    positive: bool
    uncertain: bool
    severity_band: int | None   # None when the condition has no severity banding
    risk_level: RiskLevel
    recommendation: str
    refer_suggested: bool


@dataclass(frozen=True)
class RiskPolicy:
    threshold: float
    uncertainty_margin: float = 0.10
    refer_when_positive: bool = True
    refer_when_uncertain: bool = True
    severity_bands: bool = True
    recommendations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 < self.threshold < 1.0:
            raise ValueError("threshold must be strictly between 0 and 1.")
        if not 0.0 <= self.uncertainty_margin < 0.5:
            raise ValueError("uncertainty_margin must be in [0, 0.5).")

    def assess(self, probability: float) -> RiskAssessment:
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"probability must be in [0, 1], got {probability!r}")
        positive = probability >= self.threshold
        uncertain = abs(probability - self.threshold) <= self.uncertainty_margin
        band = self._band(probability, uncertain)
        risk = RiskLevel.LOW if band <= 2 else RiskLevel.MEDIUM if band == 3 else RiskLevel.HIGH
        if not self.severity_bands:
            band = None  # the risk level still follows the same positive / borderline / negative rule
        refer_suggested = (positive and self.refer_when_positive) or (uncertain and self.refer_when_uncertain)
        return RiskAssessment(positive, uncertain, band, risk,
                              self.recommendations.get(risk.value, ""), refer_suggested)

    def _band(self, probability: float, uncertain: bool) -> int:
        if uncertain:
            return 3
        lower, upper = self.threshold - self.uncertainty_margin, self.threshold + self.uncertainty_margin
        if probability < lower:
            return 1 if probability < lower / 2 else 2
        return 4 if probability < (upper + 1.0) / 2 else 5


class ScoredResult(Protocol):
    condition: str
    model_available: bool
    positive: bool | None
    uncertain: bool | None
    severity_band: int | None
    refer_suggested: bool


@dataclass(frozen=True)
class ReferralAdvisor:
    """One recommendation per screening: a clear positive -> "recommended"; a borderline result or a photo
    with quality warnings -> ``low_quality_advice`` / "consider"; otherwise "none".

    ``queue_automatically``: recommendations put in the specialist queue without the health worker pressing
    anything (default: "consider", as in the proposal's sequence diagram, where an uncertain case is flagged and
    queued). ``urgent_from_band``: an estimated band at or above it makes the default review priority urgent."""
    low_quality_advice: ReferralAdvice = ReferralAdvice.CONSIDER
    queue_automatically: frozenset[ReferralAdvice] = frozenset({ReferralAdvice.CONSIDER})
    urgent_from_band: int = 4

    def queues_automatically(self, advice: ReferralAdvice) -> bool:
        return advice in self.queue_automatically

    def default_priority(self, results: Iterable[ScoredResult]) -> ReviewPriority:
        """Severe results (estimated band at or above ``urgent_from_band``) are urgent; everything else routine."""
        severe = any((r.severity_band or 0) >= self.urgent_from_band for r in results)
        return ReviewPriority.URGENT if severe else ReviewPriority.ROUTINE

    @staticmethod
    def queued_conditions(results: Iterable[ScoredResult]) -> list[str]:
        """What an automatically queued case is about: the flagged conditions, or every scored one when only
        the photo quality made the case uncertain."""
        results = list(results)
        flagged = sorted(r.condition for r in results if r.refer_suggested)
        return flagged or sorted(r.condition for r in results if r.model_available)

    def advise(self, results: Iterable[ScoredResult], has_quality_warnings: bool) -> ReferralAdvice:
        suggesting = [r for r in results if r.refer_suggested]
        if any(r.positive and not r.uncertain for r in suggesting):
            return ReferralAdvice.RECOMMENDED
        if suggesting:
            return ReferralAdvice.CONSIDER
        return self.low_quality_advice if has_quality_warnings else ReferralAdvice.NONE


class RiskPolicyFactory:
    """Builds a per-condition RiskPolicy from the JSON config plus the model's own threshold."""

    def __init__(self, config: dict):
        self._config = config
        self._default = config.get("default", {})
        self._overrides = config.get("conditions", {})

    @classmethod
    def from_file(cls, path: Path) -> "RiskPolicyFactory":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def advisor(self) -> ReferralAdvisor:
        config = self._config.get("referral_advice", {})
        return ReferralAdvisor(
            low_quality_advice=ReferralAdvice(config.get("low_quality_photo", ReferralAdvice.CONSIDER.value)),
            queue_automatically=frozenset(ReferralAdvice(a) for a in config.get("queue_automatically", ["consider"])),
            urgent_from_band=int(config.get("urgent_from_band", 4)),
        )

    def for_condition(self, condition: str, threshold: float) -> RiskPolicy:
        merged = {**self._default, **self._overrides.get(condition, {})}
        recommendations = {**self._default.get("recommendations", {}),
                           **self._overrides.get(condition, {}).get("recommendations", {})}
        return RiskPolicy(
            threshold=threshold,
            uncertainty_margin=float(merged.get("uncertainty_margin", 0.10)),
            refer_when_positive=bool(merged.get("refer_when_positive", True)),
            refer_when_uncertain=bool(merged.get("refer_when_uncertain", True)),
            severity_bands=bool(merged.get("severity_bands", True)),
            recommendations=recommendations,
        )
