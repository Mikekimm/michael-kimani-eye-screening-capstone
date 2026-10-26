"""RiskPolicy: turns one model score into a screening decision (Strategy pattern).

For a binary model the five-band scale is an *estimate* derived from the score, anchored on
the decision threshold ``t`` and the uncertainty margin ``m`` so bands can never contradict
the positive/negative call:

    score:   0 ........ (t-m)/2 ........ t-m ====== t ====== t+m ........ (1+t+m)/2 ........ 1
    band:         1              2           3 (uncertain)          4                5
    risk:        low            low        medium                 high             high

Every number comes from ``config/risk_policy.json`` and the model card; see docs/risk_policy.md.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..models.enums import RiskLevel


@dataclass(frozen=True)
class RiskAssessment:
    positive: bool
    uncertain: bool
    severity_band: int
    risk_level: RiskLevel
    recommendation: str
    auto_refer: bool


@dataclass(frozen=True)
class RiskPolicy:
    threshold: float
    uncertainty_margin: float = 0.10
    refer_when_positive: bool = True
    refer_when_uncertain: bool = True
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
        auto_refer = (positive and self.refer_when_positive) or (uncertain and self.refer_when_uncertain)
        return RiskAssessment(positive, uncertain, band, risk,
                              self.recommendations.get(risk.value, ""), auto_refer)

    def _band(self, probability: float, uncertain: bool) -> int:
        if uncertain:
            return 3
        lower, upper = self.threshold - self.uncertainty_margin, self.threshold + self.uncertainty_margin
        if probability < lower:
            return 1 if probability < lower / 2 else 2
        return 4 if probability < (upper + 1.0) / 2 else 5


class RiskPolicyFactory:
    """Builds a per-condition RiskPolicy from the JSON config plus the model's own threshold."""

    def __init__(self, config: dict):
        self._default = config.get("default", {})
        self._overrides = config.get("conditions", {})

    @classmethod
    def from_file(cls, path: Path) -> "RiskPolicyFactory":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def for_condition(self, condition: str, threshold: float) -> RiskPolicy:
        merged = {**self._default, **self._overrides.get(condition, {})}
        recommendations = {**self._default.get("recommendations", {}),
                           **self._overrides.get(condition, {}).get("recommendations", {})}
        return RiskPolicy(
            threshold=threshold,
            uncertainty_margin=float(merged.get("uncertainty_margin", 0.10)),
            refer_when_positive=bool(merged.get("refer_when_positive", True)),
            refer_when_uncertain=bool(merged.get("refer_when_uncertain", True)),
            recommendations=recommendations,
        )
