"""How long a referral may wait for a specialist before it is flagged as overdue.

This is a design decision, not a proposal requirement: the proposal makes specialist review
asynchronous and sets no time limit. Referrals where a model detected signs are "urgent"; borderline
and manual referrals are "routine". The hours come from settings (REVIEW_TARGET_URGENT_HOURS,
REVIEW_TARGET_ROUTINE_HOURS), defaults 24 h and 72 h. See docs/risk_policy.md.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..models.enums import ReferralReason


@dataclass(frozen=True)
class ReviewTargets:
    urgent_hours: int = 24
    routine_hours: int = 72

    def __post_init__(self) -> None:
        if not 0 < self.urgent_hours <= self.routine_hours:
            raise ValueError("Review targets must be positive and urgent must not exceed routine.")

    @staticmethod
    def priority(reason: ReferralReason) -> str:
        return "urgent" if reason == ReferralReason.POSITIVE else "routine"

    def due_at(self, referred_at: datetime, reason: ReferralReason) -> datetime:
        hours = self.urgent_hours if self.priority(reason) == "urgent" else self.routine_hours
        return referred_at + timedelta(hours=hours)

    def is_overdue(self, referred_at: datetime, reason: ReferralReason, now: datetime) -> bool:
        return now > self.due_at(referred_at, reason)
