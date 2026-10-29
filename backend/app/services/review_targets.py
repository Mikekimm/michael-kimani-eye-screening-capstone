"""How long a referral may wait for a specialist before it is flagged as overdue.

This is a design decision, not a proposal requirement: the proposal makes specialist review
asynchronous and sets no time limit. The default priority comes from the risk policy (urgent for severe
results, DR band 4-5; routine otherwise); the health worker can change it when asking a specialist. The hours come from settings (REVIEW_TARGET_URGENT_HOURS,
REVIEW_TARGET_ROUTINE_HOURS), defaults 24 h and 72 h. See docs/models/risk_policy.md.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models.enums import ReviewPriority


@dataclass(frozen=True)
class ReviewTargets:
    urgent_hours: int = 24
    routine_hours: int = 72

    def __post_init__(self) -> None:
        if not 0 < self.urgent_hours <= self.routine_hours:
            raise ValueError("Review targets must be positive and urgent must not exceed routine.")

    def due_at(self, referred_at: datetime, priority: ReviewPriority) -> datetime:
        hours = self.urgent_hours if priority == ReviewPriority.URGENT else self.routine_hours
        return referred_at + timedelta(hours=hours)

    def is_overdue(self, referred_at: datetime, priority: ReviewPriority, now: datetime) -> bool:
        return now > self.due_at(referred_at, priority)
