"""Review targets: urgent (signs detected) 24 h, routine (borderline or manual) 72 h by default."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.enums import ReferralReason
from app.services.review_targets import ReviewTargets

REFERRED = datetime(2026, 10, 27, 0, 0, tzinfo=timezone.utc)  # a case referred at midnight


@pytest.mark.parametrize(("reason", "priority", "hours"), [
    (ReferralReason.POSITIVE, "urgent", 24), (ReferralReason.UNCERTAIN, "routine", 72),
    (ReferralReason.MANUAL, "routine", 72)])
def test_priority_and_due_time(reason, priority, hours):
    targets = ReviewTargets()
    assert targets.priority(reason) == priority
    due = targets.due_at(REFERRED, reason)
    assert due == REFERRED + timedelta(hours=hours)
    assert not targets.is_overdue(REFERRED, reason, due)
    assert targets.is_overdue(REFERRED, reason, due + timedelta(seconds=1))


def test_targets_are_configurable_and_validated():
    assert ReviewTargets(6, 48).due_at(REFERRED, ReferralReason.POSITIVE) == REFERRED + timedelta(hours=6)
    for bad in ((0, 72), (48, 24)):
        with pytest.raises(ValueError):
            ReviewTargets(*bad)
