"""Value object describing the outcome of one screening."""
from dataclasses import dataclass

from .config import DEFAULT_UNCERTAINTY_MARGIN
from .quality import QualityReport


@dataclass(frozen=True)
class ScreeningResult:
    probability: float      # model score: P(DR present)
    threshold: float        # decision threshold used
    model_version: str
    quality: QualityReport
    uncertainty_margin: float = DEFAULT_UNCERTAINTY_MARGIN

    @property
    def dr_detected(self) -> bool:
        return self.probability >= self.threshold

    @property
    def uncertain(self) -> bool:
        """True when the score is too close to the threshold to trust on its own."""
        return abs(self.probability - self.threshold) <= self.uncertainty_margin

    @property
    def needs_review(self) -> bool:
        """Flagged cases and borderline cases are queued for a specialist."""
        return self.dr_detected or self.uncertain

    @property
    def label(self) -> str:
        return "Signs of DR detected" if self.dr_detected else "No signs of DR detected"

    @property
    def headline(self) -> str:
        """Short title for the UI: a borderline score is not presented as a clear negative."""
        if not self.dr_detected and self.uncertain:
            return "Borderline: specialist review advised"
        return self.label

    @property
    def recommendation(self) -> str:
        if self.dr_detected:
            return "Recommended action: refer for specialist review."
        if self.uncertain:
            return "Borderline score: queued for specialist review."
        return "Recommended action: routine follow-up screening."
